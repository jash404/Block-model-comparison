"""Interface for the MDF visualisation library.

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
from .types import T_ReadHandle, T_TypeIndex, T_ObjectHandle
from .util import (singleton, declare_dll_functions, raise_if_version_too_old,
                   CApiUnknownError, CApiDllLoadFailureError)
from .wrapper_base import WrapperBase

@singleton
class Visualisation(WrapperBase):
  """Visualisation - wrapper for mdf_visualisation.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.visualisation")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_visualisation
      self.log.debug("Loaded: mdf_visualisation.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_visualisation.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_visualisation.dll") from os_error

    if self.dll:
      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Visualisation"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"VisualisationPreDataEngineInit" : (ctypes.c_void_p, None),},
      # Functions changed in version 1.
      {"VisualisationCApiVersion" : (ctypes.c_uint32, None),
       "VisualisationCApiMinorVersion" : (ctypes.c_uint32, None),
       "VisualisationRaster2DType" : (T_TypeIndex, None),
       "VisualisationNewRaster2D" : (T_ObjectHandle, [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_bool, ]),
       "VisualisationReadRaster2DDimensions" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "VisualisationRaster2DResize" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_uint32, ]),
       "VisualisationGetRaster2DPixels" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "VisualisationSetRaster2DPixels" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ]),
       "VisualisationRasterSetTitle" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint32, ]),
       "VisualisationRasterGetTitle" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_void_p, ]),
      }
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict

  def Raster2DType(self):
    """Returns the type index of Raster2D.

    Returns
    -------
    TypeIndex
      The Type index value for Raster2D.

    """
    if self.version >= (1, 2):
      return self.dll.VisualisationRaster2DType()
    return None

  def NewRaster2D(self, width, height, is_tileable):
    """Creates a new Raster2D with the specified width and height.

    Parameters
    ----------
    width : ctypes.c_int32
      The width to assign to the new raster.
    height : ctypes.c_int32
      The height to assign to the new raster
    is_tileable : bool
      If the raster can be tiled over a surface.

    """
    raise_if_version_too_old("Creating a new Raster2D",
                             current_version=self.version,
                             required_version=(1, 2))
    return self.dll.VisualisationNewRaster2D(width, height, is_tileable)

  def ReadRaster2DDimensions(self, lock):
    """Returns the width and height of a raster object.

    Parameters
    ----------
    lock : Lock
      Lock on the raster to read the width and height of.

    Returns
    -------
    list
      The list [width, height].

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Reading 2D raster dimensions",
                             current_version=self.version,
                             required_version=(1, 2))
    dimensions = (ctypes.c_int32 * 2)()
    result = self.dll.VisualisationReadRaster2DDimensions(
      lock,
      ctypes.byref(dimensions))
    if result != 0:
      message = "Failed to read read raster dimensions."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return [int(dimensions[0]), int(dimensions[1])]

  def Raster2DResize(self, lock, width, height):
    """Resizes a raster object via simple algorithms.

    Parameters
    ----------
    lock : Lock
      Lock on the Raster2D to resize.
    width : int
      The new width of the raster.
    height : int
      The new height of the raster.

    Raises
    ------
    CAPIUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Resizing raster",
                             current_version=self.version,
                             required_version=(1, 2))

    if width <= 0 or height <= 0:
      raise ValueError(f"Invalid size for raster: ({width}, {height})")

    result = self.dll.VisualisationRaster2DResize(lock, width, height)

    if result != 0:
      message = "Failed to resize raster."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetRaster2DPixels(self, lock):
    """Returns a numpy array containing the pixels of a Raster2D object.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Getting raster 2D pixels",
                             current_version=self.version,
                             required_version=(1, 2))
    width, height = self.ReadRaster2DDimensions(lock)
    pixels = (ctypes.c_int8 * (width * height * 4))()
    result = self.dll.VisualisationGetRaster2DPixels(lock, pixels)
    if result != 0:
      message = "Failed to get raster pixels."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return pixels

  def SetRaster2DPixels(self, lock, pixels, width, height):
    """Sets the pixels of a raster 2D.

    It is the caller's responsibility to ensure that pixels contains
    row count * column count * 4 elements.

    Parameters
    ----------
    lock : Lock
      Lock on the Raster2D for which the colours will be set.
    pixels : ndarray
      The new pixels.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Setting raster 2D pixels",
                             current_version=self.version,
                             required_version=(1, 2))
    c_pixels = (ctypes.c_int8 * (width * height * 4))()
    c_pixels[:] = pixels.astype(ctypes.c_uint8, copy=False).ravel()
    result = self.dll.VisualisationSetRaster2DPixels(lock,
                                                     ctypes.byref(c_pixels),
                                                     width, height)
    if result != 0:
      message = "Failed to set raster pixels."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def RasterSetTitle(self, lock, title):
    """Sets the title of the raster. This is displayed in the manage
    images panel.

    Parameters
    ----------
    lock : Lock
      Edit lock on the raster to set the title for.
    title : str
      Title to assign to the raster.

    """
    raise_if_version_too_old("Setting raster title",
                             current_version=self.version,
                             required_version=(1, 3))

    c_title = title.encode('utf-8')
    c_length = len(c_title)

    result = self.dll.VisualisationRasterSetTitle(lock, c_title, c_length)

    if result != 0:
      message = "Failed to set raster pixels."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def RasterGetTitle(self, lock):
    """Get the title of a Raster.

    Parameters
    ----------
    lock : Lock
      Read lock on the raster whose title should be returned.

    Returns
    -------
    str
      The title of the raster.

    """
    raise_if_version_too_old("Getting raster title",
                             current_version=self.version,
                             required_version=(1, 3))

    # 32 characters should be enough.
    c_length = ctypes.c_uint32(32)
    buffer = ctypes.create_string_buffer(c_length.value)

    result = self.dll.VisualisationRasterGetTitle(lock,
                                                  buffer,
                                                  ctypes.byref(c_length))

    if result == 5:
      # Buffer was too small. c_length was set to the right size
      # so resize the buffer and try again.
      buffer = ctypes.create_string_buffer(c_length.value)
      result = self.dll.VisualisationRasterGetTitle(lock,
                                                    buffer,
                                                    ctypes.byref(c_length))

    if result != 0:
      message = "Failed to set raster pixels."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return bytearray(buffer[:c_length.value]).decode('utf-8')
