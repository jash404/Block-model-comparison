"""General operations which work with multiple applications."""
###############################################################################
#
# (C) Copyright 2021, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import csv
import ctypes
import enum
import numpy

from mapteksdk.internal.transaction import (request_transaction,
                                            RequestTransactionWithInputs,
                                            QualifierSet,
                                            Qualifiers,
                                            TransactionRequest)
from mapteksdk.view import ViewController
from mapteksdk.capi import Mcpd
from mapteksdk.data.objectid import ObjectID
from mapteksdk.workflows import WorkflowSelection


class TooOldForOperation(Exception):
  """Error raised when you attempt to use an operation that isn't supported
  by the current version of the application."""

  def __init__(self, minimum_version, current_version):
    Exception.__init__(
      self,
      f'Application is too old ({current_version}) to support this operation.'
      f' Requires newer version ({minimum_version}).')
    self.minimum_version = minimum_version
    self.current_version = current_version


class PickFailedError(ValueError):
  """Error raised when a pick operation fails."""
  def __init__(self, pick_type):
    super().__init__(f"{pick_type} pick operation was cancelled or failed.")


class SelectablePrimitiveType(enum.Enum):
  """Enum representing the selectable primitive types.

  Warning
  -------
  Block selections are impossible in PointStudio even when block objects
  are loaded into the view.

  """
  POINT = 1
  EDGE = 2
  FACET = 3
  # TETRA = 4
  CELL = 5
  BLOCK = 6


class Primitive:
  """Class which can uniquely identify a selected primitive.
  Includes the object the primitive exists in, the type of the primitive
  and the index of that primitive in the object.

  Parameters
  ----------
  path : str
    The path to the object containing the primitive.
  primitive_type : SelectablePrimitiveType
    The type of primitive selected.
  index : int
    Index of the selected primitive in the object.

  """
  def __init__(self, path, primitive_type, index):
    if not isinstance(primitive_type, SelectablePrimitiveType):
      raise TypeError("Primitive type must be SelectablePrimitiveType, "
                      f"not {type(primitive_type)}")

    self.__path = path
    self.__primitive_type = primitive_type
    self.__index = index

  def __str__(self):
    return (f"Object: '{self.__path}' {self.__primitive_type.name} at "
            f"index: {self.__index}")

  @property
  def path(self):
    """Path to the object containing the selected primitive."""
    return self.__path

  @property
  def primitive_type(self):
    """The type of primitive which was selected."""
    return self.__primitive_type

  @property
  def index(self):
    """The index of the selected primitive in the primitive array."""
    return self.__index


def open_new_view(objects=None, wait=True):
  """Open a new view window in the current application.

  This is only suitable for use by the Python SDK When connecting to an
  existing Maptek application.

  Using the Python SDK to develop an application which creates an Maptek
  Viewer within it requires special handling to set-up that isn't provided
  by this function.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Parameters
  ----------
  objects : list
    The list of objects to include in the new view.

  wait : bool
    If True then the function waits until the view has been opened and
    is considered complete before returning and will return the ObjectID of
    the newly created view. Otherwise it won't wait and it will return
    immediately with no result.

  Returns
  -------
  ViewController
    The view controller for the newly created view if wait is True.
  None
    If wait is False.

  Raises
  ------
  TooOldForOperation
    If the application does not have the necessary support for this operation.
  """
  if Mcpd().version < (1, 2):
    raise TooOldForOperation((1, 2), Mcpd().version)

  if objects is None:
    objects = []

  if objects:
    requester_icon = 'ViewSelection'
    inputs = [
      ('selection', RequestTransactionWithInputs.format_selection(objects)),
    ]
  else:
    requester_icon = 'ViewNew'
    inputs = []

  outputs = request_transaction(
    server='uiServer',
    transaction='mdf::uiS_NewViewTransaction',
    command_name='Maptek.Core.Window.Commands.New View',
    inputs=inputs,
    requester_icon=requester_icon,
    wait=wait,
  )

  if wait:
    for output in outputs.value:
      if output['idPath'] == 'viewId':
        value = output.get('value', '')
        if value:
          return ViewController(WorkflowSelection(value).ids[0])

  return None


