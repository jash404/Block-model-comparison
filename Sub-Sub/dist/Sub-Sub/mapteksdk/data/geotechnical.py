"""Geotechnical data types.

Currently this only includes discontinuities, however in the future it may
be expanded to contain other geotechnical objects such as stereonets.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################
import ctypes
import math
import logging

import numpy as np

from .base import Topology
from .errors import CannotSaveInReadOnlyModeError
from .objectid import ObjectID
from ..capi import Modelling
from ..common import trim_pad_2d_array, convert_to_rgba, trim_pad_1d_array
from ..internal.lock import LockType

log = logging.getLogger("mapteksdk.data")

class Discontinuity(Topology):
  """A discontinuity (Also known as a tangent plane). These are generally
  used to mark a change in the physical or chemical characteristics in
  soil or rock mass.

  Discontinuities with similar properties are often placed in special
  containers known as discontinuity sets.

  Examples
  --------
  The simplest way to define a discontinuity is to define the planar points.
  This example defines a discontinuity using points in the plane with the
  equation 3x - y + 2z + 4 = 0. The other properties are automatically
  derived from the points used to define the discontinuity.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Discontinuity
  >>> points = [[1, 1, -3], [-1, 2, 0.5], [-2, -2, 0],
  ...           [0, -2, -3], [-4, 0, 4], [2, 2, -4]]
  >>> project = Project()
  >>> with project.new("geotechnical/3x-y+2z+4", Discontinuity) as plane:
  ...     plane.planar_points = points
  >>> with project.read(plane.id) as read_plane:
  ...     print("Dip: ", read_plane.dip)
  ...     print("Dip direction: ", read_plane.dip_direction)
  ...     print("Location: ", read_plane.location)
  ...     print("Area: ", read_plane.area)
  ...     print("Length: ", read_plane.length)
  Dip:  1.0068536854342678
  Dip direction:  1.8925468811915387
  Location:  [-0.66666667  0.16666667 -0.91666667]
  Area:  28.062430400804566
  Length:  10.198039027185569

  A discontinuity can also be defined by setting the dip, dip direction
  and location. This is less preferable than the other methods because the
  discontinuity will not have a length or area.

  >>> import math
  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Discontinuity
  >>> project = Project()
  >>> with project.new("geotechnical/simple", Discontinuity) as plane:
  ...     plane.dip = math.pi / 4
  ...     plane.dip_direction = math.pi / 2
  ...     plane.location = [4, 2, 1]
  >>> with project.read(plane.id) as read_plane:
  ...     print("Points", read_plane.planar_points)
  ...     print("Area: ", read_plane.area)
  ...     print("Length: ", read_plane.length)
  Points [[3.29289322 2.         1.70710678]
  [4.35355339 1.1339746  0.64644661]
  [4.35355339 2.8660254  0.64644661]]
  Area:  nan
  Length:  nan

  when creating a new discontinuity, it possible to define the planar points
  and the dip, dip direction and location. This causes the points to be
  projected onto the plane defined by the dip and dip direction and to be
  translated to be centred at the specified location. In the below example,
  though the points are originally centred around the origin and in
  the XY plane they are translated to be centred around the new centre
  and to be in the new plane.

  >>> import math
  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Discontinuity
  >>> points = [[-1, -1, 0], [1, -1, 0], [-1, 1, 0], [1, 1, 0]]
  >>> project = Project()
  >>> with project.new("geotechnical/both", Discontinuity) as plane:
  ...     plane.planar_points = points
  ...     plane.dip = math.pi / 4
  ...     plane.dip_direction = math.pi / 2
  ...     plane.location = [4, 2, 1]
  >>> with project.read(plane.id) as read_plane:
  ...     print("Points", read_plane.planar_points)
  ...     print("Dip: ", read_plane.dip)
  ...     print("Dip direction: ", read_plane.dip_direction)
  ...     print("Location: ", read_plane.location)
  ...     print("Area: ", read_plane.area)
  ...     print("Length: ", read_plane.length)
  Points [[3.29289322 3.         1.70710678]
   [3.29289322 1.         1.70710678]
   [4.70710678 3.         0.29289322]
   [4.70710678 1.         0.29289322]]
  Dip:  0.7853981633974482
  Dip direction:  1.5707963267948966
  Location:  [4. 2. 1.]
  Area:  4.0
  Length:  2.8284271247461907

  """
  # :TRICKY: Though Discontinuities have points and facets, they do
  # not implement PointProperties and FacetProperties because they
  # do not support many of the operations those classes define.
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    if not object_id:
      object_id = ObjectID(Modelling().NewTangentPlane())
    super().__init__(object_id, lock_type)
    self.__points = None
    self.__facets = None
    self.__planar_colour = None
    self.__dip = None
    self.__dip_direction = None
    self.__length = None
    self.__area = None
    self.__location = None

  @classmethod
  def static_type(cls):
    return Modelling().TangentPlaneType()

  @property
  def planar_points(self):
    """The points used to define the discontinuity. This is an array of
    floats of shape (n, 3) where n is the planar_point_count. These points
    are coplanar.

    When set the first three of these points are used to define the dip
    and dip direction. If the first three points are collinear, the resulting
    discontinuity object will be empty.

    Raises
    ------
    ValueError
      If set to an array containing less than three points.

    """
    if self.__points is None:
      self.__points = self._get_points()
    return self.__points

  @planar_points.setter
  def planar_points(self, new_points):
    points = trim_pad_2d_array(new_points, -1, 3, 0).astype(ctypes.c_double)
    if points.shape[0] < 3:
      raise ValueError("Insufficient points to define a discontinuity.")
    self.__points = points

  @property
  def planar_point_count(self):
    """The number of points used to visualize the discontinuity."""
    return self.planar_points.shape[0]

  @property
  def planar_facets(self):
    """The facets used to visualise the discontinuity. These are derived
    from the points and do not support direct assignment.

    If you change planar_points, the corresponding changes to the
    planar_facets will not occur until save() is called.

    """
    if self.__facets is None:
      self.__facets = self._get_facets()
    return self.__facets

  @property
  def planar_facet_count(self):
    """The count of facets used to visualise the discontinuity."""
    return self.planar_facets.shape[0]

  @property
  def planar_colour(self):
    """The colour of the facets. This is a single value used for all facets.

    The alpha value has no effect. This is provided as an RGBA colour for
    consistency.

    """
    if self.__planar_colour is None:
      # Only the first facet colour is used for discontinuities.
      point_colours = self._get_point_colours()
      if len(point_colours) > 0:
        self.__planar_colour = point_colours[0]
      else:
        self.__planar_colour = np.array([0, 255, 0, 255])
    return self.__planar_colour

  @planar_colour.setter
  def planar_colour(self, new_colour):
    colour = convert_to_rgba(new_colour)
    self.__planar_colour = colour

  @property
  def dip(self):
    """The dip of the discontinuity. This is the angle in radians the
    discontinuity is rotated by in the dip direction.

    The dip and dip direction, taken together, define the plane the
    discontinuity lies in. If they are changed, upon save() the planar_points
    will be projected to lie on the new plane.

    Raises
    ------
    ValueError
      If set to an value which cannot be converted to a float, or is
      below zero or greater than pi / 2.

    Warnings
    --------
    Dip values close to zero cause issues with calculating the dip
    direction which can result in unintuitive behaviour.

    """
    if self.__dip is None:
      self._get_orientation()
    return self.__dip

  @dip.setter
  def dip(self, new_dip):
    dip = float(new_dip)
    if dip < 0 or dip > math.pi / 2:
      raise ValueError(f"Invalid dip: {dip}. Dip must be in [0, {math.pi / 2}]")
    self.__dip = dip

  @property
  def dip_direction(self):
    """The dip direction of the discontinuity. This is the angle in radians
    around the z axis which the plane is rotated by dip radians.

    The dip and dip direction, taken together, define the plane the
    discontinuity lies in. If they are changed, upon save() the planar_points
    will be projected to lie on the new plane.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float, or is
      below zero or greater than or equal to 2 * pi.

    Notes
    -----
    For completely horizontal discontinuities, this may be NaN.

    """
    if self.__dip_direction is None:
      self._get_orientation()
    return self.__dip_direction

  @dip_direction.setter
  def dip_direction(self, new_direction):
    direction = float(new_direction)
    if direction < 0 or direction >= math.pi * 2:
      raise ValueError(f"Invalid dip direction: {direction}. "
                       f"Dip direction must be in [0, {math.pi * 2})")
    self.__dip_direction = direction

  @property
  def strike(self):
    """The strike of the discontinuity. This is the angle in radians to the
    y axis of the line of intersection between the discontinuity plane and the
    horizontal plane (XY plane).

    This is derived from the dip direction. Changing the dip direction
    will change the strike and vice versa.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float, or is
      below zero or greater than or equal to 2 * pi.

    Notes
    -----
    For completely horizontal discontinuities, this may be NaN.

    """
    strike = self.dip_direction - math.pi / 2
    if strike < 0:
      strike += math.pi * 2
    return strike

  @strike.setter
  def strike(self, strike):
    new_strike = float(strike)
    if strike < 0 or strike >= math.pi * 2:
      raise ValueError(f"Invalid strike: {strike}. "
                       f"Strike must be in [0, {math.pi * 2})")
    dip_direction = new_strike + math.pi / 2
    if dip_direction >= math.pi * 2:
      dip_direction -= math.pi * 2
    self.dip_direction = dip_direction

  @property
  def plunge(self):
    """The plunge angle of the discontinuity.

    This is derived from the dip - changing the dip will change the plunge
    and vice versa.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float, or is
      below zero or greater than pi / 2.

    Notes
    -----
    The dip and plunge for a discontinuity always add up to pi / 2.

    """
    return (math.pi / 2) - self.dip

  @plunge.setter
  def plunge(self, plunge):
    new_plunge = float(plunge)
    if new_plunge < 0 or new_plunge > math.pi / 2:
      raise ValueError(f"Invalid plunge: {plunge}. "
                       f"Plunge must be in [0, {math.pi / 2})")
    self.dip = (math.pi / 2) - new_plunge

  @property
  def trend(self):
    """The trend of the discontinuity in radians.

    This is derived from the dip direction. Changing the dip direction
    will change the trend and vice versa.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float, or is
      below zero or greater than or equal to pi * 2.

    """
    trend = self.dip_direction + math.pi
    if trend >= math.pi * 2:
      trend -= math.pi * 2
    return trend

  @trend.setter
  def trend(self, trend):
    new_trend = float(trend)
    if new_trend < 0 or new_trend >= math.pi * 2:
      raise ValueError(f"Invalid trend: {trend}. "
                       f"Trend must be in [0, {math.pi * 2})")
    dip_direction = new_trend - math.pi
    if dip_direction < 0:
      dip_direction += math.pi * 2
    self.dip_direction = dip_direction

  @property
  def length(self):
    """The length of the discontinuity. This is the diameter of the smallest
    sphere capable of containing all of the points.

    Notes
    -----
    For empty discontinuities, the length will be NaN.

    """
    if self.__length is None:
      self.__length = Modelling().TangentPlaneGetLength(self._lock.lock)
    return self.__length

  @property
  def location(self):
    """The location of the discontinuity in the form [X, Y, Z].

    By default, this is the mean of the points used to construct the
    discontinuity.

    Notes
    -----
    For empty discontinuities, this will be NaN.

    """
    if self.__location is None:
      self.__location = Modelling().TangentPlaneGetLocation(self._lock.lock)
    return self.__location

  @location.setter
  def location(self, new_location):
    self.__location = trim_pad_1d_array(new_location, 3, 0)

  @property
  def area(self):
    """The scaled area of the discontinuity.

    Changes to the area will not occur until save() is called. This may not
    be exactly equal to the area of the planar facets.

    """
    if self.__area is None:
      self.__area = Modelling().TangentPlaneGetArea(self._lock.lock)
    return self.__area

  def _invalidate_properties(self):
    self.__points = None
    self.__facets = None
    self.__planar_colour = None
    self.__dip = None
    self.__dip_direction = None
    self.__length = None
    self.__location = None
    self.__area = None

  def save(self):
    if self.lock_type is LockType.READ:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

    if self.__points is not None:
      Modelling().SetTangentPlaneFromPoints(self._lock.lock,
                                            self.planar_points)

    if self.__dip is not None or self.__dip_direction is not None:
      Modelling().TangentPlaneSetOrientation(self._lock.lock,
                                             self.dip,
                                             self.dip_direction)

    if self.__location is not None:
      Modelling().TangentPlaneSetLocation(self._lock.lock, *self.location)

    if self.__planar_colour is not None:
      colour = (ctypes.c_uint8 * 4)()
      colour[:] = self.planar_colour
      # As only the first point colour is used so set using uniform
      # point colour.
      Modelling().SetUniformPointColour(self._lock.lock,
                                        colour)

    self._reconcile_changes()
    self._invalidate_properties()

  def _get_orientation(self):
    """Retrieves the dip and dip direction from the project and stores
    them in __dip and __dip_direction.

    """
    orientation = Modelling().TangentPlaneGetOrientation(self._lock.lock)
    # Make sure not to overwrite values set by the setter.
    if self.__dip is None:
      self.__dip = orientation[0]
    if self.__dip_direction is None:
      self.__dip_direction = orientation[1]
