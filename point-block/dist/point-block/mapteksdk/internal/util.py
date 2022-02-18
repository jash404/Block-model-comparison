"""Internal utility functions used for implementing the Python SDK.

Unlike the common/util.py file these utility functions should not
be exposed to users of the SDK - they should be considered an internal
implementation details.

Warnings
--------
Vendors and clients should not develop scripts or applications against
this package. The contents may change at any time without warning.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes

import numpy as np

# For wrapping native pointers
BUF_FROM_MEM = ctypes.pythonapi.PyMemoryView_FromMemory
BUF_FROM_MEM.restype = ctypes.py_object
BUF_FROM_MEM.argtypes = (ctypes.c_void_p, ctypes.c_int64, ctypes.c_int)

def array_of_pointer(ptr, byte_count, numpy_type):
  """Create an array of numpy pointers.

  Parameters
  ----------
  ptr : c_void_p
    Pointer to the start of memory location.
  byte_count : c_int64
    Number of bytes to allocate.
  numpy_type : c_int
    numpy dtype to create.

  Returns
  -------
  ndarray
    Numpy buffer array.

  """
  # define PyBUF_READ  0x100
  # define PyBUF_WRITE 0x200
  buffer = BUF_FROM_MEM(ptr, byte_count, 0x200)
  return np.frombuffer(buffer, numpy_type)

def to_utf8(string_to_convert):
  """Convert Python string to native C utf-8 string.

  Parameters
  ----------
  string_to_convert : str
    The string to convert to utf-8.

  Returns
  -------
  c_char_p
    The Python string converted to a native C utf-8 string.

  """
  return ctypes.c_char_p(string_to_convert.encode('utf-8'))

def cartesian_to_spherical(points, origin=None):
  """Converts a list of Cartesian points to a list of spherical
  coordinates.

  Parameters
  ----------
  points : array_like
    The points to convert to Cartesian coordinates.
  origin : point
    The origin to use when calculating Cartesian coordinates.
    If not specified, the origin is taken to be [0, 0, 0]

  Returns
  -------
  numpy.ndarray
    Numpy array of 32 bit floating point numbers representing spherical
    coordinates equivalent to points. This array is of the shape
    (3, len(points)). The zeroth element is the ranges of the points,
    the first element is the alphas and the second element is the betas.
    This means the first point is the first column.

  Examples
  --------
  Get ranges of points from the origin.

  >>> from mapteksdk.internal.util import cartesian_to_spherical
  >>> points = [[1, 2, 2], [4, 0, 0], [0, 3, 4]]
  >>> sphericals = cartesian_to_spherical(points)
  >>> print(sphericals[0])
  [3., 4., 5.]

  Get the first point in the form [range, alpha, beta]

  >>> from mapteksdk.internal.util import cartesian_to_spherical
  >>> points = [[4, 4, 4], [-1, 1, 1], [-1, -1, 1]]
  >>> sphericals = cartesian_to_spherical(points)
  >>> print(sphericals[:, 0])
  [6.92820323 0.78539816 0.61547971]

  """
  if origin is None:
    origin = np.array([0, 0, 0], dtype=ctypes.c_double)
  elif not isinstance(origin, np.ndarray):
    origin = np.array(origin, dtype=ctypes.c_double)
  spherical = np.zeros((3, len(points)), dtype=ctypes.c_double)
  vector = points - origin
  # Calculate the ranges. Out is used to perform the calculation in-place.
  np.sqrt(np.square(vector[:, 0]) + np.square(vector[:, 1]) +
          np.square(vector[:, 2]), out=spherical[0])
  # Calculate the alphas.
  np.arctan2(vector[:, 0], vector[:, 1], out=spherical[1])
  # Calculate the betas.
  np.arcsin(np.divide(vector[:, 2], spherical[0], where=spherical[0] != 0),
            out=spherical[2])
  # The where spherical[0] != 0 is used to skip dividing by zero.
  return spherical

def spherical_to_cartesian(ranges, alphas, betas, origin=None):
  """Converts spherical coordinates to Cartesian coordinates.

  Parameters
  ----------
  ranges : list
    List of ranges to convert to Cartesian coordinates.
  alphas : list
    List of vertical angles to convert to Cartesian coordinates.
  betas : list
    List of horizontal angles to convert to Cartesian coordinates.
  origin : list
    The origin of the spherical coordinates. If None (default), the origin is
    assumed to be [0, 0, 0].

  Returns
  -------
  list of points
    List of Cartesian points equivalent to spherical points.

  Notes
  -----
  Ideally:
  cartesian_to_spherical(spherical_to_cartesian(ranges, alphas, betas)) =
    ranges, alphas, betas
  and spherical_to_cartesian(cartesian_to_spherical(points)) = points

  However it is unlikely to be exact due to floating point error.

  Raises
  ------
  ValueError
    If r < 0.

  """
  if not isinstance(ranges, np.ndarray):
    ranges = np.array(ranges)
  if not isinstance(alphas, np.ndarray):
    alphas = np.array(alphas)
  if not isinstance(betas, np.ndarray):
    betas = np.array(betas)
  if ranges.shape != alphas.shape or alphas.shape != betas.shape:
    raise ValueError("Ranges, alphas and betas must have same shape")
  if np.min(ranges) < 0:
    raise ValueError("All ranges must be greater than zero.")
  cartesians = np.zeros((ranges.shape[0], 3), dtype=ctypes.c_double)
  rcos = ranges * np.cos(betas)
  np.multiply(rcos, np.sin(alphas), out=cartesians[:, 0])
  np.multiply(rcos, np.cos(alphas), out=cartesians[:, 1])
  np.multiply(ranges, np.sin(betas), out=cartesians[:, 2])

  if origin is not None:
    origin = np.array(origin)
    cartesians = cartesians + origin

  return cartesians

def default_type_error_message(argument_name, actual_value, required_type):
  """Provides a default message for type errors.

  Parameters
  ----------
  argument_name : str
    The name of the argument which was given an incorrect value.
  actual_value : any
    The incorrect value to given to the argument.
  required_type : type
    The required type of the argument.
  """
  actual_type_name = type(actual_value).__name__
  required_type_name = required_type.__name__
  return (f"Invalid value for {argument_name}: '{actual_value}' "
          f"(type: {actual_type_name}). Must be type: {required_type_name}.")
