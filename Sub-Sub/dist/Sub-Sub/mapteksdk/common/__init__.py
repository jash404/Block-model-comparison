"""Shared helpers and utilities used throughout the API."""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import numpy as np

def trim_pad_2d_array(array_to_check,
                      elements_to_keep=-1,
                      values=3,
                      fill_value=255):
  """Converts a list into a 2D np array and ensures it fits within
  sizing requirements.

  The return value is a list with length=elements_to_keep. Each item
  in this list is a list of length=values.

  Parameters
  ----------
  array_to_check : array_like
    Array-like object to convert.
  elements_to_keep : int
    Number of rows expected in the final list. If array_to_check
    has fewer rows than this number then additional rows will be
    added to reach this number. If array_to_check has more rows
    than this number then the extra rows are truncated.
    The default value is -1, causing no rows to be added or removed.
  values : int
    Number of columns (values in each row) in the final list. For each
    row, if it has less than this number of values then it is padded
    with fill_value. If it has more than this number of values
    then the row is truncated to this length.
    The default value is 3.
  fill_value : any
    Fill value to use when padding. The default is 255.

  Returns
  --------
  ndarray
    A 2D numpy array with elements_to_keep rows and
    values columns. This contains the values from array_to_check,
    however with any excess rows/columns truncated or any missing
    rows/columns padded with fill_value.

  Warnings
  --------
  This function has some unintuitive behaviour especially when
  array_to_check is jagged (rows are not all the same length).
  Calling it directly is not recommended and it may be deprecated
  in the future.

  Examples
  --------
  Truncate rows which are too long.

  >>> from mapteksdk.common import trim_pad_2d_array
  >>> points = [[1, 2, 3, 4], [4, 5, 6, 11], [7, 8, 9, 10]]
  >>> trim_pad_2d_array(points, 3, 3)
  array([[ 1,  2,  3],
         [ 4,  4,  5],
         [ 6, 11,  7]])

  Pad rows which are too short.

  >>> from mapteksdk.common import trim_pad_2d_array
  >>> points = [[1, 2], [1, 3], [1, 2], [1, 3]]
  >>> trim_pad_2d_array(points, -1, 3, 5)
  array([[1., 2., 5.],
         [1., 3., 5.],
         [1., 2., 5.],
         [1., 3., 5.]])

  """
  if not isinstance(array_to_check, np.ndarray):
    array_to_check = np.array(array_to_check)
  if array_to_check.ndim == 0 or array_to_check.size == 0:
    # The input array is empty. Create an appropriately sized array filled with
    # the fill value.
    new_shape = np.empty((elements_to_keep if elements_to_keep > 0 else 0,
                          values if values > 0 else 3))
    new_shape.fill(fill_value)
    array_to_check = new_shape
  # Convert 1D array [x,y,z] to 2D [[x,y,z]]
  if len(array_to_check.shape) == 1:
    array_to_check = array_to_check.reshape(-1, values)
  # Force array to conform to value size and element count
  # e.g. [[1, 2, 4, 5], [0,0,0], [1,2,3]] >> [[1, 2, 4]]
  if elements_to_keep > array_to_check.shape[0]:
    # Adding new rows, need to fill new slots with fill_value
    # Create empty array of desired size
    new_shape = np.empty((elements_to_keep, values)).astype(
      array_to_check.dtype)
    # Fill it will default value
    new_shape.fill(fill_value)
    # Insert original values into the filled array
    new_shape[:array_to_check.shape[0], :array_to_check.shape[1]] \
      = array_to_check[:new_shape.shape[0], :new_shape.shape[1]]
    # Replace original
    array_to_check = new_shape
  elif elements_to_keep > 0:
    # Truncate array to elements_to_keep and ensure field sizes are right
    array_to_check = np.resize(array_to_check, (elements_to_keep, values))
  elif array_to_check.shape[1] != values:
    # This is likely a sign that the caller has provided (x, y), (x, y) or
    # (x, y, z, w), (x, y, z, w) and rather than (x, y, z), (x, y, z).
    #
    # In the former case, the Z will be populated with fill_value and in the
    # latter case the information will simply be lost.
    #
    # Create a new array with the same length as the source array but with the
    # desired number of values per item (for example, 3 for (x, y, z)) and
    # then use slicing to provide a view onto the subset of the data (for
    # example (x, y)) such that it can be assigned from a source array with
    # fewer elements.
    #
    # If the source array has more items per value then it a matter of slicing
    # it down.
    values_per_item_in_source = array_to_check.shape[1]
    smallest_values_per_item = min(values_per_item_in_source, values)

    new_array = np.empty((array_to_check.shape[0], values))
    new_array.fill(fill_value)
    new_array[:, 0:smallest_values_per_item:] = \
      array_to_check[:, 0:smallest_values_per_item]
    array_to_check = new_array

  return array_to_check

def trim_pad_1d_array(array_to_check, elements_to_keep=-1, fill_value=True):
  """Flattens a 2D array into a 1D array and ensures it fits within
  sizing requirements. Alternatively, trim or pad a 1D array to have
  the specified number of elements.

  Parameters
  ----------
  array_to_check : array_like
    List to trim or pad.
  elements_to_keep : int
    The length of the final list. If array_to_check is longer than this
    value, it is truncated to this length. If array_to_check is shorter
    than this value then it is padded to this length using fill_value.
    Default is -1 which indicates to keep all elements.
  fill_value : any
    Fill value to use when padding. Default is True.

  Returns
  -------
  ndarray
    1D numpy array of length elements_to_keep.

  See Also
  --------
  trim_pad_2d_array : Similar functionality, but for 2d arrays.

  Examples
  --------
  Enforce list is 1D

  >>> from mapteksdk.common import trim_pad_1d_array
  >>> visibility = [[True, False, True]]
  >>> trim_pad_1d_array(visibility)
  array([True, False, True])

  Trim a 1D array.

  >>> from mapteksdk.common import trim_pad_1d_array
  >>> visibility = [True, False, True, True, False]
  >>> trim_pad_1d_array(visibility, 3)
  array([True, False, True])

  Pad a 1D array to the correct length.

  >>> from mapteksdk.common import trim_pad_1d_array
  >>> visibility = [True]
  >>> trim_pad_1d_array(visibility, 3, False)
  array([True, False, False])

  """
  if not isinstance(array_to_check, np.ndarray):
    array_to_check = np.array(array_to_check)
  if array_to_check.ndim == 0:
    # The input array is empty. Create an appropriately sized array filled with
    # the fill value.
    new_shape = np.empty(elements_to_keep if elements_to_keep > 0 else 0)
    new_shape.fill(fill_value)
    array_to_check = new_shape
  array_to_check = array_to_check.flatten()
  if elements_to_keep > len(array_to_check):
    # Adding new rows, need to fill new slots with fill_value
    # Create empty array of desired size
    new_shape = np.empty(elements_to_keep).astype(array_to_check.dtype)
    # Fill it will default value
    new_shape.fill(fill_value)
    # Insert original values into the filled array
    new_shape[:array_to_check.shape[0]] = array_to_check[:new_shape.shape[0]]
    # Replace original
    array_to_check = new_shape
  elif elements_to_keep > 0:
    # Truncate array to elements_to_keep and ensure field sizes are right
    array_to_check = np.resize(array_to_check, elements_to_keep)
  else:
    pass
  return array_to_check

def convert_to_rgba(colour):
  """Converts a list representing a colour into a valid
  rgba colour - a list of length 4 in the form
  [red, green, blue, alpha] with each value between 0 and
  255.

  This conversion can take three different forms:

  1. If the list contains three elements, the alpha is assumed to
     be 255 (fully visible).

  2. If the list contains a single element, the colour is treated
     as a shade of grey.

  3. The colour is already rgba - no conversion is performed.

  If none of the above cases are applicable, a ValueError is raised.

  Parameters
  ----------
  colour : array_like
    List of colours to convert. This can either be a Greyscale colour
    ([intensity]), a RGB colour [red, green, blue] or a RGBA colour
    ([red, green, blue, alpha]).

  Returns
  -------
  ndarray
    ndarray representing colour in the form [red, green, blue, alpha].

  Raises
  ------
  ValueError
    If the colour cannot be converted to a valid rgba colour.

  Notes
  -----
  A user of the SDK generally does not need to call this function
  because it is called internally by all functions which take a colour.

  Each element in a rgba array is represented as an unsigned 8 bit integer.
  If a value is assigned which is greater than 255 or less than 0, integer
  overflow will occur. The colour will be set to value % 256.

  Alpha represents the transparency of the object - an alpha of 0 indicates
  a completely transparent (and hence invisible) colour whereas an alpha
  of 255 indicates a completely opaque object.

  Examples
  --------
  Convert greyscale colour to RGBA

  >>> from mapteksdk.common import convert_to_rgba
  >>> colour = [125]
  >>> convert_to_rgba(colour)
  array([125, 125, 125, 255])

  Convert RGB colour to RGBA

  >>> from mapteksdk.common import convert_to_rgba
  >>> colour = [120, 120, 0]
  >>> convert_to_rgba(colour)
  array([120, 120, 0, 255])

  """
  if isinstance(colour, np.ndarray):
    if colour.dtype != ctypes.c_uint8:
      colour = colour.astype(ctypes.c_uint8)
  else:
    colour = np.array(colour, dtype=ctypes.c_uint8)

  if colour.shape == (1,):
    colour = np.hstack((colour, colour, colour, [255]))
  elif colour.shape == (3,):
    colour = np.hstack((colour, [255]))
  elif colour.shape != (4,):
    error_message = (f"Invalid colour: {colour}\n"
                     "Colours must be RGB, RGBA or Greyscale")
    raise ValueError(error_message)

  return colour

