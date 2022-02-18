"""Interface for the MDF MCP (Master Control Program) library.

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
from .types import T_SocketFileMutexHandle, \
 _Opaque, T_TextHandle, T_MessageHandle
from .util import singleton, declare_dll_functions, CApiDllLoadFailureError
from .wrapper_base import WrapperBase

@singleton
class Mcpd(WrapperBase):
  """Mcpd - wrapper for mdf_mcp.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.mcp")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_mcp
      self.log.debug("Loaded: mdf_mcp.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_mcp.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_mcp.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

      # Manually created wrapper functions.
      self.dll.Callback = ctypes.CFUNCTYPE(None, ctypes.POINTER(_Opaque))
      self.timer_callback_prototype = ctypes.CFUNCTYPE(None, ctypes.POINTER(_Opaque))
      try:
        self.dll.McpAddCallbackOnTimer.argtypes = [
          ctypes.c_double,
          ctypes.c_uint64,
          self.timer_callback_prototype]
        self.dll.McpAddCallbackOnMessage.restype = ctypes.c_void_p
        self.dll.McpAddCallbackOnMessage.argtypes = [
          ctypes.c_char_p,
          self.dll.Callback]
        self.dll.McpAddCallbackOnTimer.restype = ctypes.POINTER(_Opaque)
        self.dll.McpServiceEvents.restype = None
        self.dll.McpRemoveCallback.restype = None
        self.dll.McpRemoveCallback.argtypes = [ctypes.c_void_p]
      except:
        self.log.error("Failed to properly load MCP dll")
        raise

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Mcp"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"McpConnect" : (ctypes.c_bool, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ]),
       "McpDisconnect" : (ctypes.c_void_p, None),
       "McpIsConnected" : (ctypes.c_bool, None),
       "McpSoftShutdown" : (ctypes.c_void_p, None),
       "McpForceShutdown" : (ctypes.c_void_p, None),
       "McpSetKillable" : (ctypes.c_void_p, [ctypes.c_bool, ]),
       "McpRegisterServer" : (ctypes.c_bool, [ctypes.c_char_p, ]),
       "McpNewServer" : (ctypes.c_bool, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32, ]),
       "McpNewSocketFile" : (T_SocketFileMutexHandle, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "McpUnlockSocketFile" : (ctypes.c_void_p, [T_SocketFileMutexHandle, ]),
       "McpNewMessage" : (T_MessageHandle, [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_bool, ]),
       "McpNewSubMessage" : (T_MessageHandle, None),
       "McpAppendBool" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_bool, ]),
       "McpAppendUInt" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_uint64, ctypes.c_uint8, ]),
       "McpAppendSInt" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_int64, ctypes.c_uint8, ]),
       "McpAppendDouble" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_double, ]),
       "McpAppendFloat" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_float, ]),
       "McpAppendTimeDouble" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_double, ]),
       "McpAppendString" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_char_p, ]),
       "McpAppendByteArray" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_void_p, ctypes.c_uint32, ]),
       "McpAppendText" : (ctypes.c_void_p, [T_MessageHandle, T_TextHandle, ]),
       "McpAppendSubMessage" : (ctypes.c_void_p, [T_MessageHandle, T_MessageHandle, ]),
       "McpSend" : (ctypes.c_void_p, [T_MessageHandle, ]),
       "McpSendAndGetResponseBlocking" : (T_MessageHandle, [T_MessageHandle, ]),
       "McpIsBool" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractBool" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpIsUInt" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractUInt" : (ctypes.c_uint64, [T_MessageHandle, ]),
       "McpIsFloat" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractFloat" : (ctypes.c_double, [T_MessageHandle, ]),
       "McpExtractTimeDouble" : (ctypes.c_double, [T_MessageHandle, ]),
       "McpIsSInt" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractSInt" : (ctypes.c_int64, [T_MessageHandle, ]),
       "McpIsString" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractString" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_char_p, ctypes.c_uint64, ]),
       "McpGetNextStringLength" : (ctypes.c_uint32, [T_MessageHandle, ]),
       "McpIsByteArray" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractByteArray" : (ctypes.c_void_p, [T_MessageHandle, ctypes.c_void_p, ctypes.c_uint64, ]),
       "McpGetNextByteArrayLength" : (ctypes.c_uint32, [T_MessageHandle, ]),
       "McpFreeMessage" : (ctypes.c_void_p, [T_MessageHandle, ]),
       "McpIsEom" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpIsSubMessage" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractSubMessage" : (T_MessageHandle, [T_MessageHandle, ]),
       "McpIsText" : (ctypes.c_bool, [T_MessageHandle, ]),
       "McpExtractText" : (T_TextHandle, [T_MessageHandle, ]),
       "McpIsSessionVariableSet" : (ctypes.c_bool, [ctypes.c_char_p, ]),
       "McpServiceEvents" : (ctypes.c_void_p, None),
       "McpServicePendingEvents" : (ctypes.c_void_p, None),
       "McpGetMessageSender" : (ctypes.c_uint64, [T_MessageHandle, ctypes.c_char_p, ctypes.c_uint64, ]),
       "McpGetMessageSenderAuthorisationName" : (ctypes.c_uint64, [T_MessageHandle, ctypes.c_char_p, ctypes.c_uint64, ]),
       "McpBeginReply" : (T_MessageHandle, [T_MessageHandle, ]),
       "McpAnyFutureEventMatches" : (ctypes.c_bool, [T_MessageHandle, ctypes.c_bool, ]),
       "McpCreateSubMessage" : (T_MessageHandle, [ctypes.c_void_p, ctypes.c_uint32, ]),
       "McpGetSubMessageData" : (ctypes.c_uint32, [T_MessageHandle, ctypes.c_void_p, ctypes.c_uint32, ]),
       "McpEnableCrashReporting" : (ctypes.c_void_p, [ctypes.c_bool, ]),
       "McpEmulateCrash" : (ctypes.c_void_p, None),
       "McpGetSystemInformation" : (ctypes.c_uint32, [ctypes.c_char_p, ]),
       "McpInitialiseTestPacketDeMunging" : (ctypes.c_void_p, None),},
      # Functions changed in version 1.
      {"McpCApiVersion" : (ctypes.c_uint32, None),
       "McpCApiMinorVersion" : (ctypes.c_uint32, None),}
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict
