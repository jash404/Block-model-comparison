"""Settings used for projects shared between multiple modules.

Currently these are shared between mcp and modelling

Warnings
--------
Vendors and clients should not develop scripts or applications against
this package. The contents may change at any time without warning.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
from enum import IntEnum

class McpdMode(IntEnum):
  """Mode for MCP connection - use host application or create own instance."""
  CONNECT_TO_EXISTING = 1
  CREATE_NEW = 2

class ProjectOpenMode(IntEnum):
  """Mode selection for opening a Project - open, create or open/create."""
  MEMORY_ONLY = 0
  OPEN_EXISTING = 1
  CREATE_NEW = 2
  OPEN_OR_CREATE = 3

class ProjectAccessMode(IntEnum):
  """Mode selection for Project access - read/write/try write then read."""
  READ_ONLY = 1
  READ_WRITE = 2
  TRY_WRITE = 3

class ProjectUnits(IntEnum):
  """Unit selection for a Project."""
  METRES = 1
  FEET = 2
  YARDS = 3

class ProjectBackendType(IntEnum):
  """Method of storage for backend database."""
  MAPTEK_DB = 4 # Sqlite (store as a .maptekdb)
  MAPTEK_OBJ = 5 # ObjectFile (store as a .maptekobj) Caution: Read only
  SHARED = 6 # Shared (share with existing locked Project)
  VULCAN_DGD_ISIS = 8 # VulcanDgdIsis (store in a .dgd.isis database)
  VULCAN_TEK_ISIS = 9 # VulcanTekIsis (store in a .tek.isis database)
  VULCAN_DIR = 10 # Vulcan (store in a Vulcan project directory)

class ProjectOptions:
  """Provide some options for how to setup the Project class.
  This is optional and only needed if trying to load a specific project
  and/or run automated tests.

  Parameters
  ----------
  project_path : str
    Path to maptekdb directory (new or existing, depending on open_mode).
  open_mode : ProjectOpenMode
    Method to use when opening a maptekdb database for operating within.
  access_mode : ProjectAccessMode
    Whether to access the database using read only, read/write, or attempt
    write then read on fail.
  backend_type : ProjectBackendType
    Method of storage for database.
  proj_units : ProjectUnits
    Unit selection for project.
  mcpd_mode : McpdMode
    Defines whether to attach to an existing application host such as Eureka
    or PointStudio, or otherwise launch a standalone mcpd.exe instance that
    doesn't rely on a host application to be running.
    Note: This is intended for unit testing purposes and requires special
    builds.
  mcpd_path : str
    Path to locate mcpd.exe process.
  dll_path : str
    Path to locate dlls and dependencies.
  allow_hidden_objects : bool
    Sets project attribute (of same name) for whether to allow the SDK to
    create objects that are hidden by applications (these objects start with
    a full stop in their name (e.g. '.hidden').
    Default is False.

  """
  def __init__(self,
               project_path,
               open_mode=ProjectOpenMode.OPEN_OR_CREATE,
               access_mode=ProjectAccessMode.READ_WRITE,
               backend_type=ProjectBackendType.MAPTEK_DB,
               proj_units=ProjectUnits.METRES,
               mcpd_mode=McpdMode.CONNECT_TO_EXISTING,
               mcpd_path=None,
               dll_path=None,
               allow_hidden_objects=False):
    self.project_path = project_path
    self.open_mode = open_mode
    self.access_mode = access_mode
    self.backend_type = backend_type
    self.proj_units = proj_units
    self.mcpd_mode = mcpd_mode
    self.mcpd_path = mcpd_path
    self.dll_path = dll_path
    self.account_broker_connector_path = None
    self.account_broker_session_parameters = None
    self.allow_hidden_objects = allow_hidden_objects
    if self.mcpd_mode == McpdMode.CREATE_NEW:
      if self.mcpd_path is None or self.dll_path is None:
        raise FileNotFoundError("No path provided to locate mcpd executable"
                                " and/or dependencies")
