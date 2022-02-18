"""Interface for the MDF selection library.

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
class Selection(WrapperBase):
  """Selection - wrapper for mdf_selection.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.selection")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_selection
      self.log.debug("Loaded: mdf_selection.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_selection.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_selection.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Selection"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"SelectionSaveGlobalSelection" : (T_ObjectHandle, None),
       "SelectionSetGlobalSelection" : (ctypes.c_void_p, [T_ObjectHandle, ]),
       "SelectionFreeSavedSelection" : (ctypes.c_void_p, [T_ObjectHandle, ]),},
      # Functions changed in version 1.
      {"SelectionCApiVersion" : (ctypes.c_uint32, None),
       "SelectionCApiMinorVersion" : (ctypes.c_uint32, None),}
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict
