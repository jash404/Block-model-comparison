"""Cell network data types.

Cell networks are objects which are defined by quadrilateral cell primitives.
This module only contains the GridSurface class which represents a dense
irregular cell network.

See Also
--------
mapteksdk.data.scans.Scan : Scans are also cell networks, however they are not
  included in this module due to their specialised nature.

"""
import ctypes
import logging
import warnings

import numpy as np

from ..capi import Modelling
from ..internal.lock import LockType
from ..common import trim_pad_2d_array
from .base import Topology
from .objectid import ObjectID
from .primitives import PointProperties, CellProperties
from .errors import CannotSaveInReadOnlyModeError

log = logging.getLogger("mapteksdk.data")

class GridSurface(Topology, PointProperties, CellProperties):
  """A dense irregular cell network. In Eureka these are referred to as
  grid surfaces. They are generally more compact than Surfaces and
  calculations can be performed faster on them. However they cannot represent
  surfaces with disconnected parts and do not allow holes in the surface
  (except when the surface self-intersects).

  The object will contain major_dimension_count * minor_dimension_count points
  which are used to define the cells.
  The structure contains
  (major_dimension_count - 1) * (minor_dimension_count - 1) cells -
  due to the gridded nature of the object adjacent cells share points.
  To make working with the gridded data structure easier, this object provides
  two dimensional versions of the point and cell properties. This allows
  these properties to be indexed based on the row and column of the cell
  in the grid.

  The cell in the ith row and the jth column is defined as the quadrilateral
  between cell_points[i][j], cell_points[i + 1][j], cell_points[i + 1][j + 1]
  and cell_points[i][j + 1]
  For example, the zeroth cell is between the points cell_points[0][0],
  cell_points[0][1], cell_points[1][1] and cell_points[1][0]. Cell selection
  and cell visibility map the selection and visibility to the cells in the
  same way.

  The constructor for grid surfaces can generate a regular grid (via
  the x_step and y_step parameters) in the X and Y direction. If this form
  of the constructor is used then only setting the Z values will create a
  consistent grid with no self-intersections. Use the start parameter to
  specify the start position of the grid.

  Parameters
  ----------
  major_dimension_count : int
    The number of rows used to store the grid surface.
    Note that this will only correspond to the number of rows in the
    grid surface if the points are stored in row major order.
    This is ignored if opening an existing irregular grid surface.

  minor_dimension_count : int
    The number of columns used to store the grid surface.
    Note that this will only correspond to the number of columns in the
    grid surface if the points are stored in row major order.
    This is ignored if opening an existing grid surface.

  x_step : int
    If x_step, y_step or start are specified, the constructor will set the
    points to a regular grid using this as the size of each grid square in the
    X direction. If y_step is specified this should also be specified.
    Ignored when opening an existing grid surface.
    To make scripts run faster, only specify this argument if you intend to
    use the generated regular grid.

  y_step : int
    If x_step, y_step or start are specified, the constructor will set the
    points to a regular grid using this as the size of each grid square in
    the Y direction. If x_step is specified this should also be specified.
    Ignored when opening an existing grid surface.
    To make scripts run faster, only specify this argument if you intend to
    use the generated regular grid.

  start : array_like
    If x_step, y_step or start are specified, the constructor will set the
    points to a regular grid using this as the start point of the generated
    grid. The default is [0, 0, 0]. This should only be specified if
    x_step and y_step are specified.
    Ignored when opening an existing grid surface.
    To make scripts run faster, only specify this argument if you intend to
    use the generated regular grid.

  column_major : bool
    If False (default) then the generated grid will be in row major
    order (X values change in rows, Y values in columns).
    If True the generated grid will be in column major order (Y values change
    in rows, X values in columns).
    This has no effect if x_step, y_step and start are not specified.
    Ignored when opening an existing grid surface.

  Warnings
  --------
  GridSurfaces have no protection against self-intersecting cells or
  cells intersecting each other. This can cause unintuitive index to spatial
  relationships and holes in the surface.

  Raises
  ------
  ValueError
    If major_dimension_count or minor_dimension_count are less than zero.
  TypeError
    If major_dimension_count or minor_dimension_count are not integers.

  Examples
  --------
  Creates a new grid surface using the grid constructor then sets the
  Z coordinates to be the sine of the X coordinate plus the Y coordinate.
  By using the grid constructor then setting only the Z coordinates, this
  ensures the resulting surface has no self-intersections and an intuitive
  index to spatial relationship.

  >>> import math
  >>> import numpy as np
  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import GridSurface
  >>> project = Project()
  >>> with project.new("surfaces/sin_x+y", GridSurface(
  ...         major_dimension_count=8, minor_dimension_count=8,
  ...         x_step=math.pi/4, y_step=math.pi/4)) as new_grid:
  ...     np.sin(new_grid.points[:, 1] + new_grid.points[:, 2],
  ...            out=new_grid.point_z)

  If the X and Y information is already available or does not neatly
  conform to a grid, construction of the object will be faster if the X and Y
  step parameters are not specified. In the below example the X and Y
  coordinates are not regularly spaced (as is often the case for real world
  data) so it is more efficient to not specify the x_step and y_step parameters.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import GridSurface
  >>> project = Project()
  >>> points = [[1.1, 1.15, 1.11], [1.98, 1.17, 1.08], [3.02, 1.13, 1.07],
  ...           [1.08, 1.99, 1.07], [2.01, 2.03, 1.37], [3.00, 2.11, 1.33],
  ...           [1.13, 3.08, 1.08], [2.00, 3.01, 0.99], [3.18, 3.07, 1.34]]
  >>> with project.new("surfaces/noisy", GridSurface(
  ...         major_dimension_count=3, minor_dimension_count=3
  ...         )) as new_grid:
  ...     new_grid.points = points

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE,
               major_dimension_count=None, minor_dimension_count=None,
               x_step=None, y_step=None, start=None, column_major=False):
    is_new = not object_id
    if is_new:
      # :TODO: Jayden Boskell 2021-09-15 SDK-588: Change these cases
      # to raise DegenerateTopologyError.
      if major_dimension_count is None:
        message = ("Major dimension count default argument is deprecated "
                   "and will be removed in a future version.")
        warnings.warn(DeprecationWarning(message))
        major_dimension_count = 1
      if minor_dimension_count is None:
        message = ("Minor dimension count default argument is deprecated "
                   "and will be removed in a future version.")
        warnings.warn(DeprecationWarning(message))
        minor_dimension_count = 1

      if major_dimension_count <= 0 or minor_dimension_count <= 0:
        raise ValueError("Invalid dimensions for grid surface: "
                         f"({major_dimension_count},{minor_dimension_count}).\n"
                         "Major and minor dimension count must both be greater "
                         "than zero.")
      try:
        object_id = ObjectID(Modelling().NewIrregularCellNetwork(
          major_dimension_count,
          minor_dimension_count))
      except ctypes.ArgumentError as error:
        raise TypeError("Major and minor dimension counts must be integers. "
                        f"Major Dimension Count: {major_dimension_count}, "
                        f"Minor Dimension Count: {minor_dimension_count}"
                       ) from error

      # Generate a grid if we have any info on how to generate it.
      if any((x_step, y_step, start)):
        self.points = self._generate_point_grid(major_dimension_count,
                                                minor_dimension_count,
                                                x_step, y_step, start,
                                                column_major)
      assert object_id

    # Cell properties.
    self.__cells_2d = None
    self.__cell_selection_2d = None
    self.__cell_visibility_2d = None

    # Cell point properties.
    self.__cell_points = None
    self.__cell_point_colours = None
    self.__cell_point_visibility = None
    self.__cell_point_selection = None

    super().__init__(object_id, lock_type)

  def _generate_point_grid(self, major_dimension_count, minor_dimension_count,
                           x_step, y_step, start, column_major):
    """Function for generating a grid of points.

    Parameters
    ----------
    major_dimension_count : int
      Number of items in the major dimension to generate.
    minor_dimension_count : int
      Number of items in the minor dimension to generate.
    x_step : float
      Size of each grid cell in the x direction.
    y_step : float
      Size of each grid cell in the y direction.
    start : array_like
      Point representing where to start the grid.
    column_major : bool
      True if the grid should be column major, False if it should be
      row major.

    Returns
    -------
    ndarray
      The generated grid.

    """
    if start is None:
      start = [0, 0, 0]
    x_count = major_dimension_count if column_major else minor_dimension_count
    y_count = minor_dimension_count if column_major else major_dimension_count

    if x_step:
      x_values = np.arange(start[0], start[0] + x_step * x_count,
                           x_step)
    else:
      # :TODO: Jayden Boskell 2021-09-14 SDK-588: Change this case
      # to raise DegenerateTopologyError.
      message = ("x_step default argument is deprecated and will be removed "
                 "in a future version.")
      warnings.warn(DeprecationWarning(message))
      x_values = np.repeat(start[0], x_count)

    if y_step:
      y_values = np.arange(start[1], start[1] + y_step * y_count,
                           y_step)
    else:
      # :TODO: Jayden Boskell 2021-09-14 SDK-588: Change this case
      # to raise DegenerateTopologyError.
      message = ("y_step default argument is deprecated and will be removed "
                 "in a future version.")
      warnings.warn(DeprecationWarning(message))
      y_values = np.repeat(start[1], y_count)

    z_value = start[2]

    indexing = "xy" if column_major else "ij"
    return np.array(np.meshgrid(x_values, y_values, z_value, indexing=indexing),
                    dtype=ctypes.c_double).T.reshape(-1, 3)

  @property
  def cells_2d(self):
    """The cells rearranged into rows and columns.

    GridSurface.cells_2d[i][j] will return the cell in the ith row and jth
    column.

    """
    if (self.__cells_2d is None or
        not np.may_share_memory(self.cells, self.__cells_2d)):
      self.__cells_2d = self.cells[:].reshape(self.major_dimension_count - 1,
                                              self.minor_dimension_count - 1,
                                              4)
    return self.__cells_2d

  @property
  def cell_visibility_2d(self):
    """The visibility of the cells reshaped to be a grid of size
    major_dimension_count - 1 by minor_dimension_count - 1.

    Raises
    ------
    ValueError
      If assigned a value which is not
      major_dimension_count - 1 by minor_dimension_count - 1.
    ValueError
      If set using a value which cannot be converted to a bool.

    Examples
    --------
    Set all cells along the diagonal of the grid surface to be invisible,
    then print the cell visibility.
    The loop is bounded by the lower of the major and minor dimension counts,
    so it will work even for grid surfaces which are not squares.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import GridSurface
    >>> project = Project()
    >>> with project.new("surfaces/cell_visibility", GridSurface(
    ...         major_dimension_count=5, minor_dimension_count=5,
    ...         x_step=1, y_step=1)) as new_cells:
    ...     for i in range(min(new_cells.cell_visibility_2d.shape)):
    ...         new_cells.cell_visibility_2d[i][i] = False
    ...     print(new_cells.cell_visibility_2d)
    [[False, True, True, True]
     [True, False, True, True]
     [True, True, False, True]
     [True, True, True, False]]

    Note that when the object created in the previous example is viewed
    from above, the resulting cell visibility will be mirrored on the Y axis
    to what was printed. This is because ascending y will go up the screen,
    whereas the ascending rows are printed down the screen.
    i.e. The grid surface will have the following visibility:

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.read("surfaces/cell_visibility") as read_cells:
    ...     print(read_cells.cell_visibility_2d[:, ::-1])
    [[ True  True  True False]
     [ True  True False  True]
     [ True False  True  True]
     [False  True  True  True]]

    Set a 2x2 area of cells to be invisible then print the resulting
    cell visibility.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import GridSurface
    >>> project = Project()
    >>> with project.new("surfaces/cell_visibility_2", GridSurface(
    ...         major_dimension_count=5, minor_dimension_count=5,
    ...         x_step=1, y_step=1)) as new_cells:
    ...     new_cells.cell_visibility_2d[1:3, 1:3] = [[False, False],
    ...                                               [False, False]]
    [[True, True, True, True]
     [True, False, False, True]
     [True, False, False, True]
     [True, True, True, True]]

    """
    if (self.__cell_visibility_2d is None or
        not np.may_share_memory(self.cell_visibility,
                                self.__cell_visibility_2d)):
      self.__cell_visibility_2d = self.cell_visibility[:].reshape(
        self.major_dimension_count - 1,
        self.minor_dimension_count - 1)
    return self.__cell_visibility_2d

  @cell_visibility_2d.setter
  def cell_visibility_2d(self, cell_visibility_2d):
    self.cell_visibility_2d[:] = cell_visibility_2d

  @property
  def cell_selection_2d(self):
    """The selection of the cells reshaped in a grid of size:
    major_dimension_count - 1 by minor_dimension_count - 1

    Raises
    ------
    ValueError
      If set to a value which is not
      major_dimension_count - 1 by minor_dimension_count - 1.
    ValueError
      If set using a value which cannot be converted to a bool.

    """
    if (self.__cell_selection_2d is None or
        not np.may_share_memory(self.cell_selection, self.__cell_selection_2d)):
      self.__cell_selection_2d = self.cell_selection[:].reshape(
        self.major_dimension_count - 1,
        self.minor_dimension_count - 1)
    return self.__cell_selection_2d

  @cell_selection_2d.setter
  def cell_selection_2d(self, cell_selection_2d):
    self.cell_selection_2d[:] = cell_selection_2d

  @property
  def cell_points(self):
    """A view of points reshaped to follow the underlying grid structure of
    the surface. This means that for the cell in row i and column j,
    the points which define the four corners of the cell are:
    cell_points[i][j], cell_points[i+1][j], cell_points[i+1, j+1] and
    cell_points[i][j+1].

    As this is a view of the points, any changes made to points will be
    reflected in cell_points and vice versa.

    Raises
    ------
    ValueError
      If there are not exactly major_dimension_count * minor_dimension_count
      points in the object. This will cause the reshape operation to fail.
      Calling save() will trim/pad the points to be the correct size.
    ValueError
      If set using a string which cannot be converted to a float.
    ValueError
      If set to a value which cannot be broadcast to the right shape.
    TypeError
      If set using a value which cannot be converted to a float.

    See Also
    --------
    mapteksdk.data.primitives.PointProperties.points :
      Flat array access to points.

    """
    # If points and cell_points don't share memory, then the cell_points
    # view on the array must be stale, so replace it.
    if (self.__cell_points is None or
        not np.may_share_memory(self.points, self.__cell_points)):
      # self.points[:] creates a view of the points. This view
      # is then reshaped to allow indexing via rows and columns.
      self.__cell_points = self.points[:].reshape(self.major_dimension_count,
                                                  self.minor_dimension_count,
                                                  3)
      # Assert that cell points is a view not a copy.
      assert not self.__cell_points.flags['OWNDATA']
    return self.__cell_points

  @cell_points.setter
  def cell_points(self, value):
    self.cell_points[:] = value

  @property
  def cell_point_colours(self):
    """A view of the point_colours reshaped to be major_dimension_count
    by minor_dimension_count.

    Raises
    ------
    ValueError
      If set using a string which cannot be converted to an integer.
    ValueError
      If set to a value which cannot be broadcast to the right shape.
    TypeError
      If set to a value which cannot be converted to an integer.

    See Also
    --------
    mapteksdk.data.primitives.PointProperties.point_colours :
      Flat array access to point colours.

    """
    if (self.__cell_point_colours is None or
        not np.may_share_memory(self.point_colours, self.__cell_point_colours)):
      self.__cell_point_colours = self.point_colours[:].reshape(
        self.major_dimension_count, self.minor_dimension_count,
        4)
      assert not self.__cell_point_colours.flags['OWNDATA']
    return self.__cell_point_colours

  @cell_point_colours.setter
  def cell_point_colours(self, value):
    self.cell_point_colours[:] = value

  @property
  def cell_point_visibility(self):
    """A view of the point_visibility reshaped to be major_dimension_count
    by minor_dimension_count.

    Raises
    ------
    ValueError
      If set using a value which cannot be converted to a bool.
    ValueError
      If set to a value which cannot be broadcast to the right shape.

    See Also
    --------
    mapteksdk.data.primitives.PointProperties.point_visibility :
      Flat array access to point visibility.

    """
    if (self.__cell_point_visibility is None or
        not np.may_share_memory(self.point_visibility,
                                self.__cell_point_visibility)):
      self.__cell_point_visibility = self.point_visibility[:].reshape(
        self.major_dimension_count, self.minor_dimension_count)
      assert not self.__cell_point_visibility.flags['OWNDATA']
    return self.__cell_point_visibility

  @cell_point_visibility.setter
  def cell_point_visibility(self, value):
    self.cell_point_visibility[:] = value

  @property
  def cell_point_selection(self):
    """A view of the point_selection reshaped to be major_dimension_count
    by minor_dimension_count.

    Raises
    ------
    ValueError
      If set using a value which cannot be converted to a bool.
    ValueError
      If set to a value which cannot be broadcast to the right shape.

    See Also
    --------
    mapteksdk.data.primitives.PointProperties.point_selection :
      Flat array access to point selection.

    """
    if (self.__cell_point_selection is None or
        not np.may_share_memory(self.point_selection,
                                self.__cell_point_selection)):
      self.__cell_point_selection = self.point_selection[:].reshape(
        self.major_dimension_count, self.minor_dimension_count)
      assert not self.__cell_point_selection.flags['OWNDATA']
    return self.__cell_point_selection

  @cell_point_selection.setter
  def cell_point_selection(self, value):
    self.cell_point_selection[:] = value

  def _invalidate_properties(self):
    """Invalidates the properties of the object. Next time a property
    is requested, it will be loaded from the project.

    """
    # Cell properties.
    self.__cells_2d = None
    self.__cell_selection_2d = None
    self.__cell_visibility_2d = None

    # Cell point properties.
    self.__cell_points = None
    self.__cell_point_colours = None
    self.__cell_point_visibility = None
    self.__cell_point_selection = None

    PointProperties._invalidate_properties(self)
    CellProperties._invalidate_properties(self)

  @classmethod
  def static_type(cls):
    return Modelling().IrregularCellNetworkType()

  def save(self):
    if self.lock_type is LockType.READ:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error
    # Ensure the points are the correct size.
    # If points are smaller than this, they will all be set to NaN.
    # If points are larger than this, the script will crash.
    self.points = trim_pad_2d_array(
      self.points,
      elements_to_keep=self.cell_point_count,
      fill_value=0)
    self._save_point_properties()
    self._save_cell_properties()
    self._reconcile_changes()
