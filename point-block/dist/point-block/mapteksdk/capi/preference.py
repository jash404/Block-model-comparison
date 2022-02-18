"""Interface for the MDF preference library.

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
class Preference(WrapperBase):
  """Preference - wrapper for mdf_preference.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.preference")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_preference
      self.log.debug("Loaded: mdf_preference.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_preference.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_preference.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Preference"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"PreferenceResetToDefaults" : (ctypes.c_void_p, None),
       "PreferenceCategoryCount" : (ctypes.c_uint32, None),
       "PreferenceGetCategoryName" : (ctypes.c_void_p, [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint64, ]),
       "PreferenceGetCategoryEntryCount" : (ctypes.c_uint32, [ctypes.c_uint32, ]),
       "PreferenceGetEntryName" : (ctypes.c_void_p, [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint64, ]),
       "PreferenceIsBoolean" : (ctypes.c_bool, [ctypes.c_uint32, ctypes.c_uint32, ]),
       "PreferenceGetPreferenceBool" : (ctypes.c_bool, [ctypes.c_uint32, ctypes.c_uint32, ]),
       "PreferenceGetPreferenceJson" : (ctypes.c_void_p, [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint64, ]),
       "PreferenceSetPreferenceBool" : (ctypes.c_void_p, [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_bool, ]),
       "PreferenceSetPreferenceJson" : (ctypes.c_void_p, [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_char_p, ]),},
      # Functions changed in version 1.
      {"PreferenceCApiVersion" : (ctypes.c_uint32, None),
       "PreferenceCApiMinorVersion" : (ctypes.c_uint32, None),}
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict
