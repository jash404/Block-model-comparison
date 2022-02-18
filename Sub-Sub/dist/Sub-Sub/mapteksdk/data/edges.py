"""Edge data types.

Data types which are based on edge primitives. This includes:

  - EdgeNetwork which has discontinuous lines/polylines in single object.
  - Polyline which represents an open polygon.
  - Polygon which represents a closed polygon.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import logging
import ctypes

import numpy as np

from ..capi import Modelling
from ..internal.lock import LockType
from .base import Topology
from .errors import DegenerateTopologyError
from .objectid import ObjectID
from .primitives import PointProperties, EdgeProperties

# pylint: disable=too-many-lines
# pylint: disable=too-many-instance-attributes
log = logging.getLogger("mapteksdk.data")

class Edge(EdgeProperties, PointProperties, Topology):
  """Base class for EdgeNetwork, Polygon and Polyline.

  Parameters
  ----------
  object_id : ObjectID
    The ID of the object to open. If None make a new Edge.

  lock_type : LockType
    The type of lock to place on the object. Default is Read.

  """
  # pylint: disable=too-many-instance-attributes
  def __init__(self, object_id, lock_type=LockType.READWRITE):
    super().__init__(object_id, lock_type)
    if object_id:
      self._invalidate_properties()

  def _invalidate_properties(self):
    """Invalidates the properties of the object. The next time a property
    is requested they will be loaded from what is currently saved in the
    project.

    This is called during initialisation and when operations performed
    invalidate the properties (such as primitive is removed and the changes
    are saved right away).

    """
    PointProperties._invalidate_properties(self)
    EdgeProperties._invalidate_properties(self)

  def save(self):
    self._save_point_properties()
    self._save_edge_properties()
    self._reconcile_changes()

class EdgeNetwork(Edge):
  """An edge network can contain multiple discontinuous lines/polylines in
  single object. Unlike Polyline and Polygon, the user must explicitly
  set the edges in the EdgeNetwork.

  Examples
  --------
  Creating an edge network with an edge between points 0 and
  point 1 and a second edge edge between points 2 and 3.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import EdgeNetwork
  >>> project = Project()
  >>> with project.new("cad/edges", EdgeNetwork) as new_network:
  >>>     new_network.points = [[0, 0, 0], [1, 2, 3], [0, 0, 1], [0, 0, 2]]
  >>>     new_network.edges = [[0, 1], [2, 3]]

  """
  # pylint: disable=too-many-instance-attributes
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    if object_id is None:
      object_id = ObjectID(Modelling().NewEdgeNetwork())
    super().__init__(object_id, lock_type)

  @property
  def _can_set_edges(self):
    return True

  # pylint: disable=no-member
  @EdgeProperties.edges.setter
  def edges(self, edges):
    # The pylint disable is needed because we are adding a setter
    # which does not exist in the parent class.
    self._set_edges(edges)

  def remove_edges(self, edge_indices, update_immediately=True):
    """Remove one or more edges at a given index of the edges array.
    This is done directly in the project.

    Parameters
    ----------
    edge_indices : array or int
      Edge index to remove or a list of edge indices to remove.

    update_immediately : bool
      If True, perform the deletion directly in the Project.
      If False, wait until the Object is closed before
      performing the operation.

    Returns
    -------
    bool
      True if successful.

    """
    if isinstance(edge_indices, int):
      remove_request = self._remove_edge(edge_indices)
    else:
      remove_request = self._remove_edges(edge_indices)
    if remove_request and update_immediately:
      self._invalidate_properties()
    return remove_request

  @classmethod
  def static_type(cls):
    """Return the type of edge network as stored in a Project.

    This can be used for determining if the type of an object is an edge
    network.

    """
    return Modelling().EdgeNetworkType()

class Polyline(Edge):
  """A polyline is formed from an ordered sequence of points, where
  edges are between consecutive points. For example, the first edge is
  from point 0 to point 1. The second edge is from point 1 to point 2
  and so on.

  This type is also known as a continuous unclosed line, edge chain or string.

  Raises
  ------
  DegenerateTopologyError
    If the Polyline contains fewer than two points when save() is called.

  Notes
  -----
  The edges of a polyline object are implicitly defined by the points.
  The first edge is between point 0 and point 1, the second edge is
  between point 1 and point 2 and so on. Because the edges are derived
  in this way, editing the edges of a polyline is ambiguous and
  not supported. To change the edges, edit the points instead.
  If you need to edit or remove edges from a polyline, consider using
  an EdgeNetwork instead.

  Examples
  --------
  Create a c shape.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Polyline
  >>> project = Project()
  >>> with project.new("cad/c_shape", Polyline) as new_line:
  >>>     new_line.points = [[1, 1, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0]]

  Create a square. Note that a Polygon would be more appropriate for
  creating a square as it would not require the last point.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Polyline
  >>> project = Project()
  >>> with project.new("cad/square", Polyline) as new_line:
  >>>     new_line.points = [[0, 0, 0], [1, 0, 0], [1, 1, 0],
  >>>                        [0, 1, 0], [0, 0, 0]]

  """
  # pylint: disable=too-many-instance-attributes
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    if object_id is None:
      object_id = ObjectID(Modelling().NewEdgeChain())
    super().__init__(object_id, lock_type)

  @property
  def edges(self):
    edges = np.arange(self.point_count, dtype=ctypes.c_uint32)
    edges = np.repeat(edges, 2)
    edges.flags.writeable = False
    return edges[1:-1].reshape(-1, 2)

  @property
  def edge_count(self):
    return self.point_count - 1

  @classmethod
  def static_type(cls):
    """Return the type of polyline as stored in a Project.

    This can be used for determining if the type of an object is a polyline.

    """
    return Modelling().EdgeChainType()

  def save(self):
    if self.point_count < 2:
      raise DegenerateTopologyError(
        "Polyline objects must contain at least two points.")
    self._save_point_properties()
    # Reconcile changes to ensure the edge arrays are the correct length.
    self._reconcile_changes()
    self._save_edge_properties()
    self._reconcile_changes()

class Polygon(Edge):
  """A polygon is formed from an ordered sequence of points, with edges
  between consecutive points. For example, the first edge is between
  point 0 and point 1, the second edge is between point 1 and point 2
  and the final edge is between point n - 1 and point 0 (where n is the number
  of points).
  Unlike an Polyline, a Polygon is a closed loop of edges.

  Also known as a closed line or edge loop.

  See Also
  --------
  Edge : Parent class of Polygon
  EdgeNetwork : Class which supports editing edges.

  Notes
  -----
  The edges of a polygon are implicitly defined by the points. For a polygon
  with n edges, the first edge is between points 0 and 1, the second edge is
  between points 1 and 2, and the final edge is between points n - 1 and
  0. Because the edges are derived from the points, editing
  the edges is not supported - you should edit the points instead.
  If you need to edit or remove edges without changing points
  consider using an EdgeNetwork instead.

  Raises
  ------
  DegenerateTopologyError
    If the Polygon contains fewer than three points when save() is called.

  Examples
  --------
  Create a diamond

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Polygon
  >>> project = Project()
  >>> with project.new("cad/polygon_diamond", Polygon) as new_diamond:
  >>>     new_diamond.points = [[1, 0, 0], [0, 1, 0], [1, 2, 0], [2, 1, 0]]

  """
  # pylint: disable=too-many-instance-attributes
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    if object_id is None:
      object_id = ObjectID(Modelling().NewEdgeLoop())
    super().__init__(object_id, lock_type)

  @property
  def edges(self):
    edges = np.zeros(self.point_count * 2, dtype=ctypes.c_uint32)
    temp = np.arange(1, self.point_count, dtype=ctypes.c_uint32)
    edges[1:-1] = np.repeat(temp, 2)
    edges.flags.writeable = False
    return edges.reshape(-1, 2)

  @property
  def edge_count(self):
    return self.point_count

  @classmethod
  def static_type(cls):
    """Return the type of polygon as stored in a Project.

    This can be used for determining if the type of an object is a polygon.

    """
    return Modelling().EdgeLoopType()

  def save(self):
    if self.point_count < 3:
      raise DegenerateTopologyError(
        "Polygon objects must contain at least three points.")
    self._save_point_properties()
    # Reconcile changes to ensure the edge arrays are the correct length.
    self._reconcile_changes()
    self._save_edge_properties()
    self._reconcile_changes()
