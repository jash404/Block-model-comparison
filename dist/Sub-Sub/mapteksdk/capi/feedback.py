"""Interface for the MDF feedback library.

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
from .types import T_ReadHandle
from .util import singleton, declare_dll_functions, CApiDllLoadFailureError
from .wrapper_base import WrapperBase

@singleton
class Feedback(WrapperBase):
  """Feedback - wrapper for mdf_feedback.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.feedback")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_feedback
      self.log.debug("Loaded: mdf_feedback.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_feedback.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_feedback.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Feedback"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"FeedbackPrepareReport" : (ctypes.POINTER(T_ReadHandle), [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_uint32, ]),
       "FeedbackSendReport" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ]),
       "FeedbackSaveAsZip" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "FeedbackCancelReport" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "FeedbackTakeScreenshotAndAppend" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),},
      # Functions changed in version 1.
      {"FeedbackCApiVersion" : (ctypes.c_uint32, None),
       "FeedbackCApiMinorVersion" : (ctypes.c_uint32, None),}
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict
