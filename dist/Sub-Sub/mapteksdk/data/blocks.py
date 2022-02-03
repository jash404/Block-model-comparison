"""Block model data types.

Block models are objects constructed entirely from block primitives. There
are different kinds of block models, however only
DenseBlockModels and SubblockedBlockModels are currently supported.

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

from ..capi import Modelling
from .base import Topology
from .errors import ReadOnlyError
from .rotation import RotationMixin
from .objectid import ObjectID
from .primitives import BlockProperties
from ..internal.lock import LockType

log = logging.getLogger("mapteksdk.data.blocks")

class InvalidBlockCentroidError(ValueError):
  """Error raised for block centroids which lie outside of the block model."""

class InvalidBlockSizeError(ValueError):
  """Error raised for invalid block sizes."""

# =========================================================================
#
#                        DENSE BLOCK MODEL
#
# =========================================================================
class DenseBlockModel(Topology, BlockProperties, RotationMixin):
  """A dense block model consists of blocks which are the same size
  arranged in a three dimensional grid structure. The block model is dense
  because it does not allow 'holes' in the model - every region in the
  grid must contain a block.

  For example, a dense block model with an x_res of 1, a y_res of 2
  and a z_res of 3 means all of the blocks in the model are
  1 by 2 by 3 units in size.
  If the dense block model's x_count was 10, the y_count
  was 15 and the z_count was 5 then the model would consist of
  10 * 15 * 5 = 750 blocks each of which was 1x2x3 units. These blocks
  would be arranged in a grid with 10 rows, 15 columns and 5 slices with
  no gaps.

  The blocks of a dense block model are defined at creation and cannot be
  changed.

  Parameters
  ----------
  x_res : float
    The x resolution. Must be greater than zero.
  y_res  : float
    The y resolution. Must be greater than zero.
  z_res : float
    The z resolution. Must be greater than zero.
  x_count : int
    The number of columns in the block model. Must be greater than zero.
  y_count : int
    The number of rows in the block model. Must be greater than zero.
  z_count : int
    The number of slices in the block model. Must be greater than zero.

  Notes
  -----
  Parameters should only be passed for new block models.

  Raises
  ------
  ValueError
    If x_res, y_res, z_res, x_count, y_count or z_count is less than or equal
    to zero.
  TypeError
    If x_res, y_res, z_res, x_count, y_count or z_count is not numeric.
  TypeError
    If x_count, y_count or z_count are numeric but not integers.

  Examples
  --------
  Create a block model as described above and make
  every second block invisible.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import DenseBlockModel
  >>> project = Project()
  >>> with project.new("blockmodels/model", DenseBlockModel(
  >>>         x_res=1, y_res=2, z_res=3, x_count=10, y_count=15, z_count=5
  >>>         )) as new_model:
  >>>     new_model.block_visibility = [True, False] * ((10 * 15 * 5) // 2)

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE,
               x_res=None, y_res=None, z_res=None,
               x_count=None, y_count=None, z_count=None):
    if object_id is None:
      arg_tuple = [x_res, y_res, z_res, x_count, y_count, z_count]
      if any(value is None for value in arg_tuple):
        # :TODO: Jayden Boskell 2021-09-14 SDK-588: Change this to raise
        # a DegenerateTopologyError.
        message = ("*_res and *_count default arguments are deprecated "
                   "and will be removed in a future version.")
        warnings.warn(DeprecationWarning(message))
        x_res = x_res if x_res is not None else 1
        y_res = y_res if y_res is not None else 1
        z_res = z_res if z_res is not None else 1
        x_count = x_count if x_count is not None else 1
        y_count = y_count if y_count is not None else 1
        z_count = z_count if z_count is not None else 1

      # Create new block model
      if x_res <= 0 or y_res <= 0 or z_res <= 0:
        raise ValueError("x_res, y_res and z_res must be greater than 0. "
                         f"Given: ({x_res}, {y_res}, {z_res})")

      if x_count <= 0 or y_count <= 0 or z_count <= 0:
        raise ValueError("x_count, y_count and z_count must be greater than 0. "
                         f"Given: ({x_count}, {y_count}, {z_count})")

      try:
        object_id = ObjectID(Modelling().NewBlockNetworkDense(
          x_res, y_res, z_res, x_count, y_count, z_count))
      except ctypes.ArgumentError as error:
        raise TypeError("All resolutions must be numeric and all counts "
                        "must be integers. "
                        f"Resolutions: ({x_res}, {y_res}, {z_res}) "
                        f"Counts: ({x_count}, {y_count}, {z_count})"
                        ) from error

    super().__init__(object_id, lock_type)

    self.__block_visibility_3d = None
    self.__block_selection_3d = None

    if object_id is None:
      error_msg = 'Cannot create dense block model'
      log.error(error_msg)
      raise RuntimeError(error_msg)

  @classmethod
  def static_type(cls):
    """Return the type of dense block model as stored in a Project.

    This can be used for determining if the type of an object is a dense
    block model.

    """
    return Modelling().BlockNetworkDenseType()

  @property
  def block_count(self):
    # This is row count * column count * slice count.
    return np.product(self._cached_block_dimensions())

  @property
  def block_visibility_3d(self):
    """A view of the block visibility reshaped into 3 dimensions.
    block_visibility_3d[slice, row, column] gives the visibility for
    the specified slice, row and column.

    Raises
    ------
    ValueError
      If set using a value which cannot be converted to a bool.
    ValueError
      If set to a value which cannot be broadcast to the right shape.

    Examples
    --------
    Make a 10x10x10 block model and make every block in the 4th row invisible,
    excluding blocks in the 0th slice.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import DenseBlockModel
    >>> project = Project()
    >>> with project.new("blockmodels/visibility_3d", DenseBlockModel(
    ...         x_count=10, y_count=10, z_count=10, x_res=1, y_res=1, z_res=0.5
    ...         )) as new_blocks:
    ...     new_blocks.block_visibility_3d[:, 5, :] = False
    ...     new_blocks.block_visibility_3d[0, :, :] = True

    """
    if self.__block_visibility_3d is None or \
        not np.may_share_memory(self.block_visibility,
                                self.__block_visibility_3d):
      self.__block_visibility_3d = self.block_visibility[:].reshape(
        self.slice_count, self.row_count, self.column_count)
    return self.__block_visibility_3d

  @block_visibility_3d.setter
  def block_visibility_3d(self, new_visibility):
    self.block_visibility_3d[:] = new_visibility

  @property
  def block_selection_3d(self):
    """A view of the block selection reshaped into 3 dimensions.
    block_selection_3d[slice, row, column] gives the visibility for
    the block in the specified slice, row and column.

    Raises
    ------
    ValueError
      If set using a value which cannot be converted to a bool.
    ValueError
      If set to a value which cannot be broadcast to the right shape.

    """
    if self.__block_selection_3d is None or \
        not np.may_share_memory(self.block_selection,
                                self.__block_selection_3d):
      self.__block_selection_3d = self.block_selection[:].reshape(
        self.slice_count, self.row_count, self.column_count)
    return self.__block_selection_3d

  @block_selection_3d.setter
  def block_selection_3d(self, new_selection):
    self.block_selection_3d[:] = new_selection

  def save(self):
    self._save_block_properties()
    self._reconcile_changes()

  def _invalidate_properties(self):
    BlockProperties._invalidate_properties(self)
    self.__block_visibility_3d = None
    self.__block_selection_3d = None

