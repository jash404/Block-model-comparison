"""Scan data types.

This contains data types designed for representing data from LiDAR scanners.
Currently, this only includes the generic Scan class, but may be expanded
in the future to support other types of scans.

"""

###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################
import ctypes
import logging
import numpy as np

from .base import Topology
from .errors import (CannotSaveInReadOnlyModeError, DegenerateTopologyError,
                     ReadOnlyError)
from .rotation import RotationMixin
from .objectid import ObjectID
from .primitives import PointProperties, CellProperties
from ..capi import Scan as ScanAPI
from ..common import trim_pad_1d_array
from ..internal.lock import LockType, WriteLock
from ..internal.rotation import Rotation
from ..internal.util import cartesian_to_spherical, array_of_pointer

log = logging.getLogger("mapteksdk.data.scan")

class Scan(Topology, PointProperties, CellProperties, RotationMixin):
  """Class optimised for storing scans made by 3D laser scanners.

  The Cartesian points of a scan are derived from the point_ranges,
  vertical_angles and the horizontal_angles.

  When a scan is created you can populate the points instead of the
  point_ranges, vertical_angles and horizontal_angles. If you populate
  both then the point_ranges, vertical_angles and horizontal_angles will
  be ignored in favour of the points.

  When a scan is created if the dimensions parameter is not specified,
  then it is considered to have one row with point_count columns and all
  points within the scan are considered valid. This is the simplest
  method of creating a scan; however, such scans have no cells.

  If the dimensions parameter is specified to be
  (major_dimension_count, minor_dimension_count) but the
  point_validity parameter is not specified, then the points of the
  scan are expected to be arranged in a grid with the specified number
  of major and minor dimensions and all points in the grid should be finite.
  Scans created by the SDK are always row-major. The major dimension count
  should always correspond to the row count and the minor dimension count
  should always correspond to the column count.

  If the dimensions parameter is specified to be
  (major_dimension_count, minor_dimension_count) and the point_validity
  parameter is specified and contains a non-true value, then some of the
  points in the underlying cell network are considered invalid.

  Scans possess three types of properties:

  - Point properties.
  - Cell properties.
  - Cell point properties.

  Point properties are associated with the valid points.
  They start with 'point' and have point_count values - one value
  for each valid point.

  Cell properties start with 'cell' and should have cell_count values - one
  value for each cell in the scan. All cell property arrays will return a
  zero-length array before save() has been called.

  Cell point properties are a special type of cell and point properties.
  They start with 'cell_point' (with the exclusion of horizontal_angles
  and vertical_angles) and have cell_point_count values - one value for each
  point in the underlying cell network, including invalid points.

  Parameters
  ----------
  dimensions : Iterable
    Iterable containing two integers representing the major and minor
    dimension counts of the cell network. If specified, the points of the scan
    are expected to be organised in a grid with the specified number
    of major and minor dimensions.
    If this is not specified, then the scan is considered to have
    one row with an unspecified number of columns. In this case, the column
    count is determined upon save() to be equal to the point_count.

  point_validity : numpy.ndarray
    Array of length major_dimension_count * minor_dimension_count of
    booleans. True indicates the point is valid, False indicates the
    point is invalid.

  Raises
  ------
  DegenerateTopologyError
    If a value in dimensions is lower than 1.
  ValueError
    If a value in dimensions cannot be converted to an integer.
  ValueError
    If a value in point_validity cannot be converted to a bool.
  ValueError
    If point_validity does not have one value for each point.
  TypeError
    If dimensions is not iterable.
  RuntimeError
    If point_validity is specified but dimensions is not.

  Warnings
  --------
  Creating a scan using Cartesian points will result in a loss of
  precision. The final points of the scan will not be exactly equal to
  the points used to create the scan.

  See Also
  --------
  mapteksdk.data.points.PointSet : Accurate storage for Cartesian points.

  Notes
  -----
  The points of a scan can only be set on new scans. Setting the points
  on non-new scans will be ignored. Because scans have different
  behaviour when opened with project.new() versus project.edit(),
  you should never open a scan with project.new_or_edit().

  Rotating a scan does not change the horizontal_angles, vertical_angles
  or point ranges. Once save() is called the rotation will be applied
  to the cartesian points of the scan.

  Examples
  --------
  Create a scan using Cartesian coordinates. Note that when the points
  are read from the scan, they will not be exactly equal to the points
  used to create the scan.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Scan
  >>> project = Project()
  >>> with project.new("scans/cartesian_scan", Scan) as new_scan:
  >>>     new_scan.points = [[1, 2, 4], [3, 5, 7], [6, 8, 9]]

  Create a scan using spherical coordinates.

  >>> import math
  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Scan
  >>> project = Project()
  >>> with project.new("scans/spherical_scan", Scan) as new_scan:
  >>>     new_scan.point_ranges = [2, 16, 34, 12]
  >>>     new_scan.horizontal_angles = [3 * math.pi / 4, math.pi / 4,
  >>>                                   -math.pi / 4, - 3 * math.pi / 4]
  >>>     new_scan.vertical_angles = [math.pi / 4] * 4
  >>>     new_scan.max_range = 50
  >>>     new_scan.intensity = [256, 10000, 570, 12]
  >>>     new_scan.origin = [-16, 16, -16]

  Create a scan with the dimensions of the scan specified. This example
  creates a scan with four rows and five columns of points which form
  three rows and four columns of cells. Unlike the above two examples,
  this scan has cells and after save() has been called, its cell properties
  can be accessed.

  >>> import numpy as np
  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Scan
  >>> project = Project()
  >>> dimensions = (4, 5)
  >>> # Each line represents one row of points in the scan.
  >>> ranges = [10.8, 11.2, 10.7, 10.6, 10.8,
  ...           9.3, 10.3, 10.8, 10.6, 11.1,
  ...           9.2, 10.9, 10.7, 10.7, 10.9,
  ...           9.5, 11.2, 10.6, 10.6, 11.0]
  >>> horizontal_angles = [-20, -10, 0, 10, 20,
  ...                      -20, -10, 0, 10, 20,
  ...                      -20, -10, 0, 10, 20,
  ...                      -20, -10, 0, 10, 20]
  >>> vertical_angles = [-20, -20, -20, -20, -20,
  ...                    -10, -10, -10, -10, -10,
  ...                    0, 0, 0, 0, 0,
  ...                    10, 10, 10, 10, 10]
  >>> with project.new("scans/example", Scan(dimensions=dimensions),
  ...         overwrite=True) as example_scan:
  ...     example_scan.point_ranges = ranges
  ...     example_scan.horizontal_angles = np.deg2rad(horizontal_angles)
  ...     example_scan.vertical_angles = np.deg2rad(vertical_angles)
  ...     example_scan.origin = [0, 0, 0]
  >>> # Make all cells visible.
  >>> with project.edit(example_scan.id) as edit_scan:
  >>>     edit_scan.cell_visibility[:] = True

  If the dimensions of a scan are specified, the point_validity can
  also be specified. For any value where the point_validity is false,
  values for point properties (such as point_range) are not stored.

  >>> import numpy as np
  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Scan
  >>> project = Project()
  >>> dimensions = (5, 5)
  >>> # Each line represents one row of points in the scan.
  >>> # Note that rows containing invalid points have fewer values.
  >>> ranges = [10.7, 10.6, 10.8,
  ...           10.3, 10.8, 10.6,
  ...           9.2, 10.9, 10.7, 10.7, 10.9,
  ...           9.5, 11.2, 10.6, 10.6,
  ...           9.1, 9.4, 9.2]
  >>> horizontal_angles = [-20, -10, 0, 10, 20,
  ...                      -20, -10, 0, 10, 20,
  ...                      -20, -10, 0, 10, 20,
  ...                      -20, -10, 0, 10, 20,
  ...                      -20, -10, 0, 10, 20,]
  >>> vertical_angles = [-20, -20, -20, -20, -20,
  ...                    -10, -10, -10, -10, -10,
  ...                    0, 0, 0, 0, 0,
  ...                    10, 10, 10, 10, 10,
  ...                    20, 20, 20, 20, 20,]
  >>> point_validity = [False, False, True, True, True,
  ...                   False, True, True, True, False,
  ...                   True, True, True, True, True,
  ...                   True, True, True, True, False,
  ...                   True, True, True, False, False]
  >>> with project.new("scans/example_with_invalid", Scan(
  ...         dimensions=dimensions, point_validity=point_validity
  ...         ), overwrite=True) as example_scan:
  ...     example_scan.point_ranges = ranges
  ...     example_scan.horizontal_angles = np.deg2rad(horizontal_angles)
  ...     example_scan.vertical_angles = np.deg2rad(vertical_angles)
  ...     example_scan.origin = [0, 0, 0]
  >>> # Make all cells visible.
  >>> with project.edit(example_scan.id) as edit_scan:
  ...     edit_scan.cell_visibility[:] = True

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE, *,
               dimensions=None, point_validity=None):
    self.__is_new_scan = False
    if object_id:
      super().__init__(object_id, lock_type)
    else:
      object_id = ObjectID(ScanAPI().NewScan())
      super().__init__(object_id, lock_type)
      self.__is_new_scan = True

    self.__origin = None
    self.__ranges = None
    self.__horizontal_angles = None
    self.__vertical_angles = None
    self.__point_intensity = None
    self.__major_dimension_count = None
    self.__minor_dimension_count = None
    self.__max_range = None
    self.__point_validity = None
    self.__is_column_major = None
    self.__point_count = None
    if self.__is_new_scan and dimensions is not None:
      major_count = int(dimensions[0])
      minor_count = int(dimensions[1])
      if major_count < 1 or minor_count < 1:
        raise DegenerateTopologyError(
          f"Invalid dimensions for scans: {dimensions}. "
          "Scans must contain at least one row and column.")
      self.__major_dimension_count = major_count
      self.__minor_dimension_count = minor_count
      initial_validity = np.full((self.cell_point_count), True, ctypes.c_bool)
      if point_validity is not None:
        initial_validity[:] = point_validity
      initial_validity.flags.writeable = False
      self.__point_count = np.count_nonzero(initial_validity)
      self.__point_validity = initial_validity
    if dimensions is None and point_validity is not None:
      raise RuntimeError("point_validity requires dimensions to be set.")

  @classmethod
  def static_type(cls):
    """Return the type of scan as stored in a Project.

    This can be used for determining if the type of an object is a scan.

    """
    return ScanAPI().ScanType()

  @property
  def point_count(self):
    """Returns the number of points.

    For scans, point_count returns the number of valid points in the
    scan. If the scan contains invalid points then this will be
    less than cell_point_count.

    Warnings
    --------
    For new scans, if the points are not set but the ranges, horizontal_angles
    and vertical angles are, then this will not correspond to the number
    of points in the points property.

    """
    # Use the point count for non-new scans.
    if not self.__is_new_scan:
      return super().point_count
    # If the user has specified the point_validity, use the count of
    # valid points.
    if self.__point_count is not None:
      return self.__point_count
    # The dimensions were unspecified, but the user has set points.
    # Assume all points are valid.
    if super().point_count != 0:
      return super().point_count
    # The dimensions were unspecified, but the user has set ranges/vertical/
    # horizontal angles. Assume all points are valid.
    # The angle count is considered more important than the range count.
    angle_count = max(self.vertical_angles.shape[0],
                      self.horizontal_angles.shape[0])
    if angle_count != 0:
      return angle_count
    return self.point_ranges.shape[0]

  @property
  def point_ranges(self):
    """List of floats representing the distance of the points from
    the scan origin with one value per valid point.
    Any range value greater than max_range() will be set to max_range()
    when save() is called.

    The ranges array can only be assigned when the scan is first created.
    After creation, values within the range array can be only changed via
    assignment and operations which work in-place on the array.

    If the dimensions were specified in the constructor, then this must
    have one value per valid point.

    When save() is called, if there are less point_ranges than
    vertical_angles or horizontal_angles the ranges will be padded with zeroes.
    If there are more ranges than angles, the ranges will be truncated to be
    the same length as the angles arrays.

    Raises
    ------
    ReadOnlyError
      If attempting to edit while they are read-only.
    ValueError
      If new value cannot be converted to a np.array of 32-bit floats.
    DegenerateTopologyError
      If dimensions was passed to the constructor and the number of ranges
      is set to be not equal to the point_count.

    Warnings
    --------
    When creating a new scan, you should either set the points or the
    ranges, vertical angles and horizontal angles. If you set both,
    the points will be saved and the ranges ignored.

    """
    if self.__ranges is None:
      if self.__is_new_scan:
        self.__ranges = np.zeros(0, ctypes.c_float)
      else:
        self.__ranges = self._get_ranges()
    return self.__ranges

  @point_ranges.setter
  def point_ranges(self, value):
    if not self.__is_new_scan:
      raise ReadOnlyError("Ranges can only be assigned for new scans. "
                          "Values can still be assigned directly.")
    if value is None:
      self.__ranges = None
    else:
      if self.__dimensions_known:
        self.__ranges = np.zeros(self.point_count, ctypes.c_float)
        try:
          self.__ranges[:] = value
        except ValueError as error:
          raise DegenerateTopologyError(
            f"Scan requires {self.point_count} valid ranges. "
            f"Given: {len(value)}") from error
      else:
        self.__ranges = np.array(value, dtype=ctypes.c_float).ravel()

  @property
  def horizontal_angles(self):
    """List of horizontal angles of the points. This is the azimuth
    of the point measured clockwise from the Y axis.

    The horizontal angles can only be set when the scan is first created. Once
    save() has been called they become read-only. When save() is called,
    if there are more horizontal angles than vertical angles this will be
    padded with zeroes to be the same length.

    If the dimensions were specified in the constructor, then this must
    have cell_point_count values.

    Raises
    ------
    ReadOnlyError
      If attempting to edit while they are read-only.
    ValueError
      If new value cannot be converted to a np.array of 32 bit floats.
    DegenerateTopologyError
      If dimensions was passed to the constructor and this is set to
      a value with less than cell_point_count values.

    Warnings
    --------
    When creating a new scan, you should either set the points or set the
    ranges, vertical angles and horizontal angles. If you set both,
    the points will be saved and the ranges ignored.

    Notes
    -----
    Technically this should be cell_point_horizontal_angles, however
    it has been shortened to horizontal_angles. This should
    have cell_point_count values.

    This array contains values for invalid points, however the value
    for an invalid point is unspecified and may be NAN (Not A Number).
    It is not recommended to use invalid angles in algorithms.

    """
    if self.__horizontal_angles is None:
      if self.__is_new_scan:
        self.__horizontal_angles = np.array([])
      else:
        self.__horizontal_angles = self._get_horizontal_angles()
    return self.__horizontal_angles

  @horizontal_angles.setter
  def horizontal_angles(self, value):
    if not self.__is_new_scan:
      raise ReadOnlyError("Horizontal angles can only be set for new scans.")
    if value is None:
      self.__horizontal_angles = None
    else:
      if self.__dimensions_known:
        self.__horizontal_angles = np.zeros(self.cell_point_count)
        try:
          self.__horizontal_angles[:] = value
        except ValueError as error:
          raise DegenerateTopologyError(
            f"Scan requires {self.cell_point_count} valid horizontal angles. "
            f"Given: {len(value)}") from error
      else:
        self.__horizontal_angles = np.array(value,
                                            dtype=ctypes.c_float).ravel()

  @property
  def vertical_angles(self):
    """List of vertical angles of the points. This is the elevation angle
    in the spherical coordinate system.

    The vertical_angles can only be set when the scan is first created. Once
    save() has been called they become read-only. When save() is called,
    if there are more vertical angles than horizontal angles this will be
    padded with zeroes to be the same length.

    If the dimensions were specified in the constructor, then this must
    have cell_point_count values.

    Raises
    ------
    ReadOnlyError
      If attempting to edit when the vertical angles are read-only.
    ValueError
      If new value cannot be converted to a np.array of 32 bit floats.
    DegenerateTopologyError
      If dimensions was passed to the constructor and this is set to
      a value with less than cell_point_count values.

    Warnings
    --------
    When creating a new scan, you should either set the points or set the
    ranges, vertical angles and horizontal angles. If you set both,
    the points will be saved and the vertical angles ignored.

    Notes
    -----
    Technically this should be cell_point_vertical_angles, however
    it has been shortened to vertical_angles. This should
    have cell_point_count values.

    This array contains values for invalid points, however the value
    for an invalid point is unspecified and may be NAN (Not A Number).
    It is not recommended to use invalid angles in algorithms.

    """
    if self.__vertical_angles is None:
      if self.__is_new_scan:
        self.__vertical_angles = np.array([])
      else:
        self.__vertical_angles = self._get_vertical_angles()
    return self.__vertical_angles

  @vertical_angles.setter
  def vertical_angles(self, value):
    if not self.__is_new_scan:
      raise ReadOnlyError("Vertical angles can only be set for new scans.")
    if value is None:
      self.__vertical_angles = None
    else:
      if self.__dimensions_known:
        self.__vertical_angles = np.zeros(self.cell_point_count)
        try:
          self.__vertical_angles[:] = value
        except ValueError as error:
          raise DegenerateTopologyError(
            f"Scan requires {self.cell_point_count} valid vertical ranges. "
            f"Given: {len(value)}") from error
      else:
        self.__vertical_angles = np.array(value, dtype=ctypes.c_float).ravel()

  @property
  def __dimensions_known(self):
    """Returns True if the major and minor dimension counts for the
    scan are known.

    """
    return self.__major_dimension_count is not None and \
           self.__major_dimension_count is not None

  @property
  def major_dimension_count(self):
    if self.__major_dimension_count is None:
      if not self.__is_new_scan:
        self.__major_dimension_count = super().major_dimension_count
      else:
        # If the major dimension count was not set in the constructor,
        # then the scan will have one major dimension.
        self.__major_dimension_count = 1
    return self.__major_dimension_count

  @property
  def minor_dimension_count(self):
    if self.__minor_dimension_count is None:
      if not self.__is_new_scan:
        self.__minor_dimension_count = super().minor_dimension_count
      else:
        if self.point_count != 0:
          # If the minor dimension count was not set in the constructor,
          # then the scan will have one minor dimension for each valid point.
          self.__minor_dimension_count = self.point_count
        else:
          self.__minor_dimension_count = self.point_ranges.shape[0]
    return self.__minor_dimension_count

  @property
  def row_count(self):
    """The number of rows in the underlying cell network. Note that this
    is the logical count of the rows. This will only correspond to the
    major dimension for the underlying array if is_column_major() returns
    false.

    Notes
    -----
    Scans appear 'flattened' when read in the Python SDK -
    a scan with ten rows and ten columns of points will appear as a
    flat array containing one hundred points.

    """
    if self.__is_column_major:
      return self.minor_dimension_count
    return self.major_dimension_count

  @property
  def column_count(self):
    """The number of columns in the underlying cell network. Note
    that this is the logical count of the columns. This will only
    correspond to the minor dimension for the underlying array if
    is_column_major() returns false.

    """
    if self.__is_column_major:
      return self.major_dimension_count
    return self.minor_dimension_count

  @property
  def origin(self):
    """The origin of the scan represented as a point. This should be
    set to the location of the scanner when the scan was taken (if known).

    When creating a scan using Cartesian coordinates, if the origin
    is not set it will default to the centroid of the points. Changing the
    origin in this case will not change the points.

    When creating a scan using point_range, horizontal_angles and
    vertical_angles the origin will default to [0, 0, 0]. Changing the
    origin in this case will cause the points to be centred around the new
    origin.

    Editing the origin will translate the scan by the difference between
    the new origin and the old origin.

    Notes
    -----
    Points which are far away from the origin may suffer precision issues.

    Examples
    --------
    Set the origin of a scan creating using ranges and angles and print
    the points. The origin is set to [1, 1, 1] so the final points are
    translated by [1, 1, 1].

    >>> import math
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Scan
    >>> project = Project()
    >>> with project.new("scans/angle_scan", Scan) as new_scan:
    ...     new_scan.point_ranges = [1, 1, 1, 1]
    ...     new_scan.horizontal_angles = [math.pi / 4, math.pi * 0.75,
    ...                                   -math.pi / 4, -math.pi * 0.75]
    ...     new_scan.vertical_angles = [0, 0, 0, 0]
    ...     new_scan.origin = [1, 1, 1]
    >>> with project.read("scans/angle_scan") as read_scan:
    ...     print(read_scan.points)
    [[1.70710668 1.70710688 1.00000019]
     [1.70710681 0.29289325 1.00000019]
     [0.29289332 1.70710688 1.00000019]
     [0.29289319 0.29289325 1.00000019]]

    Unlike for spherical coordinates, Cartesian coordinates are round
    tripped. This means that setting the origin in new() will not
    translate the points.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Scan
    >>> project = Project()
    >>> with project.new("scans/point_scan", Scan) as new_scan:
    ...     new_scan.points = [[1, 1, 1], [-1, 1, 2], [1, -1, 3], [-1, -1, 4]]
    ...     new_scan.origin = [2, 2, 2]
    >>> with project.read("scans/point_scan") as read_scan:
    ...     print(read_scan.points)
    [[ 0.99999997  1.00000006  1.00000008]
     [-1.00000002  1.0000001   2.00000059]
     [ 0.99999975 -1.00000013  2.99999981]
     [-1.00000004 -0.99999976  4.00000031]]

    However changing the origin in edit will always translate the points.
    By changing the origin from [2, 2, 2] to [-2, -2, -2] the x, y and z
    coordinates of the scan are each reduced by four.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.edit("scans/point_scan") as edit_scan:
    ...     edit_scan.origin = [-2, -2, -2]
    >>> with project.read("scans/point_scan") as read_scan:
    ...     print(read_scan.points)
    [[-3.00000003 -2.99999994 -2.99999992]
     [-5.00000002 -2.9999999  -1.99999941]
     [-3.00000025 -5.00000013 -1.00000019]
     [-5.00000004 -4.99999976  0.00000031]]

    """
    if self.__origin is None:
      self.__origin = self._get_origin()
    return self.__origin

  @origin.setter
  def origin(self, new_origin):
    if new_origin is None:
      self.__origin = np.array([0, 0, 0], ctypes.c_double)
    else:
      self.__origin = trim_pad_1d_array(
        new_origin, 3, 0).astype(ctypes.c_double)

  @property
  def max_range(self):
    """The maximum range the generating scanner is capable of. This is used
    to normalise the ranges to allow for more compact storage.
    Any point further away from the origin will have its range set to this
    value when save() is called.

    If this is not set when creating a new scan, it will default to the
    maximum distance of any point from the origin.

    This can only be set for new scans.

    Raises
    ------
    ReadOnlyError
      If user attempts to set when this value is read-only.

    """
    if self.__max_range is None:
      if self.__is_new_scan:
        self.__max_range = max(self.point_ranges, default=0)
      else:
        self.__max_range = self._get_max_range()
    return self.__max_range

  @max_range.setter
  def max_range(self, new_max_range):
    if not self.__is_new_scan:
      raise ReadOnlyError("Max range can only be set for new scans.")
    self.__max_range = float(new_max_range)

  @property
  def cell_point_validity(self):
    """A list of booleans specifying which items in the underlying cell network
    are valid. Invalid points are not stored (and thus do not require
    point properties, such as colour to be stored for them).

    Examples
    --------
    If this is set in the constructor, point properties such as ranges
    and point_colours should have one value for each True in this
    array. This is shown in the below example:

    >>> import numpy as np
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Scan
    >>> project = Project()
    >>> dimensions = (5, 5)
    >>> # Each line represents one row of points in the scan.
    >>> # Note that rows containing invalid points have fewer values.
    >>> ranges = [10.7, 10.6, 10.8,
    ...           10.3, 10.8, 10.6,
    ...           9.2, 10.9, 10.7, 10.7, 10.9,
    ...           9.5, 11.2, 10.6, 10.6,
    ...           9.1, 9.4, 9.2]
    >>> horizontal_angles = [-20, -10, 0, 10, 20,
    ...                      -20, -10, 0, 10, 20,
    ...                      -20, -10, 0, 10, 20,
    ...                      -20, -10, 0, 10, 20,
    ...                      -20, -10, 0, 10, 20,]
    >>> vertical_angles = [-20, -20, -20, -20, -20,
    ...                    -10, -10, -10, -10, -10,
    ...                    0, 0, 0, 0, 0,
    ...                    10, 10, 10, 10, 10,
    ...                    20, 20, 20, 20, 20,]
    >>> red = [255, 0, 0, 255]
    >>> green = [0, 255, 0, 255]
    >>> blue = [0, 0, 255, 255]
    >>> point_colours = [red, green, blue,
    ...                  red, green, blue,
    ...                  red, green, blue, red, green,
    ...                  red, green, blue, red,
    ...                  red, green, blue]
    >>> point_validity = [False, False, True, True, True,
    ...                   False, True, True, True, False,
    ...                   True, True, True, True, True,
    ...                   True, True, True, True, False,
    ...                   True, True, True, False, False]
    >>> with project.new("scans/example_with_invalid_and_colours", Scan(
    ...         dimensions=dimensions, point_validity=point_validity
    ...         ), overwrite=True) as example_scan:
    ...     # Even though no points have been set, because point_validity was
    ...     # specified in the constructor point_count will return
    ...     # the required number of valid points.
    ...     print(f"Point count: {example_scan.point_count}")
    ...     # The scan contains invalid points, so cell_point_count
    ...     # will be lower than the point count.
    ...     print(f"Cell point count: {example_scan.cell_point_count}")
    ...     example_scan.point_ranges = ranges
    ...     example_scan.horizontal_angles = np.deg2rad(horizontal_angles)
    ...     example_scan.vertical_angles = np.deg2rad(vertical_angles)
    ...     example_scan.origin = [0, 0, 0]
    ...     example_scan.point_colours = point_colours
    Point count: 18
    Cell point count: 25

    This property can also be used to filter out angles from invalid
    points so that they are not used in algorithms. This example calculates
    the average vertical and horizontal angles for valid points for the
    scan created in the previous example. Make sure to run the previous
    example first.

    >>> import math
    >>> import numpy as np
    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.read("scans/example_with_invalid_and_colours") as scan:
    ...     validity = scan.cell_point_validity
    ...     valid_vertical_angles = scan.vertical_angles[validity]
    ...     mean_vertical_angles = math.degrees(np.mean(valid_vertical_angles))
    ...     valid_horizontal_angles = scan.horizontal_angles[validity]
    ...     mean_horizontal_angles = math.degrees(np.mean(
    ...         valid_horizontal_angles))
    ...     print(f"Average vertical angle: {mean_vertical_angles}")
    ...     print(f"Average horizontal angle: {mean_horizontal_angles}")
    Average vertical angle: 0.5555580888570226
    Average horizontal angle: -1.1111082803078174

    """
    if self.__point_validity is None:
      if not self.__is_new_scan:
        self.__point_validity = self._get_point_validity()
      else:
        self.__point_validity = np.full((self.cell_point_count),
                                        True,
                                        ctypes.c_bool)
    return self.__point_validity

  @property
  def point_intensity(self):
    """A list containing the intensity of the points - one value for
    each valid point.

    Each intensity value is represented as a 16 bit unsigned
    integer and should be between 0 and 65535 (inclusive). If the
    value is outside of this range, integer overflow will occur.

    """
    if self.__point_intensity is None:
      self.__point_intensity = self._get_intensity()
    return self.__point_intensity

  @point_intensity.setter
  def point_intensity(self, new_intensity):
    self.__point_intensity = np.array(new_intensity,
                                      dtype=ctypes.c_uint16).ravel()

  @property
  def is_column_major(self):
    """True if the scan is stored in a column major cell network.

    All scans created via the SDK will be in row-major order.

    """
    if self.__is_column_major is None:
      self.__is_column_major = self._get_is_column_major()
    return self.__is_column_major

  @property
  def _can_set_points(self):
    """Returns True if the scan is new and thus if the points can
    be set.

    """
    return self.__is_new_scan

  def save(self):
    if isinstance(self._lock, WriteLock):
      if self.__is_new_scan:
        # If the user has set points, convert them to ranges and angles so
        # that they can be saved.
        if super().point_count != 0:
          if self.__origin is None:
            self.origin = np.mean(self.points, axis=0)

          # Ensure we have the correct number of points.
          if self.point_count != super().point_count:
            raise ValueError(
              f"Scan requires {self.point_count} valid points. "
              f"Given: {self.point_count}")

          spherical_coordinates = cartesian_to_spherical(self.points,
                                                         self.origin)
          # Bypass the setter, as the output from Cartesian_to_spherical is
          # already correctly formatted.
          self.__ranges = spherical_coordinates[0]

          # The above call will only generate angles for valid points,
          # however the angles arrays must have values for invalid points.
          # This allocates an array of nan and writes the valid values to
          # the locations for the valid points.
          horizontal_angles = np.full((self.cell_point_count),
                                       np.nan,
                                       ctypes.c_float)
          horizontal_angles[self.cell_point_validity] = spherical_coordinates[1]
          self.__horizontal_angles = horizontal_angles

          vertical_angles = np.full((self.cell_point_count),
                                    np.nan,
                                    ctypes.c_float)
          vertical_angles[self.cell_point_validity] = spherical_coordinates[2]
          self.__vertical_angles = vertical_angles

        # Ensure the ranges array has one valid value for each point.
        if self.point_ranges.shape[0] != self.point_count:
          self.point_ranges = trim_pad_1d_array(self.point_ranges,
                                                self.point_count,
                                                0)

        self._save_scan_points()

      self._save_ranges(self.point_ranges)

      if self.__origin is not None:
        self._set_origin(self.origin)

      if self.__point_intensity is not None:
        self._save_intensity(self.point_intensity)

      if self._rotation_cached:
        self._save_rotation(self._rotation)

      self._save_point_properties()
      self._save_cell_properties()
      self._reconcile_changes()
      self.__is_new_scan = False
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  def _invalidate_properties(self):
    self.__origin = None
    self.__ranges = None
    self.__horizontal_angles = None
    self.__vertical_angles = None
    self.__point_intensity = None
    self.__major_dimension_count = None
    self.__minor_dimension_count = None
    self.__max_range = None
    self.__point_validity = None
    PointProperties._invalidate_properties(self)

  def _save_scan_points(self):
    """Combines several calls which are required to properly save the points
    of a scan and performs a few operations to ensure the values
    saved will be consistent. Should only be called for new scans.

    """
    point_validity = self.cell_point_validity
    # Scans created in the Python SDK are always row major.
    is_column_major = False
    self._set_scan(self.row_count, self.column_count, self.max_range,
                   point_validity, self.point_count, is_column_major)
    self._save_horizontal_angles(self.horizontal_angles)
    self._save_vertical_angles(self.vertical_angles)

  def _set_scan(self, row_count, col_count, max_range,
                validity, point_count, is_column_major):
    """Sets the scan. This allows the points, ranges, horizontal angle
    and vertical angles to be set again - after this is called you must
    call _save_ranges(), _save_vertical_angles() and _save_horizontal_angles().

    Calling this destroys all point properties (such as visibility and colour).

    Parameters
    ----------
    row_count : int
      Number of rows in the scan.
    col_count : int
      Number of columns in the scan.
    max_range : int
      Max range of the scan.
    validity : numpy.ndarray
      validity[i] = True if the ith point is valid. False otherwise.
    point_count : int
      The count of valid points in the scan.
    is_column_major : bool
      True if the scan is column major, False if the scan is row major.

    """
    c_point_validity = (ctypes.c_bool * (row_count * col_count))(*validity)

    # Set the size of the scan.
    ScanAPI().SetScan(self._lock.lock,
                      row_count,
                      col_count,
                      max_range,
                      c_point_validity,
                      point_count,
                      is_column_major)

  def _get_origin(self):
    """Gets the scan origin from the Project."""
    return np.array(ScanAPI().GetOrigin(self._lock.lock)).ravel()

  def _get_ranges(self):
    """Get the Ranges from the Project."""
    ptr = ScanAPI().PointRangesBeginR(self._lock.lock)
    ranges = self._array_to_numpy(ptr, self.point_count, ctypes.c_float)
    return ranges

  def _get_horizontal_angles(self):
    """Get the horizontal angles from the Project."""
    ptr = ScanAPI().GridHorizontalAnglesBeginR(self._lock.lock)
    angles = self._array_to_numpy(ptr,
                                  self.cell_point_count,
                                  ctypes.c_float)
    # Set the angles to not be writeable if the scan is not new.
    angles.flags.writeable = self.__is_new_scan
    return angles

  def _get_vertical_angles(self):
    """Get the vertical angles from the Project."""
    ptr = ScanAPI().GridVerticalAnglesBeginR(self._lock.lock)
    angles = self._array_to_numpy(ptr,
                                  self.cell_point_count,
                                  ctypes.c_float)
    # Set the angles to not be writeable if the scan is not new.
    angles.flags.writeable = self.__is_new_scan
    return angles

  def _get_intensity(self):
    """Gets the scan intensity from the Project."""
    ptr = ScanAPI().PointIntensityBeginR(self._lock.lock)
    intensity = self._array_to_numpy(ptr,
                                     self.point_count,
                                     ctypes.c_uint16)
    return intensity

  def _get_point_validity(self):
    """Get the point validity from the Project."""
    ptr = ScanAPI().GridPointValidReturnBeginR(self._lock.lock)
    validity = self._array_to_numpy(ptr,
                                    self.cell_point_count,
                                    ctypes.c_bool)
    return validity

  def _get_logical_dimensions(self):
    """Get the logical dimensions from the Project."""
    return ScanAPI().ReadLogicalDimensions(self._lock.lock)

  def _get_max_range(self):
    """Get the max range from the Project."""
    return ScanAPI().OperatingRange(self._lock.lock)

  def _get_is_column_major(self):
    """Get if the scan is column major from the Project."""
    return ScanAPI().IsColumnMajor(self._lock.lock)

  def _get_rotation(self):
    """Get the local to ellipsoid transfrom from the Project."""
    transform = ScanAPI().GetLocalToEllipsoidTransform(self._lock.lock)
    return Rotation(*transform[0])

  def _save_ranges(self, ranges):
    """Saves the ranges to the Project.

    Parameters
    ----------
    ranges : array_like
      The ranges to save to the Project.

    """
    c_ranges = array_of_pointer(ScanAPI().PointRangesBeginRW(self._lock.lock),
                                self.point_ranges.shape[0] * 4,
                                ctypes.c_float)

    c_ranges[:] = trim_pad_1d_array(ranges,
                                    self.point_ranges.shape[0],
                                    0).astype(ctypes.c_float, copy=False)

  def _save_horizontal_angles(self, horizontal_angles):
    """Saves the horizontal angles to the Project.

    Parameters
    ----------
    horizontal_angles : list of float
      The horizontal angles to save to the Project.

    """
    c_horizontal_angles = array_of_pointer(
      ScanAPI().GridHorizontalAnglesBeginRW(self._lock.lock),
      self.cell_point_count * 4,
      ctypes.c_float)
    c_horizontal_angles[:] = trim_pad_1d_array(
      horizontal_angles,
      self.cell_point_count,
      0).astype(ctypes.c_float, copy=False)

  def _save_vertical_angles(self, vertical_angles):
    """Saves the vertical angles to the Project.

    Parameters
    ----------
    vertical_angles : list of float
      The horizontal angles to save to the Project.

    """
    c_vertical_angles = array_of_pointer(
      ScanAPI().GridVerticalAnglesBeginRW(self._lock.lock),
      self.cell_point_count * 4,
      ctypes.c_float)
    c_vertical_angles[:] = trim_pad_1d_array(
      vertical_angles,
      self.cell_point_count,
      0).astype(ctypes.c_float, copy=False)

  def _save_intensity(self, intensity):
    """Saves the point intensity to the Project.

    Parameters
    ----------
    intensity : list of uint32
      The intensity values to save to the Project.

    """
    c_intensity = array_of_pointer(
      ScanAPI().PointIntensityBeginRW(self._lock.lock),
      self.point_ranges.shape[0] * 2,
      ctypes.c_uint16)
    c_intensity[:] = trim_pad_1d_array(
      intensity,
      self.point_ranges.shape[0],
      0).astype(ctypes.c_uint16, copy=False)

  def _set_origin(self, new_origin):
    """Saves the scan origin to the Project."""
    ScanAPI().SetOrigin(self._lock.lock,
                        new_origin[0],
                        new_origin[1],
                        new_origin[2])

  def _save_rotation(self, new_rotation):
    """Saves the scan rotation to the Project.

    Parameters
    ----------
    new_rotation : Rotation
      The rotation object to set the rotation to.

    """
    ScanAPI().SetLocalToEllipsoidTransform(self._lock.lock,
                                           new_rotation.quaternion,
                                           [0, 0, 0])
