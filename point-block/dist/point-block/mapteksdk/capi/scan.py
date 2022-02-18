"""Interface for the MDF scan library.

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
# pylint: disable=invalid-name
import ctypes
import logging
from .types import T_TypeIndex, T_ObjectHandle, T_ReadHandle
from .util import (singleton, declare_dll_functions, raise_if_version_too_old,
                   CApiDllLoadFailureError, CApiUnknownError)
from .wrapper_base import WrapperBase


@singleton
class Scan(WrapperBase):
  """Scan - wrapper for mdf_scan.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.scan")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_scan
      self.log.debug("Loaded: mdf_scan.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_scan.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_scan.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Scan"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"ScanPreDataEngineInit" : (ctypes.c_void_p, None),
       "ScanScanType" : (T_TypeIndex, None),},
      # Functions changed in version 1.
      {"ScanCApiVersion" : (ctypes.c_uint32, None),
       "ScanCApiMinorVersion" : (ctypes.c_uint32, None),
       "ScanNewScan" : (T_ObjectHandle, None),
       "ScanSetScan" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_int32, ctypes.c_int32, ctypes.c_double, ctypes.POINTER(ctypes.c_bool), ctypes.c_uint32, ctypes.c_bool]),
       "ScanPointRangesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ScanPointRangesBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ScanGridHorizontalAnglesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ScanGridHorizontalAnglesBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ScanGridVerticalAnglesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ScanGridVerticalAnglesBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ScanPointIntensityBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle)]),
       "ScanPointIntensityBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle)]),
       "ScanGetOrigin" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]),
       "ScanSetOrigin" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double],),
       "ScanReadLogicalDimensions" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]),
       "ScanOperatingRange" : (ctypes.c_double, [ctypes.POINTER(T_ReadHandle)]),
       "ScanSetOperatingRange" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_double]),
       "ScanGridPointValidReturnBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle)]),
       "ScanIsColumnMajor" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle)]),
       "ScanSetLocalToEllipsoidTransform" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ]),
       "ScanGetLocalToEllipsoidTransform" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_void_p, ]),}
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict

  def NewScan(self):
    """Wrapper around new scan function."""
    raise_if_version_too_old(
      "Creating a Scan",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanNewScan()

  def SetScan(self, lock, row_count, col_count, max_range,
              point_validity, point_count, is_column_major):
    """Wrapper around set scan."""
    raise_if_version_too_old(
      "Creating a Scan",
      current_version=self.version,
      required_version=(1, 1))

    self._dll().ScanSetScan(lock, row_count, col_count, max_range,
                            point_validity, point_count, is_column_major)

  def PointRangesBeginR(self, lock):
    """Wrapper around non-editable scan ranges."""
    raise_if_version_too_old(
      "Reading scan ranges",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanPointRangesBeginR(lock)

  def GridHorizontalAnglesBeginR(self, lock):
    """Wrapper around non-editable scan horizontal angles."""
    raise_if_version_too_old(
      "Reading scan horizontal angles",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanGridHorizontalAnglesBeginR(lock)

  def GridVerticalAnglesBeginR(self, lock):
    """Wrapper around non-editable scan vertical angles."""
    raise_if_version_too_old(
      "Reading scan vertical angles",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanGridVerticalAnglesBeginR(lock)

  def PointRangesBeginRW(self, lock):
    """Wrapper around editable scan ranges."""
    raise_if_version_too_old(
      "Editing scan ranges",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanPointRangesBeginRW(lock)

  def GridHorizontalAnglesBeginRW(self, lock):
    """Wrapper around editable scan horizontal angles."""
    raise_if_version_too_old(
      "Editing scan horizontal angles",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanGridHorizontalAnglesBeginRW(lock)

  def GridVerticalAnglesBeginRW(self, lock):
    """Wrapper around editable scan vertical angles."""
    raise_if_version_too_old(
      "Editing scan vertical angles",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanGridVerticalAnglesBeginRW(lock)

  def PointIntensityBeginR(self, lock):
    """Wrapper around non-editable scan intensity."""
    raise_if_version_too_old(
      "Reading point intensity",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanPointIntensityBeginR(lock)

  def PointIntensityBeginRW(self, lock):
    """Wrapper around editable scan intensity."""
    raise_if_version_too_old(
      "Editing point intensity",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanPointIntensityBeginRW(lock)

  def GetOrigin(self, lock):
    """Wrapper around get scan origin."""
    raise_if_version_too_old(
      "Reading scan origin",
      current_version=self.version,
      required_version=(1, 1))

    x = ctypes.c_double()
    y = ctypes.c_double()
    z = ctypes.c_double()
    self._dll().ScanGetOrigin(lock,
                              ctypes.byref(x),
                              ctypes.byref(y),
                              ctypes.byref(z))
    return [x.value, y.value, z.value]

  def SetOrigin(self, lock, x, y, z):
    """Wrapper set scan origin."""
    raise_if_version_too_old(
      "Setting scan origin",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanSetOrigin(lock, x, y, z)

  def ReadLogicalDimensions(self, lock):
    """Wrapper for reading the logical row and column count."""
    raise_if_version_too_old(
      "Reading scan logical dimensions",
      current_version=self.version,
      required_version=(1, 1))

    logical_row_count = ctypes.c_uint32()
    logical_col_count = ctypes.c_uint32()
    self._dll().ScanReadLogicalDimensions(lock,
                                          ctypes.byref(logical_row_count),
                                          ctypes.byref(logical_col_count))
    return (logical_row_count.value, logical_col_count.value)

  def OperatingRange(self, lock):
    """Wrapper for reading the scan operating range."""
    raise_if_version_too_old(
      "Reading scan operating range",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanOperatingRange(lock)

  def SetOperatingRange(self, lock, new_max_range):
    """Wrapper for setting the scan operating range."""
    raise_if_version_too_old(
      "Editing scan operating range",
      current_version=self.version,
      required_version=(1, 1))

    self._dll().ScanSetOperatingRange(lock, new_max_range)

  def GridPointValidReturnBeginR(self, lock):
    """Wrapper for reading the point validity."""
    raise_if_version_too_old(
      "Reading point validity",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanGridPointValidReturnBeginR(lock)

  def IsColumnMajor(self, lock):
    """Wrapper for reading the column majorness of a scan."""
    raise_if_version_too_old(
      "Reading if the scan is column major",
      current_version=self.version,
      required_version=(1, 1))

    return self._dll().ScanIsColumnMajor(lock)

  def SetLocalToEllipsoidTransform(self, lock, quaternion, origin):
    """Wrapper for setting the scan local to ellipsoid transform.

    Parameters
    ----------
    lock : Lock
      Lock on the object to set the local to transform on.
    origin : np.ndarray
      Numpy array of shape (3, ) representing the origin of the
      transform.
    quaternion : np.ndarray
      Numpy array of shape (4, ) representing the four quaternions
      used to define the transform.

    """
    raise_if_version_too_old(
      "Setting local to ellipsoid transform",
      current_version=self.version,
      required_version=(1, 3))

    result = self.dll.ScanSetLocalToEllipsoidTransform(lock, *quaternion, *origin)

    if result != 0:
      message = "Failed to set local transform."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetLocalToEllipsoidTransform(self, lock):
    """Wrapper for getting the scan local to ellipsoid transform.

    Parameters
    ----------
    lock : Lock
      Lock on the scan for which the local to ellipsoid transform should
      be queried.

    Returns
    -------
    list
      Array of shape (4,) containing the quaternion of the transform.
    list
      Array of shape (3,) containing the translation of the transform.

    """
    raise_if_version_too_old(
      "Getting local to ellipsoid transform",
      current_version=self.version,
      required_version=(1, 3))

    quaternion = (ctypes.c_double * 4)()
    translation = (ctypes.c_double * 3)()
    result = self.dll.ScanGetLocalToEllipsoidTransform(lock,
                                                       quaternion,
                                                       translation)

    if result != 0:
      message = "Failed to set local transform."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return list(quaternion), list(translation)
