"""The ObjectID class.

An ObjectID uniquely references an object within a Project. Note that an
ObjectID is only unique within one Project - an ObjectID of an object in one
project may be the ID of a different object in a different project.
Attempting to use an ObjectID once the project has been closed (or before
it has been opened) will raise an error.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
from ..capi.util import get_string, CApiDllLoadFailureError
from ..capi.types import T_ObjectHandle
from ..capi import DataEngine
from ..internal.util import to_utf8

class ObjectID:
  """ObjectID used to identify and represent an object."""

  # Specifies the underlying storage type of this class for the communication
  # system.
  storage_type = T_ObjectHandle

  def __init__(self, handle=None):
    if isinstance(handle, T_ObjectHandle):
      self.__handle = handle
    else:
      self.__handle = None

  @classmethod
  def convert_from(cls, storage_value):
    """Convert from the underlying value (of storage type) to this type.

    This is used by the communication system.
    """
    return cls(T_ObjectHandle(storage_value))

  @classmethod
  def convert_to(cls, value):
    """Convert to the underlying value.

    This is used by the communication system.
    """
    if isinstance(value, cls):
      return value.handle or T_ObjectHandle(0)
    if isinstance(value, T_ObjectHandle):
      return value

    raise TypeError('The value was not an ObjectID.')

  @classmethod
  def _from_string(cls, oid_string):
    """Constructs an ObjectID instance from a valid Object ID string
    in the form of 'OID(I##, C##, T##)' (e.g. 'OID(I123, C33, T22)').

    Newer applications no longer have the type index in the object ID
    and the ObjectID string will be of the form 'OID(I##, C##)'.

    This method relies on a valid object existing in the Project.
    for the string passed into this method.

    Parameters
    ----------
    oid_string : str
      Object ID string in the form of 'OID(I##, C##, T##)' or 'OID(I##, C##)'.

    Returns
    -------
    ObjectID
      An ObjectID instance.

    Raises
    ------
    TypeError
      If the oid_string parameter is not a string.
    ValueError
      If oid_string is not in form 'OID(I##, C##, T##)' or 'OID(I##, C##)'.
    ValueError
      If oid_string fails to convert to an ObjectID.

    """
    if isinstance(oid_string, str):
      obj = T_ObjectHandle()
      try:
        success = DataEngine().ObjectHandleFromString(
          to_utf8(oid_string),
          obj)
      except CApiDllLoadFailureError as error:
        raise CApiDllLoadFailureError(
          "Failed to parse ObjectID because no project is connected."
          ) from error
      if not success or obj is None or obj.value == 0:
        raise ValueError("'{}' failed to convert to an ObjectID.".format(
          oid_string))
      return cls(obj)
    raise TypeError("Incorrect type provided for oid_string. "
                    "Got {}.".format(repr(type(oid_string))))

  @classmethod
  def from_path(cls, object_path):
    """Constructs an ObjectID instance from a valid object path string.

    This method relies on a valid object existing in the Project
    at the path passed into this method.

    Parameters
    ----------
    object_path : str
      Path to the object to get the ID of.

    Returns
    -------
    ObjectID
      An ObjectID instance if the string was valid.

    Raises
    ------
    TypeError
      If the object_path parameter is not a string.
    ValueError
      If object_path failed to convert to an ObjectID.

    """
    if isinstance(object_path, str):
      obj = T_ObjectHandle()
      try:
        node_path_handle = DataEngine().NodePathFromString(
          to_utf8(object_path))
      except CApiDllLoadFailureError as error:
        raise CApiDllLoadFailureError(
            "Failed to parse ObjectID because no project is connected."
            ) from error
      if node_path_handle.value > 0:
        success = DataEngine().ObjectHandleFromNodePath(
          node_path_handle,
          obj)
        if success and obj.value > 0:
          return cls(obj)
        raise ValueError("Failed to create an ObjectID from path " \
          + "'{}'. The path doesn't exist.".format(object_path))
      raise ValueError("Failed to create an ObjectID from path '{}'.".format(
        object_path))
    raise TypeError("Incorrect type provided for object_path. " \
      + "Expected {}, got {}.".format(repr(str), repr(type(object_path))))

  def __str__(self):
    return (repr(self)) if self.handle else "Undefined"

  def __repr__(self):
    """Converts the Object ID to a string presentation in the form of
    'OID(I##, C##, T##)' where:
    OID = Object ID.
    "I" = Object Index, "C" = Object Index Counter, "T" = Type Index.

    For newer applications there is no type index so this will be of the form:
    'OID(I##, C##)'

    """
    raw_handle = self.native_handle if self.handle else 0
    if DataEngine().version < (1, 4):
      return 'OID(I%d, C%d, T%d)' % (raw_handle & 0xFFFFFFFF,
                                     (raw_handle >> 32) & 0xFFFF,
                                     (raw_handle >> 48) & 0xFFFF)
    return 'OID(I%d, C%d)' % (raw_handle & 0xFFFFFFFF,
                              (raw_handle >> 32) & 0xFFFFFFFF)

  def __eq__(self, obj):
    return isinstance(obj, ObjectID) and obj.native_handle == self.native_handle

  def __int__(self):
    return self.native_handle if self.native_handle else 0

  def __bool__(self):
    return self.native_handle > 0 if self.handle else False

  @property
  def handle(self):
    """T_ObjectHandle representation of the Object ID.

    Returns
    -------
    T_ObjectHandle
      T_ObjectHandle representation of the Object ID.
      None returned if the class has not been
      initialised properly.

    """
    if isinstance(self.__handle, T_ObjectHandle) and self.__handle.value > 0:
      return self.__handle
    return None

  @property
  def native_handle(self):
    """Native Integer (uint64) representation of the Object ID.

    Returns
    -------
    int
      uint64 representation of the Object ID. None returned if the
      class has not been initialised properly.

    """
    return self.__handle.value if isinstance(self.__handle, T_ObjectHandle) \
      else None

  @property
  def icon_name(self):
    """The name of the icon that represents the object.

    Returns
    -------
    str
      Icon name for the object type.

    Raises
    ------
    TypeError
      If the ObjectID handle is None.

    """
    self.__check_handle()
    return get_string(self.__handle,
                      DataEngine().ObjectHandleIcon)

  @property
  def type_name(self):
    """The type name of this object.

    This name is for diagnostics purposes only. Do not use it to alter the
    behaviour of your code. If you wish to check if an object is of a given
    type, use is_a() instead.

    Returns
    -------
    str
      The name of the type of the given object.

    Raises
    ------
    TypeError
      If the ObjectID handle is None.

    See Also
    --------
    is_a : Check if the type of an object is the expected type.
    """

    self.__check_handle()
    dynamic_type = DataEngine().ObjectDynamicType(self.__handle)
    raw_type_name: str = DataEngine().TypeName(dynamic_type).decode('utf-8')

    # Tidy up certain names for users of the Python SDK.
    raw_to_friendly_name = {
      '3DContainer': 'VisualContainer',
      '3DEdgeChain': 'Polyline',
      '3DEdgeNetwork': 'EdgeNetwork',
      '3DFacetNetwork': 'Surface',
      '3DNonBrowseableContainer': 'NonBrowseableContainer',
      '3DPointSet': 'PointSet',
      'BlockNetworkDenseRegular': 'DenseBlockModel',
      'BlockNetworkDenseSubblocked': 'SubblockedBlockModel',
      'ColourMapNumeric1D': 'NumericColourMap',
      'ColourMapString1D': 'StringColourMap',
      'EdgeLoop': 'Polygon',
      'RangeImage': 'Scan',
      'StandardContainer': 'StandardContainer',
      'TangentPlane': 'Discontinuity',
    }

    # Exclude the old (and obsolete) revision number.
    raw_type_name = raw_type_name.partition('_r')[0]

    return raw_to_friendly_name.get(raw_type_name, raw_type_name)

  @property
  def exists(self):
    """Returns true if the object associated with this object id
    exists. This can be used to check if a previously existing object
    has been deleted or if the parameters used to create the ObjectID
    instance are valid and refer to an existing object.

    Returns
    -------
    bool
      True if it exists; False if it no longer exists.
      False is also returned if ObjectID never existed.

    """
    return DataEngine().ObjectHandleExists(self.__handle) \
      if self.handle else False

  @property
  def name(self):
    """The name of the object (if one exists).

    If the object is not inside a container then it won't have a name. The
    name comes from its parent.
    If the object is inside more than one container (has multiple paths)
    then this is the name in the primary container.
    Each container that this object is in can assign it a different name.

    Returns
    -------
    str
      The name of the object.

    Raises
    ------
    TypeError
      If the ObjectID handle is None.

    """
    self.__check_handle()
    path_handle = self.__node_path_handle
    return get_string(path_handle, DataEngine().NodePathLeaf)

  @property
  def path(self):
    """The path to the object (if one exists) in the project. If an object has
    multiple paths, the primary path will be returned.

    Returns
    -------
    str
      Path to the object if one exists (e.g. '/cad/my_object').

    Raises
    ------
    TypeError
      If the ObjectID handle is None.

    """
    self.__check_handle()
    path_handle = self.__node_path_handle
    return get_string(path_handle,
                      DataEngine().NodePathToString)

  @property
  def hidden(self):
    """If the object is a hidden object.

    Returns
    -------
    bool
      True if hidden, False if not hidden.

    Raises
    ------
    TypeError
      If the ObjectID handle is None.

    """
    # Exception will be raised when checking path if handle is None
    path = self.path
    parts = path.strip("/").split("/")
    # Remove empty strings (e.g. /surfaces/ = '', surfaces, '')
    parts = list(filter(None, parts))
    return any(part.startswith('.') for part in parts)

  @property
  def parent(self):
    """The ObjectID of the primary parent of this object.

    Returns
    -------
    ObjectID
      ObjectID instance representing the parent of this object.

    Raises
    ------
    TypeError
      If the ObjectID handle is None.

    Notes
    -----
    If this object is already the root, the same object will
    be returned.
    If this object has multiple parents, the primary parent
    will be returned.

    """
    self.__check_handle()
    return ObjectID(DataEngine().ObjectParentId(self.__handle))

  @property
  def is_orphan(self):
    """Check if object is an orphan (no parents, or all of its
    ancestors are either orphans or are descendants of objects
    that are themselves orphans).

    Returns
    -------
    bool
      True if the object is an orphan or False if it is not.

    Raises
    ------
    TypeError
      If the ObjectID handle is None.

    """
    self.__check_handle()
    return DataEngine().ObjectHandleIsOrphan(self.__handle)

  def is_a(self, object_type):
    """Return true if type of the object in the project is of the type
    object_type.

    This takes into account inheritance - a polygon is both polygon
    and a topology.

    Parameters
    ----------
    object_type
      The Python class that represents a type of object in the project.
      This is the type to compare the type of the object referenced by this
      object ID to.

    Returns
    -------
    bool
      True if the object referenced by this object ID is of the type
      object_type otherwise False.

    Raises
    ------
    TypeError
      If the argument is not a type of object or a tuple of object types.
    """
    self.__check_handle()

    dynamic_type = DataEngine().ObjectDynamicType(self.__handle)

    # Support both the object type directly or a class/object which has a
    # static_type function. The latter should be favoured.
    def _static_type(object_type):
      return getattr(object_type, 'static_type', lambda: object_type)()

    if isinstance(object_type, tuple):
      try:
        return any(
          DataEngine().TypeIsA(dynamic_type, _static_type(individual_type))
          for individual_type in object_type
        )
      except ctypes.ArgumentError as error:
        # We are confident that the first argument of TypeIsA() is correct.
        raise TypeError('expected a type of an object') from error

    expected_type = DataEngine().dll.DataEngineTypeIsA.argtypes[1]
    static_type = _static_type(object_type)
    if type(static_type) is expected_type:
      return DataEngine().TypeIsA(dynamic_type, static_type)

    raise TypeError('is_a must be provided an object type, a class ' +
                    'with static_type property, or tuple, not ' +
                    static_type)

  @property
  def __node_path_handle(self):
    """Get the node path (as a T_NodePathHandle) for the object.

    Notes
    -----
    If the object has been appended to the project more than
    once this may not return the first occurrence.

    """
    return DataEngine().ObjectHandleNodePath(self.__handle)

  def __check_handle(self):
    """Check if the handle of this ObjectID is valid and raises
    a TypeError if not.

    """
    is_a_handle = isinstance(self.__handle, T_ObjectHandle)
    if not is_a_handle:
      raise TypeError("ObjectID handle is None.")
    if is_a_handle and self.__handle.value <= 0:
      raise TypeError("ObjectID handle value is invalid.")
