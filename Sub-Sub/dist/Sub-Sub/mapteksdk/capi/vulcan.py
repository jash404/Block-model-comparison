"""Interface for the MDF vulcan library.

Warnings
--------
Vendors and clients should not develop scripts or applications against
this module. The contents may change at any time without warning.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

# pylint: disable=line-too-long
import ctypes
import logging
from .types import T_ObjectHandle
from .util import singleton, declare_dll_functions, CApiDllLoadFailureError
from .wrapper_base import WrapperBase

@singleton
class Vulcan(WrapperBase):
  """Vulcan - wrapper for mdf_vulcan.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.vulcan")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_vulcan
      self.log.debug("Loaded: mdf_vulcan.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_vulcan.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_vulcan.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      # It is theoretically faster to have a baked version of the supported
      # list of capi functions to use instead of generating it each time.
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Vulcan"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"VulcanErrorMessage" : (ctypes.c_char_p, []),
       "VulcanRead00tFile" : (T_ObjectHandle, [ctypes.c_char_p, ctypes.c_int32]),
       "VulcanWrite00tFile" : (ctypes.c_bool, [T_ObjectHandle, ctypes.c_char_p, ctypes.c_int32]),
       "VulcanReadBmfFile" : (T_ObjectHandle, [ctypes.c_char_p, ctypes.c_int32]),
       "VulcanWriteBmfFile" : (ctypes.c_bool, [T_ObjectHandle, ctypes.c_char_p, ctypes.c_int32]),},
      # Functions changed in version 1.
      {"VulcanCApiVersion" : (ctypes.c_uint32, None),
       "VulcanCApiMinorVersion" : (ctypes.c_uint32, None),}
    ]

    # Returns the changes made up to version.
    # EG: If version = 2 then returns:
    # [functions_changed_in_version[0],
    #  functions_changed_in_version[1],
    #  functions_changed_in_version[2]]
    # If functions_changed_in_version[3] exists, it would not
    # returned as the caller only requested version 2.
    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict
