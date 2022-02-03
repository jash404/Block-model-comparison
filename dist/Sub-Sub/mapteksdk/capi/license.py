"""Interface for the MDF license library.

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
class License(WrapperBase):
  """License - wrapper for mdf_license.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.license")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_license
      self.log.debug("Loaded: mdf_license.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_license.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_license.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Licence"

  def supported_licence_format(self):
    """Return string of the supported licence format."""
    supported_format_size = ctypes.c_uint32(10)
    supported_format = ctypes.create_string_buffer(supported_format_size.value)
    result = self.GetFormat(
      supported_format,
      ctypes.byref(supported_format_size))
    if result == -3:
      # The buffer was too small; try again with buffer of the correct size.
      supported_format = ctypes.create_string_buffer(supported_format_size.value)
      result = self.GetFormat(
        supported_format,
        ctypes.byref(supported_format_size))

    if result != 1:
      raise ValueError('Could not determine supported licence format.')

    return bytearray(supported_format.value).decode('utf-8')

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"LicenceGetFormat" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),
       "LicenceGetFormatOfLicenceString" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),
       "LicenceGetLicenceHostInformation" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),
       "LicenceSystemHostId" : (ctypes.c_int32, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "LicenceCheckLicence" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_bool, ]),
       "LicenceCheckLicenceAllProducts" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_bool, ]),
       "LicenceGetProductLicenceByFeatures" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),
       "LicenceGetFilePath" : (ctypes.c_uint32, [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ]),
       "LicenceGetDongles" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),
       "LicenceDongleHasRecordSpace" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ]),
       "LicenceGetDongleByName" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),
       "LicenceGetUninitialisedVulcanDongles" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),
       "LicenceInitialiseVulcanDongle" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint64, ]),
       "LicenceGetTpmId" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_bool), ]),
       "LicenceIsTpmHybrid" : (ctypes.c_int64, None),
       "LicenceTpmHasRecordSpace" : (ctypes.c_int64, [ctypes.c_uint32, ctypes.c_uint32, ]),
       "LicenceBorrowLicenceSet" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint64, ctypes.c_bool, ]),
       "LicenceReturnLicenceSet" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ]),
       "LicenceGetLastError" : (ctypes.c_int64, [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p), ]),
       "LicenceGetFeatures" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_uint64, ]),
       "LicenceRemoveExpiredTpmLicences" : (ctypes.c_int64, [ctypes.c_uint64, ]),
       "LicenceRemoveExpiredDongleLicences" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint64, ]),
       "LicenceGetHaspDriverVersion" : (ctypes.c_int64, [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ]),},
      # Functions changed in version 1.
      {"LicenceCApiVersion" : (ctypes.c_uint32, None),
       "LicenceCApiMinorVersion" : (ctypes.c_uint32, None),}
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict
