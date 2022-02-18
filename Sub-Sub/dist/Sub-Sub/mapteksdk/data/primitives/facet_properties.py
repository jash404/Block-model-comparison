"""Support for facet primitives.

A facet is a triangle defined by three points. In Python, a facet is
represented as a numpy array containing three integers representing the
indices of the points which make up the three corners of the triangle.
For example, the facet [0, 1, 2] indicates the triangle defined by the
0th, 1st and 2nd points. Because facets are defined based on points, all
objects which inherit from FacetProperties must also inherit from
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

class FacetProperties:
  """Mixin class which provides spatial objects support for facet primitives.

  A facet is a triangle drawn between three points. For example, the
  facet [i, j, k] is the triangle drawn between object.points[i],
  object.points[j] and object.points[k].

  Functions and properties defined on this class are available on all
  classes which support facets.

  """
  __facets = None
  __facet_colours = None
  __facet_selection = None
  __facet_attributes = None

  @property
  def facets(self):
    """A 2D numpy array of facets in the object. This is of the form:
    [[i0, j0, k0], [i1, j1, k1], ..., [iN, jN, kN]] where N is the
    number of facets. Each i, j and k value is the index of the point
    in Objects.points for the point used to define the facet.

    """
    if self.__facets is None:
      self.__facets = self._get_facets()
    return self.__facets

  @facets.setter
  def facets(self, facets):
    if facets is None:
      self.__facets = None
    else:
      self.__facets = trim_pad_2d_array(facets, -1, 3, 0).astype(
        ctypes.c_uint32)

  @property
  def facet_colours(self):
    """A 2D numpy array containing the colours of the facets.
    When setting the colour you may use a list of RGB or greyscale colours.

    When facet colours are set, if there are more colours than facets then
    the excess colours are silently ignored. If there are fewer colours
    than facets the uncoloured facets are coloured green.
    If only a single colour is specified, instead of padding with green
    all of the facets are coloured with that colour.
    ie: object.facet_colours = [[Red, Green, Blue]] will set all facets to
    be the colour [Red, Green, Blue].

    """
    if self.__facet_colours is None:
      self.__facet_colours = self._get_facet_colours()

    if self.__facet_colours.shape[0] != self.facet_count:
      self.__facet_colours = convert_array_to_rgba(self.__facet_colours,
                                                   self.facet_count)

    return self.__facet_colours

  @facet_colours.setter
  def facet_colours(self, facet_colours):
    if facet_colours is None:
      self.__facet_colours = facet_colours
    else:
      if len(facet_colours) != 1:
        self.__facet_colours = convert_array_to_rgba(facet_colours,
                                                     self.facet_count)
      else:
        self.__facet_colours = convert_array_to_rgba(
          facet_colours, self.facet_count,
          facet_colours[0])

  @property
  def facet_selection(self):
    """A 1D numpy array representing which facets are selected.

    If object.facet_selection[i] = True then the ith facet
    is selected.

    """
    if self.__facet_selection is None:
      self.__facet_selection = self._get_facet_selection()

    if self.__facet_selection.shape[0] != self.facet_count:
      self.__facet_selection = trim_pad_1d_array(
        self.__facet_selection, self.facet_count, False).astype(
          ctypes.c_bool)

    return self.__facet_selection

  @facet_selection.setter
  def facet_selection(self, facet_selection):
    if facet_selection is None:
      self.__facet_selection = facet_selection
    else:
      self.__facet_selection = trim_pad_1d_array(
        facet_selection, self.facet_count, False).astype(
          ctypes.c_bool)

  @property
  def facet_count(self):
    """The number of facets in the object."""
    if self.__facets is None:
      return self._get_facet_count()
    return self.facets.shape[0]

  def _invalidate_properties(self):
    """Invalidates the cached facet properties. The next time one is requested
    its values will be loaded from the project.

    """
    self.__facets = None
    self.__facet_colours = None
    self.__facet_selection = None
    self.__facet_attributes = None

  def remove_facets(self, facet_indices, update_immediately=True):
    """Remove one or more facets. This is done directly in the project
    and thus changes made by this function will be saved even if save()
    is not called.

    Parameters
    ----------
    facet_indices : array or int
      1D array of uint32 indices of edges to remove or a single uint32 of
      index of facet to remove.

    update_immediately : bool
      Applies changes to project and re-loads numpy arrays and properties
      immediately. May be disabled for large datasets.

    Returns
    -------
    bool
      True if successful.

    Notes
    -----
    Immediately reconciling changes on arrays is recommended.

    """
    if isinstance(facet_indices, int):
      remove_request = self._remove_facet(facet_indices)
    else:
      remove_request = self._remove_facets(facet_indices)
    if remove_request and update_immediately:
      self._invalidate_properties()
    return remove_request

  def _save_facet_properties(self):
    """Save the facet properties.

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
      # Write all relevant properties for this primitive type
      if self.facet_count == 0:
        message = "Object must contain at least one facet"
        raise DegenerateTopologyError(message)

      if self.__facets is not None:
        self._save_facets(self.facets)

      if self.__facet_colours is not None:
        self._save_facet_colours(self.facet_colours)

      if self.__facet_selection is not None:
        self._save_facet_selection(self.facet_selection)

      if self.__facet_attributes is not None:
        self.__facet_attributes.save_attributes()

    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  @property
  def facet_attributes(self):
    """Access the custom facet attributes. These are arrays of values of the
    same type with one value for each facet.

    Use Object.facet_attributes[attribute_name] to access a facet attribute
    called attribute_name. See PrimitiveAttributes for valid operations
    on facet attributes.

    Returns
    -------
    PrimitiveAttributes
      Access to the facet attributes.

    Raises
    ------
    ValueError
      If the type of the attribute is not supported.

    """
    if self.__facet_attributes is None:
      self.__facet_attributes = PrimitiveAttributes(PrimitiveType.FACET, self)
    return self.__facet_attributes

  def save_facet_attribute(self, attribute_name, data):
    """Create new and/or edit the values of the facet attribute attribute_name.

    This is equivalent to Object.facet_attributes[attribute_name] = data.

    Parameters
    ----------
    attribute_name : str
      The name of attribute.
    data : array
      A numpy array of a base type data to store for the attribute
      per-primitive.

    """
    self.facet_attributes[attribute_name] = data

  def delete_facet_attribute(self, attribute_name):
    """Delete a facet attribute by name.

    This is equivalent to: facet_attributes.delete_attribute(attribute_name)

    Parameters
    ----------
    attribute_name : str
      The name of attribute.

    Raises
    ------
    Exception
      If the object is opened in read-only mode.

    """
    self.facet_attributes.delete_attribute(attribute_name)
