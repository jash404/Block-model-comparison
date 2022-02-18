"""Support for edge primitives.

An edge is a line between two points. In Python, an edge is represented
as a numpy array containing two integers representing the indices of the
points the edge connects. For example, the edge [0, 1] indicates the line
between the 0th and 1st point. Because edges are defined based on points, all
objects which inherit from EdgeProperties must also inherit from
PointProperties.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import logging

from .primitive_attributes import PrimitiveAttributes, PrimitiveType
from ..errors import CannotSaveInReadOnlyModeError, DegenerateTopologyError
from ...common import (trim_pad_1d_array, trim_pad_2d_array,
                       convert_array_to_rgba)
from ...internal.lock import WriteLock

log = logging.getLogger("mapteksdk.data")

# The following warning can be enabled if the <Primitive>Properties classes
# ended in Mixin as then pylint expects that the members are defined elsewhere.
# pylint: disable=no-member

class EdgeProperties:
  """Mixin class which provides spatial objects support for edge primitives.

  The edge [i, j] indicates the line is between the points Object.points[i]
  and Object.points[j].

  Functions and properties defined on this class are available on all
  classes which support edges.

  Notes
  -----
  Currently all objects which inherit from EdgeProperties also inherit
  from PointProperties to allow using the points from point properties
  to define the edges.

  """
  __edges = None
  __edge_colours = None
  __edge_selection = None
  __edge_attributes = None

  @property
  def _can_set_edges(self):
    """Returns true if the edges of the object can be set. If this is false,
    changes to the edges will never be saved to the project.

    This is false by default.

    """
    return False

  @property
  def edges(self):
    """A 2D Numpy array of edges of the form:
    [[i0, j0], [i1, j1], ..., [iN, jN]]
    where N is the number of edges and all iK and jK are valid indices
    in Object.points.

    Warnings
    --------
    For Surfaces the edges are derived from the points and facets. If any
    changes are made to the points or facets, the corresponding changes
    to the edges will not be made until save() has been called.

    Notes
    -----
    Invalid edges are removed during save().

    """
    if self.__edges is None:
      self.__edges = self._get_edges()
      if isinstance(self._lock, WriteLock):
        self.__edges.flags.writeable = self._can_set_edges
    return self.__edges

  def _set_edges(self, edges):
    """Private setter function for edges.

    Most objects implicitly define the edges based on other primitives so by
    default the setter for edges is not available.

    """
    if not self._can_set_edges:
      raise ValueError("This object does not support setting edges.")
    if edges is None:
      self.edges = None
    else:
      self.__edges = trim_pad_2d_array(edges, -1, 2, 0).astype(ctypes.c_uint32)

  @property
  def edge_colours(self):
    """The colours of the edges, represented as a numpy array of RGBA colours,
    with one colour for each edge.
    When setting the colour you may use RGB or greyscale colours instead.

    If there are more edge colours than edges, the excess colours are silently
    ignored. If there are fewer colours than edges, the uncoloured edges
    are coloured green.
    If only a single colour is passed, instead of padding with green
    all of the edges are coloured with that colour.
    ie: object.edge_colours = [[Red, Green, Blue]] will set all edge colours
    to be the colour [Red, Green, Blue].

    """
    if self.__edge_colours is None:
      self.__edge_colours = self._get_edge_colours()

    if self.__edge_colours.shape[0] != self.edge_count:
      self.__edge_colours = convert_array_to_rgba(self.__edge_colours,
                                                  self.edge_count)

    return self.__edge_colours

  @edge_colours.setter
  def edge_colours(self, edge_colours):
    if edge_colours is None:
      self.__edge_colours = edge_colours
    else:
      if len(edge_colours) != 1:
        self.__edge_colours = convert_array_to_rgba(edge_colours,
                                                    self.edge_count)
      else:
        # If only one colour given, colour all edges with that colour.
        self.__edge_colours = convert_array_to_rgba(
          edge_colours, self.edge_count, edge_colours[0])

  @property
  def edge_selection(self):
    """A 1D ndarray representing which edges are selected.

    edge_selection[i] = True indicates edge i is selected.

    """
    if self.__edge_selection is None:
      self.__edge_selection = self._get_edge_selection()

    if len(self.__edge_selection) != self.edge_count:
      self.__edge_selection = trim_pad_1d_array(
        self.__edge_selection, self.edge_count, False).astype(
          ctypes.c_bool)

    return self.__edge_selection

  @edge_selection.setter
  def edge_selection(self, edge_selection):
    if edge_selection is None:
      self.__edge_selection = edge_selection
    else:
      self.__edge_selection = trim_pad_1d_array(
        edge_selection, self.edge_count, False).astype(
          ctypes.c_bool)

  @property
  def edge_count(self):
    """The count of edges in the object."""
    # If the edges have not been loaded or set, get the edge
    # count from the DataEngine. Otherwise derive it.
    if self.__edges is None:
      return self._get_edge_count()
    return self.edges.shape[0]

  def _invalidate_properties(self):
    """Invalidates the cached edge properties. The next time one is requested
    its values will be loaded from the project.

    """
    self.__edges = None
    self.__edge_colours = None
    self.__edge_selection = None
    self.__edge_attributes = None


  def _save_edge_properties(self):
    """Save the edge properties.

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
      # Write all relevant properties for this primitive type.
      if self._can_set_edges:
        if self.edge_count == 0:
          message = "Object must contain at least one edge."
          raise DegenerateTopologyError(message)
        if self.__edges is not None:
          self._save_edges(self.edges)

      if self.__edge_colours is not None:
        self._save_edge_colours(self.edge_colours)

      if self.__edge_selection is not None:
        self._save_edge_selection(self.edge_selection)

      if self.__edge_attributes is not None:
        self.__edge_attributes.save_attributes()
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  @property
  def edge_attributes(self):
    """Access to custom edge attributes. These are arrays of values of the
    same type with one value for each edge.

    Use Object.edge_attributes[attribute_name] to access the edge attribute
    called attribute_name. See PrimitiveAttributes for valid operations
    on edge attributes.

    Returns
    -------
    PrimitiveAttributes
      Access to the edge attributes.

    Raises
    ------
    ValueError
      If the type of the attribute is not supported.

    Warnings
    --------
    For Surfaces if you have changed the points or facets in the object,
    you must call save() before accessing the edge attributes.

    """
    if self.__edge_attributes is None:
      self.__edge_attributes = PrimitiveAttributes(PrimitiveType.EDGE, self)
    return self.__edge_attributes

  def save_edge_attribute(self, attribute_name, data):
    """Create and/or edit the values of the edge attribute attribute_name.

    This is equivalent to Object.edge_attributes[attribute_name] = data

    Parameters
    ----------
    attribute_name : str
      The name of attribute.
    data : array_like
      An array_like of a base type data to store for the attribute
      per-primitive.

    Raises
    ------
    Exception
      If the object is opened in read-only mode.
    ValueError
      If the type of the attribute is not supported.

    """
    self.edge_attributes[attribute_name] = data

  def delete_edge_attribute(self, attribute_name):
    """Delete a edge attribute by name.

    Parameters
    ----------
    attribute_name : str
      The name of attribute

    Raises
    ------
    Exception
      If the object is opened in read-only mode.

    """
    self.edge_attributes.delete_attribute(attribute_name)
