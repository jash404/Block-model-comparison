"""Core functionality for connecting to a Maptek MDF-based application.

This handles connecting to the application and initialises internal
dependencies. The Project class provides methods for interacting with user
facing objects and data within the application.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import atexit
from contextlib import contextmanager
import ctypes
import logging
import os
import posixpath
import typing
from ..capi import DataEngine, Modelling, License
from ..capi.types import T_ObjectHandle
from ..data import (Surface, EdgeNetwork, Marker, Text2D, Text3D, Container,
                    VisualContainer, PointSet, Polygon, Polyline,
                    DenseBlockModel, Topology, NumericColourMap,
                    StringColourMap, StandardContainer, Scan,
                    GridSurface, SubblockedBlockModel, Raster, Discontinuity)
from ..data.containers import ChildView
from ..data.objectid import ObjectID
from ..internal import account
from ..internal.lock import ReadLock, WriteLock, LockType
from ..internal.logger import configure_log
from ..internal.mcp import (ExistingMcpdInstance, McpdConnection,
                            find_mdf_hosts, McpdDisconnectError)
from ..internal.options import (ProjectOptions, ProjectBackendType,
                                ProjectOpenMode, McpdMode)
from ..internal.util import to_utf8
from ..labs.blocks import SparseBlockModel
from ..labs.cells import SparseIrregularCellNetwork
from .errors import (DeleteRootError, ObjectDoesNotExistError,
                     ProjectConnectionFailureError, ApplicationTooOldError)

# pylint: disable=no-self-use
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-statements

ObjectType = typing.TypeVar('ObjectType')

def _add_dll_directory(dll_path):
  """Adds a directory to the search path for DLLs.

  In Python 3.8 and higher this will return a wrapper around the added
  DLL directory. Call close on this to remove DLL directory from the DLL
  search path.

  In Python 3.7 this will modify PATH and return None. In this
  case once a DLL directory has been added it cannot be removed.

  Parameters
  ----------
  dll_path : str
    Path to the DLL directory to add to the search path.

  Returns
  -------
  os._AddedDllDirectory
    The added DLL directory
  None
    When called in Python 3.7.

  """
  added_directory = None
  try:
    added_directory = os.add_dll_directory(dll_path)
  except AttributeError:
    pass
  # :HACK: Jayden Boskell 2021-06-21 This should be inside the
  # except AttributeError block, however Vulcan ignores add_dll_directory
  # so it is always necessary to add this to PATH.
  # Ideally in Python 3.8 the SDK shouldn't alter PATH to avoid
  # issues such as SDK-307.
  os.environ['PATH'] = os.pathsep.join([
    dll_path, os.environ['PATH']])
  return added_directory

class Project:
  """Main class to connect to an instance of an MDF application.
  Project() establishes the communication protocol and provides base
  functionality into the application, such as object naming, locating,
  copying and deleting.

  Parameters
  ----------
  options : ProjectOptions
    Optional specification of project and connection
    settings. Used for unit testing to start a new database and
    processes without an MDF host application already running.
  existing_mcpd : ExistingMcpdInstance or McpdConnection or None
    If None (default) then the latest relevant application that was launched
    will be connected to. This is equivalent to passing in
    Project.find_running_applications()[0].

    Otherwise it may be ExistingMcpdInstance which refers to the host
    application to connect to otherwise a McpdConnection which is an
    existing connection to a host application (its mcpd).

  Raises
  ------
  ProjectConnectionFailureError
    If the script fails to connect to the project. Generally this is
    because there is no application running, or the specified application
    is no longer running.

  """

  # Keep track of if the logging has been configured.
  # See configure_log for details.
  _configured_logging = False

  def __init__(self, options=None, existing_mcpd=None):
    self.mcp_instance = None
    self.backend_index = None
    self.dataengine_connection = False
    self.broker_session = None

    # In Python 3.8 and higher this is set to the return value of
    # add_dll_directory. Calling dispose on this will remove the dll
    # directory.
    self.dll_directory = None

    # :TRICKY: atexit.register to ensure project is properly unloaded at exit.
    # By implementing the standard logging library, __del__ and __exit__ are
    # no longer guaranteed to be called. During unit testing, spawned mcpd.exe
    # and backendserver.exe would remain open indefinitely after the unit tests
    # finished - preventing subsequent runs.
    # Not an issue if connecting to an existing host application.
    self._exit_function = atexit.register(self.unload_project)

    # Configure all the MDF loggers with defaults. This is done when the user
    # creates the Project() instance so they don't need to do it themselves and
    # so by default we can have consistent logging.
    #
    # Only configure the logging once as otherwise output will be duplicated as
    # it set-up multiple log handlers.
    if not Project._configured_logging:
      configure_log(logging.getLogger('mapteksdk'))
      Project._configured_logging = True

    self.log = logging.getLogger('mapteksdk.project')

    # If no options are provided, there are some default options we expect.
    if not options:
      options = ProjectOptions('')

      # When no options are provided we are expecting to connect to the
      # project of a running application.
      assert options.mcpd_mode == McpdMode.CONNECT_TO_EXISTING

    broker_connector_path = options.account_broker_connector_path
    connection_parameters = options.account_broker_session_parameters

    # Configure the DLL load path, (possibly by finding an mcpd to connect
    # to in the process).
    if not options.dll_path:
      # No DLL path was set, so the MDF DLLs can't be loaded yet (unless
      # there is an existing mcpd which would already have set it up, and
      # has simply not provided the where in the ProjectOptions).
      #
      # If the plan is to connect to an existing mcpd, then finding one will
      # discover the DLLs required.
      #
      # If creating a new mcpd, then the DLL path should already be set.
      # Unless a new mode is supported where an existing mcpd (application) is
      # found first then it is used to start it.
      #
      if options.mcpd_mode == McpdMode.CONNECT_TO_EXISTING:
        if not existing_mcpd:
          # If the bin path and mcp path environment variables are
          # defined, use them to determine which mcpd instance (and hence
          # which application) to connect to. This ensures scripts run
          # from workbench connect to the correct application.
          # Otherwise connect to the most recently opened application.
          try:
            dll_path = os.environ["SDK_OVERWRITE_BIN_PATH"]
            socket_path = os.environ["SDK_OVERWRITE_MCP_PATH"]
            existing_mcpd = ExistingMcpdInstance(-1, dll_path, socket_path)
          except KeyError:
            # The result of the find is used when trying to connect to ensure
            # looking for the mcpd is not performed twice. That itself could
            # lead to different mcpd being found (and thus a mismatch).
            existing_mcpd = find_mdf_hosts(self.log)[0]
          options.dll_path = existing_mcpd[1]
        elif not isinstance(existing_mcpd, McpdConnection):
          # The connection hasn't been established yet so the DLL path isn't
          # configured either.
          options.dll_path = existing_mcpd[1]

    if options.dll_path:
      # The shlib folder accounts for running the application from the source.
      # In an installed application, the DLLs are placed in the bin folder
      # rather than shlib, whereas when building from source they are
      # separated.
      shlib_path = os.path.join(os.path.dirname(options.dll_path), 'shlib')
      if os.path.isdir(shlib_path):
        self.dll_directory = _add_dll_directory(shlib_path)
      elif os.path.isdir(options.dll_path):
        self.dll_directory = _add_dll_directory(options.dll_path)
      else:
        raise ProjectConnectionFailureError(
          "Failed to locate folder containing required dlls. "
          f"Searched:\n {shlib_path} \n and \n {options.dll_path}")
      del shlib_path

    # Acquire a licence for Maptek Extend.
    #
    # First, try with an anonymous session. This allows the use of borrowed
    # licences when the user isn't logged into Maptek Account.
    #
    # Secondly, if that that fails then we try non-anonymous so the user is
    # prompted to log-in. Unless the caller has been explicit and said they
    # only want an anonymous session.
    self.log.info('Acquiring licence for Maptek Extend')
    required_parameters = {
      'AnonymousSession': True,
      'MaptekAccountUserName': '',
      'MaptekAccountAuthKey': '',
      'ApiToken': '',
    }
    if connection_parameters:
      force_parameters = connection_parameters.copy()
      force_parameters.update(required_parameters)
    else:
      force_parameters = required_parameters

    for try_parameters in [force_parameters, connection_parameters]:
      try:
        self.broker_session = account.connect_to_maptek_account_broker(
          broker_connector_path, try_parameters)

        with self.broker_session.acquire_extend_licence(
            License().supported_licence_format()) as licence:
          self.log.info('Acquired licence for Maptek Extend')
          os.environ["MDF_ACTIVE_PACKAGE"] = licence.license_string
          os.environ["MDF_EXTEND_LICENCE_STRING"] = licence.license_string

        break
      except ValueError as error:
        # That failed, but we can try again this time without requiring it
        # to be anonymous to allow the user to login.
        if self.broker_session:
          self.broker_session.disconnect()

        # There are two options for how to log the message here. One is to be
        # generic to match how this code is written (which is rather generic)
        # so it would be future-proof, for example "Initial attempt to licence
        # has failed, trying again.". Two is to actually say the intent at
        # the time which was "Failed to find a borrowed licence. Trying a live
        # licence."
        self.log.info('Failed to find a borrowed licence. Trying a live '
                      'licence.')

        # However it is possible the caller has explicitally said be
        # anonymous in which case this won't make any difference.
        if connection_parameters and connection_parameters.get(
            'AnonymousSession', False):
          raise

        # Capture the error so it can throw if it was the last one.
        broker_error = error
    else:
      raise broker_error

    # Setup mcpd connection
    self.options = options
    self.allow_hidden_objects = self.options.allow_hidden_objects

    if isinstance(existing_mcpd, McpdConnection):
      self.mcp_instance = existing_mcpd
    else:
      # An existing McpdConnection instance has not been supplied but if
      # existing_mcpd isn't None then connection details have been.
      self.mcp_instance = McpdConnection(
        self.options,
        specific_mcpd=existing_mcpd,
        )

    # Assuming mcpd connected, set up dataengine and modelling library.
    DataEngine()
    Modelling()

    # Load other DLLs which define DataEngine types before opening the
    # DataEngine. This at a minimum needs to be the DLLs loaded by the
    # Python SDK.
    self._dlls_with_object_types = []
    for library_name in ['mdf_selection', 'mdf_scan', 'mdf_viewer',
                         'mdf_vulcan']:
      self.log.info('Loading library: %s', library_name)
      try:
        self._dlls_with_object_types.append(getattr(ctypes.cdll, library_name))
      except OSError:
        # This may be as simple as the application/tests doesn't have this
        # library.
        self.log.warning('Library failed library: %s', library_name)

    # Check the project options to see if using a host application DataEngine,
    # or creating/opening a new or existing one.
    if self.options.open_mode is ProjectOpenMode.MEMORY_ONLY:
      # No executables or servers will be used. This means no mcpd or
      # backendServer will be launched or used.
      self.dataengine_connection = DataEngine().CreateLocal()
      if self.dataengine_connection:
        self.log.info("Created memory-only dataengine")
      else:
        last_error = DataEngine().ErrorMessage().decode(
          "utf-8")
        error_message = "There was an error while creating" + \
          " memory-only project (%s)" % last_error
        self.log.critical(error_message)
        raise ProjectConnectionFailureError(error_message)

      # A backend index of 0 means the backend is the DataEngine itself.
      self.backend_index = 0
    elif self.options.mcpd_mode is McpdMode.CONNECT_TO_EXISTING:
      # The host is expected to have an existing backend server running.
      if not self.mcp_instance.is_connected:
        error_message = "Connection with the mcpd failed. Can't connect " + \
          "to existing application. Check the application is functioning " + \
          "and is properly licenced."
        self.log.critical(error_message)
        raise ProjectConnectionFailureError(error_message)
    elif self.options.mcpd_mode is McpdMode.CREATE_NEW:
      # Start a backend server.
      backend_registered = self.mcp_instance.register_server('backendServer')
      if not backend_registered:
        error_message = "Failed to register backend server"
        self.log.critical(error_message)
        raise ProjectConnectionFailureError(error_message)

      # Ensure there are no stale lock files.
      if not DataEngine().DeleteStaleLockFile(
          self.options.project_path.encode('utf-8')):
        last_error = DataEngine().ErrorMessage().decode("utf-8")
        error_message = "There was a problem ensuring no stale lock files " \
          + "had been left in the project. Error message: " + last_error
        self.log.error(error_message)

        # Try sharing the project?
        self.options.backend_type = ProjectBackendType.SHARED
        self.log.warning('Attempting to share the project "%s"',
                         self.options.project_path)

      # Create or open project.
      self.backend_index = DataEngine().OpenProject(
        self.options.project_path.encode('utf-8'),
        self.options.open_mode,
        self.options.access_mode,
        self.options.backend_type,
        self.options.proj_units)
      if self.backend_index == 0:
        last_error = DataEngine().ErrorMessage().decode("utf-8")
        error_message = "There was a problem using the requested database " \
                        + "load or creation settings. If running in " \
                        + "stand-alone mode, check that the libraries " \
                        + "were built with appropriate license. " \
                        + "Error message: " + last_error
        self.log.critical(error_message)
        raise ProjectConnectionFailureError(error_message)
    else:
      raise ProjectConnectionFailureError(
        'Unsupported McpdMode: %s' % self.options.mcpd_mode)

    if not self.dataengine_connection:
      # Connecting to an existing DataEngine session.
      create_new_session = False
      self.dataengine_connection = DataEngine().Connect(
        create_new_session)
      if not self.dataengine_connection:
        last_error = DataEngine().ErrorMessage().decode("utf-8")
        error_message = "There was an error connecting to the database (%s)" %\
          last_error
        self.log.critical(error_message)
        raise ProjectConnectionFailureError(error_message)

      # The backend is managed by an existing application and what kind of
      # backend is not provided when connecting to it.
      self.backend_index = -1

    DataEngine().is_connected = self.dataengine_connection

    # Store easy access for project's root object.
    self.root_id = ObjectID(DataEngine().RootContainer())

  def __enter__(self):
    self.log.debug("__enter__ called")
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.log.debug("__exit__ called")
    self.unload_project()

  def __find_from(self, object_id, names, create_if_not_found):
    """Internal function for find_object() and
    _find_object_or_create_if_missing().

    Parameters
    ----------
    object_id : ObjectID
      the ID of the object to start at.
    names : list
      list of container paths to recursively search through
      and / or create if not found (if create_if_not_found)
      e.g. ['surfaces', 'new container', 'surfaces 2'].
    create_if_not_found : bool
      Create specified path if it doesn't exist.

    Returns
    -------
    ObjectID
      Object ID of the object if found.
    None
      Object could not be found.

    Raise
    -----
    Exception: Error trying to create path that didn't exist (unknown error).
    ValueError: A new path needs to be created and will result in
      creating hidden objects (i.e. start with '.') when
      project attribute allow_hidden_objects is False.

    """
    if not names:
      return object_id
    with ReadLock(object_id.handle) as r_lock:
      found = ObjectID(DataEngine().ContainerFind(
        r_lock.lock, to_utf8(names[0])))

    if not found and create_if_not_found:
      self.log.info("The path %s didn't exist so attempting to create it.",
                    '/'.join(names))

      if not self.allow_hidden_objects:
        # Check that none of the objects created would be hidden.
        if any(name.startswith('.') for name in names):
          raise ValueError("Invalid path provided. No object name may start "
                           "with '.' as that would be a hidden object.")

      # Create a new container for each part of the path (as none of them
      # exist)
      new_containers = [
        ObjectID(Modelling().NewVisualContainer())
        for _ in range(len(names))
      ]

      # Add each new container to the container before it.
      new_parents = [object_id] + new_containers[:-1]
      for parent, child, name in zip(reversed(new_parents),
                                     reversed(new_containers),
                                     reversed(names)):
        with WriteLock(self.__get_obj_handle(parent)) as w_lock:
          DataEngine().ContainerAppend(
            w_lock.lock,
            to_utf8(name),
            self.__get_obj_handle(child),
            True)
      return new_containers[-1]
    elif not found and not create_if_not_found:
      return None # doesn't exist and we want to know
    return self.__find_from(found, names[1:], create_if_not_found)

  def unload_project(self):
    """Call the mcp class to unload a spawned mcp instance (i.e. when not
    using a host application like Eureka or PointStudio).
    Use this when finished operating on a project that has
    ProjectOptions that requested an mcpd_mode of CREATE_NEW.

    Also unloads dataengine created with same methods.

    Failure to call this un-loader may leave orphan mcpd.exe processes
    running on the machine.

    """
    self.log.info("unload_project() called")
    if self.backend_index is not None:
      if self.backend_index == -1:
        # The backend for the project is hosted by another application, we
        # simply need to disconnect from it. However if our connection was
        # keeping the backend alive we need to close it if we are the last
        # one.
        self.log.info("Disconnecting from a project opened by an another "
                      "application.")
        close_backends_if_last_client = True
        DataEngine().Disconnect(close_backends_if_last_client)
      elif self.backend_index == 0:
        # A DataEngine backed project aren't expected to have any other
        # clients. Its primary use is for tests and scripts which need to
        # open a DataEngine, create/import and save results then close it, i.e
        # not in multi-process situations where the lifetime of the processes
        # are unknown.
        self.log.info("Disconnecting from an in-memory project.")
        close_backends_if_last_client = False
        DataEngine().Disconnect(close_backends_if_last_client)
      else:
        self.log.info("Closing project with backend index: %s",
                      self.backend_index)
        DataEngine().CloseProject(self.backend_index)
      self.backend_index = None

    if self.mcp_instance:
      try:
        self.mcp_instance.unload_mcp()
      except McpdDisconnectError:
        # The exception is already logged, so it is safe to ignore it.
        pass

    if self.broker_session:
      self.broker_session.disconnect()

    # Remove the dll directory from the search path.
    try:
      if self.dll_directory:
        self.dll_directory.close()
    except OSError as error:
      self.log.exception(error)

    # The project has been unloaded so it doesn't need to be done when the
    # interpreter terminates.
    if self._exit_function:
      atexit.unregister(self._exit_function)
      self._exit_function = None

  @property
  def api_version(self):
    """Returns the API version reported by the application.

    Returns
    -------
    tuple
      The API version of the application in the form: (major, minor).

    Notes
    -----
    PointStudio 2020 / Eureka 2020 / Blastlogic 2020.1 have api_version (1, 1).
    PointStudio 2020.1 has api_version (1, 2).
    Earlier applications will have api_version (0, 0). It is not recommended to
    connect to applications with api versions less than (1, 1).

    """
    # Though each C API could have its own version, currently they all
    # return the same version.
    return Modelling().version

  def raise_if_version_below(self, version):
    """Raises an error if the script has connected to an application whose
    version is lower than the specified version.

    This allows for scripts to exit early when attaching to an application
    which does not support the required data types.

    Raises
    ------
    ApplicationTooOldError
      If the API version is lower than the specified version.

    Examples
    --------
    Exit if the application does not support GridSurface (api_version is
    less than (1, 2)).

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> project.raise_if_version_below((1, 2))

    It is also possible to catch this error and add extra information.

    >>> from mapteksdk.project import Project, ApplicationTooOldError
    >>> project = Project()
    >>> try:
    ...     project.raise_if_version_below((1, 2))
    >>> except ApplicationTooOldError as error:
    ...     raise SystemExit("The attached application does not support "
    ...                      "irregular grids") from error

    """
    if self.api_version < version:
      message = (f"API version is too old: {self.api_version}. "
                 f"This script requires an API version of at least: {version}")
      raise ApplicationTooOldError(message)

  def find_object(self, path):
    """Find the ObjectID of the object at the given path.

    Parameters
    ----------
    path : str
      Path to the object.

    Returns
    -------
      ObjectID
        The ID of the object at the given path.
      None
        If there was no object at path.

    """
    parts = path.strip("/").split("/")
    # Remove empty strings (e.g. /surfaces/ = '', surfaces, '')
    parts = list(filter(None, parts))
    return self.__find_from(self.root_id, parts, create_if_not_found=False)

  def _find_object_or_create_if_missing(self, path):
    """Find object ID of the object at the given path.

    Parameters
    ----------
    path : str
      path (defaults to root path with no input).

    create_if_not_found : bool
      Create specified path if it doesn't exist.

    Returns
    -------
    ObjectID
      The ID of the object at the given path.
    None
      If the path doesn't exist.

    """
    parts = path.strip("/").split("/")
    # Remove empty strings (e.g. /surfaces/ = '', surfaces, '')
    parts = list(filter(None, parts))
    return self.__find_from(self.root_id, parts, create_if_not_found=True)

  @contextmanager
  def read(self, path_or_id):
    """Open an existing object in read-only mode. In read-only mode
    the values in the object can be read, but no changes can be
    saved. Use this function instead of edit() if you do not intend to
    make any changes to the object.

    If this is called using a with statement, close() is called
    automatically at the end of the with block.

    Parameters
    ----------
    path_or_id : str or ObjectID
      The path or the ID of the object to open.

    Raises
    ------
    ObjectDoesNotExistError
      If path_or_id is not an existent object.
    TypeError
      If path_or_id is an unsupported object.

    Examples
    --------
    Read an object at path/to/object/to/read and then print out the
    point, edge and facet counts of the object.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> path = "path/to/object/to/read"
    >>> with project.read(path) as read_object:
    ...     if hasattr(read_object, "point_count"):
    ...         print(f"{path} contains {read_object.point_count} points")
    ...     if hasattr(read_object, "edge_count"):
    ...         print(f"{path} contains {read_object.edge_count} edges")
    ...     if hasattr(read_object, "facet_count"):
    ...         print(f"{path} contains {read_object.facet_count} edges")

    """
    if isinstance(path_or_id, ObjectID):
      object_id = path_or_id
      if not object_id.exists:
        error_msg = "Tried to read an object that doesn't exist: %s" \
          % path_or_id
        self.log.error(error_msg)
        raise ObjectDoesNotExistError(error_msg)
    else:
      object_id = self.find_object(path_or_id)
      if not object_id:
        error_msg = "Tried to read an object that doesn't exist: %s" \
          % path_or_id
        self.log.error(error_msg)
        raise ObjectDoesNotExistError(error_msg)

    object_type = self._type_for_object(object_id)
    opened_object = object_type(object_id, LockType.READ)
    try:
      yield opened_object
    finally:
      opened_object.close()

  @contextmanager
  def new(self, object_path, object_class: ObjectType,
          overwrite=False) -> ObjectType:
    """Create a new object and add it to the project. Note that
    changes made to the created object will not appear in the
    view until save() or close() is called.

    If this is called using a with statement, save() and close()
    are called automatically at the end of the with block.

    Parameters
    ----------
    object_path : string
      Full path for new object. e.g. "surfaces/generated/new surface 1"
      If None, the new object will not be assigned a path and will
      only be available through its object ID.
    object_class : class
      The type of the object to create. (e.g. Surface).
    overwrite : bool
      If overwrite=False (default) a ValueError is raised if
      there is already an object at new_name.
      If overwrite=True then any object at object_path is replaced
      by the new object. The overwritten object is orphaned rather
      than deleted and may still be accessible through its id.

    Yields
    ------
    DataObject
      The newly created object. The type of this will be object_class.

    Raises
    ------
    ValueError
      If an object already exists at new_path and overwrite = False.
    ValueError
      If object path is blank, '.' or '/'.

    Notes
    -----
    If an exception is raised while creating the object the object will
    not be saved.

    If you do not assign a path to an object on creation, project.add_object()
    can be used to assign a path to the object after creation.

    Examples
    --------
    Create a new surface and set it to be a square with side length
    of two and centred at the origin.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Surface
    >>> project = Project()
    >>> points = [[-1, -1, 0], [1, -1, 0], [-1, 1, 0], [1, 1, 0]]
    >>> facets = [[0, 1, 2], [1, 2, 3]]
    >>> with project.new("surfaces/square", Surface) as new_surface:
    ...   new_surface.points = points
    ...   new_surface.facets = facets
    ...   # new_surface.close is called implicitly here.

    """
    # Background process:
    # Create empty object of provided type, get new handle & open write lock
    # with [yield >> user populates with data]
    # finally [done] >> Add to project
    # pylint: disable=unidiomatic-typecheck
    if type(object_class) is type:
      # :TRICKY: Check if the user passed in a type, like Triangle,
      # or instance of that type, like Triangle().  This is
      # required to support more complicated types that require
      # constructor parameters to be useful (like DenseBlockModel(...)).
      # If not an instance, then create one:
      object_class = object_class(lock_type=LockType.READWRITE)
    try:
      yield object_class
      object_class.save()
      if object_path is not None:
        # The new object does not yet exist as an item in the Project
        # add it now.
        self.add_object(object_path, object_class, overwrite=overwrite)
      object_class.close()
    except:
      # If there was an exception the object is an orphan,
      # so delete it then re-raise the exception.
      object_class.close()
      self.delete(object_class, True)
      raise

  @contextmanager
  def edit(self, path_or_id):
    """Open an existing object in read/write mode. Unlike read, this
    allows changes to be made to the object. Note that changes made will
    not appear in the view until save() or close() is called.

    If this is called using a with statement, save() and close()
    are called automatically at the end of the with block.

    Parameters
    ----------
    path_or_id : str or ObjectID
      Path or ID of the object to edit.

    Yields
    ------
    DataObject
      The object at the specified path opened for editing.

    Raises
    ------
    ObjectDoesNotExistError
      If the object to edit does not exist.
    TypeError
      If the object type is not supported.

    Notes
    -----
    If an exception is raised while editing an object, any changes made
    inside the with block are not saved.

    Examples
    --------
    Edit the surface created in the example for project.new to a hourglass
    shape instead of a square.

    >>> from mapteksdk.project import Project
    >>> points = [[-1, -1, 0], [1, -1, 0], [-1, 1, 0], [1, 1, 0], [0, 0, 0]]
    >>> facets = [[0, 1, 4], [2, 3, 4]]
    >>> project = Project()
    >>> with project.edit("surfaces/square") as edit_surface:
    ...     edit_surface.points = points
    ...     edit_surface.facets = facets
    ...     # edit_surface.close is called implicitly here.

    """
    if isinstance(path_or_id, ObjectID):
      object_id = path_or_id
      if not object_id.exists:
        error_msg = "Tried to edit an object that doesn't exist: %s" \
          % path_or_id
        self.log.error(error_msg)
        raise ObjectDoesNotExistError(error_msg)
    else:
      object_id = self.find_object(path_or_id)
      if not object_id:
        error_msg = "Tried to edit an object that doesn't exist: %s" \
          % path_or_id
        self.log.error(error_msg)
        raise ObjectDoesNotExistError(error_msg)

    object_type = self._type_for_object(object_id)
    opened_object = object_type(object_id, LockType.READWRITE)
    try:
      yield opened_object
      opened_object.save()
    finally:
      opened_object.close()

  @contextmanager
  def new_or_edit(self, path, object_class: ObjectType,
                  overwrite=False) -> ObjectType:
    """This function works as project.new if the specified object does not
    exist. Otherwise it acts as project.edit.

    Parameters
    ----------
    path : string
      Path to the object to create or edit.

    object_class : type
      Class of the object to create or edit.

    overwrite : bool
      If False (default) and there is already an object at path
      whose type is not editable as object_class a ValueError is raised.
      If True, any object at path which is not object_class
      is orphaned to make room for the new object.

    Yields
    ------
    DataObject
      The newly created object or the object at the specified path.

    Raises
    ------
    ValueError
      If overwrite=False and there exists an object at path whose
      type is not object class.
    AttributeError
      If path is not a string.

    """
    existing_id = self.find_object(path)

    # Edit if there is an object of the correct type at path. Otherwise
    # attempt to create a new object of the correct type at path.
    if existing_id and existing_id.is_a(object_class):
      with self.edit(path) as opened_object:
        yield opened_object
    else:
      with self.new(path, object_class, overwrite) as opened_object:
        yield opened_object

  def __get_obj_handle(self, object_or_handle):
    """Helper to retrieve T_ObjectHandle for passing to the C API.

    Parameters
    ----------
    object_or_handle : DataObject, ObjectID, T_ObjectHandle or str
      Object with a handle, ID of an object, object handle or path to object.

    Returns
    -------
    T_ObjectHandle
      The object handle.
    None
      On exception.

    """
    if object_or_handle is None:
      return None

    if isinstance(object_or_handle, ObjectID):
      return object_or_handle.handle

    if isinstance(object_or_handle, str):
      object_or_handle = self.find_object(object_or_handle)
      return None if object_or_handle is None else object_or_handle.handle

    if isinstance(object_or_handle, T_ObjectHandle):
      return object_or_handle

    return object_or_handle.id.handle

  def add_object(self, full_path, new_object, overwrite=False):
    r"""Adds a new DataObject to the project. Normally this is not necessary
    because Project.new() will add the object for you. This should only need
    to be called if Project.new() was called with path = None or after a call
    to a function from the mapteksdk.io module.

    Parameters
    ----------
    full_path : str
      Full path to the new object (e.g. '/surfaces/new obj').
    new_object : DataObject or ObjectID
      Instance or ObjectID of the object to store at full_path.
    overwrite : bool
      If overwrite=False (default) a ValueError will be raised if there is
      already an object at full_path. If overwrite=True and there is an
      object at full_path it will be overwritten and full_path will now point
      to the new object. The overwritten object becomes an orphan.

    Returns
    -------
    ObjectID
      ID of newly stored object. This will be the object ID of
      new_object.

    Raises
    ------
    ValueError
      If invalid object name (E.g. '/', '', or (starting with) '.' when
      project options don't allow hidden objects).
    ValueError
      If paths contains back slashes (\).
    ValueError
      If overwrite=False and there is already an object at full_path.

    Notes
    -----
    Has no effect if new_object is already at full_path.

    """
    container_name, object_name = self._valid_path(full_path)
    if container_name == '':
      container_object = self.root_id
    else:
      self.log.info('Adding object %s to %s', object_name, container_name)
      container_object = self._find_object_or_create_if_missing(container_name)
    handle_to_add = self.__get_obj_handle(new_object)
    self.log.debug("Opening container %s to store object: %s",
                   container_name, ObjectID(handle_to_add))
    with WriteLock(self.__get_obj_handle(container_object)) as w_lock:
      existing_object = DataEngine().ContainerFind(
        w_lock.lock, to_utf8(object_name))
      if existing_object:
        if handle_to_add.value == existing_object.value:
          return ObjectID(existing_object)
        if overwrite:
          DataEngine().ContainerRemoveObject(
            w_lock.lock, existing_object, False)
        else:
          raise ValueError(
            f"There is already an object in the container called {object_name}"
          )

      DataEngine().ContainerAppend(w_lock.lock,
                                   to_utf8(object_name),
                                   handle_to_add,
                                   True)
    self.log.debug("Stored new object %s into container %s",
                   object_name,
                   container_name)
    return ObjectID(handle_to_add)

  def get_children(self, path_or_id=""):
    """Return the children of the container at path as (name, id) pairs.

    Parameters
    ----------
    path_or_id : str or ObjectID
      The path or object ID of the container to work with.

    Returns
    -------
    ChildView
      Provides a sequence that can be iterated over to provide the
      (name, id) for each child. It also provides name() and ids() functions
      for querying just the names and object IDs respectively.

    Raises
    ------
    ObjectDoesNotExistError
      If the path does not exist in the project.
    TypeError
      If the path is not a container.
    ValueError
      If the path is a container but not suitable for accessing its children.

    """

    if isinstance(path_or_id, str):
      if path_or_id and path_or_id != '/':
        container = self.find_object(path_or_id)
      else:
        container = self.root_id
    else:
      container = path_or_id
      path_or_id = '/'

    if not container:
      message_template = '"%s" is not in the project.'
      self.log.error(message_template, path_or_id)
      raise ObjectDoesNotExistError(message_template % path_or_id)

    if not container.is_a(Container):
      message_template = 'The object "%s" (%s) is not a container.'
      self.log.error(message_template, path_or_id, container)
      raise TypeError(message_template % (path_or_id, container))

    # TODO: Prevent the users from querying the children of certain objects
    # that they don't see as being containers like edge chain/loops
    # (topologies). This issue is tracked by SDK-46.

    # Don't include hidden objects if access to them is not allowed and don't
    # include objects without a name (which shouldn't happen).
    if self.allow_hidden_objects:
      include = lambda name: name
    else:
      include = lambda name: name and not name.startswith('.')

    children = []
    with ReadLock(self.__get_obj_handle(container)) as r_lock:
      iterator = DataEngine().ContainerBegin(r_lock.lock)
      end = DataEngine().ContainerEnd(r_lock.lock)
      while iterator.value != end.value:
        buf_size = DataEngine().ContainerElementName(
          r_lock.lock,
          iterator,
          None,
          0)
        str_buffer = ctypes.create_string_buffer(buf_size)
        DataEngine().ContainerElementName(r_lock.lock,
                                          iterator,
                                          str_buffer,
                                          buf_size)
        name = str_buffer.value.decode("utf-8")

        if include(name):
          object_id = ObjectID(
            DataEngine().ContainerElementObject(
              r_lock.lock,
              iterator))

          children.append((name, object_id))
        iterator = DataEngine().ContainerNextElement(
          r_lock.lock,
          iterator)

    return ChildView(children)

  def get_descendants(self, path_or_id=""):
    """Return all descendants of the container at path as (name, id) pairs.

    Parameters
    ----------
    path_or_id : str or ObjectID
      The path or object ID of the container to work with.

    Returns
    -------
    ChildView
      Provides a sequence that can be iterated over to provide the
      (name, id) for each child. It also provides name() and ids() functions
      for querying just the names and object IDs respectively.

    Raises
    ------
    KeyError
      If the path does not exist in the project.

    TypeError:
      If the path is not a container.

    ValueError:
      If the path is a container but not suitable for accessing its children.

    """
    def list_all_descendants(parent):
      # Recursive function to retrieve all children of all VisualContainers
      results = []
      for child_name, child_id in self.get_children(parent):
        results.append((child_name, child_id))
        if child_id.is_a(VisualContainer):
          if isinstance(parent, str):
            # if provided, use a path to define the next level of the family,
            # avoiding any issue where an ObjectID has multiple paths.
            path = posixpath.join(parent, child_name)
            results.extend(list_all_descendants(path))
          else:
            results.extend(list_all_descendants(child_id))
      return results
    return ChildView(list_all_descendants(path_or_id))

  def copy_object(self, object_to_clone, new_path, overwrite=False,
                  allow_standard_containers=False):
    """Deep clone DataObject to a new object (and ObjectID).

    If this is called on a container, it will also copy all of the
    container's contents.

    Parameters
    ----------
    object_to_clone : DataObject or ObjectID or str
      The object to clone or the ID for the object to clone
      or a str representing the path to the object.

    new_path : str
      full path to place the copy (e.g. 'surfaces/new/my copy').
      Set as None for just a backend object copy.

    overwrite : bool
      If False (default) a ValueError will be raised if
      there is already an object at new_name.
      If True and there is an object at new_path the object
      at new_path is overwritten. The overwritten object is orphaned
      instead of deleted and may still be accessible via its id.

    allow_standard_containers : bool
      If False (default) then attempting to copy a standard container
      will create a visual container instead.
      If True (not recommended) copying a standard container will
      create a new standard container.

    Returns
    -------
    ObjectID
      Id of new object (The clone).
    None
      If the operation failed.

    Raises
    ------
    ValueError
      If an object already exists at new_path and overwrite = False.

    """
    if isinstance(object_to_clone, str):
      object_to_clone = self.find_object(object_to_clone)
    old_handle = self.__get_obj_handle(object_to_clone)

    # Special handling for standard containers.
    # Copying a standard container creates a visual container instead
    # of a standard container.
    # If allow_standard_containers, this is bypassed.
    if object_to_clone.is_a(StandardContainer) \
        and not allow_standard_containers:
      with self.new(new_path, VisualContainer, overwrite=False) as copy:
        pass
      for child_name, child_id in self.get_children(object_to_clone):
        self.copy_object(child_id, new_path + "/" + child_name)

      return copy.id

    with ReadLock(old_handle) as r_lock:
      copyobj = ObjectID(DataEngine().CloneObject(r_lock.lock, 0))
      if not copyobj:
        last_error = DataEngine().ErrorMessage().decode(
          "utf-8")
        self.log.error('Failed to clone object %s because %s',
                       object_to_clone, last_error)

    self.log.debug("Deep copy %s to %s",
                   old_handle,
                   new_path if new_path is not None else "[Backend Object]")
    if new_path is not None:
      return self.add_object(new_path, copyobj, overwrite=overwrite)
    return copyobj

  def rename_object(self, object_to_rename, new_name, overwrite=False,
                    allow_standard_containers=False):
    """Rename (and/or move) an object.

    Renaming an object to its own name has no effect.

    Parameters
    ----------
    object_to_rename : DataObject or ObjectID or str
      The object to rename or
      the ID of the object to rename or
      full path to object in the Project.
    new_name : str
      new name for object.
      Standalone name (e.g. 'new tri') will keep root path.
      Full path (e.g. 'surfaces/new tri') will change location.
      Prefix with '/' (e.g. '/new tri' to move to the root
      container).
    overwrite : bool
      If False (default) then if there is already an object at new_name
      then a ValueError is raised.
      If True and if there is already an object at new_name then
      the object at new_name is overwritten. The overwritten object is
      orphaned rather than deleted and may still be accessible via
      its ID.
    allow_standard_containers : bool
      If False (default) then attempting to rename a standard container
      will create a new container and move everything in the standard
      container into the new container.
      If True (not recommended) standard containers can be renamed.

    Returns
    -------
    bool
      True if rename/move successful,
      False if failed (overwrite checks failed).

    Raises
    ------
    ValueError
      New object name begins with full stop when project
      attribute allow_hidden_objects is False (default).
    ValueError
      New object name can't be '.'.
    ValueError
      If there is already an object at new_name and overwrite=False.
    ObjectDoesNotExistError
      Attempting to rename an object that doesn't exist.
    DeleteRootError
      Attempting to rename root container.

    Notes
    -----
    new_name can not start with a full stop '.' when allow_hidden_objects is
    False and cannot be '/' or '' or '.'.

    """
    object_to_rename = ObjectID(self.__get_obj_handle(object_to_rename))

    # Safety checks:
    if not object_to_rename:
      error_message = "Unable to locate object for renaming"
      self.log.error(error_message)
      raise ObjectDoesNotExistError(error_message)

    if object_to_rename == self.root_id:
      error_message = "Can't rename root container"
      self.log.error(error_message)
      raise DeleteRootError(error_message)

    # Special handling for standard containers.
    # Rename creates a new visual container and moves the standard container's
    # contents into the copy.
    # If allow_standard_containers, this is bypassed.
    if object_to_rename.is_a(StandardContainer) \
        and not allow_standard_containers:
      with self.new(new_name, VisualContainer, overwrite=False):
        pass
      for child_name, child_id in self.get_children(object_to_rename):
        self.rename_object(child_id, new_name + "/" + child_name)
      return True

    # Shift/rename object or container:
    old_parent = object_to_rename.parent
    if old_parent:
      old_parent_path = old_parent.path
    else:
      old_parent_path = ''  # The object is not in a container.

    new_parent_path, new_obj_name = self._valid_path(new_name)
    new_parent_is_root = new_parent_path == '' and new_name.startswith('/')

    if not new_parent_path and not new_parent_is_root:
      new_parent_path = old_parent_path

    old_path = object_to_rename.path.strip('/')
    new_path = (new_parent_path + "/" + new_obj_name).strip('/')

    self.add_object(
      new_path,
      object_to_rename, overwrite=overwrite)

    # If the object didn't have a parent, then it wasn't in a container so there
    # is no need to remove it from a container.
    # Additionally, if the new path and the old path are the same, then it
    # is in the same container, so don't remove it.
    if old_parent and old_path != new_path:
      try:
        self.__remove_from_container(object_to_rename, old_parent)
      except OSError:
        self.log.exception("Error while removing object %r from container %r",
                           old_parent, object_to_rename)

    return True

  def delete_container_contents(self, container):
    """Deletes all the contents of a container.

    Parameters
    ----------
    container : DataObject or ObjectID or str
      the object to delete or
      the ID for the object to delete or
      path to container (e.g. '/surfaces/old').

    """
    handle = self.__get_obj_handle(container)
    if handle is not None:
      object_type = DataEngine().ObjectDynamicType(handle)
      required_type = Modelling().VisualContainerType()
      if DataEngine().TypeIsA(object_type, required_type):
        self.log.info("Delete container contents: %s", ObjectID(handle).path)
        try:
          with WriteLock(handle) as w_lock:
            DataEngine().ContainerPurge(w_lock.lock)
        except OSError as ex:
          self.log.error("Error purging container %s: %s", container, ex)

  def new_visual_container(self, parent_container, container_name):
    """Creates a new visual container.

    Parameters
    ----------
    parent_container : str
      Parent container name.
    container_name : str
      New container name.

    Returns
    -------
    ObjectID
      The object ID for newly created container.

    Raises
    ------
    ValueError
      When attempting to create a container name or part of path
      that would result in hidden objects (i.e. starts with '.')
      and allow_hidden_objects is False.
    ValueError
      If the container name contains "/" characters.

    """
    if parent_container not in ["", "/"]:
      parent_container = "/".join(self._valid_path(parent_container))
    self._check_path_component_validity(container_name)

    mdf_object = self._find_object_or_create_if_missing(parent_container)
    with WriteLock(self.__get_obj_handle(mdf_object)) as w_lock:
      container = ObjectID(Modelling().NewVisualContainer())
      DataEngine().ContainerAppend(
        w_lock.lock,
        to_utf8(container_name),
        self.__get_obj_handle(container),
        True)
      self.log.info("Created new container: [%s] under [%s]",
                    container_name,
                    parent_container)
    return container

  def __remove_from_container(self, object_to_remove, container):
    """Removes an object from a container but doesn't delete it.

    Parameters
    ----------
    object_to_remove : ObjectID
      The ID of the object to remove.
    container : ObjectID
      The ID of the container to remove the object from.

    """
    if self.log.isEnabledFor(logging.DEBUG):
      self.log.info("Remove object %r (%s) from parent container %r (%s).",
                    object_to_remove, object_to_remove.path, container,
                    container.path)
    else:
      self.log.info("Remove object %r from parent container %r.",
                    object_to_remove, container)

    with WriteLock(container.handle) as w_lock:
      return DataEngine().ContainerRemoveObject(
        w_lock.lock, object_to_remove.handle, False)

  def delete(self, mdf_object_or_name, allow_standard_containers=False):
    """Deletes the given object.

    Parameters
    ----------
    mdf_object_or_name : string or DataObject or ObjectID
      Container name, instance of object as DataObject or
      ObjectID of the object.

    allow_standard_containers : bool
      If False (default) then attempting to delete a standard
      container will result in the container contents being deleted.
      If True then standard containers will be deleted. See warnings
      for why you shouldn't do this.

    Returns
    -------
    bool
      True if deleted successfully or False if not.

    Raises
    ------
    DeleteRootError
      If the object provided is the root container.

    RuntimeError
      If the the object can't be deleted. The most common cause is something
      is writing to the object at this time.

    Warnings
    --------
    Deleting a standard container created by a Maptek application
    may cause the application to crash. The allow_standard_containers
    flag should only be used to delete standard containers you have created
    yourself (It is not recommended to create your own standard containers).

    """
    self.log.info("Delete object: %s", mdf_object_or_name)
    try:
      if isinstance(mdf_object_or_name, str):
        object_id = self.find_object(mdf_object_or_name)
        self._delete(object_id, allow_standard_containers)
      else:
        self._delete(mdf_object_or_name, allow_standard_containers)
      return True
    except RuntimeError as error:
      self.log.error("Error deleting object: %s [%s]",
                     mdf_object_or_name, error)
      raise

  def _delete(self, mdf_object, allow_standard_containers):
    """Internal delete - by object (not string).

    Parameters
    ----------
    mdf_object : DataObject or ObjectID
      The object to delete.
    allow_standard_containers : bool
      If False (default) then attempting to delete a standard
      container will result in the container contents being deleted.
      If True then standard containers will be deleted.

    Returns
    -------
    bool
      True if successful or False if not.

    Raises
    ------
    DeleteRootError
      If the object provided is the root container.
    RuntimeError
      If the the object can't be deleted. The most common cause is something
      is writing to the object at this time.
    """
    object_id = ObjectID(self.__get_obj_handle(mdf_object))
    if object_id == self.root_id:
      raise DeleteRootError("You cannot delete the root container.")
    if mdf_object is None:
      return True

    # Special handling for standard containers.
    # Deleting a standard container deletes its contents
    # and leaves the container untouched.
    # If allow_standard_containers, this is bypassed.
    if object_id.is_a(StandardContainer) and not allow_standard_containers:
      return self.delete_container_contents(mdf_object)

    mdf_object = self.__get_obj_handle(mdf_object)

    success = DataEngine().DeleteObject(mdf_object)
    if not success:
      error = DataEngine().ErrorMessage().decode("utf-8")
      raise RuntimeError(error)

  def _type_for_object(self, object_handle):
    """Return the type of an object based on the object ID without needing
    to read the object.

    Parameters
    ----------
    object_handle : DataObject or ObjectID
      The object to query the type for.

    Returns
    --------
    type:
      The DataObject type e.g. Surface, Marker as type only.

    Raises
    ------
    TypeError
      If the object handle is of a type that isn't known or supported.
    ObjectDoesNotExistError
      If object_handle does not refer to a valid object.

    """
    object_handle = self.__get_obj_handle(object_handle)
    if object_handle is None:
      error_message = "Unable to locate object"
      self.log.error(error_message)
      raise ObjectDoesNotExistError(error_message)

    object_type = DataEngine().ObjectDynamicType(object_handle)

    # Define a list of types that correspond to the Python classes that are
    # used to represent and access the data stored in the project. The order
    # in this list is important, derived types must come first before the base
    # types.
    types_for_data = [
      StandardContainer,
      VisualContainer,
      Surface,
      Text2D,
      Text3D,
      EdgeNetwork,
      Polyline,
      Polygon,
      Marker,
      PointSet,
      Scan,
      GridSurface,
      SparseIrregularCellNetwork,
      Discontinuity,

      # TODO: Handle RegularCellNetwork, SparseCellNetwork and
      # SparseRegularCellNetwork.

      NumericColourMap,
      StringColourMap,
      SparseBlockModel,
      DenseBlockModel,
      SubblockedBlockModel,

      Raster,
    ]

    for class_type in types_for_data:
      type_index = class_type.static_type()
      if DataEngine().TypeIsA(object_type, type_index):
        return class_type

    # This doesn't use an is_a() because we want to handle the case where a
    # plain container was created. Typically a Container is a base-class
    # of higher level types and treating them as such wouldn't be ideal.
    if object_type == Container.static_type():
      return Container

    raise TypeError('Unsupported object type')

  def get_selected(self):
    """Return the IDs of the selected objects.

    When connected to an existing application, these are the objects selected
    in that application (via the explorer, view or some other method).

    Returns
    -------
    list
      A list of selected ObjectIDs.

    """
    # Query how many objects are selected.
    count = DataEngine().GetSelectedObjectCount()
    # Allocate to receive the selected objects.
    object_array = (T_ObjectHandle * count)()
    # Populate the array and build up a list of object IDs.
    DataEngine().GetSelectedObjects(object_array)
    selected_objects = [ObjectID(buff) for buff in object_array]
    return selected_objects

  def set_selected(self, object_ids_or_paths=None, include_descendants=True):
    """Set active project selection to one or more objects.
    If None specified, selection will be cleared.
    If objects are provided but are not valid, they will not be selected.
    No action will be taken if entire selection specified is invalid.
    Any VisualContainer objects specified will include their descendants.

    Parameters
    ----------
    mdf_objects_or_paths : list, str, ObjectID, or None
      List of object paths to select, List of ObjectID to select,
      path to object to select, ObjectID of object to select.
      Pass None or an empty list to clear the existing selection.

    include_descendants : bool
      whether to also select descendants of any VisualContainer provided
      within the selection criteria (default=True).

    Raises
    -------
    ValueError
      If any or all objects within the selection specified is invalid.

    """
    if not object_ids_or_paths:
      # Clear selection
      self.log.info("Clearing active object selection")
      DataEngine().SetSelectedObjects(None, 0)
    else:
      # List of selected visual containers.
      containers = []
      # Handles of the selected objects.
      selected_handles = []
      if not isinstance(object_ids_or_paths, typing.Iterable) or \
          isinstance(object_ids_or_paths, str):
        object_ids_or_paths = [object_ids_or_paths]

      # Ensure all objects provided are valid and exist
      for obj in object_ids_or_paths:
        handle = self.__get_obj_handle(obj)
        if handle and DataEngine().ObjectHandleExists(handle):
          oid = ObjectID(handle)
          if oid.is_a(VisualContainer):
            containers.append(oid)
          selected_handles.append(handle)
        else:
          error_msg = ("An invalid object ({}) was specified for "
                       + "selection.\nVerify objects specified in the "
                       + "selection are valid and still exist.").format(obj)
          self.log.error(error_msg)
          raise ValueError(error_msg)

      if include_descendants:
        # Include handles of descendant objects for any VisualContainer objects
        # specified and their children.
        descendants = []
        for obj in containers:
          descendants.extend(self.get_descendants(obj).ids())
        if descendants:
          self.log.info("Adding %d descendant objects to selection",
                        len(descendants))
          selected_handles.extend(child.handle for child in descendants)

      object_count = len(selected_handles)
      self.log.info("Set selection with %d objects", object_count)
      object_array = (T_ObjectHandle * object_count)(*selected_handles)
      DataEngine().SetSelectedObjects(object_array, object_count)

  def is_recycled(self, mdf_object):
    """Check if an object is in the recycle bin.

    Parameters
    ----------
    mdf_object : DataObject or ObjectID
      Object to check.

    Returns
    -------
    bool
      True if the object is in the recycle bin (deleted)
      and False if it is not.

    """
    mdf_object = self.__get_obj_handle(mdf_object)
    return DataEngine().ObjectHandleIsInRecycleBin(mdf_object)

  def type_name(self, path_or_id):
    """Return the type name of an object.

    This name is for diagnostics purposes only. Do not use it to alter the
    behaviour of your code. If you wish to check if an object is of a given
    type, use ObjectID.is_a() instead.

    Parameters
    ----------
    path_or_id : str or ObjectID
      The path or the ID of the object to query its type's name.

    Returns
    -------
    str
      The name of the type of the given object.

    See Also
    --------
    mapteksdk.data.objectid.ObjectID.is_a : Check if the type of an object is
      the expected type.
    """
    mdf_object = self.__get_obj_handle(path_or_id)
    dynamic_type = DataEngine().ObjectDynamicType(mdf_object)
    raw_type_name: str = DataEngine().TypeName(dynamic_type).decode('utf-8')

    # Tidy up certain names for users of the Python SDK.
    raw_to_friendly_name = {
      '3DContainer': 'VisualContainer',
      '3DEdgeChain': 'Polyline',
      '3DEdgeNetwork': 'EdgeNetwork',
      '3DNonBrowseableContainer': 'NonBrowseableContainer',
      '3DPointSet': 'PointSet',
      'BlockNetworkDenseRegular': 'DenseBlockModel',
      'BlockNetworkDenseSubblocked': 'SubblockedBlockModel',
      'EdgeLoop': 'Polygon',
      'RangeImage': 'Scan',
      'StandardContainer': 'StandardContainer',
      'TangentPlane': 'Discontinuity',
    }

    # Exclude the old (and obsolete) revision number.
    raw_type_name = raw_type_name.partition('_r')[0]

    return raw_to_friendly_name.get(raw_type_name, raw_type_name)

  def _check_path_component_validity(self, path):
    """Raises an appropriate error if the path component is invalid.

    Parameters
    ----------
    path : str
      The path to check for validity.

    Raises
    ------
    ValueError
      path is empty or only whitespace.
    ValueError
      Backslash character is in the path.
    ValueError
      path starts with "." and hidden objects are disabled.
    ValueError
      If path starts or ends with whitespace.
    ValueError
      If path contains newline characters.
    ValueError
      If path contains a "/" character.

    """
    if path == "" or path.isspace():
      raise ValueError("Object name cannot be blank.")

    if path[0].isspace() or path[-1].isspace():
      raise ValueError("Names cannot start or end with whitespace.")

    if "\\" in path:
      raise ValueError("Paths cannot contain \\ characters.")

    if "\n" in path:
      raise ValueError("Paths cannot contain newline characters.")

    if "/" in path:
      raise ValueError("Names cannot contain / characters.")

    if not self.allow_hidden_objects and path.startswith("."):
      raise ValueError(
        "Names cannot start with '.' if hidden objects are disabled.")

  def _valid_path(self, full_path):
    """Returns a tuple consisting of the container name and the object
    name for the passed full_path with any leading/trailing "/" or
    whitespace removed.

    Parameters
    ----------
    full_path : str
      Full path to the object. This includes all parent containers, along
      with an optional leading and trailing "/" character.

    Returns
    -------
    tuple
      Tuple containing two elements. The first is the container name and
      the second is the object name. This has leading and trailing "/"
      characters and whitespace removed.

    Raises
    ------
    ValueError
      If any path component is invalid, as specified by
      _check_path_component_validity.

    Notes
    -----
    The returned container name can be nested. For example, if full_path =
    "cad/lines/line1" then the return value would be:
    ("cad/lines", "line1")

    """
    full_path = full_path.strip()
    if full_path.startswith("/"):
      full_path = full_path[1:]

    if full_path.endswith("/"):
      full_path = full_path[:-1]
    full_path = full_path.split("/")

    for path in full_path:
      self._check_path_component_validity(path)

    if len(full_path) == 1:
      return ("", full_path[0])

    return ("/".join(full_path[:-1]), full_path[-1])

  @staticmethod
  def find_running_applications():
    """Return a list of applications that are candidates to be connected to.

    No checking is performed on the application to determine if it is suitable
    to connect to. For example, if the product is too old to support the SDK.

    Once you select which application is suitable then pass the result as the
    existing_mcpd parameter of the Project class's constructor.

    The list is ordered based on the creation time of the mcpd process with the
    latest time appearing first in the list.

    Returns
    -------
    list of ExistingMcpdInstance
      The list of candidate applications (host) that are running.

    Examples
    --------
    Finds the running applications and chooses the oldest one.

    >>> from mapteksdk.project import Project
    >>> applications = Project.find_running_applications()
    >>> project = Project(existing_mcpd=applications[-1])

    """
    return find_mdf_hosts(logging.getLogger('mapteksdk.project'))
