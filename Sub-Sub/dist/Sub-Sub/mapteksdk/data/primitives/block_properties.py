"""Support for block primitives.

Block primitives are three dimensional cubes or rectangular prisms defined by
a centroid and a block size. Given a block with centroid [0, 0, 0] and size
[2, 4, 8] then the block will be the rectangular prism centred at [0, 0, 0]
and 2 metres by 4 metres by 8 metres in size.

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
from ..errors import CannotSaveInReadOnlyModeError, DegenerateTopologyError
from ...common import (trim_pad_1d_array, convert_array_to_rgba)
from ...internal.rotation import Rotation
from ...internal.lock import WriteLock

log = logging.getLogger("mapteksdk.data")

# The following warning can be enabled if the <Primitive>Properties classes
# ended in Mixin as then pylint expects that the members are defined elsewhere.
# pylint: disable=no-member

class BlockProperties:
  """Mixin class which provides spatial object support for block primitives.

  Functions and properties defined on this class are available on all
  classes which support blocks.
  """
  __block_visibility = None
  __block_colours = None
  __block_centroids = None
  __block_dimensions = None
  __block_selection = None
  __block_sizes = None
  __block_attributes = None
  __origin = None
  __block_resolution = None
  __block_to_grid_index = None

  @property
  def _can_set_blocks(self):
    """Returns whether the block centroids and block sizes can be set.
    By default this is false and setting the block centroids and sizes
    will be ignored.

    """
    return False

  @property
  def block_count(self):
    """The count of blocks in the model."""
    if self.__block_centroids is None and self.__block_sizes is None:
      # The block count has not been changed, so read the block count from the
      # object.
      return self._get_block_count()
    # The block count may have changed so base it off the centroids and
    # sizes.
    return min(self.block_centroids.shape[0], self.block_sizes.shape[0])

  @property
  def block_resolution(self):
    """The resolution of the block model.

    This is the x_res, y_res and z_res values used when creating the model
    in an array. Once the block model has been created, these values
    cannot be changed.

    """
    if self.__block_resolution is None:
      self.__block_resolution = self._get_block_resolution()
    return self.__block_resolution

  @property
  def block_centroids(self):
    """The centroids of the blocks. This is represented as an ndarray of shape
    (block_count, 3) of the form:
    [[x1, y1, z1], [x2, y2, z2], ..., [xN, yN, zN]]
    Where N is the block_count.

    """
    if self.__block_centroids is None:
      # Populate when called
      self.__block_centroids = self._get_block_centroids()
      if isinstance(self._lock, WriteLock):
        self.__block_centroids.flags.writeable = self._can_set_blocks
    return self.__block_centroids

  def _set_block_centroids(self, new_centroids):
    """Sets the block centroids. If set to None, they will be loaded
    from the Project when next requested.

    Raises
    ------
    RuntimeError
      If blocks are not settable.

    """
    if not self._can_set_blocks:
      raise RuntimeError("This object does not support setting centroids.")
    if new_centroids is None:
      self.__block_centroids = None
    elif not isinstance(new_centroids, np.ndarray):
      self.__block_centroids = np.array(new_centroids)
    else:
      self.__block_centroids = new_centroids

  @property
  def block_sizes(self):
    """The block sizes represented as an ndarray of shape (block_count, 3).
    Each row represents the size of one block in the form [x, y, z] where
    x, y and z are positive numbers.

    This means that the extent for the block with index i is calculated as:
    (block_centroids[i] - block_sizes[i] / 2,
    block_centroids[i] + block_sizes[i] / 2)

    Notes
    -----
    For DenseBlockModels, all block_sizes are the same.

    """
    if self.__block_sizes is None:
      # Populate when called
      self.__block_sizes = self._get_block_sizes()
      if isinstance(self._lock, WriteLock):
        self.__block_sizes.flags.writeable = self._can_set_blocks
    return self.__block_sizes

  def _set_block_sizes(self, block_sizes):
    if not self._can_set_blocks:
      raise RuntimeError("This object does not support setting sizes.")
    if block_sizes is None:
      self.__block_sizes = None
    elif not isinstance(block_sizes, np.ndarray):
      self.__block_sizes = np.array(block_sizes)
    else:
      self.__block_sizes = block_sizes

  @property
  def block_colours(self):
    """The colour of the blocks, represented as a ndarray of shape
    (block_count, 4) with each row i representing the colour of the ith
    block in the model in the form [Red, Green, Blue, Alpha].

    When setting block colours, you may omit the Alpha component.

    """
    if self.__block_colours is None:
      # Populate when called
      self.__block_colours = self._get_block_colours()

    if self.__block_colours.shape[0] != self.block_count:
      self.__block_colours = convert_array_to_rgba(self.__block_colours,
                                                   self.block_count)

    return self.__block_colours

  @block_colours.setter
  def block_colours(self, block_colours):
    if block_colours is None:
      self.__block_colours = None
    else:
      self.__block_colours = convert_array_to_rgba(block_colours,
                                                   self.block_count)

  @property
  def slice_count(self):
    """The number of slices in the underlying block model.

    This can be thought of as the number of blocks in the Z
    direction (assuming no rotation is made). This can only be set by the
    block model's constructor.

    """
    return self._cached_block_dimensions()[0]

  @property
  def row_count(self):
    """The number of rows in the underlying block model.

    This can be thought of as the number of blocks in the Y
    direction (assuming no rotation is made). This can only be set by the
    block model's constructor.

    """
    return self._cached_block_dimensions()[1]

  @property
  def column_count(self):
    """The number of columns in the underlying block model.

    This can be thought of as the number of blocks in the X
    direction (assuming no rotation is made). This can only be set by the
    block model's constructor.

    """
    return self._cached_block_dimensions()[2]

  @property
  def block_selection(self):
    """The block selection represented as an ndarray of bools with shape:
    (block_count,). True indicates the block is selected; False indicates it
    is not selected.

    Notes
    -----
    In mapteksdk version 1.0, block_selection returned a 3D ndarray. To
    get the same functionality, see block_selection_3d property of dense
    block models.

    """
    if self.__block_selection is None:
      self.__block_selection = self._get_block_selection()
    if self.__block_selection.shape != (self.block_count,):
      self.__block_selection = trim_pad_1d_array(self.__block_selection,
                                                 self.block_count,
                                                 False)
    return self.__block_selection

  @block_selection.setter
  def block_selection(self, block_selection):
    if block_selection is None:
      selection = None
    else:
      if isinstance(block_selection, np.ndarray):
        selection = block_selection
      else:
        selection = np.array(block_selection, dtype=ctypes.c_bool)

      if selection.shape != (self.block_count,):
        selection = trim_pad_1d_array(selection, self.block_count, False)

      self.__block_selection = selection

  @property
  def block_visibility(self):
    """The block visibility represented as an ndarray of bools with shape:
    (block_count,). True indicates the block is visible, False indicates it
    is not visible.

    Notes
    -----
    In mapteksdk version 1.0 block_visibility returned a 3D ndarray. To
    get the same functionality, see block_visibility_3d property of dense
    block models.

    """
    if self.__block_visibility is None:
      self.__block_visibility = self._get_block_visibility()
    if self.__block_visibility.shape != (self.block_count,):
      self.__block_visibility = trim_pad_1d_array(self.__block_visibility,
                                                    self.block_count,
                                                    True)

    return self.__block_visibility

  @block_visibility.setter
  def block_visibility(self, block_visibility):
    if block_visibility is None:
      self.__block_visibility = None
    else:
      if isinstance(block_visibility, np.ndarray):
        visibility = block_visibility
      else:
        visibility = np.array(block_visibility, dtype=ctypes.c_bool)

      if visibility.shape != (self.block_count,):
        visibility = trim_pad_1d_array(visibility, self.block_count, True)

    self.__block_visibility = visibility

  @property
  def origin(self):
    """The origin of the block model represented as a point.

    Setting the origin will translate the entire block model to be
    centred around the new origin.

    Notes
    -----
    For DenseBlockModels the resulting changes to the block_centroids will
    not occur until save is called.
    For SubblockedBlockModels the resulting changes to the block_centroids
    are immediately available, however changing the origin of such a model
    is slower.

    Examples
    --------
    Changing the origin will change the block model centroids, in this case
    by translating them by 1 unit in the X direction, 2 units in the Y direction
    and 3 units in the Z direction. Note that as this is a DenseBlockModel,
    the model needs to be saved (in this case via closing ending the with block)
    before the changes to the centroids will occur.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import DenseBlockModel
    >>> project = Project()
    >>> with project.new("blockmodels/model", DenseBlockModel(
    ...         x_res=2, y_res=3, z_res=4,
    ...         x_count=2, y_count=2, z_count=2)) as new_model:
    ...     new_model.origin = [1, 2, 3]
    >>> with project.edit("blockmodels/model") as edit_model:
    ...     print(edit_model.block_centroids)
    [[1, 2, 3], [3, 2, 3], [1, 5, 3], [3, 5, 3], [1, 2, 7], [3, 2, 7],
    [1, 5, 7], [3, 5, 7]]

    """
    if self.__origin is None:
      transform = self._get_block_transform()
      self.__origin = transform[0]
      # If the rotation has been changed, don't overwrite it.
      if not self._rotation_cached:
        self._rotation = Rotation(*transform[1])
    return self.__origin

  @origin.setter
  def origin(self, new_origin):
    old_origin = self.origin
    if new_origin is None:
      self.__origin = new_origin
    else:
      self.__origin = trim_pad_1d_array(new_origin, 3, 0)
      if self._can_set_blocks and self.block_centroids.shape[0] != 0:
        adjustment = old_origin - new_origin
        new_centroids = self.block_centroids - adjustment
        self._set_block_centroids(new_centroids)

  @property
  def block_to_grid_index(self):
    """An ndarray containing the mapping of the blocks to the row, column
    and slice their centroid lies within. This has shape (N, 3) where N is the
    block_count and each item is of the form [column, row, slice].

    This means that the column, row and slice of the block centred at
    block_centroids[i] is block_to_grid_index[i].

    For DenseBlockModels, there is only one block per grid cell and thus
    each item of the block_to_grid_index will be unique.

    """
    if self.__block_to_grid_index is None:
      block_coordinates = self.convert_to_block_coordinates(
        self.block_centroids)
      index = np.rint(block_coordinates / self.block_resolution)
      self.__block_to_grid_index = index
    return self.__block_to_grid_index

  def _delete_cached_block_to_grid_index(self):
    self.__block_to_grid_index = None

  def grid_index(self, start, stop=None):
    """Generates a boolean index for accessing block properties by
    row, column and slice instead of by block. The boolean index will include
    all subblocks between primary block start (inclusive) and primary block
    stop (exclusive), or all subblocks within primary block start if stop
    is not specified.

    Parameters
    ----------
    start : array_like or int
      An array_like containing three elements - [column, row, slice].
      The returned boolean index will include all blocks in a greater column,
      row and slice.
      If this is an integer, that integer is interpreted as the column,
      row and slice.
    end : array_like or int
      An array_like containing three elements - [column, row, slice].
      If None (Default) this is start + 1 (The resulting index will
      contain all blocks within primary block start).
      If not None, the boolean index will include all blocks between
      start (inclusive) and end (exclusive).
      If this is an integer, that integer is interpreted as the column,
      row and slice index.

    Returns
    -------
    ndarray
      A boolean index into the block property arrays. This is an array
      of booleans of shape (block_count,). If element i is True then
      subblock i is within the range specified by start and stop. If
      False it is not within that range.

    Raises
    ------
    TypeError
      If start or stop are invalid types.
    ValueError
      If start or stop are incorrect shapes.

    Examples
    --------
    These examples require a block model to be at "blockmodels/target"

    This example selects all subblocks within the primary block in column 0,
    row 0 and slice 0:

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.edit("blockmodels/target") as edit_model:
    ...     index = edit_model.grid_index([0, 0, 0])
    ...     edit_model.block_selection[index] = True

    By passing two values to grid index, it is possible to operate on
    all subblocks within a range of subblocks. This example passes
    [0, 2, 2] and [4, 5, 6] meaning all subblocks which have
    0 <= column < 4 and 2 <= row < 5 and 2 <= slice < 6 will be selected
    by grid_index. By passing this index to block visibility, all subblocks
    within those primary blocks are made invisible.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.edit("blockmodels/target") as edit_model:
    ...     index = edit_model.grid_index([0, 2, 2], [4, 5, 6])
    ...     edit_model.block_visibility[index] = False

    """
    if stop is None:
      return np.all(self.block_to_grid_index == start, axis=1)
    index = self.block_to_grid_index
    pre = index >= start
    post = index < stop
    return np.all(np.logical_and(pre, post), axis=1)

  def convert_to_block_coordinates(self, world_coordinates):
    """Converts points in world coordinates to points in block coordinates.

    The block coordinate system for a particular model is defined such that
    [0, 0, 0] is the centre of the block in row 0, column 0 and slice 0.
    The X axis is aligned with the columns, the Y axis is aligned with the
    rows and the Z axis is aligned with the slices of the model. This makes
    the centre of the primary block in column i, row j and slice k to be:
    [x_res * i, y_res * j, z_res * k].

    This function performs no error checking that the points lies within the
    model.

    Parameters
    ----------
    world_coordinates : array_like
      Points in world coordinates to convert to block coordinates.

    Returns
    -------
    numpy.ndarray
      Numpy array containing world_coordinates converted to be in
      block_coordinates.

    Raises
    ------
    ValueError
      If world_coordinates has an invalid shape.

    Notes
    -----
    If a block model has origin = [0, 0, 0] and has not been rotated,
    then the block and world coordinate systems are identical.

    Block models of differing size, origin or rotation will have different
    block coordinate systems.

    """
    # Make a copy to convert to block coordinates.
    block_coordinates = np.array(world_coordinates)
    if len(block_coordinates.shape) != 2 or block_coordinates.shape[1] != 3:
      raise ValueError(f"Invalid shape for points array: "
                       f"{block_coordinates.shape}. Shape must be (n, 3) "
                       "where n is the number of points to convert.")

    block_coordinates -= self.origin
    block_coordinates = self._rotation.invert_rotation().rotate_vectors(
      block_coordinates)

    return block_coordinates

  def convert_to_world_coordinates(self, block_coordinates):
    """Converts points in block coordinates to points in world coordinates.

    This is the inverse of the transformation performed by
    convert_to_block_coordinates.

    Parameters
    ----------
    block_coordinates : array_like
      Points in block coordinates to convert to world coordinates.

    Returns
    -------
    numpy.ndarray
      Numpy array containing block_coordinates converted to world_coordinates.

    Raises
    ------
    ValueError
      If block_coordinates has an invalid shape.

    Notes
    -----
    Block models of differing size, origin or rotation will have different
    block coordinate systems.

    """
    world_coordinates = np.array(block_coordinates)
    if len(world_coordinates.shape) != 2 or world_coordinates.shape[1] != 3:
      raise ValueError(f"Invalid shape for points array: "
                       f"{world_coordinates.shape}. Shape must be (n, 3) "
                       "where n is the number of points to convert.")

    world_coordinates = self._rotation.rotate_vectors(world_coordinates)
    world_coordinates += self.origin

    return world_coordinates

  def _adjust_centroids_for_rotation(self, inverse_rotation, new_rotation):
    """Adjusts the centroids based on changes to rotations. This also takes
    into account the origin of the block model.

    The old rotation is undone and then the new rotation applied.

    Parameters
    ----------
    inverse_rotation : Rotation
      Rotation to undo the previous rotation on the block model.
    new_rotation : Rotation
      The new rotation of the block model.

    """
    centroids = self.block_centroids - self.origin
    centroids = inverse_rotation.rotate_vectors(centroids)
    new_centroids = new_rotation.rotate_vectors(centroids)
    new_centroids += self.origin
    self._set_block_centroids(new_centroids)

  def _invalidate_properties(self):
    """Invalidates the cached block properties. The next time one is requested
    its values will be loaded from the project.

    """
    self.__block_visibility = None
    self.__block_colours = None
    self.__block_centroids = None
    self.__block_dimensions = None
    self.__block_selection = None
    self.__block_sizes = None
    self.__block_attributes = None
    self.__origin = None
    self._delete_cached_block_to_grid_index()

  def _save_block_properties(self):
    """Save the block properties.

    This must be called during save() of the inheriting object.
    This should never be called directly. To save an object, call save()
    instead.

    Raises
    ------
    CannotSaveInReadOnlyModeError
      If in read-only mode.

    """
    if isinstance(self._lock, WriteLock):
      if self._can_set_blocks:
        block_count = self.block_count
        if block_count == 0:
          message = "Object must contain at least one block"
          raise DegenerateTopologyError(message)
        if not (self.__block_centroids is None and self.__block_sizes is None):
          self._save_block_count(block_count)
          if self.__block_centroids is not None:
            self._save_block_centroids(self.block_centroids[:block_count])
          if self.__block_sizes is not None:
            self._save_block_sizes(self.block_sizes[:block_count])

      if self.__block_selection is not None:
        self._save_block_selection(self.block_selection)

      if self.__block_visibility is not None:
        self._save_block_visibility(self.block_visibility)

      if self.__block_colours is not None:
        self._save_block_colours(self.block_colours)

      if self.__origin is not None or self._rotation_cached:
        # Uses the getter instead of the variable because otherwise
        # if the rotation was set and the origin was not set (or vice
        # versa) the uncached value would be set to default.
        # By using the getter, uncached values are loaded from the
        # Project and saved back to ensure they aren't changed.
        self._save_transform(*self._rotation.quaternion, *self.origin)

      if self.__block_attributes is not None:
        self.__block_attributes.save_attributes()
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  def _delete_block(self, block_index):
    """Flags a single block for removal when the object is closed.

    DenseBlockModels do not support the removal of blocks.

    Parameters
    ----------
    block_index : long
      Index of the block to remove.

    Notes
    -----
    Changes will not be reflected until save() or close() is called.

    """
    if not self._can_set_blocks:
      raise ValueError("Object does not support removal of blocks.")
    self._remove_block(block_index)

  def save_block_attribute(self, attribute_name, data):
    """Create a new block attribute with the specified name and associate the
    specified data.

    Parameters
    ----------
    attribute_name : str
      The name of attribute.
    data : array_like
      Data for the associated attribute. This should be a ndarray of shape
      (block_count,). The ith entry in this array is the value of this
      primitive attribute for the ith block.

    Raises
    ------
    Exception
      If the object is opened in read-only mode.
    ValueError
      If the type of the attribute is not supported.

    """
    self.block_attributes[attribute_name] = data

  def delete_block_attribute(self, attribute_name):
    """Delete a block attribute.

    Parameters
    ----------
    attribute_name : str
      The name of attribute to delete.

    Raises
    ------
    Exception
      If the object is opened in read-only mode.

    """
    self.block_attributes.delete_attribute(attribute_name)

  @property
  def block_attributes(self):
    """Access block attributes.

    block_model.block_attributes["Blocktastic"] will return the block attribute
    called "Blocktastic".

    Returns
    -------
    PrimitiveAttributes
      Access to the block attributes.

    """
    if self.__block_attributes is None:
      self.__block_attributes = PrimitiveAttributes(PrimitiveType.BLOCK, self)
    return self.__block_attributes

  def _cached_block_dimensions(self):
    """Read the block dimensions from the model and cache the result.

    Returns
    -------
    tuple
      the number of slices, rows and columns in the block model.

    """
    if self.__block_dimensions is None:
      dimensions = self._get_block_dimensions()
      self.__block_dimensions = tuple(dimensions)
    return self.__block_dimensions

  def _get_rotation(self):
    origin, quaternion = self._get_block_transform()
    # If the origin has been changed, don't overwrite it.
    if self.__origin is None:
      self.__origin = origin
    return Rotation(*quaternion)