def convert_array_to_rgba(colour_array, expected_size, default_colour=None):
  """Converts a list of colours to a valid ndarray of RGBA colours containing
  expected_size colours. The conversions uses the same rules as convert_to_rgba.

  Parameters
  ----------
  colour_array : array_like
    List of lists representing colours to convert to RGBA.
  expected_size : int
    Number of elements required in the final array.
    If colour_array is too long it is truncated to the correct length.
    If colour_array is too short it is padded with default_colour to
    the correct length.
  default_colour : array_like
    List representing the colour to append when padding the colour
    array. Default is Green ([0, 255, 0, 255]).

  Returns
  -------
  ndarray
    Input list trimmed or padded to the correct length with each
    element converted to RGBA ([red, green, blue, alpha]).

  Raises
  ------
  ValueError
    If colour_array is jagged - Not all colours in the array are in the
    same format, for example if some colours are represented as RGB and
    others are represented as RGBA.
  ValueError
    If colour array contains colours which are not represented in
    greyscale, RGB or RGBA format.
  ValueError
    If default colour is not valid.

  Examples
  --------
  Convert list of RGB colours to RGBA.

  >>> from mapteksdk.common import convert_array_to_rgba
  >>> colours = [[125, 125, 125], [120, 120, 0]]
  >>> convert_array_to_rgba(colours, 3)
  array([[125, 125, 125, 255],
         [120, 120,   0, 255],
         [  0, 255,   0, 255]], dtype=uint8)

  """
  # Colour to use when extending the list.
  if default_colour is None:
    default_colour = np.array([0, 255, 0, 255], dtype=ctypes.c_uint8)
  else:
    default_colour = convert_to_rgba(default_colour)

  # Make sure the input is an ndarray and not too long.
  if isinstance(colour_array, np.ndarray):
    if colour_array.dtype != ctypes.c_uint8:
      colour_array = colour_array.astype(ctypes.c_uint8)
    colour_array = colour_array[:expected_size]
  else:
    colour_array = np.array(colour_array[:expected_size], dtype=ctypes.c_uint8)

  # If input is empty, generate the default array.
  if colour_array.shape in ((0,), (0, 0), (1,), (1, 0)):
    return np.repeat(default_colour[np.newaxis, :], expected_size, 0)

  if colour_array.ndim != 2:
    raise ValueError(
      "Unable to convert colours to RGBA. The colour array is jagged. All "
      "colours must be specified in the same format (Greyscale, RGB or RGBA."
      f"Actual shape: {colour_array.shape}.")

  if colour_array.shape[1] == 1:
    # Handling for greyscale colours.
    alpha = np.full((colour_array.shape[0], 1), 255, dtype=ctypes.c_uint8)
    colour_array = np.column_stack((colour_array, colour_array,
                                    colour_array, alpha))
  elif colour_array.shape[1] == 3:
    # Handling for RGB colours.
    alpha = np.full((colour_array.shape[0], 1), 255, dtype=ctypes.c_uint8)
    colour_array = np.hstack((colour_array, alpha))
  elif colour_array.shape[1] != 4:
    raise ValueError("Unable to convert colours to RGBA. Colours must have "
                     "one, three or four components (Greyscale, RGB or RGBA)."
                     f"Actual components: {colour_array.shape[1]}.")

  # Pad the colours with default if there is not enough.
  if colour_array.shape[0] < expected_size:
    new_row_count = expected_size - colour_array.shape[0]
    extras = np.repeat(default_colour[np.newaxis, :], new_row_count, 0)
    colour_array = np.vstack((colour_array, extras))

  return colour_array