# =========================================================================
#
#                        DENSE SUBLOCKED BLOCK MODEL
#
# =========================================================================

class SubblockedBlockModel(Topology, BlockProperties, RotationMixin):
  """A dense subblocked block model. Each primary block can contain subblocks
  allowing for the model to hold greater detail in areas of greater interest
  and less detail in areas of less interest.

  Block attributes, such as block_visibility and block_colour, have one value
  per subblock. A subblocked block model is empty when created and contains
  no blocks. Use the add_subblocks function to add additional subblocks to the
  model.

  Note that it is possible for a subblocked block model to include invalid
  subblocks. For example, subblocks which are outside of the extents of the
  block model. These blocks will not be displayed in the viewer.

  If interoperability with Vulcan is desired, the subblock sizes should always
  be a multiple of the primary block sizes (the resolution defined on
  construction) and you should be careful to ensure subblocks do not intersect
  each other.

  Parameters
  ----------
  x_res : float
    The x resolution. Must be greater than zero.
  y_res  : float
    The y resolution. Must be greater than zero.
  z_res : float
    The z resolution. Must be greater than zero.
  x_count : int
    The number of columns in the block model. Must be greater than zero.
  y_count : int
    The number of rows in the block model. Must be greater than zero.
  z_count : int
    The number of slices in the block model. Must be greater than zero.

  Notes
  -----
  Parameters should only be passed for new block models.

  Raises
  ------
  ValueError
    If x_res, y_res, z_res, x_count, y_count or z_count is less than or equal
    to zero.
  TypeError
    If x_res, y_res, z_res, x_count, y_count or z_count is not numeric.
  TypeError
    If x_count, y_count or z_count are numeric but not integers.

  Examples
  --------
  Creating a subblocked block model with two parent blocks, one of which
  is completely filled by a single subblock and another which is split into
  three subblocks. Each subblock is made invisible individually. Though
  the block model has two primary blocks, it has four subblocks so four
  values are required for the visibility.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import SubblockedBlockModel
  >>> centroids = [[0, 0, 0], [-1, 3, 0], [1, 3, 0], [0, 5, 0]]
  >>> sizes = [[4, 4, 4], [2, 2, 4], [2, 2, 4], [4, 2, 4]]
  >>> visibility = [True, True, False, False]
  >>> project = Project()
  >>> with project.new("blockmodels/subblocked_model", SubblockedBlockModel(
  ...         x_count=1, y_count=2, z_count=1, x_res=4, y_res=4, z_res=4
  ...         )) as new_blocks:
  ...     new_blocks.add_subblocks(centroids, sizes)
  ...     new_blocks.block_visibility = visibility

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE,
               x_res=None, y_res=None, z_res=None,
               x_count=None, y_count=None, z_count=None):
    if object_id is None:
      arg_tuple = (x_res, y_res, z_res, x_count, y_count, z_count)
      if any(value is None for value in arg_tuple):
        # :TODO: Jayden Boskell 2021-09-14 SDK-588: Change this to raise
        # a DegenerateTopologyError.
        message = ("*_res and *_count default arguments are deprecated "
                   "and will be removed in a future version.")
        warnings.warn(DeprecationWarning(message))
        x_res = x_res if x_res is not None else 1
        y_res = y_res if y_res is not None else 1
        z_res = z_res if z_res is not None else 1
        x_count = x_count if x_count is not None else 1
        y_count = y_count if y_count is not None else 1
        z_count = z_count if z_count is not None else 1
      # pylint: disable=invalid-name
      # Create new block model
      if x_res <= 0 or y_res <= 0 or z_res <= 0:
        raise ValueError("x_res, y_res and z_res must be greater than 0. "
                         f"Given: ({x_res}, {y_res}, {z_res})")

      if x_count <= 0 or y_count <= 0 or z_count <= 0:
        raise ValueError("x_count, y_count and z_count must be greater than 0. "
                         f"Given: ({x_count}, {y_count}, {z_count})")
      try:
        object_id = ObjectID(Modelling().NewBlockNetworkSubblocked(
          x_res, y_res, z_res, x_count, y_count, z_count))
      except ctypes.ArgumentError as error:
        raise TypeError("All resolutions must be numeric and all counts "
                        "must be integers. "
                        f"Resolutions: ({x_res}, {y_res}, {z_res}) "
                        f"Counts: ({x_count}, {y_count}, {z_count})"
                        ) from error

    super().__init__(object_id, lock_type)

  @classmethod
  def static_type(cls):
    """Return the type of subblocked block model as stored in a Project.

    This can be used for determining if the type of an object is a subblocked
    block model.

    """
    return Modelling().BlockNetworkSubblockedType()

  def add_subblocks(self, block_centroids, block_sizes,
                    use_block_coordinates=True):
    """Adds an array of subblocks to the subblocked block model.

    By default the block_centroids should be in block model coordinates
    rather than world coordinates. See convert_to_world_coordinates() for
    more information.

    Parameters
    ----------
    block_centroid : array_like
      An array of block centroids of the new blocks. This is of the form:
      [x, y, z].
    block_sizes : array_like
      An array of block sizes of the new blocks, each containing three floats.
      This is of the form: [x_size, y_size, z_size].
    use_block_coordinates : bool
      If True (default) then the coordinates of the block centroids will be
      interpreted as block model coordinates (They will be passed through
      convert_to_world_coordinates()).
      If False, then the coordinates of the block centroids will be interpreted
      as world coordinates.

    Raises
    ------
    InvalidBlockSizeError
      If any block_size is less than zero or greater than the primary block
      size.
    InvalidBlockCentroidError
      If any block_centroid is not within the block model.
    ReadOnlyError
      If called when in read-only mode.

    Notes
    -----
    Calling this function in a loop is very slow. You should calculate all of
    the subblocks and pass them to this function in a single call.

    Examples
    --------
    The block centroids are specified in block model coordinates relative
    to the bottom left hand corner of the block model. In the below example,
    the block model is rotated around all three axes and translated
    away from the origin. By specifying the centroids in block model
    coordinates, the centroids remain simple.
    The output shows the resulting block centroids of the model. To get
    the same model with use_block_coordinates=False these are the centroids
    which would be required. As you can see they are significantly more
    complicated.

    >>> import math
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import SubblockedBlockModel, Axis
    >>> centroids = [[-1.5, -1, -1], [-0.5, -1, -1], [-1, 1, -1],
    ...              [-1.5, -1, 1], [-0.5, -1, 1], [-1, 1, 1],
    ...              [-1.5, -1, 3], [-0.5, -1, 3], [-1, 1, 3]]
    >>> sizes = [[1, 2, 2], [1, 2, 2], [2, 2, 2],
    ...          [1, 2, 2], [1, 2, 2], [2, 2, 2],
    ...          [1, 2, 2], [1, 2, 2], [2, 2, 2]]
    >>> project = Project()
    >>> with project.new("blockmodels/transformed", SubblockedBlockModel(
    ...         x_count=1, y_count=2, z_count=3, x_res=4, y_res=4, z_res=4
    ...         )) as new_blocks:
    ...     new_blocks.origin = [94, -16, 12]
    ...     new_blocks.rotate(math.pi / 3, Axis.X)
    ...     new_blocks.rotate(-math.pi / 4, Axis.Y)
    ...     new_blocks.rotate(math.pi * 0.75, Axis.Z)
    ...     new_blocks.add_subblocks(centroids, sizes)
    ...     print(new_blocks.block_centroids)
    [[ 95.95710678 -16.64693601  11.96526039]
     [ 95.45710678 -15.86036992  12.32763283]
     [ 94.70710678 -16.09473435  10.42170174]
     [ 94.54289322 -17.87168089  12.67236717]
     [ 94.04289322 -17.08511479  13.03473961]
     [ 93.29289322 -17.31947922  11.12880852]
     [ 93.12867966 -19.09642576  13.37947395]
     [ 92.62867966 -18.30985966  13.74184639]
     [ 91.87867966 -18.54422409  11.8359153 ]]

    Specifying the block centroids in world coordinates is useful when
    the centroids are already available in world coordinates. This example
    shows copying the blocks from the model created in the previous example
    into a new model. Notice that the origin and rotations are the same for
    the copy. If this were not the case the centroids would likely lie
    outside of the block model and would not appear in the viewer.

    >>> import math
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import SubblockedBlockModel, Axis
    >>> project = Project()
    >>> with project.new("blockmodels/transformed_copy", SubblockedBlockModel(
    ...         x_count=1, y_count=2, z_count=3, x_res=4, y_res=4, z_res=4
    ...         )) as new_blocks:
    ...     new_blocks.origin = [94, -16, 12]
    ...     new_blocks.rotate(math.pi / 3, Axis.X)
    ...     new_blocks.rotate(-math.pi / 4, Axis.Y)
    ...     new_blocks.rotate(math.pi * 0.75, Axis.Z)
    ...     with project.read("blockmodels/transformed") as read_blocks:
    ...         new_blocks.add_subblocks(read_blocks.block_centroids,
    ...                                  read_blocks.block_sizes,
    ...                                  use_block_coordinates=False)

    """
    if self.lock_type is LockType.READ:
      raise ReadOnlyError("Cannot add subblocks in read-only mode")

    # Adding subblocks invalidates the block to grid index.
    self._delete_cached_block_to_grid_index()

    if not isinstance(block_centroids, np.ndarray):
      block_centroids = np.array(block_centroids, dtype=ctypes.c_double)

    if not isinstance(block_sizes, np.ndarray):
      block_sizes = np.array(block_sizes, dtype=ctypes.c_double)

    # Make sure the block centroids are sensible.
    if len(block_centroids.shape) != 2:
      raise InvalidBlockCentroidError(
        f"Invalid shape for block centroids: {block_centroids.shape}. "
        f"Must have 2 dimensions, not {len(block_centroids.shape)}.")
    if block_centroids.shape[1] != 3:
      raise InvalidBlockCentroidError(
        f"Invalid shape for block centroids: {block_centroids.shape}. "
        f"Must have 3 elements per centroid, not {block_centroids.shape[1]}")

    # Make sure the block sizes are sensible.
    if len(block_sizes.shape) != 2:
      raise InvalidBlockSizeError(
        f"Invalid shape for block sizes: {block_sizes.shape}. "
        f"Must have 2 dimensions, not {len(block_sizes.shape)}.")
    if block_sizes.shape[1] != 3:
      raise InvalidBlockSizeError(
        f"Invalid shape for block sizes: {block_sizes.shape}. "
        f"Must have 3 elements per block, not {block_sizes.shape[1]}")

    # We must make sure that block sizes and block centroids are the same
    # length as otherwise there will be blocks without sizes/centroids
    # which could cause odd behaviour if this function is called
    # multiple times.
    if block_sizes.shape[0] > block_centroids.shape[0]:
      log.warning("Given more sizes than centroids. Ignoring excess.")
      block_sizes = block_sizes[:block_centroids.shape[0]]
    elif block_sizes.shape[0] < block_centroids.shape[0]:
      log.warning("Given more centroids than sizes. Ignoring excess.")
      block_centroids = block_centroids[:block_sizes.shape[0]]

    # Ensure all block sizes are valid.
    if np.any(block_sizes <= 0):
      raise InvalidBlockSizeError("Block size must be greater than zero.")
    if np.any(block_sizes > self.block_resolution):
      raise InvalidBlockSizeError("Subblock cannot be larger than primary"
                                  "block size")

    if use_block_coordinates:
      # Ensure all of the centroids are valid.
      block_centroid_min = -0.5 * self.block_resolution
      block_centroid_max = (np.array(self._cached_block_dimensions()[::-1]) \
        - 0.5) * self.block_resolution
      if np.any(block_centroids < block_centroid_min):
        raise InvalidBlockCentroidError("All block centroids must be greater "
                                        f"than: {block_centroid_min}")
      if np.any(block_centroids > block_centroid_max):
        raise InvalidBlockCentroidError("All block centroids must be lower "
                                        f"than: {block_centroid_max}")

      # Adjust the blocks based on the rotation of the model and
      # the origin.
      block_centroids = self.convert_to_world_coordinates(block_centroids)

    try:
      new_block_centroids = np.vstack((self.block_centroids, block_centroids))
      new_block_sizes = np.vstack((self.block_sizes, block_sizes))
    except Exception as exception:
      # Due to the above error checking, this shouldn't happen.
      log.error(exception)
      raise

    self._set_block_centroids(new_block_centroids)
    self._set_block_sizes(new_block_sizes)

  def remove_block(self, index):
    """Deletes the block at the specified index.

    This operation is performed directly on the project to ensure that
    all properties (such as block_visibility and block_attributes) for the
    deleted block are deleted as well.

    Does nothing if requesting to delete a nonexistent block.

    Parameters
    ----------
    index : int
      Index of the block to the delete.

    Warning
    -------
    Any unsaved changes to the object when this function is called are
    discarded before the block is deleted. If you wish to keep these changes,
    call save() before calling this function.

    """
    if index < 0 or index >= self.block_count:
      return

    # Discard unsaved changes.
    self._invalidate_properties()
    self._delete_block(index)
    # Save to ensure this is left in a consistent state.
    self.save()

  def rotate(self, angle, axis):
    inverse_rotation = self._rotation.invert_rotation()
    super().rotate(angle, axis)
    if self._can_set_blocks and self.block_centroids.shape[0] != 0:
      self._adjust_centroids_for_rotation(inverse_rotation, self._rotation)

  def set_rotation(self, angle, axis):
    inverse_rotation = self._rotation.invert_rotation()
    super().set_rotation(angle, axis)
    if self._can_set_blocks and self.block_centroids.shape[0] != 0:
      self._adjust_centroids_for_rotation(inverse_rotation, self._rotation)

  def set_orientation(self, dip, plunge, bearing):
    inverse_rotation = self._rotation.invert_rotation()
    super().set_orientation(dip, plunge, bearing)
    if self._can_set_blocks and self.block_centroids.shape[0] != 0:
      self._adjust_centroids_for_rotation(inverse_rotation, self._rotation)

  @property
  def _can_set_blocks(self):
    return True

  def save(self):
    self._save_block_properties()
    self._reconcile_changes()

  def _invalidate_properties(self):
    BlockProperties._invalidate_properties(self)
