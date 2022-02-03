"""Interface for the MDF system library.

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
from .util import singleton, declare_dll_functions, CApiDllLoadFailureError
from .wrapper_base import WrapperBase

@singleton
class System(WrapperBase):
  """System - wrapper for mdf_system.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.system")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_system
      self.log.debug("Loaded: mdf_system.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_system.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_system.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "System"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"SystemFlagInWorkbench" : (ctypes.c_void_p, None),
       "SystemSetApplicationInformation" : (ctypes.c_void_p, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ]),
       "SystemSetEtcPath" : (ctypes.c_void_p, [ctypes.c_char_p, ]),
       "SystemSetBinPath" : (ctypes.c_void_p, [ctypes.c_char_p, ]),
       "SystemNotifyEnvironmentChanged" : (ctypes.c_void_p, None),
       "SystemBanEnvironmentUse" : (ctypes.c_void_p, [ctypes.c_char_p, ]),
       "SystemAddToEnvironmentWhiteList" : (ctypes.c_void_p, [ctypes.c_char_p, ]),
       "SystemHostId" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "SystemLogFilePath" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "SystemApplicationLogFilePath" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "SystemBaseConfigurationDirectory" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "SystemApplicationVersionSuffix" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "SystemBranchVersion" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "SystemBuildId" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "SystemApplicationFeatureStrings" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),},
      # Functions changed in version 1.
      {}
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict
