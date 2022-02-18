"""The base classes of all objects in a Project.

The basic unit of data in a Project is an object. All objects in a Project
are subclasses of DataObject and thus can access the properties and
functions defined by DataObject.

Objects which are intended to be visualised, such as Surface, Polyline
or Polygon, inherit from the Topology class.

Objects which are not intended to be visualised on their own, such
as colour maps and rasters, inherit directly from the DataObject class.

For objects which contain other objects, see mapteksdk.data.containers.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import datetime
import logging
import numpy as np
from pyproj.enums import WktVersion
from ..capi import DataEngine, Modelling
from ..capi.types import T_ObjectHandle
from ..common import trim_pad_1d_array
from ..internal.util import array_of_pointer, to_utf8
from ..internal.lock import ReadLock, WriteLock, LockType
from .coordinate_systems import CoordinateSystem, LocalTransform
from .errors import CannotSaveInReadOnlyModeError, ReadOnlyError
from .objectid import ObjectID

# pylint: disable=too-many-lines
# pylint: disable=too-many-instance-attributes
log = logging.getLogger("mapteksdk.data")

class AlreadyClosedError(RuntimeError):
  """Error raised when the user attempts to close a closed object."""

class Extent:
  """A multidimensional, axially-aligned "intervals" or "extents".

  This extent is bound to a volume in 3D space.

  Attributes
  ----------
  minimum : tuple
    Point representing minimum values in the form [x, y, z].

  maximum : tuple
    Point representing maximum values in the form [x, y, z].
  """
  def __init__(self, minimum, maximum):
    self.minimum = minimum
    self.maximum = maximum
    assert len(self.minimum) == len(self.maximum)

  @property
  def centre(self):
    """Returns the center of the extent.

    Returns
    -------
    point
      Point representing the center of the extent.

    """
    assert len(self.minimum) == len(self.maximum)
    midpoints = [
      (minimum + maximum) / 2.0
      for minimum, maximum in zip(self.minimum, self.maximum)
    ]

    return tuple(midpoints)

  @property
  def length(self):
    """The length is the maximum of the X, Y or Z dimension.

    Returns
    -------
    float
      Maximum width of the extent.

    """
    assert len(self.minimum) == len(self.maximum)
    lengths = [
      maximum - minimum
      for minimum, maximum in zip(self.minimum, self.maximum)
    ]
    return max(lengths)

  def as_numpy(self):
    """Returns the extent as a numpy array.

    Returns
    -------
    np.array
      The extent representing as a numpy array.

    """
    return np.array(self.minimum + self.maximum)

class _ObjectAttribute:
  """Holds data for an object attribute.

  Parameters
  ----------
  name : str
    The name of the object attribute.
  id : int
    The id of this object attribute.
  dtype : type
    The type of data stored by this object attribute.
  value : dtype
    The data stored in this attribute. Default is None.

  """
  def __init__(self, name, new_id, dtype, value):
    self.name = name
    self.id = new_id
    self.dtype = dtype
    self.value = value

class DataObject:
  """The basic unit of data in a Project.

  Each object can be referenced (opened/loaded) from its ID, see `ObjectID`,
  `Project.read()` and `Project.edit()`.

  """

  # This corresponds to C++ type called mdf::deC_Object.

  _object_attribute_table = {
    0: None, 1: type(None), 2: ctypes.c_bool, 3: ctypes.c_int8,
    4: ctypes.c_uint8, 5: ctypes.c_int16, 6: ctypes.c_uint16,
    7: ctypes.c_int32, 8: ctypes.c_uint32, 9: ctypes.c_int64,
    10: ctypes.c_uint64, 11: ctypes.c_float, 12: ctypes.c_double,
    13: ctypes.c_char_p, 14: datetime.datetime, 15: datetime.date,
  }

  def __init__(self, object_id, lock_type):
    """Opens the object for read or read-write.

    It is recommended to go through `Project.read()` and `Project.edit()`
    instead of constructing this object directly.

    Parameters
    ----------
    object_id : ObjectID
      The ID of the object to open for read or read-write.
    lock_type : LockType
      Specify read/write operation intended for the
      lifespan of this object instance.

    """
    assert object_id
    self.__id = object_id
    self.__lock_type = lock_type
    self.__explicit_lock = False
    self.__object_attributes = None
    self._lock = None
    self.__begin_lock()

  @property
  def id(self):
    """Object ID that uniquely references this object in the project.

    Returns
    -------
    ObjectID
      The unique id of this object.

    """
    return self.__id

  @property
  def lock_type(self):
    """Indicates whether operating in read-only or read-write mode.

    Returns
    -------
    LockType
      The type of lock.

    """
    return self.__lock_type

  def close(self):
    """Closes the object. This should be called as soon as you are finished
    working with an object. To avoid needing to remember to call this function,
    open the object using a with block and project.read(), project.new()
    or project.edit(). Those functions automatically call this function
    at the end of the with block.

    A closed object cannot be used for further reading or writing. The ID of
    a closed object may be queried and this can then be used to re-open the
    object.

    Raises
    ------
    AlreadyClosedError
      If the object has already been closed.

    """
    self.__end_lock()

  def _array_to_numpy(self, pointer, count, ctypes_type):
    """From the pointer to the first element in a C array, this copies the
    data to a numpy array.

    A copy is taken to avoid crashes and unwanted behaviour if the user tries
    to use the array after it has been freed (after the object was closed). To
    the lesser extent also in case the arrays have been invalidated.

    Parameters
    ----------
    pointer : c_void_p
      A pointer returned by the C API.
    count : int
      The number of elements in the array of the given type.
    ctypes_type : c_int
      The type of element.

    """

    array = array_of_pointer(
      pointer,
      count * ctypes.sizeof(ctypes_type),
      ctypes_type,
    ).copy()

    array.setflags(write=self.lock_type is LockType.READWRITE)

    return array

  def __begin_lock(self):
    if self.__explicit_lock:
      raise AlreadyClosedError(
        "This object instance is no longer available for reading/editing. "
        "You should start a new context manager using the with statement.")
    if self.__id and self.__lock_type and self._lock is None:
      # handle changed, or lock type changed, reset lock
      if self._lock is not None:
        self._lock.close()
      if self.__lock_type is LockType.READWRITE:
        self._lock = WriteLock(self.__id.handle)
        log.debug("Opened object for writing: %s of type %s",
                  self.__id, self.__derived_type_name)
      else:
        self._lock = ReadLock(self.__id.handle)
        log.debug("Opened object for reading: %s of type %s",
                  self.__id, self.__derived_type_name)

  def __end_lock(self):
    if self._lock is not None:
      self.__explicit_lock = True
      self._lock.close()
      if self.__lock_type is LockType.READWRITE:
        log.debug("Closed object for writing: %s of type %s",
                  self.__id, self.__derived_type_name)
      else:
        log.debug("Closed object for reading: %s of type %s",
                  self.__id, self.__derived_type_name)

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    """Close the object. See close()"""
    self.close()

  @property
  def __derived_type_name(self):
    """Return qualified name of the derived object type."""
    return type(self).__qualname__

  def __repr__(self):
    return '%s(%s)' % (self.__derived_type_name, self.__id)

  # =========================================================================
  # Properties of the underlying object in the project.
  # =========================================================================

  @property
  def created_date(self):
    """The date and time (in UTC) of when this object was created.

    Returns
    -------
    datetime.datetime:
      The date and time the object was created.
      0:0:0 1/1/1970 if the operation failed.

    """
    value = ctypes.c_int64() # value provided in microseconds
    success = DataEngine().GetObjectCreationDateTime(
      self._lock.lock, ctypes.byref(value))
    if success:
      try:
        return datetime.datetime.utcfromtimestamp(float(value.value) / 1000000)
      except (OSError, OverflowError) as error:
        message = str(error)
    else:
      message = DataEngine().ErrorMessage().decode('utf-8')

    log.warning(
      'Failed to determine the creation date of object %s because %s',
      self.id, message)
    return datetime.datetime.utcfromtimestamp(0)

  @property
  def modified_date(self):
    """The date and time (in UTC) of when this object was last modified.

    Returns
    -------
    datetime.datetime
      The date and time this object was last modified.
      0:0:0 1/1/1970 if the operation failed.

    """
    value = ctypes.c_int64() # value provided in microseconds
    success = DataEngine().GetObjectModificationDateTime(
      self._lock.lock, ctypes.byref(value))
    if success:
      return datetime.datetime.utcfromtimestamp(float(value.value) / 1000000)

    message = DataEngine().ErrorMessage().decode('utf-8')
    log.warning(
      'Failed to determine the last modified date of object %s because %s',
      self.id, message)
    return datetime.datetime.utcfromtimestamp(0)

  @property
  def _object_attributes(self):
    """Property for accessing the object attributes. When first called,
    the names of all object attributes are cached.

    """
    if self.__object_attributes is None:
      self.__object_attributes = self.__construct_attribute_dictionary()
    return self.__object_attributes

  def set_attribute(self, name, dtype, data):
    """Sets the value for the object attribute with the specified name.
    This will overwrite any existing attribute with the specified name.

    Parameters
    ----------
    name : str
      The name of the object attribute for which the value should be set.
    dtype : type
      The type of data to assign to the attribute. This should be
      a type from the ctypes module or datetime.datetime or datetime.date.
      Passing bool is equivalent to passing ctypes.c_bool.
      Passing str is equivalent to passing ctypes.c_char_p.
      Passing int is equivalent to passing ctypes.c_int16.
      Passing float is equivalent to passing ctypes.c_double.
    data : any
      The value to assign to object attribute `name`.
      For `dtype` = datetime.datetime this can either be a datetime
      object or timestamp which will be passed directly to
      datetime.utcfromtimestamp().
      For `dtype` = datetime.date this can either be a date object or a
      tuple of the form: (year, month, day).

    Raises
    ------
    ValueError
      If `dtype` is an unsupported type.
    TypeError
      If `value` is an inappropriate type for object attribute `name`.
    RuntimeError
      If a different error occurs.

    Warnings
    --------
    Object attributes are saved separately from the object itself - any
    changes made by this function (assuming it does not raise an
    error) will be saved even if save() is not called (for example,
    due to an error being raised by another function).

    Examples
    --------
    Create an object attribute on an object at "target" and then read its
    value.

    >>> import ctypes
    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.edit("target") as edit_object:
    ...     edit_object.set_attribute("count", ctypes.c_int16, 0)
    ... with project.read("target") as read_object:
    ...     print(read_object.get_attribute("count"))
    0

    """
    if self.lock_type is LockType.READ:
      raise ReadOnlyError("Cannot set object attributes in read-only mode.")
    attribute_id = DataEngine().GetAttributeId(to_utf8(name))

    if dtype == bool:
      dtype = ctypes.c_bool
    elif dtype == str:
      dtype = ctypes.c_char_p
    elif dtype == int:
      dtype = ctypes.c_int16
    elif dtype == float:
      dtype = ctypes.c_double

    if dtype is datetime.date and not isinstance(data, datetime.date):
      data = datetime.date(data[0], data[1], data[2])

    if dtype is datetime.datetime and not isinstance(data, datetime.datetime):
      data = datetime.datetime.utcfromtimestamp(data)

    try:
      result = self.__save_attribute(attribute_id,
                                     dtype,
                                     data)
    except ctypes.ArgumentError as exception:
      raise TypeError(f"Cannot convert {data} of type {type(data)} to "
                      f"type: {dtype}.") from exception
    except AttributeError as exception:
      raise TypeError(f"Cannot convert {data} of type {type(data)} to "
                      f"type: {dtype}.") from exception

    if not result:
      message = DataEngine().ErrorMessage().decode('utf-8')
      raise RuntimeError(f"Failed to save attribute: '{name}' on object "
                         f"'{self.id}'. {message}")

    if name in self._object_attributes:
      self._object_attributes[name].data = data
      self._object_attributes[name].dtype = dtype
      self._object_attributes[name].id = attribute_id
    else:
      self._object_attributes[name] = _ObjectAttribute(name, attribute_id,
                                                       dtype, data)

  def attribute_names(self):
    """Returns a list containing the names of all object-level attributes.
    Use this to iterate over the object attributes.

    Returns
    -------
    list
      List containing the attribute names.

    Examples
    --------
    Iterate over all object attributes of the object stared at "target"
    and print their values.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.read("target") as read_object:
    ...     for name in read_object.attribute_names():
    ...         print(name, ":", read_object.get_attribute(name))

    """
    return list(self._object_attributes.keys())

  def get_attribute(self, name):
    """Returns the value for the attribute with the specified name.

    Parameters
    ----------
    name : str
      The name of the object attribute to get the value for.

    Returns
    -------
    any
      The value of the object attribute `name`.
      For `dtype` = datetime.datetime this is an integer representing
      the number of milliseconds since 1st Jan 1970.
      For `dtype` = datetime.date this is a tuple of the form:
      (year, month, day).

    Raises
    ------
    KeyError
      If there is no object attribute called `name`.

    Warnings
    --------
    In the future this function may be changed to return datetime.datetime
    and datetime.date objects instead of the current representation for
    object attributes of type datetime.datetime or datetime.date.

    """
    attribute = self._object_attributes[name]
    # If value is None and the type is not NoneType, the value will
    # need to be loaded from the DataEngine.
    if attribute.value is None and attribute.dtype is not type(None):
      attribute.value = self.__load_attribute_value(attribute.id,
                                                    attribute.dtype)
    return attribute.value

  def get_attribute_type(self, name):
    """Returns the type of the attribute with the specified name.

    Parameters
    ----------
    name : str
      Name of the attribute whose type should be returned.

    Returns
    -------
    type
      The type of the object attribute `name`.

    Raises
    ------
    KeyError
      If there is no object attribute called `name`.

    """
    return self._object_attributes[name].dtype

  def delete_all_attributes(self):
    """Delete all object attributes attached to an object.

    This only deletes object attributes and has no effect
    on PrimitiveAttributes.

    Raises
    ------
    RuntimeError
      If all attributes cannot be deleted.

    """
    result = DataEngine().DeleteAllAttributes(self._lock.lock)

    if not result:
      message = DataEngine().ErrorMessage().decode('utf-8')
      raise RuntimeError(f"Failed to delete all attributes on object: "
                         f"'{self.id}'. {message}")

    self.__object_attributes = None

  def delete_attribute(self, attribute):
    """Deletes a single object-level attribute.

    Deleting a non-existent object attribute will not raise an error.

    Parameters
    ----------
    attribute : str
      Name of attribute to delete.

    Returns
    -------
    bool
      True if the object attribute existed and was deleted;
      False if the object attribute did not exist.

    Raises
    ------
    RuntimeError
      If the attribute cannot be deleted.

    """
    # Get the attribute id from the attribute name
    if attribute not in self._object_attributes:
      # If the attribute doesn't exist, no need to delete it.
      return False
    attribute_id = self._object_attributes[attribute].id
    result = DataEngine().DeleteAttribute(self._lock.lock, attribute_id)

    if not result:
      message = DataEngine().ErrorMessage().decode('utf-8')
      raise RuntimeError(f"Failed to delete attribute '{attribute}' on "
                         f"object '{self.id}'. {message}.")

    self._object_attributes.pop(attribute)
    return result

  def __construct_attribute_dictionary(self):
    """Constructs a blank dictionary containing the name, id and type
    of every object attribute on this object.

    Returns
    -------
    dict
      Dictionary of object attributes. Key is the name, value is
      a __ObjectAttribute containing the name, id, type and a None
      value for the object attribute.

    """
    attributes = {}
    # Get the attribute id list
    # Get size of list
    attr_list_size = DataEngine().GetAttributeList(
      self._lock.lock,
      None,
      0)
    id_buf = (ctypes.c_uint32 * attr_list_size) # Create buffer type
    attribute_buffer = id_buf() # Create buffer
    # Get the list of attributes
    DataEngine().GetAttributeList(self._lock.lock,
                                  attribute_buffer,
                                  attr_list_size)

    for attribute in attribute_buffer:
      # Get the attribute name
      char_sz = DataEngine().GetAttributeName(attribute, None, 0)
      # Create string buffer to hold path
      str_buffer = ctypes.create_string_buffer(char_sz)
      DataEngine().GetAttributeName(attribute, str_buffer, char_sz)
      name = str_buffer.value.decode("utf-8")

      # Get the attribute data type
      dtype_id = DataEngine().GetAttributeValueType(
        self._lock.lock,
        attribute)

      dtype = self._object_attribute_table[dtype_id.value]

      attributes[name] = _ObjectAttribute(name, attribute, dtype, None)

    return attributes

  def __save_attribute(self, attribute_id, dtype, data):
    """Saves an attribute to the project."""
    if dtype is None:
      pass
    elif dtype is type(None):
      result = DataEngine().SetAttributeNull(
        self._lock.lock,
        attribute_id)
    elif dtype is ctypes.c_bool or dtype is bool:
      result = DataEngine().SetAttributeBool(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_int8:
      result = DataEngine().SetAttributeInt8s(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_uint8:
      result = DataEngine().SetAttributeInt8u(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_int16:
      result = DataEngine().SetAttributeInt16s(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_uint16:
      result = DataEngine().SetAttributeInt16u(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_int32:
      result = DataEngine().SetAttributeInt32s(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_uint32:
      result = DataEngine().SetAttributeInt32u(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_int64:
      result = DataEngine().SetAttributeInt64s(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_uint64:
      result = DataEngine().SetAttributeInt64u(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_float:
      result = DataEngine().SetAttributeFloat32(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_double:
      result = DataEngine().SetAttributeFloat64(
        self._lock.lock,
        attribute_id,
        data)
    elif dtype is ctypes.c_char_p or dtype is str:
      result = DataEngine().SetAttributeString(
        self._lock.lock,
        attribute_id,
        to_utf8(data))
    elif dtype is datetime.datetime:
      data = data.replace(tzinfo=datetime.timezone.utc)
      result = DataEngine().SetAttributeDateTime(
        self._lock.lock,
        attribute_id,
        int(data.timestamp() * 1000000))
    elif dtype is datetime.date:
      result = DataEngine().SetAttributeDate(
        self._lock.lock,
        attribute_id,
        data.year,
        data.month,
        data.day)
    else:
      if isinstance(dtype, str):
        raise TypeError(f"Invalid dtype \"{dtype}\". Pass the type directly, "
                         "not a string containing the name of the type.")
      raise TypeError(f"Unsupported dtype: \"{dtype}\".")

    return result

  def __load_attribute_value(self, attribute_id, dtype):
    """Loads the value of the attribute with id `attribute_id` and type `dtype`
    from the Project.

    Parameters
    ----------
    attribute_id : int
      ID of the attribute to load.
    dtype: type
      The type of the attribute to load.

    Returns
    -------
    The value of the attribute.

    """
    if dtype is None:
      raise KeyError(f"Object attribute: {attribute_id} does not exist.")
    if dtype is type(None):
      # The type was null so there is no data here but there is still an
      # attribute.
      return None

    type_to_function = {
      ctypes.c_bool: DataEngine().GetAttributeValueBool,
      ctypes.c_int8: DataEngine().GetAttributeValueInt8s,
      ctypes.c_uint8: DataEngine().GetAttributeValueInt8u,
      ctypes.c_int16: DataEngine().GetAttributeValueInt16s,
      ctypes.c_uint16: DataEngine().GetAttributeValueInt16u,
      ctypes.c_int32: DataEngine().GetAttributeValueInt32s,
      ctypes.c_uint32: DataEngine().GetAttributeValueInt32u,
      ctypes.c_int64: DataEngine().GetAttributeValueInt64s,
      ctypes.c_uint64: DataEngine().GetAttributeValueInt64u,
      ctypes.c_float: DataEngine().GetAttributeValueFloat32,
      ctypes.c_double: DataEngine().GetAttributeValueFloat64,

      # The following types need special handling.
      ctypes.c_char_p: DataEngine().GetAttributeValueString,
      datetime.datetime: DataEngine().GetAttributeValueDateTime,
      datetime.date: DataEngine().GetAttributeValueDate,
    }

    function = type_to_function.get(dtype)
    if function is None:
      raise ValueError('The type of the attribute (%s) is an unsupported '
                       'type.' % dtype)

    if dtype is datetime.datetime:
      # Convert timestamp from the project to a datetime object.
      value = ctypes.c_int64()
      got_result = function(self._lock.lock, attribute_id, ctypes.byref(value))
      value = datetime.datetime.utcfromtimestamp(value.value / 1000000)
    elif dtype is datetime.date:
      # Convert date tuple from the project to a date object.
      year = ctypes.c_int32()
      month = ctypes.c_uint8()
      day = ctypes.c_uint8()
      got_result = function(
        self._lock.lock,
        attribute_id,
        ctypes.byref(year),
        ctypes.byref(month),
        ctypes.byref(day)
        )
      value = datetime.date(year.value, month.value, day.value)
    elif dtype is ctypes.c_char_p:
      # Get attribute value as text string
      value_sz = function(self._lock.lock, attribute_id, None, 0)

      # Create string buffer to hold path
      value_buffer = ctypes.create_string_buffer(value_sz)
      got_result = function(self._lock.lock, attribute_id, value_buffer,
                            value_sz)
      value = value_buffer.value.decode("utf-8")
    else:
      value = dtype()  # Define a value of the given type.
      got_result = function(self._lock.lock, attribute_id, ctypes.byref(value))
      value = value.value

    if not got_result:
      raise KeyError(f"Object attribute: {attribute_id} does not exist.")

    return value

class Topology(DataObject):
  """Base class for "geometric objects" in a Project.

  This object is best thought of as the union of the following:

    - An arrangement of topological "primitives" including their location in
      space (known as their geometry).
    - The connectivity relationships between them (known as their topology).
    - The properties applied to them.

  A given geometric object may contain any number of any of the six basic
  primitives: points, edges, facets (triangles), tetras (4 sided polyhedra),
  cells (quadrilaterals) and blocks (cubes or rectangular boxes).
  However, derived classes typically enforce constraints on the type and number
  of each primitive allowed in objects of their type. For example an edge
  chain will have points and edges but not facets.

  """

  def close(self):
    """Closes the object and saves the changes to the Project,
    preventing any further changes.

    """
    self._invalidate_properties()
    DataObject.close(self)

  @classmethod
  def static_type(cls):
    """Return the type of a topology as stored in a Project.

    This can be used for determining if the type of an object is topology.

    """
    return Modelling().TopologyType()

  def _invalidate_properties(self):
    """Invalidates the properties of the object. The next time a property
    is requested they will be loaded from what is currently saved in the
    project.

    This is called during initialisation and when operations performed
    invalidate the properties (such as primitive is removed and the changes
    are saved right away).

    """
    raise NotImplementedError("_invalidate_properties() must be implemented "
                              "on child classes")

  def save(self):
    """Save the changes made to the object.

    Generally a user does not need to call this function
    because it is called automatically at the end of a with block
    using Project.new() or Project.edit().

    """
    raise NotImplementedError("save() must be implemented on child classes")

  def _reconcile_changes(self):
    """Request reconciliation of flagged changes.
    All properties need to be re-loaded after calling.

    """
    try:
      Modelling().ReconcileChanges(self._lock.lock)
    except:
      log.exception("Unexpected error when trying to save changes.")
      raise

  @property
  def extent(self):
    """The axes aligned bounding extent of the object."""
    extents = (ctypes.c_double * 6)()
    Modelling().ReadExtent(self._lock.lock, ctypes.byref(extents))
    return Extent(
      minimum=(extents[0], extents[1], extents[2]),
      maximum=(extents[3], extents[4], extents[5]))

  def get_colour_map(self):
    """Return the ID of the colour map object currently associated with this
    object.

    Returns
    -------
    ObjectID
      The ID of the colour map object or null object ID if there is
      no colour map.

    """
    colour_map = Modelling().GetDisplayedColourMap(self._lock.lock)
    colour_map = ObjectID(T_ObjectHandle(colour_map))
    return colour_map

  @property
  def rasters(self):
    """A dictionary of raster indices and Object IDs of the raster images
    currently associated with this object.

    The keys are the raster ids and the values are the Object IDs of the
    associated rasters. Note that all raster ids are integers however they
    may not be consecutive - for example, an object may have raster ids
    0, 1, 5 and 200.

    Notes
    -----
    Rasters with higher indices appear on top of rasters with lower indices.
    The maximum possible raster id is 255.

    Removing a raster from this dictionary will not remove the raster
    association from the object. Use dissociate_raster to do this.

    Examples
    --------
    Iterate over all rasters on an object and invert the colours. Note
    that this will fail if there is no object at the path "target" and
    it will do nothing if no rasters are associated with the target.

    >>> from mapteksdk.project import Project
    >>> project = Project()
    >>> with project.read("target") as read_object:
    ...     for raster in read_object.rasters.values():
    ...         with project.edit(raster) as edit_raster:
    ...             edit_raster.pixels[:, :3] = 255 - edit_raster.pixels[:, :3]

    """
    rasters = Modelling().GetAssociatedRasters(self._lock.lock)
    final_rasters = {}
    for key, value in rasters.items():
      final_rasters[key] = ObjectID(value)
    return final_rasters

  @property
  def coordinate_system(self):
    """The coordinate system the points of this object are in.

    Warning
    -------
    Setting this property does not change the points.
    This is only a label stating the coordinate system the points are in.

    Notes
    -----
    If the object has no coordinate system, this will be None.

    Changes are done directly in the project and will not be undone
    if an error occurs.

    Examples
    --------
    Creating an edge network and setting the coordinate system to be
    WGS84. Note that setting the coordinate system does not change the points.
    It is only stating which coordinate system the points are in.

    >>> from pyproj import CRS
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Polygon
    >>> project = Project()
    >>> with project.new("cad/rectangle", Polygon) as new_edges:
    ...     # Coordinates are in the form [longitude, latitude]
    ...     new_edges.points = [[112, 9], [112, 44], [154, 44], [154, 9]]
    ...     new_edges.coordinate_system = CRS.from_epsg(4326)

    Often a standard map projection is not convenient or accurate for
    a given application. In such cases a local transform can be provided
    to allow coordinates to be specified in a more convenient system.
    The below example defines a local transform where the origin is
    translated 1.2 degrees north and 2.1 degree east, points are scaled to be
    twice as far from the horizontal origin and the coordinates are rotated
    45 degrees clockwise about the horizontal_origin. Note that the points
    of the polygon are specified in the coordinate system after the local
    transform has been applied.

    >>> import math
    >>> from pyproj import CRS
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Polygon, CoordinateSystem, LocalTransform
    >>> project = Project()
    >>> transform = LocalTransform(
    ...     horizontal_origin = [1.2, 2.1],
    ...     horizontal_scale_factor = 2,
    ...     horizontal_rotation = math.pi / 4)
    >>> system = CoordinateSystem(CRS.from_epsg(20249), transform)
    >>> with project.new("cad/rectangle_transform", Polygon) as new_edges:
    ...     new_edges.points = [[112, 9], [112, 44], [154, 44], [154, 9]]
    ...     new_edges.coordinate_system = system

    See Also
    --------
    mapteksdk.data.coordinate_systems.CoordinateSystem : Allows for a
      coordinate system to be defined with an optional local transform.

    """
    wkt, local_transform = Modelling().GetCoordinateSystem(self._lock.lock)
    if wkt != "":
      local_transform = self._array_to_numpy(local_transform,
                                             11,
                                             ctypes.c_double)
      return CoordinateSystem(wkt, LocalTransform(local_transform))
    return None

  @coordinate_system.setter
  def coordinate_system(self, value):
    if self.lock_type is LockType.READ:
      raise CannotSaveInReadOnlyModeError(
        "Cannot set coordinate system in read-only mode")
    if not isinstance(value, CoordinateSystem):
      value = CoordinateSystem(value)
    wkt_string = value.crs.to_wkt(WktVersion.WKT2_2019)
    local_transform = value.local_transform.to_numpy()

    Modelling().SetCoordinateSystem(self._lock.lock,
                                    wkt_string,
                                    local_transform)

  def dissociate_raster(self, raster):
    """Removes the raster from the object.

    This is done directly on the Project and will not be undone if an
    error occurs.

    Parameters
    ----------
    raster : ObjectID or Raster
      The raster to dissociate.

    Returns
    -------
    bool
      True if the raster was successfully dissociated from the object,
      False if the raster was not associated with the object.

    Raises
    ------
    TypeError
      If raster is not a Raster.

    Notes
    -----
    This only removes the association between the Raster and the object,
    it does not clear the registration information from the Raster.

    Examples
    --------
    Dissociate the first raster found on a picked object.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk import operations
    >>> project = Project()
    >>> oid = operations.object_pick(
    ...     support_label="Pick an object to remove a raster from.")
    ... with project.edit(oid) as data_object:
    ...     report = f"There were no raster to remove from {oid.path}"
    ...     for index in data_object.rasters:
    ...         data_object.dissociate_raster(data_object.rasters[index])
    ...         report = f"Removed raster {index} from {oid.path}"
    ...         break
    ... # Now that the raster is dissociated and the object is closed,
    ... # the raster can be associated with a different object.
    ... operations.write_report("Remove Raster", report)

    """
    if self.lock_type is LockType.READ:
      raise ReadOnlyError("Cannot dissociate raster in read-only mode.")

    # :TODO: Jayden Boskell 2021-04-16 SDK-471: It might be useful to
    # cache this information and do it during save.
    if not isinstance(raster, ObjectID):
      try:
        raster = raster.id
      except AttributeError as error:
        raise TypeError("raster must be a ObjectID or DataObject, "
                        f"not '{raster}' of type {type(raster)}.") from error

    # :NOTE: Jayden Boskell 2021-04-16 We can't call Raster.static_type()
    # because importing images.py into this file would result in
    # a circular dependency.
    if not raster.is_a(Modelling().ImageType()):
      raise TypeError('raster must be an object of type Raster.')

    return Modelling().DissociateRaster(self._lock.lock, raster.handle)

  # =========================================================================
  #
  #                             POINT SUPPORT
  #
  # =========================================================================
  def _get_points(self):
    """Get all points as a numpy array

    Returns
    -------
    ndarray
      An array of (n, 3) where n is the number of points in the array.
      Each row consists of the x,y,z location of a point.

    """
    point_count = Modelling().ReadPointCount(self._lock.lock)
    ptr = Modelling().PointCoordinatesBeginR(self._lock.lock)

    # There are 3 doubles per point.
    points = self._array_to_numpy(ptr, point_count * 3, ctypes.c_double)

    # Each element in the resulting array will have 3 elements inside it.
    return np.reshape(points, (-1, 3))

  def _save_points(self, points):
    """Save array of points to object in database

    Parameters
    ----------
    points : ndarray
      2D numpy array of points - [[x,y,z],] of np.float64.

    """
    if points is not None:
      point_count = points.shape[0]
      # ensure object point count is correct
      Modelling().SetPointCount(self._lock.lock, point_count)
      # array size = point_count * 3 (fields: x,y,z) * 8 (size of float64)
      coords = array_of_pointer(
        Modelling().PointCoordinatesBeginRW(self._lock.lock),
        point_count*3*8,
        ctypes.c_double)
      # store values in pointer array
      coords[:] = points.astype(ctypes.c_double, copy=False).ravel()

  def _get_point_colours(self):
    """Get all point colours as a numpy array

    Returns
    -------
    ndarray
      A 2D array of (n, 4) where n is the number of points in the array.
      Each row consists of the R,G,B,A value of the colour for a point.

    """
    point_count = Modelling().ReadPointCount(self._lock.lock)
    ptr = Modelling().PointColourBeginR(self._lock.lock)

    # There will be 4 bytes per point which are the (R,G,B,A).
    point_colours = self._array_to_numpy(ptr, point_count * 4, ctypes.c_uint8)

    # Each element in the resulting array will have 4 elements inside it.
    return np.reshape(point_colours, (-1, 4))

  def _save_point_colours(self, point_colours):
    """Save array of point colours to object in database

    Parameters
    ----------
    point_colours : ndarray
      2D numpy array of point colours
      [[r,g,b,a],[rn,gn,bn,an]] of np.uint8.

    """
    if point_colours is not None:
      point_count = point_colours.shape[0]
      Modelling().SetPointCount(self._lock.lock, point_count)
      # array size = point_count * 4 (fields: r,g,b,a) * 1 (size of uint8)
      colour_map = array_of_pointer(
        Modelling().PointColourBeginRW(self._lock.lock),
        point_count*4*1,
        ctypes.c_uint8)
      # store values in pointer array
      colour_map[:] = point_colours.astype(
        ctypes.c_uint8, copy=False).ravel()

  def _get_point_count(self):
    """Get point count of container.

    Returns
    -------
    int
      The number of points in the container.

    """
    point_count = Modelling().ReadPointCount(self._lock.lock)
    return point_count

  def _get_point_visibility(self):
    """Get array of visibility values for each point within the set.

    Returns
    -------
    ndarray
      numpy array of visibility status (bool) per point (n, 1) where n is the
      number of points.

    """
    point_count = Modelling().ReadPointCount(self._lock.lock)
    ptr = Modelling().PointVisibilityBeginR(self._lock.lock)
    visibility = self._array_to_numpy(ptr, point_count, ctypes.c_bool)
    return visibility

  def _save_point_visibility(self, point_visibility):
    """Save array of point visibility status to object in database.

    Parameters
    ----------
    point_visibility : ndarray
      1D numpy array of bool representing the visibility of each
      point [True,False].

    """
    if point_visibility is not None:
      point_count = point_visibility.shape[0]
      Modelling().SetPointCount(self._lock.lock, point_count)
      # array size = point_count * 1 (fields: visibility) * 1 (size of bool)
      visibility_map = array_of_pointer(
        Modelling().PointVisibilityBeginRW(self._lock.lock),
        point_count, # point_count * 1 * 1
        ctypes.c_bool)
      visibility_map[:] = point_visibility.astype(
        ctypes.c_bool, copy=False).ravel()

  def _get_point_selection(self):
    """Get array of selection values for each point within the set.

    Returns
    -------
    ndarray
      numpy array of selection status (bool) per point (n, 1) where n is the
      number of points.

    """
    point_count = Modelling().ReadPointCount(self._lock.lock)
    ptr = Modelling().PointSelectionBeginR(self._lock.lock)
    selection = self._array_to_numpy(ptr, point_count, ctypes.c_bool)
    return selection

  def _save_point_selection(self, point_selection):
    """Save array of point selection status to object in database.

    Parameters
    ----------
    point_selection : ndarray
      1D numpy array of bool representing the selection of each
      point [True,False].

    """
    if point_selection is not None:
      point_count = point_selection.shape[0]
      Modelling().SetPointCount(self._lock.lock, point_count)
      # array size = point_count * 1 (fields: selection) * 1 (size of bool)
      selection_map = array_of_pointer(
        Modelling().PointSelectionBeginRW(self._lock.lock),
        point_count, # point_count * 1 * 1
        ctypes.c_bool)
      selection_map[:] = point_selection.astype(
        ctypes.c_bool, copy=False).ravel()

  def _remove_point(self, point_index):
    """Flag single Point index for removal when the lock is closed.

    Parameters
    ----------
    point_index : long
      Index of point to remove.

    Returns
    -------
    bool
      True if successful.

    Notes
    -----
    Changes will not be reflected until context manager is closed.

    """
    return Modelling().RemovePoint(self._lock.lock,
                                              point_index)

  def _remove_points(self, point_indices):
    """Remove list of point at given indices of point array.

    Parameters
    ----------
    point_indices : array
      1D array of uint32 indices of points to remove.

    Returns
    -------
    bool
      True if successful.

    Notes
    -----
    Changes will not be reflected until context manager is closed

    """
    point_indices = trim_pad_1d_array(point_indices).astype(ctypes.c_uint32)
    arr_type = (ctypes.c_uint32 * point_indices.size)
    point_array = arr_type(*point_indices)
    return Modelling().RemovePoints(
      self._lock.lock, point_array, point_indices.size)

  # =========================================================================
  #
  #                             EDGE SUPPORT
  #
  # =========================================================================
  def _get_edges(self):
    """Get all edges.

    Returns
    -------
    ndarray
      2D numpy array of (n, 2) where n =  number of edges.
      Each row consists of [[p1, p2],[p1n,p2n]] where px refers to the point
      numbers which make up the edge.

    """
    edge_count = self._get_edge_count()
    ptr = Modelling().EdgeToPointIndexBeginR(self._lock.lock)
    # Each edge is made up of 2 integers (the index of a point)
    edges = self._array_to_numpy(ptr, edge_count * 2, ctypes.c_int32)
    return np.reshape(edges, (-1, 2))

  def _save_edges(self, edge_topology):
    """Save array of edges to object in database.

    Parameters
    ----------
    edge_topology : ndarray
      2D numpy array of edge to point topology
      [[p1,p2],[p1n,p2n]] of uint32.

    """
    if edge_topology is not None:
      edge_count = edge_topology.shape[0]
      # array size = edge_count * 2 (fields: p1,p2) * 4 (size of uint32)
      Modelling().SetEdgeCount(self._lock.lock, edge_count)
      edge_map = array_of_pointer(
        Modelling().EdgeToPointIndexBeginRW(self._lock.lock),
        edge_count*2*4,
        ctypes.c_uint32)
      # store values in pointer array
      edge_map[:] = edge_topology.astype(ctypes.c_uint32, copy=False).ravel()

  def _get_edge_colours(self):
    """Get edge colours.

    Returns
    -------
    ndarray
      2D numpy array of (n,4) [[r,g,b,a],[rn,gn,bn,an]] where n is
      the number of points in the array. Each row consists of the
      [r,g,b,a] (of uint8) value of the colour for an edge.

    """
    edge_count = self._get_edge_count()
    ptr = Modelling().EdgeColourBeginR(self._lock.lock)

    # Each element in the resulting array will have 4 elements inside it.
    edge_colours = self._array_to_numpy(ptr, edge_count * 4, ctypes.c_uint8)

    # There will be 4 bytes per point which are the (R,G,B,A).
    return np.reshape(edge_colours, (-1, 4))

  def _save_edge_colours(self, edge_colours):
    """Save array of edge colours to object in database.

    Parameters
    ----------
    edge_colours : ndarray
      2D numpy array of edge colours
      [[r,g,b,a],[rn,gn,bn,an]] of uint8.

    """
    if edge_colours is not None:
      edge_count = edge_colours.shape[0]
      Modelling().SetEdgeCount(self._lock.lock, edge_count)
      # array size = point_count * 4 (fields: r,g,b,a) * 1 (size of uint8)
      colour_map = array_of_pointer(
        Modelling().EdgeColourBeginRW(self._lock.lock),
        edge_count*4*1,
        ctypes.c_uint8)
      # store values in pointer array
      colour_map[:] = edge_colours.astype(ctypes.c_uint8, copy=False).ravel()

  def _get_edge_selection(self):
    """Get array of selection values for each edge within the set

    Returns
    -------
    ndarray
      numpy array of selection status (bool) per edge (n, 1) where n
      is the number of edges.

    """
    edge_count = Modelling().ReadEdgeCount(self._lock.lock)

    ptr = Modelling().EdgeSelectionBeginR(self._lock.lock)
    selection = self._array_to_numpy(ptr, edge_count, ctypes.c_bool)
    return selection

  def _save_edge_selection(self, edge_selection):
    """Save array of edge selection status to object in database.

    Parameters
    ----------
    edge_selection : ndarray
      1D numpy array of bool representing
      the selection of each edge [True,False].

    """
    if edge_selection is not None:
      edge_count = edge_selection.shape[0]
      Modelling().SetEdgeCount(self._lock.lock, edge_count)
      # array size = edge_count * 1 (fields: selection) * 1 (size of bool)
      selection_map = array_of_pointer(
        Modelling().EdgeSelectionBeginRW(self._lock.lock),
        edge_count, # edge_count * 1 * 1
        ctypes.c_bool)
      selection_map[:] = edge_selection.astype(
        ctypes.c_bool, copy=False).ravel()

  def _get_edge_count(self):
    """Get edge count

    Returns
    -------
    int
      count of edges in object.

    """
    edge_count = Modelling().ReadEdgeCount(self._lock.lock)
    return edge_count

  def __remove_edge(self, edge_index):
    """Flag single Edge index for removal when the lock is closed.

    Parameters
    ----------
    edge_index : long
      Index of edge to remove.

    Returns
    -------
    bool
      True if successful.

    Notes
    -----
    Changes may not be reflected until context manager is closed
    or until self._reconcile_changes is called.

    """
    return Modelling().RemoveEdge(self._lock.lock, edge_index)

  def _remove_edge(self, edge_index):
    """Remove edge at given index of edges array

    Parameters
    ----------
    edge_index : int
      index of edge to remove

    Returns
    -------
    bool
      True if successful.

    """
    return self.__remove_edge(edge_index)

  def _remove_edges(self, edge_indices):
    """Remove list of edges at given indices of edges array.

    Parameters
    ----------
    edge_indices : array
      1D array of uint32 indices of edges to remove

    Returns
    -------
      bool
        True if successful.

    """
    edge_indices = trim_pad_1d_array(edge_indices).astype(ctypes.c_uint32)
    arr_type = (ctypes.c_uint32 * edge_indices.size)
    edge_array = arr_type(*edge_indices)
    return Modelling().RemoveEdges(self._lock.lock,
                                   edge_array,
                                   edge_indices.size)

  # =========================================================================
  #
  #                             FACET SUPPORT
  #
  # =========================================================================
  def _get_facets(self):
    """Get all facets.

    Returns
    -------
    ndarray
      2D numpy array of (n, 3) where n =  number of facets.
      Each row consists of [[p1, p2, p3],] where px refers
      to the point index numbers which make up the facet.

    """
    facet_count = self._get_facet_count()
    ptr = Modelling().FacetToPointIndexBeginR(self._lock.lock)

    # There are 3 integers for each facet. They are the 3 indices for points
    # that form the facet.
    facets = self._array_to_numpy(ptr, facet_count * 3, ctypes.c_int32)

    return np.reshape(facets, (-1, 3))

  def _get_facet_count(self):
    """Get facet count.

    Returns
    -------
    int
      count of facets in object.

    """
    facet_count = Modelling().ReadFacetCount(self._lock.lock)
    return facet_count

  def _save_facets(self, facet_topology):
    """Save array of facets to object in database.

    Parameters
    ----------
    facet_topology : ndarray
      2D numpy array of facet to point topology
      [[p1,p2,p3],[p1n,p2n,p3n]] of np.uint32.

    """
    if facet_topology is not None:
      facet_count = facet_topology.shape[0]
      # ensure facet count is correct
      Modelling().SetFacetCount(self._lock.lock, facet_count)
      # array size = facet_count * 3 (fields: p1,p2,p3) * 4 (size of uint32)
      facet_map = array_of_pointer(
        Modelling().FacetToPointIndexBeginRW(self._lock.lock),
        facet_count*3*4,
        ctypes.c_uint32)
      # store values in pointer array
      facet_map[:] = facet_topology.astype(
        ctypes.c_uint32, copy=False).ravel()

  def _get_facet_colours(self):
    """Get all facet colours.

    Returns
    -------
    ndarray
      2D numpy array of (n, 3) where n = number of facets.
      Each row consists of an [[R, G, B, A],] ubyte/uint8 where
      R = Red, G = Green, B = Blue and A = Alpha.

    """
    facet_count = self._get_facet_count()
    ptr = Modelling().FacetColourBeginR(self._lock.lock)

    # There will be 4 bytes per point which are the (R,G,B,A).
    facet_colours = self._array_to_numpy(ptr, facet_count * 4, ctypes.c_uint8)

    # Each element in the resulting array will have 4 elements inside it.
    return np.reshape(facet_colours, (-1, 4))

  def _save_facet_colours(self, facet_colours):
    """Save array of facet colours to object in database.

    Parameters
    ----------
    facet_colours : ndarray
      2D numpy array of facet colours
      [[r,g,b,a],[rn,gn,bn,an]] of uint8.

    """
    if facet_colours is not None:
      facet_count = facet_colours.shape[0]
      # ensure facet count is correct
      Modelling().SetFacetCount(self._lock.lock, facet_count)
      # array size = facet_count * 4 (fields: r,g,b,a) * 1 (size of uint8)
      colour_map = array_of_pointer(
        Modelling().FacetColourBeginRW(self._lock.lock),
        facet_count*4*1,
        ctypes.c_uint8)
      # store values in pointer array
      colour_map[:] = facet_colours.astype(ctypes.c_uint8, copy=False).ravel()

  def _get_facet_selection(self):
    """Get array of selection values for each facet within the set.

    Returns
    -------
    ndarray
      numpy array of selection status (bool) per facet
      (n, 1) where n is the number of facets.

    """
    facet_count = Modelling().ReadFacetCount(self._lock.lock)
    ptr = Modelling().FacetSelectionBeginR(self._lock.lock)
    selection = self._array_to_numpy(ptr, facet_count, ctypes.c_bool)
    return selection

  def _save_facet_selection(self, facet_selection):
    """Save array of facet selection status to object in database.

    Parameters
    ----------
    facet_selection : ndarray
      1D numpy array of bool representing
      the selection of each facet [True,False].

    """
    if facet_selection is not None:
      facet_count = facet_selection.shape[0]
      Modelling().SetFacetCount(self._lock.lock, facet_count)
      # array size = facet_count * 1 (fields: selection) * 1 (size of bool)
      selection_map = array_of_pointer(
        Modelling().FacetSelectionBeginRW(self._lock.lock),
        facet_count, # facet_count * 1 * 1
        ctypes.c_bool)
      selection_map[:] = facet_selection.astype(
        ctypes.c_bool, copy=False).ravel()

  def _remove_facet(self, facet_index):
    """Remove facet at given index of facet array.

    Parameters
    ----------
    facet_index : int
      Index of facet to remove.

    Returns
    -------
    bool
      True if successful.

    Notes
    -----
    Changes may not be reflected until context manager is closed.

    """
    return Modelling().RemoveFacet(self._lock.lock,
                                   facet_index)

  def _remove_facets(self, facet_indices):
    """Remove list of facets at given indices of facets array.

    Parameters
    ----------
    facet_indices : array
      1D array of uint32 indices of facets to remove.

    Returns
    -------
    bool
      True if successful.

    Notes
    -----
    Changes may not be reflected until context manager is closed.

    """
    facet_indices = trim_pad_1d_array(facet_indices).astype(ctypes.c_uint32)
    arr_type = (ctypes.c_uint32 * facet_indices.size)
    facet_array = arr_type(*facet_indices)
    return Modelling().RemoveFacets(
      self._lock.lock, facet_array, facet_indices.size)

  # =========================================================================
  #
  #                             CELL SUPPORT
  #
  # =========================================================================
  def _get_cells(self):
    """Returns the cell to point index saved in the project.

    Returns
    -------
    ndarray
      2D numpy array of shape (n, 4) where n = number of cells.
      Each row consists of [p1, p2, p3, p4] where px refers
      to the point index which make up the cell.

    """
    cell_dimensions = self._get_cell_dimensions()
    if 0 not in cell_dimensions:
      cell_count = (cell_dimensions[0] - 1) * (cell_dimensions[1] - 1)
    else:
      cell_count = 0
    ptr = Modelling().CellToPointIndexBeginR(self._lock.lock)

    # There are 4 points for each cell. They are the 4 indices for points
    # that form the cell.
    cells = self._array_to_numpy(ptr, cell_count * 4, ctypes.c_int32)

    return np.reshape(cells, (-1, 4))


  def _get_cell_dimensions(self):
    """Returns the cell dimensions saved in the project.

    Returns
    -------
    tuple
      The tuple (major_dimension_count, minor_dimension_count)

    """
    return Modelling().ReadCellDimensions(self._lock.lock)

  def _get_cell_visibility(self):
    """Returns the cell visibility saved in the project.

    Returns
    -------
    ndarray
      Numpy array of visibility, one per cell.

    """
    cell_count = Modelling().ReadCellCount(self._lock.lock)
    ptr = Modelling().CellVisibilityBeginR(self._lock.lock)
    visibility = self._array_to_numpy(ptr, cell_count, ctypes.c_bool)
    return visibility

  def _save_cell_visibility(self, cell_visibility):
    """Saves the cell visibility to the project.

    Parameters
    ----------
    cell_visibility : ndarray
      1D array of bool representing the cell visibility.

    """
    if cell_visibility is not None:
      cell_count = Modelling().ReadCellCount(self._lock.lock)
      if cell_visibility.shape[0] < cell_count:
        # It might be good to make more of the save functions work
        # like this.
        raise ValueError("Too many values for cell visibility.")

      visibility_map = array_of_pointer(
        Modelling().CellVisibilityBeginRW(self._lock.lock),
        cell_count,
        ctypes.c_bool)
      visibility_map[:] = cell_visibility.astype(ctypes.c_bool,
                                                 copy=False).ravel()


  def _get_cell_selection(self):
    """Returns the cell selection saved in the project.

    Returns
    -------
    ndarray
      Numpy array of selection, one per cell.

    """
    cell_count = Modelling().ReadCellCount(self._lock.lock)
    ptr = Modelling().CellSelectionBeginR(self._lock.lock)
    selection = self._array_to_numpy(ptr, cell_count, ctypes.c_bool)
    return selection

  def _save_cell_selection(self, cell_selection):
    """Saves the cell selection to the project.

    Parameters
    ----------
    cell_selection : ndarray
      1D array of bool representing the cell visibility.

    """
    if cell_selection is not None:
      cell_count = Modelling().ReadCellCount(self._lock.lock)
      if cell_selection.shape[0] < cell_count:
        # It might be good to make more of the save functions work
        # like this.
        raise ValueError("Too many values for cell selection.")

      selection_map = array_of_pointer(
        Modelling().CellSelectionBeginRW(self._lock.lock),
        cell_count,
        ctypes.c_bool)
      selection_map[:] = cell_selection.astype(ctypes.c_bool,
                                               copy=False).ravel()

  def _get_cell_colours(self):
    """Returns the cell colour as saved in the project.

    Returns
    -------
    cell_colour : ndarray
      Array of 8 bit unsigned integers representing the cell colours.

    """
    cell_count = Modelling().ReadCellCount(self._lock.lock)
    ptr = Modelling().CellColourBeginR(self._lock.lock)
    colours = self._array_to_numpy(ptr, cell_count * 4, ctypes.c_uint8)
    return colours

  def _save_cell_colours(self, cell_colours):
    """Saves the cell colours to the project.

    Parameters
    ----------
    cell_colours : ndarray
      1D array of 8 bit unsigned integers representing the cell colours.

    """
    if cell_colours is not None:
      cell_count = Modelling().ReadCellCount(self._lock.lock)
      if cell_colours.shape[0] < cell_count:
        # It might be good to make more of the save functions work
        # like this.
        raise ValueError("Too many values for cell colour.")

      colour_map = array_of_pointer(
        Modelling().CellColourBeginRW(self._lock.lock),
        cell_count * 4,
        ctypes.c_uint8)
      colour_map[:] = cell_colours.astype(ctypes.c_uint8,
                                          copy=False).ravel()

  # =========================================================================
  #
  #                             BLOCK SUPPORT
  #
  # =========================================================================
  def _get_block_dimensions(self):
    """Read the block dimensions for this object.

    Returns
    -------
    tuple
      The tuple (slice_count, row_count, column_count).

    """
    dimensions = (ctypes.c_uint32 * 3)()
    Modelling().ReadBlockDimensions(self._lock.lock,
                                    ctypes.byref(dimensions))
    return dimensions

  def _get_block_resolution(self):
    """Read the block resolutions for this object.

    Returns
    -------
    ndarray
      ndarray of the form [x_res, y_res, z_res].

    """
    resolution = (ctypes.c_double * 3)()
    Modelling().ReadBlockSize(self._lock.lock, resolution)
    return np.array(resolution, ctypes.c_double)

  def _get_block_count(self):
    """Get the number of blocks in the model.

    Returns
    -------
    int
      The number of blocks in the model.

    """
    return Modelling().ReadBlockCount(self._lock.lock)

  def _save_block_count(self, new_count):
    """Saves the block count. Only supported by subblocked and sparse
    block models.

    Parameters
    ----------
    new_count : int
      The new block count. This will expand or shrink property arrays.

    Warnings
    --------
    This does not change the value returned from _get_block_count() until
    the object is saved.

    """
    Modelling().SetBlockCount(self._lock.lock, new_count)

  def _get_block_transform(self):
    """Get the current block transform.

    Returns
    -------
    tuple
      A tuple containing the origin and quaternion
      (ndarray, ndarray) > ([x, y, z], [q0, q1, q2, q3]).

    """
    origin = (ctypes.c_double * 3)()
    quaternion = (ctypes.c_double * 4)()
    Modelling().ReadBlockTransform(self._lock.lock,
                                   ctypes.byref(quaternion),
                                   ctypes.byref(origin))

    return np.array(origin), np.array(quaternion)

  def _save_transform(self, q0, q1, q2, q3, x, y, z):
    """Changes the origin and rotation of the block model.

    Parameters
    ----------
    q0 : double
      The first component of the quaternion.
    q1 : double
      The second component of the quaternion.
    q2 : double
      The third component of the quaternion.
    q3 : double
      The fourth component of the quaternion.
    x : double
      The x component of the origin of the block model.
    y : double
      The y component of the origin of the block model.
    z : double
      The z component of the origin of the block model.

    Raise
    -----
    Exception if in read-only mode

    """
    # pylint: disable=invalid-name
    # pylint: disable=too-many-arguments
    # Set the rotation and origin
    Modelling().SetBlockTransform(
      self._lock.lock, q0, q1, q2, q3, x, y, z)

  def _get_block_centroids(self):
    """Get the block centroids.

    Returns
    -------
    ndarray
      2D numpy array of block centroids of shape (n, 3) where n is the number
      of blocks. Each row is the centroid of a single block in the form
      [x, y, z].

    """
    ptr = Modelling().BlockCentroidsBeginR(self._lock.lock)
    block_count = Modelling().ReadBlockCount(self._lock.lock)
    centroids = self._array_to_numpy(ptr, block_count * 3, ctypes.c_double)
    return np.reshape(centroids, (-1, 3))

  def _save_block_centroids(self, new_centroids):
    """Saves the block centroids to the project.

    This function performs no bounds checking. new_sizes must have shape
    (n, 3) where n is the block count (as of the last call to
    _save_block_count).

    Parameters
    ----------
    new_centroids : ndarray
      Numpy array of block centroids.

    """
    block_centroids = array_of_pointer(
      Modelling().BlockCentroidsBeginRW(self._lock.lock),
      new_centroids.shape[0] * 3 * 8,
      ctypes.c_double)

    # This probably already be ctypes.c_double before it hits this function.
    block_centroids[:] = new_centroids.astype(ctypes.c_double).ravel()

  def _get_block_sizes(self):
    """Get the block sizes.

    Returns
    -------
    ndarray
      2D numpy array of block sizes of shape (n, 3) where n is the number of
      blocks in the model. Each row is the size of a single block of the form
      [x, y, z].

    """
    ptr = Modelling().BlockSizesBeginR(self._lock.lock)
    block_count = Modelling().ReadBlockCount(self._lock.lock)
    block_sizes = self._array_to_numpy(ptr, block_count * 3, ctypes.c_float)
    return np.reshape(block_sizes, (-1, 3))

  def _save_block_sizes(self, new_sizes):
    """Saves the block sizes to the project.

    This function performs no bounds checking. new_sizes must have shape
    (n, 3) where n is the block count (as of the last call to
    _save_block_count).

    Parameters
    ----------
    new_sizes : ndarray
      Numpy array of block sizes.

    """
    block_sizes = array_of_pointer(
      Modelling().BlockSizesBeginRW(self._lock.lock),
      new_sizes.shape[0] * 3 * 4,
      ctypes.c_float)

    # This should probably already be ctypes.c_float before it hits
    # this function.
    block_sizes[:] = new_sizes.astype(ctypes.c_float).ravel()

  def _get_block_colours(self):
    """Get the block colours.

    Returns
    -------
    ndarray
      2D numpy array of block colours of shape (n, 4) where n is the number of
      blocks in the model. Each row contains the colour of one block in the
      form: [r, g, b, a]

    """
    ptr = Modelling().BlockColourBeginR(self._lock.lock)
    block_count = Modelling().ReadBlockCount(self._lock.lock)

    # There will be 4 bytes per block which are the (R,G,B,A).
    block_colours = self._array_to_numpy(ptr, block_count * 4, ctypes.c_uint8)

    # Each element in the resulting array will have 4 elements inside it.
    return np.reshape(block_colours, (-1, 4))

  def _save_block_colours(self, block_colours):
    """Set the colours for each block in the block model.

    This function performs no bounds checking. new_sizes must have shape
    (n, 4) where n is the block count (as of the last call to
    _save_block_count).

    Parameters
    ----------
    block_colours : ndarray
      2D numpy array of block colours.

    """
    # array size = block_count * 4 (fields: r,g,b,a) * 1 (size of uint8)
    colour_map = array_of_pointer(
      Modelling().BlockColourBeginRW(self._lock.lock),
      block_colours.shape[0] * 4 * 1,
      ctypes.c_uint8)
    colour_map[:] = block_colours.astype(ctypes.c_uint8, copy=False).ravel()

  def _get_block_selection(self):
    """Get the block selection from the project.

    Returns
    -------
    ndarray
      The block selection.

    """
    block_count = Modelling().ReadBlockCount(self._lock.lock)
    ptr = Modelling().BlockSelectionBeginR(self._lock.lock)
    selection = self._array_to_numpy(ptr, block_count, ctypes.c_bool)
    return selection

  def _save_block_selection(self, block_selection):
    """Set selection values for each block in the block model.

    This function performs no bounds checking. new_sizes must have shape
    (n,) where n is the block count (as of the last call to
    _save_block_count).

    Parameters
    ----------
    block_selection : ndarray
      The block selection as a numpy array.
    """
    # array size = block_count * 1 (fields: selection) * 1 (size of bool)
    selection = array_of_pointer(
      Modelling().BlockSelectionBeginRW(self._lock.lock),
      block_selection.shape[0] * 1,
      ctypes.c_bool)
    selection[:] = block_selection.astype(ctypes.c_bool, copy=False).ravel()

  def _get_block_visibility(self):
    """Get visibility values for each block within the block model.

    Returns
    -------
    ndarray
      The block visibility as a numpy array.

    """
    block_count = Modelling().ReadBlockCount(self._lock.lock)
    ptr = Modelling().BlockVisibilityBeginR(self._lock.lock)
    visibility = self._array_to_numpy(ptr, block_count, ctypes.c_bool)
    return visibility

  def _save_block_visibility(self, block_visibility):
    """Set visibility values for each block within the block model.

    This function performs no bounds checking. new_sizes must have shape
    (n,) where n is the block count (as of the last call to
    _save_block_count).

    Parameters
    ----------
    block_visibility : ndarray
      The block visibility as a numpy array.
    """
    # array size = block_count * 1 (fields: visibility) * 1 (size of bool)

    visible = array_of_pointer(
      Modelling().BlockVisibilityBeginRW(self._lock.lock),
      block_visibility.shape[0] * 1,
      ctypes.c_bool)
    visible[:] = block_visibility.astype(ctypes.c_bool, copy=False).ravel()

  def _remove_block(self, block_index):
    """Removes the blocks at the given indices in the project.

    Parameters
    ----------
    block_index : int
      Index of the block to remove.

    """
    return Modelling().RemoveBlock(self._lock.lock, block_index)

  # =========================================================================
  #
  #                      TEXT / ANNOTATION SUPPORT
  #
  # =========================================================================
  def _get_text(self):
    """Get text string.

    Returns
    -------
    str
      Annotation text string.

    Notes
    -----
    C API: Support maker test and 2d text.

    """
    buf_size = Modelling().GetAnnotationText(self._lock.lock, None, 0)
    str_buf = ctypes.create_string_buffer(buf_size)
    Modelling().GetAnnotationText(self._lock.lock, str_buf, buf_size)
    text = str_buf.value.decode("utf-8")
    return text

  def _get_text_size(self):
    """Get text size.

    Returns
    -------
    Double
      Text size.

    Notes
    -----
    C API: Support marker text and 2d text.

    """
    return Modelling().GetAnnotationSize(self._lock.lock)

  def _get_text_colour(self):
    """Get text colour.

    Returns
    -------
    array
      1D array of [R,G,B,A] uint8.

    Notes
    -----
      C API: Support marker text and 2d text.

    """
    col = (ctypes.c_uint8*4)
    buffer = col()
    Modelling().GetAnnotationTextColour(self._lock.lock,
                                        ctypes.byref(buffer))
    return [buffer[0], buffer[1], buffer[2], buffer[3]]

  def _save_annotation_text(self, text):
    """Save text for Marker or 2DText annotations.

    Parameters
    ----------
    text : str
      Text to write to the annotation object.

    """
    if text is not None:
      Modelling().SetAnnotationText(self._lock.lock, to_utf8(text))

  def _save_annotation_text_size(self, text_size):
    """Save text for Marker or 2DText annotations.

    Parameters
    ----------
    text_size : double
      Text size to write to the annotation object.

    """
    if text_size is not None:
      Modelling().SetAnnotationSize(self._lock.lock, text_size)

  def _save_annotation_text_colour(self, text_colour):
    """Save text for Marker or 2DText annotations.

    Parameters
    ----------
    text_colour : array
      [r,g,b,a] 1D array of uint8.

    """
    if text_colour is not None:
      rgba_colour = (ctypes.c_uint8 * len(text_colour))\
        (*text_colour.astype(ctypes.c_uint8))
      # .astype is used in case padding accidentally added new data as floats
      Modelling().SetAnnotationTextColour(self._lock.lock, rgba_colour)