def opened_views():
  """Return the list of opened views in the current application.

  This does not include embedded views in panels.

  This is only suitable for use by the Python SDK when connecting to an
  existing Maptek application.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Returns
  -------
  list
    A list containing the ViewController for each of the opened views.
    If there are no opened views this list will be empty.

  Raises
  ------
  TooOldForOperation
    If the application does not have the necessary support for this operation.

  Example
  -------
  Print out the list of active views.

  >>> from mapteksdk.project import Project
  >>> import mapteksdk.operations as operations
  >>> project = Project()
  >>> print('Open views:')
  >>> for view in operations.opened_views():
  >>>     print(view.server_name, view.window_title)
  """

  if Mcpd().version < (1, 2):
    raise TooOldForOperation((1, 2), Mcpd().version)

  outputs = request_transaction(
    server='uiServer',
    transaction='mdf::uiS_ListViewsTransaction',
    command_name='Maptek.Core.Window.Commands.List Views',
    inputs=[],
    requester_icon='ListViews',
  )

  selection = _decode_selection(outputs).ids
  return [ViewController(view_id) for view_id in selection]


def active_view():
  """Return the active view of the current application otherwise None if there
  is no active view

  This is only suitable for use by the Python SDK when connecting to an
  existing Maptek application.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Returns
  -------
  ViewController
    The view controller for the active view
  None
    If there was no active view.

  Raises
  ------
  TooOldForOperation
    If the application does not have the necessary support for this operation.

  Example
  -------
  Query the active view

  >>> from mapteksdk.project import Project
  >>> import mapteksdk.operations as operations
  >>> project = Project()
  >>> view = operations.active_view()
  >>> if view:
  >>>    print(f"The active view is: {view}")
  >>> else:
  >>>     print("There is no active view.")
  """

  if Mcpd().version < (1, 2):
    raise TooOldForOperation((1, 2), Mcpd().version)

  outputs = request_transaction(
    server='uiServer',
    transaction='mdf::uiS_ListViewsTransaction',
    command_name='Maptek.Core.Window.Commands.List Views',
    inputs=[],
    requester_icon='ActiveView',
  )

  for output in outputs.value:
    if output['idPath'] == 'viewId':
      value = output.get('value', 'OID(I0, C0, T0)')
      if value == 'OID(I0, C0, T0)':
        return None
      return ViewController(WorkflowSelection(value).ids[0])

  # There was no active view.
  return None


def active_view_or_new_view():
  """Return the active view of the current application or opens a new view if
  there is none.

  This is only suitable for use by the Python SDK when connecting to an
  existing Maptek application.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Returns
  -------
  ViewController
    The view controller for the active view or new view.
  None
    If it was unable to determine the active view or create a new view.

  Raises
  ------
  TooOldForOperation
    If the application does not have the necessary support for this operation.

  Example
  -------
  Query the active view or create a new view if there is no active view.

  >>> from mapteksdk.project import Project
  >>> import mapteksdk.operations as operations
  >>> project = Project()
  >>> view = operations.active_view_or_new_view()
  """

  if Mcpd().version < (1, 2):
    raise TooOldForOperation((1, 2), Mcpd().version)

  outputs = request_transaction(
    server='uiServer',
    transaction='mdf::uiS_GetActiveOrNewViewTransaction',
    command_name='Maptek.Core.Window.Commands.Get Active/New View',
    inputs=[],
    requester_icon='ActiveView',
  )

  for output in outputs.value:
    if output['idPath'] == 'viewId':
      view = WorkflowSelection(output.get('value', '')).ids[0]
      return ViewController(view)

  # Unable to find the active view or create a new view.
  return None


def coordinate_pick(*,
    label="",
    support_label="",
    help_text=""):
  """Requests for the user to select a coordinate in the software.

  This will wait for the user to select a coordinate and then returns the
  point.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Parameters
  ----------
  label : str
    The label to show for the coordinate pick. This is shown in the status
    bar to the left of the X, Y and Z coordinates of the selected point.
    Default is "Select a coordinate". The default may be translated to the
    user's selected language within the application.

  support_label : str
    The support label to display in a yellow box at the top of the view.
    Default is "Select a coordinate". The default may be translated to the
    user's selected language within the application.
    If label is specified and this is not, this will default to label.

  help_text : str
    Text to display when the mouse hovers over the status bar during the
    coordinate pick option.
    Default is: "Select a coordinate for the running Python Script".
    The default may be translated to the user's selected language within the
    application.

  Returns
  -------
  ndarray
    A ndarray with shape (3,) representing the selected coordinate.

  Raises
  ------
  TooOldForOperation
    If the application does not have the necessary support for this operation.
  PickFailedError
    If the pick operation is cancelled or fails.

  Notes
  -----
  A coordinate pick allows the user to pick any coordinate and thus the
  coordinate may not be a part of any object. If the selected coordinate
  must be a coordinate on an object, use primitive pick instead.

  Examples
  --------
  Request for the user to select two points in the running application and
  then calculates the distance between those two points. The selected points
  and the distance is displayed in the report window. When picking the first
  point, the message in the bottom corner of the screen will be:
  "Pick the first point". For the second point it will be:
  "Pick the second point".

  >>> import numpy as np
  >>> from mapteksdk.operations import (coordinate_pick, write_report)
  >>> from mapteksdk.project import Project
  >>> project = Project()
  >>> start = coordinate_pick(label="Pick the first point.")
  >>> end = coordinate_pick(label="Pick the second point.")
  >>> difference = start - end
  >>> distance = np.linalg.norm(difference)
  >>> write_report(f"Distance between points",
  ...              f"The distance between {start} and {end} is {distance}")

  """
  if Mcpd().version < (1, 3):
    raise TooOldForOperation((1, 3), Mcpd().version)

  if label != "" and support_label == "":
    support_label = label

  inputs = [("source", "Python Script"), ("label", label),
            ("supportLabel", support_label), ("help", help_text),]

  print("Select a point in the running application.")
  outputs = request_transaction(
    server="cadServer",
    transaction="mtp::cadS_CoordinatePickWithLabelsTransaction",
    command_name="",
    inputs=inputs,
    wait=True,
    confirm_immediately=True)

  for output in outputs.value:
    if output["idPath"] == "coordinate":
      try:
        result = output.get("value")
      except KeyError as error:
        raise PickFailedError("Coordinate") from error

      try:
        return numpy.array(result.strip("()").split(","),
                           dtype=ctypes.c_double)
      except ValueError as error:
        raise PickFailedError("Coordinate") from error
  raise PickFailedError("Coordinate")


def object_pick(*,
    label="",
    support_label="",
    help_text=""):
  """Requests for the user to select an object in the software.

  This will wait for the user to select an object and then returns it.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Parameters
  ----------
  label : str
    The label to show for the object pick. This is shown in the status
    bar.
    Default is "Select a object". The default may be translated to the user's
    selected language within the application.

  support_label : str
    The support label to display in a yellow box at the top of the view.
    Default is "Select a object". The default may be translated to the user's
    selected language within the application.
    If label is specified and this is not, this will default to label.

  help_text : str
    Text to display when the mouse hovers over the status bar during the
    object pick option.
    Default is: "Select a object for the running Python Script".
    The default may be translated to the user's selected language within the
    application.

  Returns
  -------
  ObjectID
    Object ID of the selected object. This may be a null object id.

  Raises
  ------
  TooOldForOperation
    If the application does not have the necessary support for this operation.
  PickFailedError
    If the pick operation is cancelled or fails.

  Examples
  --------
  Ask for the user to select an object in the running application. A
  report is added to the report window containing the type of the
  selected object.

  >>> from mapteksdk.operations import object_pick, write_report
  >>> from mapteksdk.project import Project
  >>> project = Project()
  >>> oid = object_pick(label="Query object type",
  ...                   support_label="Select an object to query its type")
  >>> write_report("Query type", f"{oid.path} is a {oid.type_name}")

  """
  if Mcpd().version < (1, 3):
    raise TooOldForOperation((1, 3), Mcpd().version)

  if label != "" and support_label == "":
    support_label = label

  inputs = [("source", "Python Script"), ("label", label),
            ("supportLabel", support_label), ("help", help_text),]

  print("Select an object in the running application.")
  outputs = request_transaction(
    server="cadServer",
    transaction="mtp::cadS_ObjectPickWithLabelsTransaction",
    command_name="",
    inputs=inputs,
    wait=True,
    confirm_immediately=True)

  for output in outputs.value:
    if output["idPath"] == "object":
      try:
        value = output.get("value")
        # Blank value indicates the pick operation was cancelled.
        if value == "":
          raise PickFailedError("Object")
        return ObjectID.from_path(value)
      except KeyError as error:
        raise PickFailedError("Object") from error
  raise PickFailedError("Object")


def primitive_pick(
    primitive_type=SelectablePrimitiveType.POINT,
    *,
    label="",
    support_label="",
    help_text=""):
  """Requests for the user to select a primitive of the specified type
  in the software.

  This will wait for the user to select a primitive and returns it.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Parameters
  ----------
  primitive_type : SelectablePrimitiveType
    The type of Primitive the user will be asked to select.

  label : str
    The label to show for the primitive pick. This is shown in the status
    bar.
    Default is "Select a primitive". The default may be translated to the user's
    selected language within the application.

  support_label : str
    The support label to display in a yellow box at the top of the view.
    Default is "Select a primitive". The default may be translated to the
    user's selected language within the application.
    If label is specified and this is not, this will default to label.

  help_text : str
    Text to display when the mouse hovers over the status bar during the
    primitive pick option.
    Default is: "Select a primitive for the running Python Script".
    The default may be translated to the user's selected language within the
    application.

  Returns
  -------
  Primitive
    Object representing the selected primitive.

  Raises
  ------
  TooOldForOperation
    If the application does not have the necessary support for this operation.
  PickFailedError
    If the pick operation is cancelled or fails.

  Examples
  --------
  Request for the user to pick a point and then displays a report
  containing the coordinate of the selected point.

  >>> from mapteksdk.operations import (primitive_pick,
  ...                                   SelectablePrimitiveType,
  ...                                   write_report)
  >>> from mapteksdk.project import Project
  >>> project = Project()
  >>> primitive = primitive_pick(SelectablePrimitiveType.POINT)
  >>> with project.read(primitive.path) as read_object:
  ... write_report("Selected point", str(read_object.points[primitive.index]))

  Request for the user to pick an edge then displays a report containing the
  points the selected edge connects.

  >>> from mapteksdk.operations import (primitive_pick,
  ...                                   SelectablePrimitiveType,
  ...                                   write_report)
  >>> from mapteksdk.project import Project
  >>> project = Project()
  >>> primitive = primitive_pick(SelectablePrimitiveType.EDGE)
  >>> with project.read(primitive.path) as read_object:
  ...     edge = read_object.edges[primitive.index]
  ...     start = read_object.points[edge[0]]
  ...     end = read_object.points[edge[1]]
  ...     write_report("Selected Edge", f"{start} to {end}")

  """
  if Mcpd().version < (1, 3):
    raise TooOldForOperation((1, 3), Mcpd().version)

  if label != "" and support_label == "":
    support_label = label

  inputs = [("source", "Python Script"), ("label", label),
            ("supportLabel", support_label), ("help", help_text),
            ("primitiveType", str(primitive_type.value))]

  print(f"Select a {primitive_type.name} in the running application.")
  outputs = request_transaction(
    server="cadServer",
    transaction="mtp::cadS_PrimitivePickWithLabelsTransaction",
    command_name="",
    inputs=inputs,
    wait=True,
    confirm_immediately=True)

  for output in outputs.value:
    if output["idPath"] == "primitive":
      try:
        result = output.get("value")
      except KeyError as error:
        raise PickFailedError(primitive_type.name) from error

      try:
        # Format is: path,primitive_type_id,index.
        # Use csv reader to read as it will handle paths containing quoted
        # commas.
        result = list(csv.reader([result]))[0]
        type_id = SelectablePrimitiveType(int(result[1]))
        index = int(result[2])
        return Primitive(result[0], type_id, index)
      except IndexError as error:
        # This will occur if the pick is cancelled.
        raise PickFailedError(primitive_type.name) from error
  raise PickFailedError(primitive_type.name)


def write_report(label, message):
  """Write a report to the report window of the application.

  Supported by PointStudio 2021.1, Vulcan GeologyCore 2021 and higher.

  Parameters
  ----------
  label : str
    The label to show on the report.
  message : str
    The message to include in the report. This is essentially the body of the
    report itself.

  Example
  -------
  Write out a simple report

  >>> from mapteksdk.project import Project
  >>> import mapteksdk.operations as operations
  >>> project = Project()
  >>> operations.write_report(
  ...     'My Script', 'Completed filtering in 1.5 seconds')
  """
  request = TransactionRequest()
  request.transaction = 'mdf::uiC_Report'
  request.qualifiers = QualifierSet()

  if Mcpd().version <= (1, 3):
    title_qualifier = Qualifiers.label(label)
  else:
    title_qualifier = Qualifiers.title(label)

  request.qualifiers.values = [
    title_qualifier,
    Qualifiers.message(message),
    ]
  request.send(destination='appServer')

def _decode_selection(outputs):
  """Function for decoding the selection from the transaction output."""
  for output in outputs.value:
    if output['idPath'] == 'selection':
      selection_string = output.get('value', '')
      break
  else:
    selection_string = ''

  return WorkflowSelection(selection_string)
