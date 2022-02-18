"""Implementation for sparse block model objects.

SparseBlockModel should be moved into data/blocks.py once the implementation
has been finished and appropriate tests have been written. Or deleted.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import logging

from ..capi import Modelling
from ..data.primitives import BlockProperties
from ..data.objectid import ObjectID
from ..data.base import Topology
from ..data.errors import CannotSaveInReadOnlyModeError
from ..internal.lock import LockType, WriteLock

log = logging.getLogger("mapteksdk.data.blocks")

# =========================================================================
#
#                        SPARSE BLOCK MODEL
#
# =========================================================================
class SparseBlockModel(Topology, BlockProperties):
  """Sparse Block Model Class. This is similar to a dense block model,
  however it allows for 'holes' in the model - there can be regions
  within the extent of the model which do not contain a block.

  This allows for more compact storage for block models where a large
  proportion of the blocks do not contain data as blocks which do not
  contain data do not need to be stored. For block models in which
  most blocks contain data, a dense block model will provide more
  efficient storage.

  Parameters
  ----------
  x_res : double
    The x resolution.
  y_res : double
    The y resolution.
  z_res : double
    The z resolution.
  x_count : int
    The x count of blocks.
  y_count : int
    The y count of blocks.
  z_count : int
    The z count of blocks.

  See Also
  --------
  DenseBlockModel : Block model which does not allow holes.

  Notes
  -----
  Parameters are only required for new block models.

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE,
               x_res=0, y_res=0, z_res=0,
               x_count=0, y_count=0, z_count=0):
    if object_id is None:
      # pylint: disable=invalid-name
      # Create new block model
      object_id = ObjectID(Modelling().NewBlockNetworkSparse(
        x_res, y_res, z_res, x_count, y_count, z_count))

    super().__init__(object_id, lock_type)

    if object_id is None:
      error_msg = 'Cannot create sparse block model'
      log.error(error_msg)
      raise RuntimeError(error_msg)

  @classmethod
  def static_type(cls):
    """Return the type of sparse block model as stored in a Project.

    This can be used for determining if the type of an object is a sparse
    block model.

    """
    return Modelling().BlockNetworkSparseType()

  @property
  def block_count(self):
    """Returns the number of blocks in the block model."""
    return super().block_count

  @block_count.setter
  def block_count(self, block_count):
    if isinstance(self._lock, WriteLock):
      Modelling().SetBlockCount(self._lock.lock, block_count)
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  def save(self):
    self._save_block_properties()
    self._reconcile_changes()

  def _invalidate_properties(self):
    BlockProperties._invalidate_properties(self)
