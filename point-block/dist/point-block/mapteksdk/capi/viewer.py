"""Interface for the MDF viewer library.

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
import enum
import logging
from .types import T_ObjectHandle
from .util import singleton, declare_dll_functions, CApiDllLoadFailureError
from .wrapper_base import WrapperBase


class ViewerErrorCodes(enum.IntEnum):
  """The "null" error code"""
  NO_ERROR = 0

  """A generic error has occurred. This means the error does not fit into a
  more specific category of error or simply does not make sense to try to
  distinguish from another. For example a developer error where the error
  is with calling the function.
  """
  GENERIC_ERROR = 1

  """The provided buffer for a string was too small."""
  STRING_BUFFER_TOO_SMALL = 2

  """The view no longer exists. This is often a sign the view has been closed.
  """
  VIEW_NO_LONGER_EXISTS = 3


@singleton
class Viewer(WrapperBase):
  """Viewer - wrapper for mdf_viewer.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.viewer")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_viewer
      self.log.debug("Loaded: mdf_viewer.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_viewer.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_viewer.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Viewer"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"ViewerInitialise" : (ctypes.c_void_p, None),
       "ViewerCreateNewViewObject" : (T_ObjectHandle, None),
       "ViewerCreateNewDynamicObject" : (T_ObjectHandle, [ctypes.c_char_p, ]),
       "ViewerGetServerName" : (ctypes.c_void_p, [T_ObjectHandle, ctypes.c_char_p, ctypes.c_uint64, ]),},
      # Functions changed in version 1.
      {"ViewerCApiVersion" : (ctypes.c_uint32, None),
       "ViewerCApiMinorVersion" : (ctypes.c_uint32, None),

       # The following were new in 1.3.
       "ViewerErrorCode" : (ctypes.c_uint32, None),
       "ViewerErrorMessage" : (ctypes.c_char_p, None),
      },
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict

  def ErrorCode(self):
    """Return the last known error code returned by the viewer library.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """

    if self.version < (1, 3):
      # Let us assume this was called when a function signaled that there was
      # an error.
      return ViewerErrorCodes.GENERIC_ERROR

    return ViewerErrorCodes(self.dll.ViewerErrorCode())

  def ErrorMessage(self):
    """Return the last known error message. This is specific to the viewer library.

    It is unspecified what this returns if there has been no error.
    """
    if self.version < (1, 3):
      return 'Unknown error - This application does not provide error information.'

    return self.dll.ViewerErrorMessage().decode('utf-8')
