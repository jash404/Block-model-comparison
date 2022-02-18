"""Image data objects.

Image objects are used to apply complicated textures to other objects.
"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import logging
import warnings

import numpy as np

from ..capi import Visualisation, Modelling, Sdp
from ..internal.lock import LockType, WriteLock
from ..common import convert_array_to_rgba
from .base import DataObject
from .objectid import ObjectID
from .errors import CannotSaveInReadOnlyModeError

log = logging.getLogger("mapteksdk.data")

class Raster(DataObject):
  """Class representing raster images which can be draped onto other objects.

  Topology objects which support raster association possess an associate_raster
  function which accepts a Raster and a RasterRegistration object which allows
  the raster to be draped onto that object.

  Parameters
  ----------
  width : int
    The width of the raster.
  height : int
    The height of the raster.

  Notes
  -----
  This object provides a consistent interface to the pixels of the raster image
  regardless of the underlying format. If the underlying format is
  JPEG or another format which does not support alpha, the alpha will always
  be read as 255 and any changes to the alpha components will be ignored.

  See Also
  --------
  mapteksdk.data.facets.Surface.associate_raster: associate a raster with
    a surface.

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE, width=None,
      height=None):
    self.__is_new = not object_id
    self.__error_on_access_pixels = False
    if self.__is_new:
      # :TODO: Jayden Boskell 2021-09-14 SDK-588: Change these cases
      # to raise a DegenerateTopologyError.
      if width is None:
        message = ("Width default argument is deprecated "
                  "and will be removed in a future version.")
        warnings.warn(DeprecationWarning(message))
        width = 1
      if height is None:
        message = ("Width default argument is deprecated "
                  "and will be removed in a future version.")
        warnings.warn(DeprecationWarning(message))
        height = 1
      if width < 1:
        raise ValueError(f"Invalid width: {width}. Must be greater than zero.")
      if height < 1:
        raise ValueError(
          f"Invalid height: {height}. Must be greater than zero.")
      try:
        object_id = ObjectID(Visualisation().NewRaster2D(width, height,
                                                         False))
      except ctypes.ArgumentError as error:
        raise TypeError("Width and height must be integers. "
                        f"Width: {width}, Height: {height}") from error
    super().__init__(object_id, lock_type)
    self.__dimensions = None
    self.__registration = None
    self.__title = None
    if self.__is_new:
      # If we don't set the pixels to anything in new it causes an
      # access violation when the pixels are accessed later.
      self.__pixels = np.zeros((self.height * self.width, 4),
                                 dtype=ctypes.c_uint8)
    else:
      self.__pixels = None
    self.__pixels_2d = None

  @classmethod
  def static_type(cls):
    """Return the type of raster as stored in a Project.

    This can be used for determining if the type of an object is a raster.

    """
    return Modelling().ImageType()

  @property
  def width(self):
    """The width of the raster. This is the number of pixels in each row."""
    if self.__dimensions is None:
      self.__dimensions = Visualisation().ReadRaster2DDimensions(
        self._lock.lock)
    return self.__dimensions[0]

  @property
  def height(self):
    """The height of the raster. This is the number of pixels in each column."""
    if self.__dimensions is None:
      self.__dimensions = Visualisation().ReadRaster2DDimensions(
        self._lock.lock)
    return self.__dimensions[1]

  def resize(self, new_width, new_height, resize_image=True):
    """Resizes the raster to the new width and height.

    Parameters
    ----------
    new_width : int
      The new width for the raster. Pass None to keep the width unchanged.
    new_height : int
      The new height for the raster. Pass None to keep the height unchanged.
    resize_image : bool
      If True (default) The raster will be resized to fill the new size using
      a simple nearest neighbour search if the size is reduced, or
      simple bilinear interpolation. This will also change the format
      to JPEG (and hence the alpha component of the pixels will be discarded).
      If False, the current pixels are discarded and replaced with transparent
      white (or white if the format does not support transparency). This will
      not change the underlying format.

    Raises
    ------
    TypeError
      If width or height cannot be converted to an integer.
    ValueError
      If width or height is less than one.
    RuntimeError
      If called when creating a new raster.

    Warnings
    --------
    After calling resize with resize_image=True it is an error to access
    pixels or pixels_2d until the object is closed and reopened.

    Examples
    --------
    Halve the size of all rasters on an object. Note that because
    resize_image is true, the existing pixels will be changed to make
    a smaller version of the image.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.read("surfaces/target") as read_object:
    >>>     for raster in read_object.rasters.values():
    ...         with project.edit(raster) as edit_raster:
    ...             edit_raster.resize(edit_raster.width // 2,
    ...                                edit_raster.height // 2,
    ...                                resize_image=True)

    """
    # Resizing during new causes an access violation.
    if self.__is_new:
      raise RuntimeError("Cannot resize when creating new raster.")
    new_width = int(new_width)
    new_height = int(new_height)

    if new_width < 1 or new_height < 1:
      raise ValueError(f"Invalid size for raster: {new_width}, {new_height}. "
                       "Width and height must be greater than zero.")

    self.__dimensions = [new_width, new_height]

    if resize_image:
      if self.width == new_width or self.height == new_height:
        if Visualisation().version < (1, 3):
          log.warning("There is a bug in PointStudio 2021 and other "
                      "applications where resizing an image without changing "
                      "both width and height is ignored.")
      Visualisation().Raster2DResize(self._lock.lock, new_width, new_height)
      self.__pixels = None
      self.__error_on_access_pixels = True
    else:
      self.__pixels = np.zeros((new_width * new_height, 4))

  @property
  def pixel_count(self):
    """The total number of pixels in the raster."""
    return self.height * self.width

  @property
  def pixels(self):
    """The pixels of the raster object represented as a numpy array
    of shape (pixel_count, 4) where each row is the colour of a pixel
    in the form: [Red, Green, Blue, Alpha].

    See pixels_2d for the pixels reshaped to match the width and height of
    the raster.

    Raises
    ------
    RuntimeError
      If accessed after calling resize with resize_image = True.

    Notes
    -----
    The default colour is transparent white. This may appear as white if
    the raster is stored in a format which does not support alpha.

    Examples
    --------
    Accessing the pixels via this function is best when the two dimensional
    nature of the raster is not relevant or useful. The below example shows
    removing the green component from all of the pixels in an raster. Has no
    effect if the object at surfaces/target does not have an associated
    raster.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.read("surfaces/target") as read_object:
    >>>     for raster in read_object.rasters.values():
    ...         with project.edit(raster) as edit_raster:
    ...             edit_raster.pixels[:, 1] = 0

    """
    if self.__error_on_access_pixels:
      raise RuntimeError("Cannot read pixels after resizing with "
                         "resize_image = True. You must close the "
                         "object before accessing pixels.")
    if self.__pixels is None:
      self.__pixels = np.array(
        Visualisation().GetRaster2DPixels(self._lock.lock),
        dtype=ctypes.c_uint8).reshape((-1, 4))
    if self.__pixels.shape != (self.pixel_count, 4):
      self.__pixels = convert_array_to_rgba(self.__pixels, self.pixel_count,
                                            np.array([0, 0, 0, 0]))
    return self.__pixels

  @pixels.setter
  def pixels(self, new_pixels):
    if not isinstance(new_pixels, np.ndarray):
      new_pixels = np.array(new_pixels)
    new_pixels = convert_array_to_rgba(new_pixels, self.pixel_count,
                                       np.array([0, 0, 0, 0]))
    self.__pixels = new_pixels

  @property
  def pixels_2d(self):
    """The pixels reshaped to match the width and height of the raster.
    pixels_2d[0][0] is the colour of the pixel in the bottom left hand
    corner of the raster. pixels_2d[i][j] is the colour of the pixel i
    pixels to the right of the bottom left hand corner and j pixels
    above the bottom left hand corner.

    The returned array will have shape (height, width, 4).

    Raises
    ------
    ValueError
      If set using a string which cannot be converted to an integer.
    ValueError
      If set to a value which cannot be broadcast to the right shape.
    TypeError
      If set to a value which cannot be converted to an integer.

    Notes
    -----
    This returns the pixels in an ideal format to be passed to the
    raster.fromarray function in the 3rd party pillow library.

    Examples
    --------
    As pixels_2d allows access to the two dimensional nature of the raster,
    it can allow different transformations to be applied to different
    parts of the raster. The example below performs a different transformation
    to each quarter of the raster. Has no effect if the object at
    surfaces/target has no associated rasters.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.read("surfaces/target") as read_object:
    ...     for raster in read_object.rasters.values():
    ...         with project.edit(raster) as edit_raster:
    ...             width = edit_raster.width
    ...             height = edit_raster.height
    ...             half_width = edit_raster.width // 2
    ...             half_height = edit_raster.height // 2
    ...             # Remove red from the bottom left hand corner.
    ...             edit_raster.pixels_2d[0:half_height, 0:half_width, 0] = 0
    ...             # Remove green from the top left hand corner.
    ...             edit_raster.pixels_2d[half_height:height,
    ...                                   0:half_width, 1] = 0
    ...             # Remove blue from the bottom right hand corner.
    ...             edit_raster.pixels_2d[0:half_height,
    ...                                   half_width:width, 2] = 0
    ...             # Maximizes the red component in the top right hand corner.
    ...             edit_raster.pixels_2d[half_height:height,
    ...                                   half_width:width, 0] = 255

    """
    if self.__pixels_2d is None or not np.may_share_memory(self.pixels,
                                                           self.__pixels_2d):
      self.__pixels_2d = self.pixels[:].reshape((self.height, self.width, 4))
    return self.__pixels_2d

  @pixels_2d.setter
  def pixels_2d(self, new_pixels_2d):
    self.pixels_2d[:] = new_pixels_2d

  @property
  def title(self):
    """The title of the raster.

    This is shown in the manage images panel. Generally this is the name
    of the file the raster was imported from.

    """
    if self.__title is None:
      self.__title = self._load_title()
    return self.__title

  @title.setter
  def title(self, value):
    self.__title = str(value)

  @property
  def registration(self):
    """Returns the registration object which defines how the raster is draped
    onto Topology Objects.

    If no raster registration is set, this will return a RasterRegistrationNone
    object. If raster registration is set, but the SDK does not support the
    type of registration, it will return a RasterRegistrationUnsupported
    object. Otherwise it will return a RasterRegistration subclass representing
    the existing registration.

    Raises
    ------
    TypeError
      If set to a value which is not a RasterRegistration.
    ValueError
      If set to an invalid RasterRegistration.

    Notes
    -----
    You should not assign to this property directly. Instead pass the
    registration to the associate_raster() function of the object you would
    like to associate the raster with.

    """
    if self.__registration is None:
      self.__registration = self._load_registration_information()
    return self.__registration

  @registration.setter
  def registration(self, value):
    if not isinstance(value, RasterRegistration):
      raise TypeError("registration must be RasterRegistration, "
                      f"not {type(value)}")
    value.raise_if_invalid()
    self.__registration = value

  def _save_title(self, title):
    """Save the title of the raster to the Project.

    Parameters
    ----------
    title : str
      The title to save to the Project.

    """
    Visualisation().RasterSetTitle(self._lock.lock, title)

  def _load_title(self):
    """Load the title of the raster from the Project.

    Returns
    -------
    str
      The title of the raster.

    """
    return Visualisation().RasterGetTitle(self._lock.lock)

  def _save_registration_two_point(self, image_points, world_points,
                                   orientation):
    """Saves the registration information of the raster for two point
    registration to the project.

    Parameters
    ----------
    image_points : numpy.ndarray
      Numpy array of shape (n, 2) containing the points on the image to
      use for mapping the raster onto an object.
    world_points : numpy.ndarray
      Numpy array of shape (n, 3) containing the points in worldspace used
      for mapping the raster onto an object.
    orientation : numpy.ndarray
      Numpy array of shape (3,) representing the orientation the raster
      will be mapped onto an object.

    Raises
    ------
    ValueError
      If image points and world points do not contain the same number of points.

    """
    if image_points.shape[0] != world_points.shape[0]:
      raise ValueError("Image points and world points must contain the "
                       "same number of points. "
                       f"Image points contains: {image_points.shape[0]}, "
                       f"World points contains: {world_points.shape[0]}. ")
    Modelling().RasterSetControlTwoPoint(self._lock.lock,
                                         image_points,
                                         world_points,
                                         orientation)

  def _save_registration_multi_point(self, image_points, world_points):
    if image_points.shape[0] != world_points.shape[0]:
      raise ValueError("Image points and world points must contain the "
                       "same number of points. "
                       f"Image points contains: {image_points.shape[0]}, "
                       f"World points contains: {world_points.shape[0]}. ")
    Sdp().RasterSetControlMultiPoint(self._lock.lock,
                                     world_points,
                                     image_points)

  def _load_registration_information(self):
    """Loads the registration information from the project.

    This sets the image points, world points and orientation used
    to register the raster onto an object. This will not override
    any existing values.

    """
    registration_type = Modelling().GetRasterRegistrationType(self._lock.lock)
    if registration_type == 0:
      return RasterRegistrationNone()
    if registration_type == 3:
      registration = Modelling().RasterGetRegistration(self._lock.lock)
      image_points, world_points, point_count, orientation = registration

      image_points = self._array_to_numpy(image_points,
                                          point_count * 2,
                                          ctypes.c_double).reshape(-1, 2)
      world_points = self._array_to_numpy(world_points,
                                          point_count * 3,
                                          ctypes.c_double).reshape(-1, 3)
      orientation = self._array_to_numpy(orientation,
                                         3,
                                         ctypes.c_double)
      return RasterRegistrationTwoPoint(image_points,
                                        world_points,
                                        orientation)
    if registration_type == 6:
      registration = Modelling().RasterGetRegistration(self._lock.lock)
      image_points, world_points, point_count, _ = registration
      image_points = self._array_to_numpy(image_points,
                                          point_count * 2,
                                          ctypes.c_double).reshape(-1, 2)
      world_points = self._array_to_numpy(world_points,
                                          point_count * 3,
                                          ctypes.c_double).reshape(-1, 3)
      return RasterRegistrationMultiPoint(image_points, world_points)
    if registration_type == 8:
      # :TODO: Jayden Boskell 2021-04-22 SDK-484 Implement scan
      # association similar to the pointstudio transaction.
      return RasterRegistrationUnsupported()
    return RasterRegistrationUnsupported()

  def save(self):
    """Saves changes to the raster to the Project."""
    if not isinstance(self._lock, WriteLock):
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error
    if self.__pixels is not None:
      Visualisation().SetRaster2DPixels(self._lock.lock, self.pixels,
                                        self.width, self.height)
    if self.__registration is not None:
      registration = self.registration
      registration.raise_if_invalid()
      if isinstance(registration, RasterRegistrationTwoPoint):
        self._save_registration_two_point(registration.image_points,
                                          registration.world_points,
                                          registration.orientation)
      elif isinstance(registration, RasterRegistrationMultiPoint):
        self._save_registration_multi_point(registration.image_points,
                                            registration.world_points)
    if self.__title is not None:
      self._save_title(self.__title)
    self._invalidate_properties()

  def _invalidate_properties(self):
    """Invalidates the properties causing them to be loaded from the
    project next time they are requested.

    """
    self.__pixels = None
    self.__pixels_2d = None
    self.__dimensions = None
    self.__registration = None

class RasterRegistration:
  """Base class for all types of raster registration. This is useful
  for type checking.

  """
  @property
  def is_valid(self):
    """True if the object is valid."""
    raise NotImplementedError

  def raise_if_invalid(self):
    """Checks if the raster is invalid and raises a ValueError if any invalid
    information is detected.

    If is_valid is False then calling this function will raise a ValueError
    containing information on why the registration is considered invalid.

    Raises
    ------
    ValueError
      If the raster is invalid.

    """
    raise NotImplementedError

class RasterRegistrationNone(RasterRegistration):
  """Class representing no raster registration is present.

  Notes
  -----
  This is always considered valid, so raise_if_valid will never raise
  an error for this object.

  """
  def __eq__(self, other):
    return isinstance(other, RasterRegistrationNone)

  @property
  def is_valid(self):
    return True

  def raise_if_invalid(self):
    return

class RasterRegistrationUnsupported(RasterRegistration):
  """Class representing a raster registration which is not supported by
  the SDK.

  If you would like an unsupported registration method to be supported then
  use request support.

  Notes
  -----
  This is always considered invalid so raise_if_valid will always raise
  an error.

  """
  def __eq__(self, other):
    return isinstance(other, RasterRegistrationUnsupported)

  @property
  def is_valid(self):
    return False

  def raise_if_invalid(self):
    raise ValueError("Cannot perform operations on unsupported registration.")

class PointPairRegistrationBase(RasterRegistration):
  """Base class for registration objects which use image/world point
  pairs to register the image to a Surface.

  """
  @classmethod
  def minimum_point_pairs(cls):
    """The minimum number of world / image point pairs required
    for this type of registration.

    Returns
    -------
    int
      The minimum number of world / image point pairs required.

    """
    raise NotImplementedError

  @property
  def is_valid(self):
    if self.world_points.shape[0] < self.minimum_point_pairs():
      return False
    if self.image_points.shape[0] < self.minimum_point_pairs():
      return False
    if self.image_points.shape[0] != self.world_points.shape[0]:
      return False
    return True

  def raise_if_invalid(self):
    if self.world_points.shape[0] < self.minimum_point_pairs():
      raise ValueError(f"{type(self).__name__} requires at least "
                       f"{self.minimum_point_pairs()} world points. "
                       f"Given: {self.world_points.shape[0]}")
    if self.image_points.shape[0] < self.minimum_point_pairs():
      raise ValueError(f"{type(self).__name__} requires at least "
                       f"{self.minimum_point_pairs()} image points. "
                       f"Given: {self.image_points.shape[0]}")
    if self.image_points.shape[0] != self.world_points.shape[0]:
      raise ValueError("Image points and world points must contain the "
                       "same number of points. "
                       f"Image points contains: {self.image_points.shape[0]}, "
                       f"World points contains: {self.world_points.shape[0]}. ")

  @property
  def image_points(self):
    """The points on the image used to map the raster onto an object. This is
    a numpy array of points in image coordinates where [0, 0] is the bottom
    left hand corner of the image and [width, height] is the top right hand
    corner of the image.

    Each of these points should match one of the world points. If the
    raster is mapped onto an object, the pixel at image_points[i] will
    be placed at world_points[i] on the surface.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a two dimensional array
      containing two dimensional points or if any value in the array cannot
      be converted to a floating point number.
    TypeError
      If set to a value which cannot be converted to a numpy array.

    """
    return self.__image_points

  @image_points.setter
  def image_points(self, value):
    if value is None:
      value = np.zeros((0, 2), dtype=ctypes.c_double)
    if not isinstance(value, np.ndarray):
      value = np.array(value, dtype=ctypes.c_double)
    if value.dtype != ctypes.c_double:
      value = value.astype(ctypes.c_double)
    if len(value.shape) != 2:
      raise ValueError(f"Image points must be two dimensional, not "
                       f"{len(value.shape)} dimensional.")
    if value.shape[1] != 2:
      raise ValueError(f"Each image point must have two dimensions, not "
                       f"{value.shape[1]} dimensions.")

    self.__image_points = value

  @property
  def world_points(self):
    """The world points used to map the raster onto an object. This is a
    numpy array of points in world coordinates.

    Each of these points should match one of the image points. If the
    raster is mapped onto an object, the pixel at image_points[i] will
    be placed at world_points[i] on the surface.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a two dimensional array
      containing three dimensional points or if any value in the array cannot
      be converted to a floating point number.
    TypeError
      If set to a value which cannot be converted to a numpy array.

    """
    return self.__world_points

  @world_points.setter
  def world_points(self, value):
    if value is None:
      value = np.zeros((0, 3), dtype=ctypes.c_double)
    if not isinstance(value, np.ndarray):
      value = np.array(value, dtype=ctypes.c_double)
    if value.dtype != ctypes.c_double:
      value = value.astype(ctypes.c_double)
    if len(value.shape) != 2:
      raise ValueError(f"World points must be two dimensional, not "
                       f"{len(value.shape)} dimensional.")
    if value.shape[1] != 3:
      raise ValueError(f"Each world point must have 3 dimensions, not "
                       f"{value.shape[1]} dimensions.")

    self.__world_points = value

class RasterRegistrationTwoPoint(PointPairRegistrationBase):
  """Represents a simple raster registration which uses two points and
  an orientation to project a raster onto an object (typically a Surface).

  Parameters
  ----------
  image_points : numpy.ndarray
    The image points to assign to the object. See the property for more details.
  world_points : numpy.ndarray
    The world points to assign to the object. See the property for more details.
  orientation : numpy.ndarray
    The orientation to assign to the object. See the property for more details.

  See Also
  --------
  mapteksdk.data.facets.Surface.associate_raster : Pass a
    RasterRegistrationTwoPoint and a raster to this function to associate the
    raster with a surface.

  """
  def __init__(self, image_points=None, world_points=None, orientation=None):
    self.image_points = image_points
    self.world_points = world_points
    self.orientation = orientation

  @classmethod
  def minimum_point_pairs(cls):
    return 2

  @property
  def is_valid(self):
    if not super().is_valid:
      return False
    if not np.all(np.isfinite(self.orientation)):
      return False
    return True

  def raise_if_invalid(self):
    super().raise_if_invalid()
    if not np.all(np.isfinite(self.orientation)):
      raise ValueError("Orientation must be finite. "
                       f"Orientation: {self.orientation}")

  def __eq__(self, other):
    if not isinstance(other, RasterRegistrationTwoPoint):
      return False

    return (np.all(np.isclose(self.image_points, other.image_points))
            and np.all(np.isclose(self.world_points, other.world_points))
            and np.all(np.isclose(self.orientation, other.orientation)))

  @property
  def orientation(self):
    """The orientation vector used to map the raster onto an object. This is
    a numpy array of shape (3,) of the form [X, Y, Z] representing
    the direction from which the raster is projected onto the object. The
    components may all be nan for certain raster associations which do
    not use projections (eg: panoramic image onto a scan).

    If this is [0, 0, 1] the raster is projected onto the object from the
    positive z direction (above).
    [0, 0, -1] would project the raster onto the object from the negative
    z direction (below).

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a numpy array of
      shape (3,) or if any value in the array cannot be converted to
      a floating point number.
    TypeError
      If set to a value which cannot be converted to a numpy array.

    """
    return self.__orientation

  @orientation.setter
  def orientation(self, value):
    if value is None:
      value = np.full((3,), np.nan, dtype=ctypes.c_double)
    if not isinstance(value, np.ndarray):
      value = np.array(value, dtype=ctypes.c_double)
    if value.dtype != ctypes.c_double:
      value = value.astype(ctypes.c_double)
    if value.shape != (3,):
      raise ValueError("Orientation must have shape (3,), not: "
                       f"{value.shape}")
    self.__orientation = value

class RasterRegistrationMultiPoint(PointPairRegistrationBase):
  """Represents a raster registration which uses eight or more points to
  project a raster onto an object (typically a Surface).

  Parameters
  ----------
  image_points : numpy.ndarray
    The image points to assign to the object. See the property for more details.
  world_points : numpy.ndarray
    The world points to assign to the object. See the property for more details.

  See Also
  --------
  mapteksdk.data.facets.Surface.associate_raster : Pass a
    RasterRegistrationMultiPoint and a raster to this function to associate the
    raster with a surface.

  Notes
  -----
  Though the minimum points required for multi point registration is eight,
  in most cases twelve or more points are required to get good results.

  """
  def __init__(self, image_points=None, world_points=None):
    self.image_points = image_points
    self.world_points = world_points

  @classmethod
  def minimum_point_pairs(cls):
    return 8

  def __eq__(self, other):
    if not isinstance(other, RasterRegistrationMultiPoint):
      return False

    return (np.all(np.isclose(self.image_points, other.image_points))
            and np.all(np.isclose(self.world_points, other.world_points)))
