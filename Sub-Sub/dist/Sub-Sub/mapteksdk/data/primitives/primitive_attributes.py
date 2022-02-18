"""Access to primitive attributes.

Unlike object attributes, which have one value for the entire object,
primitive attributes have one value for each primitive of a particular type.
For example, a point primitive attribute has one value for each point and
a block primitive attribute has one value for each block.

Users of the SDK should never need to construct these objects directly.
Instead, they should be accessed via the point_attributes, edge_attributes,
facet_attributes, cell_attributes and block_attributes properties.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import enum
import logging

import numpy as np

from ..colourmaps import NumericColourMap, StringColourMap, ObjectID
from ..errors import CannotSaveInReadOnlyModeError
from ...capi import Modelling
from ...capi.types import T_ObjectHandle
from ...common import trim_pad_1d_array
from ...internal.lock import WriteLock
from ...internal.util import array_of_pointer

log = logging.getLogger("mapteksdk.data")

class PrimitiveType(enum.Enum):
  """Enumeration of fundamental primitive types."""
  POINT = 1
  EDGE = 2
  FACET = 3
  TETRA = 4
  CELL = 5
  BLOCK = 6


class PrimitiveAttributes:
  """Provides access to the attributes for a given primitive type on an object.

  A primitive attribute is an attribute with one value for each primitive
  of a particular type. For example, if an object contains ten points
  then a point primitive attribute would have ten values - one for each
  point. Primitive attributes can be accessed by name using the [] operator
  (This is similar to accessing a dictionary).

  Parameters
  ----------
  primitive_type : PrimitiveType
    The type of primitive these attributes are from.

  owner_object : Any
    The object that the attributes are from.

  Warnings
  --------
  Primitive attributes set through the Python SDK may not appear in the user
  interface of Maptek applications.

  Edge and facet primitive attributes are not well supported by Maptek
  applications. You can read and write values from/to them via the SDK,
  however they are not visible from the application side.

  Notes
  -----
  It is not recommended to create PrimitiveAttribute objects directly.
  Instead use `PointProperties.point_attributes`,
  `EdgeProperties.edge_attributes` or `FacetProperties.facet_attributes`.

  Examples
  --------
  Create a point primitive attribute of type string called "temperature".
  Note that new_set.point_attributes["temperature"][i] is the value
  associated with new_set.points[i] (so point[0] has the attribute "Hot",
  point[1] has the attribute "Warm" and point[2] has the attribute["Cold"]).

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import PointSet
  >>> project = Project()
  >>> with project.new("cad/points", PointSet) as new_set:
  >>>     new_set.points = [[1, 1, 0], [2, 0, 1], [3, 2, 0]]
  >>>     new_set.point_attributes["temperature"] = ["Hot", "Warm", "Cold"]

  Colour the point set created in the previous example with a colour map
  such that points with attribute "Hot" are red, "Warm" are orange and
  "Cold" are blue.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import StringColourMap
  >>> project = Project()
  >>> with project.new("legends/heatMap", StringColourMap) as new_legend:
  >>>     new_legend.legend = ["Hot", "Warm", "Cold"]
  >>>     new_legend.colours = [[255, 0, 0], [255, 165, 0], [0, 0, 255]]
  >>> with project.edit("cad/points") as edit_set:
  >>>     edit_set.point_attributes.set_colour_map("temperature", new_legend)

  """

  __attribute_table = {
    0: None, 1: ctypes.c_bool, 2: ctypes.c_uint8, 3: ctypes.c_int8,
    4: ctypes.c_uint16, 5: ctypes.c_int16, 6: ctypes.c_uint32,
    7: ctypes.c_int32, 8: ctypes.c_uint64, 9: ctypes.c_int64,
    10: ctypes.c_float, 11: ctypes.c_double, 12: ctypes.c_char_p,
  }

  def __init__(self, primitive_type, owner_object):
    self.primitive_type = primitive_type
    self.owner = owner_object
    self.__attributes = {}
    self.__deleted_attributes = []
    self.__colour_map = None
    self.__colour_map_attribute = None

    # Populate the attribute names, but set the values as None to indicate they
    # haven't been loaded yet.
    for name in self._load_names():
      self.__attributes[name] = None

  @property
  def names(self):
    """Returns the names of the attributes. Use this to iterate over all
    attributes.

    Returns
    -------
    dict_keys
      The names of the attributes associated with this primitive.

    Raises
    ------
    RuntimeError
      If an attribute is deleted while iterating over names.

    Examples
    --------
    Iterate over all attributes and print their values. This assumes
    there is a object with points at cad/points.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.edit("cad/points") as point_set:
    ...     for name in point_set.point_attributes.names:
    ...         print(point_set.point_attributes[name])

    """
    return self.__attributes.keys()

  def __getitem__(self, name):
    """Allows access to the attributes.

    object.point_attributes[name] will return the point attribute with the
    specified name.

    Parameters
    ----------
    name : str
      Name of the primitive attribute to get the value of.

    Returns
    -------
    ndarray
      numpy array of length number_of_primitives containing the values for the
      specified primitive attribute.

    Raises
    ------
    KeyError
      If there is no primitive attribute with the specified name.

    """
    # Load the attribute if not loaded already.
    if self.__attributes[name] is None:
      self.__attributes[name] = self._load_attribute(name)
    # :TODO: Jayden Boskell 2021-09-13 SDK-517 This should probably be how
    # trim_pad_1d_array is implemented.
    primitive_count = self.primitive_count
    current_count = self.__attributes[name].shape[0]
    # Make sure the attribute array is the right size.
    if current_count > primitive_count:
      self.__attributes[name] = self.__attributes[name][:primitive_count]
    elif current_count < primitive_count:
      new_array = np.zeros((self.primitive_count,),
                           dtype=self.__attributes[name].dtype)
      new_array[:current_count] = self.__attributes[name]
      self.__attributes[name] = new_array
    return self.__attributes[name]

  def __setitem__(self, name, value):
    """Allows attributes to be set.

    object.point_attributes[name] = value will set the point attribute
    of the specified name to value. Note that value should be an array-like
    with one element for each primitive of the specified primitive type.
    If the value is too short it will be padded until it is the correct length,
    and if it is too long it will be silently truncated.

    Parameters
    ----------
    name : string
      The name of the attribute to set.
    value : array_like
      An array_like of values of the same type with length = number of
      primitives of this type in the object.

    Raises
    ------
    ValueError
      If name is not a string.

    """
    if not isinstance(name, str):
      raise ValueError(f"Invalid type for name: {type(name)}")

    data = np.array(value)
    # Choose the correct value to fill the attributes array with.
    fill_value = 0
    if data.dtype.kind in {'U', 'S'}:
      fill_value = ""

    data = trim_pad_1d_array(data, self.primitive_count, fill_value)
    self.__attributes[name] = data

  def __contains__(self, name):
    """Implementation of the in operator for primitive attributes."""
    return name in self.names

  def delete_attribute(self, name):
    """Deletes the attribute with name, if it exists.

    This method does not throw an exception if the attribute does not exist.

    Parameters
    ----------
    name : string
      The name of the primitive attribute to delete.

    """
    if name in self.__attributes:
      self.__deleted_attributes.append(name)
      self.__attributes.pop(name, None)

  @property
  def colour_map(self):
    """Get the colour map used to colour the primitives.

    This returns the colour map passed into set_colour_map.

    Returns
    -------
    ObjectID
      Object id of the colour map associated with this object.
    None
      If no colour map is associated with this object.

    """
    if self.__colour_map is None:
      self.__load_colour_map()
    return self.__colour_map

  @property
  def colour_map_attribute(self):
    """Returns the attribute the colour map is associated with.

    Returns
    -------
    string
      Name of attribute associated with the colour map.
    None
      If no colour map is associated with this primitive.

    """
    if self.__colour_map_attribute is None:
      self.__load_colour_map()
    return self.__colour_map_attribute

  def set_colour_map(self, attribute, colour_map):
    """Set the colour map for this type of primitive.

    Parameters
    ----------
    attribute : string
      The name of the attribute to colour by.
    colour_map : ObjectID or NumericColourMap or StringColourMap
      Object id of the colour map to use for this object. You can also pass
      the colour map directly.

    Raises
    ------
    ValueError
      If colour map is an invalid type.
    RuntimeError
      If this object's primitive type is not point.

    Warnings
    --------
    An object can have only one colour map associated with it at a time! If
    this function is called multiple times (including on different primitives)
    it is undefined which call (if any) will be honoured.

    Associating a colour map to edge, facet or cell attributes is not currently
    supported by the viewer. Attempting to do so will raise a RuntimeError.

    Notes
    -----
    Calling this functions triggers an implicit save operation on the owning
    object, causing all changes to be saved to the Project.

    """
    if self.primitive_type not in (PrimitiveType.POINT, PrimitiveType.BLOCK):
      name = self.primitive_type.name.lower() + " attributes"
      raise RuntimeError(f"Setting a colour map to {name} is not supported.")
    self.owner.save()
    if colour_map is None:
      # Passing None unsets the colour map, resulting in no change.
      self.__colour_map = None
      self.__colour_map_attribute = None
    elif isinstance(colour_map, (NumericColourMap, StringColourMap)):
      # Handing for if the user passes the colour map directly.
      self.__colour_map_attribute = attribute
      self.__colour_map = colour_map.id
    elif not isinstance(colour_map, ObjectID):
      # Raise an error if the user didn't pass a colour map or a ObjectId
      # which represents a colour map.
      raise ValueError(
        f"Invalid colour map: {colour_map} of type: {type(colour_map)}")
    elif colour_map.is_a(NumericColourMap) or colour_map.is_a(StringColourMap):
      # The above lines would look nicer and be more maintainable if there was
      # a base class for colour maps.
      self.__colour_map = colour_map
      self.__colour_map_attribute = attribute
    else:
      raise ValueError(f"Object {colour_map} is not a valid colour map.")

  @property
  def primitive_count(self):
    """The number of primitives of the given type in the object.

    Returns
    -------
    int
      Number of points, edges, facets or blocks. Which is returned depends
      on primitive type given when this object was created.

    Raises
    ------
    ValueError
      If the type of primitive is unsupported.

    """
    if self.primitive_type == PrimitiveType.POINT:
      return self.owner.point_count
    if self.primitive_type == PrimitiveType.EDGE:
      return self.owner.edge_count
    if self.primitive_type == PrimitiveType.FACET:
      return self.owner.facet_count
    if self.primitive_type == PrimitiveType.BLOCK:
      return self.owner.block_count
    if self.primitive_type == PrimitiveType.CELL:
      return self.owner.cell_count
    raise ValueError('Unexpected primitive type %r' % self.primitive_type)

  def save_attributes(self):
    """Saves changes to the attributes to the Project.

    This should not need to be explicitly called - it is called during save()
    and close() of an inheriting object. It is not recommended to call this
    function directly.

    """
    # Delete the attributes which were deleted.
    for deleted in self.__deleted_attributes:
      self._delete_attribute(deleted)
    self.__deleted_attributes = []
    # Set the existing attributes.
    for name, value in self.__attributes.items():
      if value is not None:
        self._save_attribute(name, value)
    # Set the colour map if possible.
    if self.__colour_map is not None:
      self._save_colour_map(self.__colour_map_attribute, self.colour_map)

  def type_of_attribute(self, name):
    """Returns the ctype of the specified attribute."""
    if self[name].dtype.kind in {'U', 'S'}:
      return ctypes.c_char_p
    return np.ctypeslib.as_ctypes_type(self[name].dtype)

  def _load_type_of_attribute(self, name):
    """Loads the type of the attribute called name from the Project.

    Parameters
    ----------
    name : str
      The name of the attribute.

    Returns
    -------
    type
      A type from ctypes that represented the type of the attributes.

    Raises
    ------
    ValueError
      If this type of primitive isn't supported or doesn't have attributes.

    """

    # TODO: It may be simpler to return a type from ctypes instead. That way
    # the user doesn't have to compare the strings.

    if self.primitive_type == PrimitiveType.POINT:
      type_query_function = Modelling().PointAttributeType
    elif self.primitive_type == PrimitiveType.EDGE:
      type_query_function = Modelling().EdgeAttributeType
    elif self.primitive_type == PrimitiveType.FACET:
      type_query_function = Modelling().FacetAttributeType
    elif self.primitive_type == PrimitiveType.BLOCK:
      type_query_function = Modelling().BlockAttributeType
    elif self.primitive_type == PrimitiveType.CELL:
      type_query_function = Modelling().CellAttributeType
    else:
      raise ValueError('Unexpected primitive type %r' % self.primitive_type)

    name = name.encode('utf-8')
    # pylint:disable=protected-access; reason="This is a mixin class"
    attribute_type = type_query_function(self.owner._lock.lock, name)
    return self.__attribute_table[attribute_type]

  def _load_names(self):
    """Loads the names of all attributes from the Project.

    Returns
    -------
    list
      List of str, one for each attribute name.

    """
    if self.primitive_type == PrimitiveType.POINT:
      name_query_function = Modelling().ListPointAttributeNames
    elif self.primitive_type == PrimitiveType.EDGE:
      name_query_function = Modelling().ListEdgeAttributeNames
    elif self.primitive_type == PrimitiveType.FACET:
      name_query_function = Modelling().ListFacetAttributeNames
    elif self.primitive_type == PrimitiveType.BLOCK:
      name_query_function = Modelling().ListBlockAttributeNames
    elif self.primitive_type == PrimitiveType.CELL:
      name_query_function = Modelling().ListCellAttributeNames
    else:
      raise ValueError('Unexpected primitive type %r' % self.primitive_type)

    # pylint:disable=protected-access; reason="This is a mixin class"
    buffer_size = name_query_function(self.owner._lock.lock, None, 0)
    string_buffer = ctypes.create_string_buffer(buffer_size)
    name_query_function(self.owner._lock.lock, string_buffer, buffer_size)
    # The last two items after the split are ignored because the last string is
    # null-terminated and the list itself is null-terminated, so there are no
    # name between them and there is no name after the final terminator.
    return bytearray(string_buffer).decode('utf-8').split('\x00')[:-2]

  def _load_attribute(self, name):
    """Return a numpy array of the values for an attribute called name.

    Parameters
    ----------
    name : str
      The name of the attribute.

    Returns
    -------
    numpy.ndarray
      The numpy array of values for the attribute.

    Raises
    ------
    ValueError
      If the type of primitive is unsupported.
      If the type of the attribute is unsupported.

    """
    array_type = self._load_type_of_attribute(name)

    type_to_function = {
      ctypes.c_float: '{}AttributeFloat32BeginR',
      ctypes.c_double: '{}AttributeFloat64BeginR',
      ctypes.c_int64: '{}AttributeInt64sBeginR',
      ctypes.c_uint64: '{}AttributeInt64uBeginR',
      ctypes.c_int32: '{}AttributeInt32sBeginR',
      ctypes.c_uint32: '{}AttributeInt32uBeginR',
      ctypes.c_int16: '{}AttributeInt16sBeginR',
      ctypes.c_uint16: '{}AttributeInt16uBeginR',
      ctypes.c_int8: '{}AttributeInt8sBeginR',
      ctypes.c_uint8: '{}AttributeInt8uBeginR',
      ctypes.c_bool: '{}AttributeBoolBeginR',
      ctypes.c_char_p: '{}AttributeStringBeginR',
    }

    function_name = type_to_function.get(array_type)
    if function_name is None:
      raise ValueError('The type of the attribute (%s) is an unsupported type.'
                       % array_type)

    if self.primitive_type == PrimitiveType.POINT:
      function_name = function_name.format('Point')
    elif self.primitive_type == PrimitiveType.EDGE:
      function_name = function_name.format('Edge')
    elif self.primitive_type == PrimitiveType.FACET:
      function_name = function_name.format('Facet')
    elif self.primitive_type == PrimitiveType.BLOCK:
      function_name = function_name.format('Block')
    elif self.primitive_type == PrimitiveType.CELL:
      function_name = function_name.format('Cell')
    else:
      raise ValueError('The primitive type %r is an unsupported type.' %
                       self.primitive_type)

    # pylint:disable=protected-access; reason="This is a mixin class"
    ptr = getattr(Modelling(), function_name)(self.owner._lock.lock,
                                              name.encode('utf-8'))
    if not ptr:
      try:
        Modelling().RaiseOnErrorCode()
      except MemoryError as error:
        log.error('Failed to read the %s attribute (%s) on %s: %s',
                  self.primitive_type.name, name, self.owner.id, str(error))
        raise MemoryError(
          'The attribute could not fit in the Project\'s cache') from None
      except:
        log.exception('Failed to read the attribute (%s) on %s',
                      name, self.owner.id)
        raise

    # Strings have special case handling, as each string can have a variable
    # length and the data is potentially stored outside the array.
    if array_type == ctypes.c_char_p:
      str_array = []
      # There will be a string for each primitive.
      for index in range(0, self.primitive_count):
        # Get the modelling library to work out how to store the strings
        # by iterating over each and feeding it in
        str_len = Modelling().AttributeGetString(
          ptr, index, None, 0)
        str_buffer = ctypes.create_string_buffer(str_len)
        Modelling().AttributeGetString(
          ptr, index, str_buffer, str_len)
        str_array.append(str_buffer.value.decode("utf-8"))
      return np.array(str_array)  # Convert list to numpy array and return

    attribute_array = array_of_pointer(
      ptr, ctypes.sizeof(array_type) * self.primitive_count, array_type).copy()
    attribute_array.setflags(write=isinstance(self.owner._lock, WriteLock))
    return attribute_array

  def _save_colour_map(self, attribute_name, colour_map):
    """Saves the colour map to the Project.

    Parameters
    ----------
    attribute_name : str
      Name of attribute to colour by colour_map
    colour_map : ObjectID
      The ID of the colour map object to use.

    Raises
    ------
    ValueError
      If this type of primitive doesn't support setting a colour map.
    Exception
      If the object is opened in read-only mode.

    """
    # pylint:disable=protected-access; reason="This is a mixin class"
    if isinstance(self.owner._lock, WriteLock):
      if self.primitive_type == PrimitiveType.POINT:
        set_function = Modelling().SetDisplayedPointAttribute
      elif self.primitive_type == PrimitiveType.EDGE:
        set_function = Modelling().SetDisplayedEdgeAttribute
      elif self.primitive_type == PrimitiveType.FACET:
        set_function = Modelling().SetDisplayedFacetAttribute
      elif self.primitive_type == PrimitiveType.BLOCK:
        set_function = Modelling().SetDisplayedBlockAttribute
      elif self.primitive_type == PrimitiveType.CELL:
        set_function = Modelling().SetDisplayedCellAttribute
      else:
        raise ValueError('Unexpected primitive type %r' % self.primitive_type)
      set_function(
        self.owner._lock.lock,
        attribute_name.encode('utf-8'),
        colour_map.handle)
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  def _load_colour_map(self):
    """Loads the associated colour map from the Project.

    Returns
    -------
    ObjectID
      The colour map associated with this object.

    """
    # pylint:disable=protected-access; reason="This is a mixin class"
    result = Modelling().GetDisplayedColourMap(
      self.owner._lock.lock)
    # If result is zero, no colour map was set.
    if result.value != 0:
      return ObjectID(T_ObjectHandle(result.value))
    return None

  def __load_colour_map(self):
    """Loads information related to the colour map into memory."""
    # pylint:disable=protected-access; reason="This is a mixin class"
    try:
      colour_map_attribute_type = \
        Modelling().GetDisplayedAttributeType(
          self.owner._lock.lock)
    except AttributeError:
      # If the above method can't be found, assume the Primitive type
      # is point.
      colour_map_attribute_type = PrimitiveType.POINT

    if colour_map_attribute_type != self.primitive_type.value:
      # Either no colour map is associated, or it isn't associated with
      # an attribute of this type.
      return

    length = Modelling().GetDisplayedAttribute(
      self.owner._lock.lock,
      None,
      0)
    str_buffer = ctypes.create_string_buffer(length)
    Modelling().GetDisplayedAttribute(
      self.owner._lock.lock,
      str_buffer,
      length)

    name = str_buffer.value.decode("utf-8")
    if not name:
      return

    # Avoid reporting that the colour map is associated with a attribute which
    # does not exist.
    if name in self.names:
      self.__colour_map_attribute = name
      self.__colour_map = self._load_colour_map()

  def _delete_attribute(self, name):
    """Delete an array of attribute values for this primitive type based on
    name. This version of the function performs the deletion in the Project.

    Parameters
    ----------
    name : str
      The name of attribute

    Raises
    ------
    Exception
      If the object is opened in read-only mode.
    ValueError
      If the primitive type is not supported.

    """
    # pylint:disable=protected-access; reason="This is a mixin class"
    if isinstance(self.owner._lock, WriteLock):
      if self.primitive_type == PrimitiveType.POINT:
        delete_function = Modelling().DeletePointAttribute
      elif self.primitive_type == PrimitiveType.EDGE:
        delete_function = Modelling().DeleteEdgeAttribute
      elif self.primitive_type == PrimitiveType.FACET:
        delete_function = Modelling().DeleteFacetAttribute
      elif self.primitive_type == PrimitiveType.BLOCK:
        delete_function = Modelling().DeleteBlockAttribute
      elif self.primitive_type == PrimitiveType.CELL:
        delete_function = Modelling().DeleteCellAttribute
      else:
        raise ValueError('Unexpected primitive type %r' % self.primitive_type)

      delete_function(
        self.owner._lock.lock,
        name.encode('utf-8'))
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  def _save_attribute(self, name, data):
    """Saves a new primitive attribute in the Project.

    Parameters
    ----------
    name : str
      The name of attribute
    data : array
      A numpy array of a base type data to store for the attribute
      per-primitive.

    Raises
    ------
    Exception
      If the object is opened in read-only mode.
    ValueError
      If the type of the attribute is not supported.
    ValueError
      If the primitive type is not supported.

    """
    # pylint:disable=protected-access; reason="This is a mixin class"
    if not isinstance(self.owner._lock, WriteLock):
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

    if not isinstance(data, np.ndarray):
      data = np.array(data)

    # Maps the data type of an numpy array to its corresponding type in
    # ctypes.
    if data.dtype.kind in {'U', 'S', 'O'}:
      array_ctype = ctypes.c_char_p
    else:
      array_ctype = np.ctypeslib.as_ctypes_type(data.dtype)

    ctype_to_function = {
      ctypes.c_float: '{}AttributeFloat32BeginRW',
      ctypes.c_double: '{}AttributeFloat64BeginRW',
      ctypes.c_int64: '{}AttributeInt64sBeginRW',
      ctypes.c_uint64: '{}AttributeInt64uBeginRW',
      ctypes.c_int32: '{}AttributeInt32sBeginRW',
      ctypes.c_uint32: '{}AttributeInt32uBeginRW',
      ctypes.c_int16: '{}AttributeInt16sBeginRW',
      ctypes.c_uint16: '{}AttributeInt16uBeginRW',
      ctypes.c_int8: '{}AttributeInt8sBeginRW',
      ctypes.c_uint8: '{}AttributeInt8uBeginRW',
      ctypes.c_bool: '{}AttributeBoolBeginRW',
      ctypes.c_char_p: '{}AttributeStringBeginRW',
    }

    function_name = ctype_to_function.get(array_ctype)
    if function_name is None:
      raise ValueError('The type of the attribute (%s) is an unsupported type.'
                       % array_ctype)

    # Update the function name to include the primitive type.
    if self.primitive_type == PrimitiveType.POINT:
      function_name = function_name.format('Point')
    elif self.primitive_type == PrimitiveType.EDGE:
      function_name = function_name.format('Edge')
    elif self.primitive_type == PrimitiveType.FACET:
      function_name = function_name.format('Facet')
    elif self.primitive_type == PrimitiveType.BLOCK:
      function_name = function_name.format('Block')
    elif self.primitive_type == PrimitiveType.CELL:
      function_name = function_name.format('Cell')
    else:
      raise ValueError('The primitive type %r is an unsupported type.' %
                       self.primitive_type)

    ptr = getattr(Modelling(), function_name)(self.owner._lock.lock,
                                              name.encode('utf-8'))

    if not ptr:
      try:
        Modelling().RaiseOnErrorCode()
      except MemoryError as error:
        log.error('Failed to write to the %s attribute (%s) on %s: %s',
                  self.primitive_type.name, name, self.owner.id, str(error))
        raise MemoryError(
          'The attribute could not fit in the Project\'s cache') from None
      except:
        log.exception('Failed to write to the attribute (%s) on %s',
                      name, self.owner.id)
        raise

    # Strings have special case handling, as each string can have a variable
    # length and the data is potentially stored outside the array.
    if array_ctype == ctypes.c_char_p:
      data = trim_pad_1d_array(data, self.primitive_count, None).astype(
        str)

      # There will be a string for each primitive.
      for index, string in enumerate(data):
        utf8string = string.encode('utf-8')
        Modelling().AttributeSetString(
          ptr, index, utf8string, len(utf8string))
      return

    data = trim_pad_1d_array(data, self.primitive_count, 0).astype(array_ctype)

    ptr = getattr(Modelling(), function_name)(self.owner._lock.lock,
                                              name.encode('utf-8'))

    attr = array_of_pointer(ptr,
                            self.primitive_count * ctypes.sizeof(array_ctype),
                            array_ctype)
    attr[:] = data.flatten()
