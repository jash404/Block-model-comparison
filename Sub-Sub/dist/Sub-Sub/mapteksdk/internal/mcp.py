"""Support for Master Control Program (MCP).

This is for lower bandwidth "message passing" for synchronisation purposes,
small volume data transfer and general communication.

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

import collections
import ctypes
import logging
import os
import subprocess
import psutil
from .options import ProjectOptions, McpdMode, ProjectOpenMode
from ..capi import Mcpd

# pylint: disable=missing-docstring
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-few-public-methods
MCPD_EXE = "mcpd.exe"
DEFAULT_LICENCE = "<xml>ViewOnlyLicence</xml>"

ExistingMcpdInstance = collections.namedtuple(
  'ExistingMcpdInstance', ('mcpd_process_id', 'bin_path', 'mcp_socket_path'))
ExistingMcpdInstance.mcpd_process_id.__doc__ = 'The process ID of the mcpd ' + \
  'process.'
ExistingMcpdInstance.bin_path.__doc__ = 'The path to the bin directory for ' + \
  'host application (the directory with mcpd.exe)'
ExistingMcpdInstance.mcp_socket_path.__doc__ = 'The path to MCP socket file'

class McpdDisconnectError(Exception):
  """Error raised when disconnecting from the MCP."""

class McpdConnection:
  """Calls the processes required to connect to an active instance of an
  MDF application or mcpd executable.

  Parameters
  ----------
  options : ProjectOptions
    Set of options to specify the
    settings used to connect to a data backend
    and/or host application.
  specific_mcpd : ExistingMcpdInstance or None
    By using find_mdf_hosts() you can find out if multiple applications are
    running. It provides the connection details for them. From there,
    you can select one of the items in the list to choose which mcpd to
    connect to.
  mdf_licence : str
    Licence string to use for mcpd connection.
    A generic default will be used that relies on host application licensing
    to operate.
  mcpd_licence : str
    Licence string for the mcpd itself. This is used when creating a new mcpd.
    The standard behaviour for the mcpd is to require the MDF140 feature code,
    as clients connecting to it will connect using that feature code.

  See Also
  --------
  find_mdf_hosts : Finds applications to connect to.

  """
  def __init__(self, options, specific_mcpd=None, mdf_licence=None,
               mcpd_licence=None):
    self.log = logging.getLogger("mapteksdk.internal.mcp")
    self.options = options
    self.is_connected = False
    if specific_mcpd is None:
      self.mcp_dict = {'PRODUCT_LOCATION_INFO': None,
                       'MCP_PATH': None,
                       'PID': None}
      self.pid = -1
      self.socket_path = None
    else:
      self.mcp_dict = {'PRODUCT_LOCATION_INFO': specific_mcpd[1],
                       'MCP_PATH': specific_mcpd[2],
                       'PID': specific_mcpd[0]}
      self.pid = self.mcp_dict['PID']
      self.socket_path = self.mcp_dict['MCP_PATH']
    # :NOTE: additional requirements when finished running in test_mode:
    # call mcpd().UnlockSocketFile with the socket mutex handle
    self.socket_mutex_handle = None
    # use the stored process id to kill the spawned mpcd.exe
    # before unlocking mutex
    self.spawned_mcpd = None
    self.licence = mdf_licence
    if self.licence is None:
      self.licence = DEFAULT_LICENCE
    if isinstance(self.options, ProjectOptions) and \
      self.options.mcpd_mode == McpdMode.CREATE_NEW:
      self.is_connected = self.__connect_to_mcp_testmode(mcpd_licence)
    elif isinstance(self.options, ProjectOptions) and \
      self.options.open_mode == ProjectOpenMode.MEMORY_ONLY:
      self.is_connected = True
      self.log.info("Skip MCPD connection: memory only project selected")
      # Configure dll search paths without connecting to mcp
      self.preload_dlls()
    else:
      self.is_connected = self.connect_to_mcp("python")
    self.all_callbacks = []

  def register_server(self, servername):
    """Register MDF servers with mcpd.

    Parameters
    ----------
    servername : string
      Name of server without .exe, case sensitive.
      E.g. 'backendServer' or 'viewerServer'.

    Returns
    --------
    bool
      True if successful, False if failed.

    """
    # pylint: disable=no-self-use
    return Mcpd().RegisterServer(('server ' + servername).encode('utf-8'))

  def unload_mcp(self):
    """Unload the instance (if any) of mcpd.exe spawned from this class
    instance and remove socket file locks that were created by this instance.

    Raises
    ------
    McpdDisconnectError
      If unloading the MCP fails.

    """
    self.log.info("unload_mcp() called")
    if not isinstance(self.options, ProjectOptions) or \
      (isinstance(self.options, ProjectOptions) and \
      self.options.open_mode != ProjectOpenMode.MEMORY_ONLY):
      Mcpd().Disconnect()
    if self.spawned_mcpd is not None:
      pid_to_kill = self.spawned_mcpd.pid
      self.log.info("Closing down process ID: %s", pid_to_kill)
      try:
        self.spawned_mcpd.terminate()
        # Wait for the spawned mcp to exit. Otherwise the mcp process will be
        # kept alive until the calling process exits, waiting for the calling
        # process to read the return code.
        self.spawned_mcpd.wait()
      except Exception as original_error:
        error = McpdDisconnectError("Error unloading mcpd.exe")
        self.log.info(error)
        raise error from original_error
    # remove any socket locks created for this instance
    if self.socket_mutex_handle is not None:
      self.log.info("Unlocking socket: %s", self.socket_path)
      try:
        Mcpd().UnlockSocketFile(self.socket_mutex_handle)
      except Exception as original_error:
        error = McpdDisconnectError("Error unlocking socket file")
        self.log.info(error)
        raise error from original_error
      self.socket_mutex_handle = None

  def preload_dlls(self):
    """Pre-loads boost dlls to prevent conflicts with running instances
    of Vulcan (Win Error 127).

    """
    exist_mcp_defined = (not self.mcp_dict['PRODUCT_LOCATION_INFO'] is None \
      and not self.mcp_dict['MCP_PATH'] is None \
      and not self.mcp_dict['PID'] is None)
    if isinstance(self.options, ProjectOptions) and \
         (self.options.mcpd_mode == McpdMode.CREATE_NEW or \
         self.options.open_mode == ProjectOpenMode.MEMORY_ONLY):
      product_location_info = self.options.dll_path
      mcp_path = self.options.mcpd_path + "\\" + MCPD_EXE
      pid = -1
      exist_mcp_defined = False
    else:
      if not exist_mcp_defined:
        # Get last started mcpd host automatically
        mcpd_hosts = find_mdf_hosts(self.log)
        pid, product_location_info, mcp_path = mcpd_hosts[0]

    if not exist_mcp_defined:
      self.mcp_dict = {'PRODUCT_LOCATION_INFO': product_location_info,
                       'MCP_PATH': mcp_path,
                       'PID': pid}
    if not hasattr(os, "add_dll_directory"):
      self.log.debug("Loading dlls from %s", \
      self.mcp_dict['PRODUCT_LOCATION_INFO'])
      # This must be done to allow dlls in folder to be loaded with ctypes.CDLL
      os.environ['PATH'] = self.mcp_dict['PRODUCT_LOCATION_INFO'] + ';' \
        + os.environ['PATH']

    def preload_dll(dll):
      """Function for preloading a boost DLL. It first attempts to find
      the DLL at the bin path. If that fails, it attempts to find the DLL
      at the alternate path for debug environments.

      If a DLL is not found it is assumed that it must not be needed by
      the application and no error is raised.

      Parameters
      ----------
      dll : string
        Name of the DLL to load.

      """
      try:
        dll_path = os.path.join(self.mcp_dict['PRODUCT_LOCATION_INFO'], dll)
        dll = ctypes.CDLL(dll_path)
        return
      except OSError:
        pass

      try:
        debug_path = os.path.join(self.mcp_dict['PRODUCT_LOCATION_INFO'], "..",
                                  "shlib")
        debug_path = os.path.abspath(debug_path)
        dll_path = os.path.join(debug_path, dll)
        dll = ctypes.CDLL(dll_path)
        return
      except OSError:
        pass

    # :NOTE:
    # Fixes dll error on import (Win Error 127) conflicting dll's with Vulcan
    preloaded_dll_list = ["boost_regex.dll",
                          "boost_system.dll",
                          "boost_chrono.dll",
                          "boost_date_time.dll",
                          # boost_date_time is only needed for backwards
                          # compatability with PointStudio 2021 and earlier.
                          "boost_program_options.dll",
                          "boost_thread.dll",
                          "boost_locale.dll",
                          "MeshDll.dll"]

    for dll in preloaded_dll_list:
      preload_dll(dll)

  def run_timer(self, callback, period):
    def callbk(message):
      try:
        next(callback)
      except StopIteration:
        Mcpd().RemoveCallback(self.all_callbacks[0]["handle"])
        self.all_callbacks.pop()
        self.log.debug("McpRemoveCallback")

    cwrap = Mcpd().timer_callback_prototype(callbk)
    handle = Mcpd().AddCallbackOnTimer(period, 10000000, cwrap)
    self.all_callbacks.append({"func":cwrap, "handle":handle})

  def main_loop(self):
    # pylint: disable=no-self-use
    Mcpd().ServiceEvents()

  def connect_to_mcp(self, name):
    """Automatically connect to a running mcpd if there is one (last opened).

    Parameters
    ------------
    name : str
      The name to use for registering with the mcpd.

    Returns
    -----------
    bool
      True if successfully connected.

    """
    self.preload_dlls()
    self.pid = self.mcp_dict['PID']
    self.socket_path = self.mcp_dict['MCP_PATH']
    self.log.info("Connect to mcpd: %s", self.socket_path)
    self.is_connected = Mcpd().Connect(
      self.socket_path.encode('utf-8'),
      name.encode('utf-8'),
      self.licence.encode('utf-8'))
    self.log.info("MCP connected? %r, PID: %i", self.is_connected, self.pid)
    return self.is_connected

  def __connect_to_mcp_testmode(self, mcpd_licence):
    """Spawn own mcp process to conduct unit tests or prototype design
    against, without a host MDF application present.

    Returns
    -----------
    bool
      True if successfully connected.

    Notes
    -----
    Assumes self.options (ProjectOptions) exists.

    """

    mcpd_licence = mcpd_licence or DEFAULT_LICENCE

    self.preload_dlls()
    os.environ['MDF_BIN'] = self.options.mcpd_path
    os.environ['MDF_SHLIB'] = self.options.dll_path
    os.environ['MDF_ACTIVE_PACKAGE'] = self.licence
    os.environ['MDF_EXTEND_LICENCE_STRING'] = self.licence
    os.environ['PATH'] = self.options.dll_path + ';' + \
      self.options.mcpd_path + ";" + os.environ['PATH']

    try:
      # create and lock new socket file
      buf_size = 511 #512-1
      str_buffer = ctypes.create_string_buffer(buf_size)
      self.socket_mutex_handle = Mcpd().NewSocketFile(str_buffer,
                                                      buf_size)
      self.socket_path = str_buffer.value.decode("utf-8")

      # Set-up the environment for the new process.
      mcpd_environment = os.environ.copy()
      mcpd_environment['MDF_MCP_SOCKET'] = self.socket_path

      # Licences come as either XML or JSON where XML is used for the
      # floating licence server and the latter for Maptek Account. This
      # is a simple check to determine which is used.
      if mcpd_licence.startswith('<'):
        mcpd_environment['MDF_ACTIVE_PACKAGE'] = mcpd_licence
        mcpd_environment.pop('MDF_ACTIVE_PACKAGE')
      else:
        mcpd_environment['MDF_ACTIVE_LICENCE_SET'] = mcpd_licence
        mcpd_environment.pop('MDF_ACTIVE_PACKAGE')

      self.spawned_mcpd = subprocess.Popen(
        os.path.join(self.options.mcpd_path, MCPD_EXE),
        env=mcpd_environment)
      self.log.info("Connect to spawned mcpd..")
      self.pid = self.spawned_mcpd.pid
      self.is_connected = Mcpd().Connect(self.socket_path.encode('utf-8'),
                                         "test".encode('utf-8'),
                                         self.licence.encode('utf-8'))

      self.log.info("MCP connected? %r, PID: %i", self.is_connected,
                    self.pid)
    except OSError as os_error:
      self.log.error("Unable to load the MCP or UI dll")
      self.log.error(os_error)
      return False
    return self.is_connected

def find_ps_by_exe(exe_name=MCPD_EXE):
  """Find running processes by file name.

  Parameters
  ----------
  exe_name : str
    Name of process (defaults to MCPD_EXE).

  Returns
  -------
    List
      Processes with given name, ordered descending by start time.

  """
  results = [proc for proc in psutil.process_iter() if proc.name() == exe_name]
  # sort by process start time
  results = sorted(results, key=psutil.Process.create_time, reverse=True)
  return results

def find_mdf_hosts(logger=None):
  """Searches for running mcpd.exe processes to try and best determine
  which application to connect to and where to find its DLLs.

  Parameters
  ----------
  logger : logging.Logger
    The logger for writing messages.
    If None then no logging is performed.

  Returns
  -------
  list of ExistingMcpdInstance
    The list of candidate hosts (mcpd) that are running.

  Raises
  ------
  EnvironmentError
    No host applications found running to connect to.
  """
  # Locate running mcpd.exe list ordered by start time (descending)
  mcpd_processes = find_ps_by_exe(MCPD_EXE)

  results = []
  for process in mcpd_processes:
    bin_path = os.path.dirname(process.exe())
    pid = process.pid

    closest_mcp_file = process.environ().get('MDF_MCP_SOCKET', '')
    if logger:
      if closest_mcp_file:
        logger.debug(
          'Found MCP socket file (%s) used by process %d', closest_mcp_file,
          pid)
      else:
        logger.warning(
          'Unable to find the MCP socket file used by process %d',
          pid)

    if closest_mcp_file:
      results.append(ExistingMcpdInstance(pid, bin_path, closest_mcp_file))

  if not results:
    error_message = "No host applications found running to connect to."
    if logger is not None:
      logger.error(error_message)
    raise EnvironmentError(error_message)

  return results
