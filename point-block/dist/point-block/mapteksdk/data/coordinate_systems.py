"""Support for coordinate systems.

By default, points and other primitives are defined in an arbitrary space
with no correlation to the real world. A coordinate system provides
a mapping of the coordinates to locations in the real world.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################
import ctypes

from pyproj import CRS
import numpy as np

from ..internal.util import default_type_error_message

class LocalTransformNotSupportedError(Exception):
  """Geographic projections do not support local transforms. This error is
  raised when a user attempts to define a local transform for such
  a coordinate system.

  """


class CoordinateSystem:
  """A PROJ coordinate system (see https://proj.org) with an optional additional
  local transformation.

  A local transformation can be used when the standard map project
  is not convenient. For example a local origin, an X direction aligned
  to the strike of a pit and a scaling factor to counter the UTM
  distortion away from the central meridian would create a coordinate system
  that is more convenient to use and represents distances more accurately.

  Parameters
  ----------
  crs : pyproj.CRS or string
    Coordinate reference system of the coordinate system. This can be
    a pyproj.CRS object or a "Well Known Text" (wkt) string.
  local_transform : LocalTransform
    The local transform of the coordinate system. The default is no local
    transform.

  Raises
  ------
  pyproj.exceptions.CRSError
    If crs cannot be parsed as a wkt string.
  LocalTransformNotSupportedError
    If the CRS is a geographic projection and local transform was specified.

  Warnings
  --------
  Vulcan GeologyCore 2021 and PointStudio 2021/2021.1 use PROJ version 6.3.1
  which roughly matches up with the version of PROJ used by pyproj versions
  2.5.0 and 2.6.0.
  mapteksdk will work with newer versions of pyproj, however if the installed
  version of pyproj uses a newer version of PROJ than the connected
  application then pyproj may be able to represent coordinate systems which
  the application cannot understand.

  """
  def __init__(self, crs, local_transform=None):
    if not isinstance(crs, CRS):
      crs = CRS.from_wkt(crs)
    self.crs = crs
    self.local_transform = local_transform

  def __eq__(self, other):
    if not isinstance(other, CoordinateSystem):
      return False

    return (self.crs == other.crs
            and self.local_transform == other.local_transform)

  @property
  def crs(self):
    """The base coordinate system of the object. This is an object
    of type pyproj.CRS.

    When set, this can be a pyproj.CRS class or a string in wkt format.

    Raises
    ------
    TypeError
      If set to a value which is not a pyproj.CRS.
    pyproj.exceptions.CRSError
      If set to a string which cannot be converted to a CRS.

    """
    return self.__crs

  @crs.setter
  def crs(self, crs):
    if isinstance(crs, str):
      crs = CRS.from_wkt(crs)
    if not isinstance(crs, CRS):
      raise TypeError(default_type_error_message("crs", crs, CRS))
    self.__crs = crs
    # If set to a geographic projection local transforms are not supported
    # so erase any existing local transform.
    if crs.is_geographic:
      self.__local_transform = LocalTransform()

  @property
  def local_transform(self):
    """The local transform applied to the coordinate system to provide
    a more convenient coordinate system.

    Raises
    ------
    TypeError
      If set to a value which is not a LocalTransform.
    LocalTransformNotSupportedError
      If set when CRS is a geographic projection.

    """
    return self.__local_transform

  @local_transform.setter
  def local_transform(self, value):
    if value is None:
      value = LocalTransform()
    if not isinstance(value, LocalTransform):
      raise TypeError(default_type_error_message("local_transform",
                                                 value,
                                                 LocalTransform))
    if self.crs.is_geographic and not np.all(np.isnan(value.to_numpy())):
      raise LocalTransformNotSupportedError(
        "Local transforms are not supported when using geographic projections.")
    self.__local_transform = value


class LocalTransform:
  """Class representing a local transform that can be applied on top of a
  coordinate system to provide a more useful and accurate coordinate system
  for a particular application.

  Parameters
  ----------
  local_transform
    The local transform represented as eleven floats. See notes for details
    on the meaning of each float. If this is specified, all other parameters
    are ignored. Generally users of the SDK will use the other arguments
    in preference to this one.
  horizontal_origin : numpy.ndarray
    Numpy array of shape (2,) representing the horizontal origin.
    Default is [nan, nan].
  horizontal_scale_factor : float
    Float representing the horizontal scale factor.
    Default is nan.
  horizontal_rotation : float
    Float represtenting the horizontal rotation.
    Default is nan.
  horizontal_shift: numpy.ndarray
    Numpy array of shape (2,) representing the horizontal shift.
    Default is [nan, nan]
  vertical_shift: float
    Float representing the vertical shift.
    Default is nan.
  vertical_origin: numpy.ndarray
    Numpy array of shape (2,) representing the vertical origin.
    Default is [nan, nan]
  vertical_slope: numpy.ndarray
    Numpy array of shape (2,) representing the vertical slope.
    Default is [nan, nan]

  Raises
  ------
  ValueError
    If the numpy arrays shape is not (11,).
  TypeError
    If any of the local transform parameters are an incorrect type.

  Notes
  -----
  This local transform object can be represented as a numpy array of eleven
  floats. These floats have the following meaning:

  0. Horizontal origin X
  1. Horizontal origin Y
  2. Horizontal scale factor
  3. Horizontal rotation
  4. Horizontal shift X
  5. Horizontal shift Y
  6. Vertical shift
  7. Vertical origin X
  8. Vertical origin Y
  9. Vertical slope X
  10. Vertical slope Y

  """
  def __init__(self, local_transform=None, *, horizontal_origin=None,
      horizontal_scale_factor=np.nan, horizontal_rotation=np.nan,
      horizontal_shift=None, vertical_shift=np.nan, vertical_origin=None,
      vertical_slope=None):
    self.__local_transform = np.full((11,), np.nan, ctypes.c_double)
    if local_transform is not None:
      self.__local_transform[:] = local_transform
    else:
      self.horizontal_origin = horizontal_origin
      self.horizontal_scale_factor = horizontal_scale_factor
      self.horizontal_rotation = horizontal_rotation
      self.horizontal_shift = horizontal_shift
      self.vertical_shift = vertical_shift
      self.vertical_origin = vertical_origin
      self.vertical_slope = vertical_slope

  def __eq__(self, other):
    if not isinstance(other, LocalTransform):
      return False

    return np.allclose(self.to_numpy(),
                       other.to_numpy(),
                       equal_nan=True)

  @property
  def horizontal_origin(self):
    """The origin in the pre-calibrated coordinate system about which
    the coordinates are scaled and rotated.

    This is a numpy array of shape (2,) in the form [X, Y] (or
    [Northing, Easting])

    Raises
    ------
    ValueError
      If the value cannot be converted to an ndarray with shape (2,).
    TypeError
      If set to a value which cannot be converted to a floating point number.

    """
    return self.__local_transform[0:2]

  @horizontal_origin.setter
  def horizontal_origin(self, value):
    if value is None:
      self.__local_transform[0:2] = [np.nan, np.nan]
    else:
      self.__local_transform[0:2] = value

  @property
  def horizontal_scale_factor(self):
    """The scale factor of the points about the horizontal origin.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float.
    ValueError
      If set to a non-nan value when the horizontal origin has not been set.

    """
    return self.__local_transform[2]

  @horizontal_scale_factor.setter
  def horizontal_scale_factor(self, value):
    value = float(value)
    if np.any(np.isnan(self.horizontal_origin)) and not np.isnan(value):
      raise ValueError("Setting scale factor without setting horizontal "
                       "origin is invalid.")
    self.__local_transform[2] = value

  @property
  def horizontal_rotation(self):
    """The clockwise horizontal rotation applied to the coordinates about the
    horizontal origin. The value is in radians.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float.
    ValueError
      If set to a non-nan value when the horizontal origin has not been set.

    """
    return self.__local_transform[3]

  @horizontal_rotation.setter
  def horizontal_rotation(self, value):
    value = float(value)
    if np.any(np.isnan(self.horizontal_origin)) and not np.isnan(value):
      raise ValueError("Setting scale factor without setting horizontal "
                       "origin is invalid.")
    self.__local_transform[3] = value

  @property
  def horizontal_shift(self):
    """The translation applied to the coordinates relative to the horizontal
    origin.

    Raises
    ------
    ValueError
      If the value cannot be converted to an ndarray with shape (2,).
    TypeError
      If set to a value which cannot be converted to a floating point number.

    """
    return self.__local_transform[4:6]

  @horizontal_shift.setter
  def horizontal_shift(self, value):
    if value is None:
      self.__local_transform[4:6] = [np.nan, np.nan]
    else:
      self.__local_transform[4:6] = value

  @property
  def vertical_shift(self):
    """The translation of the coordinates in the z direction. A positive value
    shifts upwards.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float.

    """
    return self.__local_transform[6]

  @vertical_shift.setter
  def vertical_shift(self, value):
    self.__local_transform[6] = float(value)

  @property
  def vertical_origin(self):
    """The origin of the plane used for a position dependent vertical
    shift. vertical_slope defines the slope of this plane.
    The point is defined in the post horizontal calibration system.

    Raises
    ------
    ValueError
      If the value cannot be converted to an ndarray with shape (2,).
    TypeError
      If set to a value which cannot be converted to a floating point number.

    """
    return self.__local_transform[7:9]

  @vertical_origin.setter
  def vertical_origin(self, value):
    if value is None:
      self.__local_transform[7:9] = [np.nan, np.nan]
    else:
      self.__local_transform[7:9] = value

  @property
  def vertical_slope(self):
    """The slope of the plane in parts per million in the form [East, North].
    The origin or the plane is defined by vertical_origin.
    Each value can be considered the height change in mm over a horizontal
    distance of 1km in the specified direction.

    Raises
    ------
    ValueError
      If the value cannot be converted to an ndarray with shape (2,).
    TypeError
      If set to a value which cannot be converted to a floating point number.

    """
    return self.__local_transform[9:11]

  @vertical_slope.setter
  def vertical_slope(self, value):
    if value is None:
      self.__local_transform[9:11] = [np.nan, np.nan]
    else:
      self.__local_transform[9:11] = value

  def to_numpy(self):
    """Converts the local transform to a numpy array of shape (11,).
    See notes on the class for an explanation of each element.

    """
    return self.__local_transform
