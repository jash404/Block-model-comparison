"""Support for cell primitives.

Cell primitives are quadrilaterals defined by four points. In Python, a cell
is represented as a numpy array containing four integers representing
the indices of the points used to define the corners of the cell. For example,
the cell [0, 1, 2, 3] indicates the quadrilateral with the 0th, 1st, 2nd and
3rd point as the four corners. Because cells are defined based on points, all
objects which inherit from CellProperties must also inherit from
PointProperties.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import logging

import numpy as np

from .primitive_attributes import PrimitiveAttributes, PrimitiveType
from ..errors import CannotSaveInReadOnlyModeError
from ...common import trim_pad_1d_array
from ...internal.lock import WriteLock

log = logging.getLogger("mapteksdk.data")

# The following warning can be enabled if the <Primitive>Properties classes
# ended in Mixin as then pylint expects that the members are defined elsewhere.
# pylint: disable=no-member

class CellProperties:
  """Mixin class which provides spatial objects support for cell primitives.

  Functions and properties defined on this class are available on all
  classes which support cells. Inheriting classes may impose restrictions on
  the quadrilaterals which can be included in that object.

  """
  __major_dimension_count = None
  __minor_dimension_count = None

  # Cell properties.
  __cells = None
  __cell_visibility = None
  __cell_selection = None
  __cell_colours = None
  __cell_attributes = None

  @property
  def major_dimension_count(self):
    """The major dimension count of the Cell Network.

    If the inheriting object is stored in row major order, then this will
    correspond to the row count. If stored in column major order then this will
    correspond to the column count.

    """
    if self.__major_dimension_count is None:
      dimensions = self._get_cell_dimensions()
      self.__major_dimension_count = dimensions[0]
      self.__minor_dimension_count = dimensions[1]
    return self.__major_dimension_count

  @property
  def minor_dimension_count(self):
    """The major dimension count of the Cell Network.

    If the inheriting object is stored in row major order, then this will
    correspond to the column count. If stored in column major order then this
    will correspond to the row count.

    """
    if self.__minor_dimension_count is None:
      dimensions = self._get_cell_dimensions()
      self.__major_dimension_count = dimensions[0]
      self.__minor_dimension_count = dimensions[1]
    return self.__minor_dimension_count

  @property
  def cells(self):
    """This property maps the cells to the points used to define the cells.
    Use this to refer to the points which define the four corners of
    a cell.

    This is a numpy array of shape (n, 4) where n is the cell count.
    If cells[i] is [a, b, c, d] then the four corner points of the ith cell are
    points[a], points[b], points[c] and points[d].

    Notes
    -----
    Sparse cell objects (such as Scans) may contain cells with point indices
    of -1. These represent invalid points.

    Examples
    --------
    This example creates a GridSurface object with 3 rows and 3 columns of
    points and prints the cells. Then it prints the four points which
    define the first cell (index 0).

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import GridSurface
    >>> project = Project()
    >>> with project.new("surfaces/small_square", GridSurface(
    ...         major_dimension_count=3, minor_dimension_count=3,
    ...         x_step=0.1, y_step=0.1)) as small_square:
    ...     print("Cells:")
    ...     print(small_square.cells)
    ...     print("The points which define the first cell are:")
    ...     for index in small_square.cells[0]:
    ...         print(f"Point {index}:", small_square.points[index])
    Cells:
    [[0 3 4 1]
     [1 4 5 2]
     [3 6 7 4]
     [4 7 8 5]]
    The points which define the first cell are:
    Point 0: [0. 0. 0.]
    Point 3: [0.3 0.  0. ]
    Point 4: [0.  0.1 0. ]
    Point 1: [0.1 0.  0. ]

    """
    if self.__cells is None:
      self.__cells = self._get_cells()
      # As of 2021-09-23 no objects support writing to the cells,
      # so disable editing them.
      self.__cells.flags.writeable = False
    return self.__cells

  @property
  def cell_count(self):
    """The number of cells in the cell network.

    By default this is equal to the
    (major_dimension_count - 1) x (minor_dimension_count - 1),
    however subclasses may override this function to return different values.

    """
    return (self.major_dimension_count - 1) * (self.minor_dimension_count - 1)

  @property
  def cell_visibility(self):
    """The visibility of the cells as a flat array.

    This array will contain cell_count booleans - one for each cell.
    True indicates the cell is visible and False indicates the cell is
    invisible.

    Notes
    -----
    If set to an array which is too large, the excess values will be ignored.
    If set to an array which is too small, this will be padded with True.

    """
    if self.__cell_visibility is None:
      self.__cell_visibility = self._get_cell_visibility()
    return self.__cell_visibility

  @cell_visibility.setter
  def cell_visibility(self, cell_visibility):
    if not isinstance(cell_visibility, np.ndarray):
      cell_visibility = np.array(cell_visibility, dtype=ctypes.c_bool)
    self.__cell_visibility = trim_pad_1d_array(cell_visibility,
                                               elements_to_keep=self.cell_count,
                                               fill_value=True)

  @property
  def cell_selection(self):
    """The selection of the cells as a flat array.

    This array will contain cell_count booleans - one for each cell.
    True indicates the cell is selected and False indicates the cell is not
    selected.

    Notes
    -----
    If set to an array which is too large, the excess values will be ignored.
    If set to an array which is too small, this will be padded with False.

    """
    if self.__cell_selection is None:
      self.__cell_selection = self._get_cell_selection()
    return self.__cell_selection

  @cell_selection.setter
  def cell_selection(self, cell_selection):
    if not isinstance(cell_selection, np.ndarray):
      cell_selection = np.array(cell_selection, dtype=ctypes.c_bool)
    self.__cell_selection = trim_pad_1d_array(cell_selection,
                                              elements_to_keep=self.cell_count,
                                              fill_value=False)

  @property
  def cell_point_count(self):
    """The number of points in the cell network, including invalid points for
    which point properties are not stored. This is equal to:
    major_dimension_count * minor_dimension_count.

    If the object contains invalid points, then cell_point_count > point_count.

    See Also
    --------
    mapteksdk.data.primitives.PointProperties.point_count :
      The count of valid points in the object.

    """
    return self.major_dimension_count * self.minor_dimension_count

  @property
  def cell_attributes(self):
    """Access custom cell attributes. These are arrays of values of the
    same type with one value for each cell.

    Use Object.cell_attributes[attribute_name] to access a cell attribute
    called attribute_name. See PrimitiveAttributes for valid operations
    on cell attributes.

    Returns
    -------
    PrimitiveAttributes
      Access to the cell attributes.

    Raises
    ------
    ValueError
      If the type of the attribute is not supported.

    """
    if self.__cell_attributes is None:
      self.__cell_attributes = PrimitiveAttributes(PrimitiveType.CELL, self)
    return self.__cell_attributes

  def save_cell_attribute(self, attribute_name, data):
    """Create and/or edit the values of the call attribute attribute_name.

    This is equivalent to Object.cell_attributes[attribute_name] = data.

    Parameters
    ----------
    attribute_name : str
      The name of attribute
    data : array_like
      An array_like of length cell_count containing the values
      for attribute_name.

    Raises
    ------
    Exception
      If the object is opened in read-only mode.
    ValueError
      If the type of the attribute is not supported.

    """
    self.cell_attributes[attribute_name] = data

  def delete_cell_attribute(self, attribute_name):
    """Delete a cell attribute by name.

    This is equivalent to: cell_attributes.delete_attribute(attribute_name)

    Parameters
    ----------
    attribute_name : str
      The name of attribute

    Raises
    ------
    Exception
      If the object is opened in read-only mode.
    ValueError
      If the primitive type is not supported.

    """
    self.cell_attributes.delete_attribute(attribute_name)

  def _invalidate_properties(self):
    """Invalidates the cached cell properties. The next time one is requested
    its values will be loaded from the project.

    """
    self.__major_dimension_count = None
    self.__minor_dimension_count = None
    self.__cell_visibility = None
    self.__cell_selection = None
    self.__cell_colours = None
    self.__cell_attributes = None

  def _save_cell_properties(self):
    """Save the cell properties.

    This must be called during save() of the inheriting object.
    This should never be called directly. To save an object, call save()
    instead.

    Raises
    ------
    CannotSaveInReadOnlyModeError
      If in read-only mode.

    Notes
    -----
    Generally this should be called after PointProperties.save_points().

    """
    if isinstance(self._lock, WriteLock):
      if self.__cell_visibility is not None:
        self._save_cell_visibility(self.cell_visibility)
      if self.__cell_selection is not None:
        self._save_cell_selection(self.cell_selection)
      if self.__cell_colours is not None:
        self._save_cell_colours(self.__cell_colours)
      if self.__cell_attributes is not None:
        self.__cell_attributes.save_attributes()
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error
