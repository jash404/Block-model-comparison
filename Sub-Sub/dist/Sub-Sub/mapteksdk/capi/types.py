"""Type definitions exposed by the C API.

These types should be considered an implementation detail. Users should not
rely on the definition of these types. They should be considered opaque data
types.

Warnings
--------
Vendors and clients should not develop scripts or applications against
this module. The contents may change at any time without warning.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes

# pylint: disable=invalid-name
# The names of the classes match the names in the C API.

# pylint: disable=too-few-public-methods
# These classes represent pure data with no actions.

class T_ObjectHandle(ctypes.c_uint64):
  """T_ObjectHandle is used to represent an object.

  See higher-level libraries (Eg Modelling) for object creation methods.

  The value of zero is used to represent a null object, i.e there is no
  object.
  """

class T_AttributeId(ctypes.c_uint32):
  """Attributes are tags on objects that include a name (represented by an
  attribute ID) and an optional value. The value can be a number, a string
  or a date. This type represents attribute IDs that are used to identify
  an attribute in an object.
  """

class T_NodePathHandle(ctypes.c_void_p):
  """Used to represent a node path object (deC_Path)."""

class T_ReadHandle(ctypes.c_void_p):
  """T_ReadHandle is used to represent a Read or Read/Write lock on an object.
  """

class T_EditHandle(ctypes.c_void_p):
  """T_EditHandle is used to represent a Write lock on an object.
  An EditHandle can be converted to a ReadHandle, but not vice versa.

  """

class T_TextHandle(ctypes.c_void_p):
  """Used to represent user facing text (serC_Text).
  """

class T_SocketFileMutexHandle(ctypes.c_void_p):
  """Used to represent a native handle for locking/unlocking socket files."""

class T_MessageHandle(ctypes.c_void_p):
  """Used to represent a MCP message (mcpC_Message/mcpC_Request)."""

class T_ContextHandle(ctypes.c_void_p):
  """Used to represent the translation context (trC_Context)."""

class T_ObjectWatcherHandle(ctypes.c_void_p):
  """Used to represent a object watch (deC_LegacyObjectWatcher)."""

class T_MenuFileHandle(ctypes.c_void_p):
  """Used to represent a parsed menu file (mnuC_MenuFile)."""

class T_MenuItemHandle(ctypes.c_void_p):
  """Used to represent a menu item (mnuC_Item)."""

class T_MenuSegmentHandle(ctypes.c_void_p):
  """Used to represent a menu segment (mnuC_Segment)."""

class _Opaque(ctypes.Structure):
  """An opaque value, useful for C extension modules who need to pass an opaque
  value (as a void* pointer) through Python code to other C code.

  """

class T_AttributeValueType(ctypes.c_uint32):
  """The actual type used to store the type of an attribute value.
  We use a Tint32u here instead of the enum type because C enums
  and C++ enums are not compatible with each other. C++ enums are
  implementation-defined, so they can't be used in C APIs.

  """
  # Usage of this class may require instance.value to get the actual int

class T_ContainerIterator(ctypes.c_uint32):
  """This iterator type is only meaningful in the context of the container from
  which it was obtained. Its value is implementation-defined, and does not
  necessarily correspond to the offset from the beginning of the container
  in iteration order.
  Therefore, DON'T DO ARITHMETIC ON THESE ITERATORS DIRECTLY.

  Instead, use the functions below to increment and decrement them.
  Within mdf_dataengine context:
  DataEngineContainerBegin, DataEngineContainerEnd,
  DataEngineContainerPreviousElement, DataEngineContainerNextElement,
  DataEngineContainerFindElement, etc.

  """
  # Usage of this class may require instance.value to get the actual int

class T_TypeIndex(ctypes.c_uint16):
  """T_TypeIndex is used to identify the type of an object in a Project."""

# The following types would be candidates for being public if numpy was not
# the preferred approach.

class DoubleIndex(ctypes.Structure):
  """A struct that represents a double index using two uint32s."""
  _fields_ = ("a", ctypes.c_uint32), ("b", ctypes.c_uint32)

  def __str__(self):
    return '(%d, %d)' % (self.a, self.b)

class TripleIndex(ctypes.Structure):
  """A struct that represents a triple index using three uint32s."""
  _fields_ = ("a", ctypes.c_uint32), ("b", ctypes.c_uint32), \
    ("c", ctypes.c_uint32)

  def __str__(self):
    return '(%d, %d, %d)' % (self.a, self.b, self.c)

class Point(ctypes.Structure):
  """Ctypes structure to hold vector information."""
  _fields_ = ("x", ctypes.c_double), ("y", ctypes.c_double), \
    ("z", ctypes.c_double)

  def __str__(self):
    return '(x: %f, y: %f, z: %f)' % (self.x, self.y, self.z)

class Colour(ctypes.Structure):
  """Ctypes structure to hold colour information."""
  _fields_ = ("red", ctypes.c_ubyte), ("green", ctypes.c_ubyte), \
    ("blue", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte)

  def __str__(self):
    return '(red: %d, green: %d, blue: %d, alpha: %d)' % (self.red,
                                                          self.green,
                                                          self.blue,
                                                          self.alpha)
