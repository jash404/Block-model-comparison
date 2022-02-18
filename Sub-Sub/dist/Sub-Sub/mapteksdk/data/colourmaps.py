"""Colour map data types.

Colour maps (also known as legends) can be used to apply a colour schema to
other objects based on their properties (e.g. by primitive attribute, position,
etc).

The two supported types are:
  - NumericColourMap - Colour based on a numerical value.
  - StringColourMap  - Colour based on a string (letters/words) value.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import logging
import numpy as np
from ..capi import Modelling
from ..common import trim_pad_1d_array, convert_to_rgba, convert_array_to_rgba
from ..internal.lock import LockType, WriteLock
from .base import DataObject
from .objectid import ObjectID
from .errors import CannotSaveInReadOnlyModeError, InvalidColourMapError
# pylint: disable=too-many-instance-attributes

log = logging.getLogger("mapteksdk.data")

class UnsortedRangesError(InvalidColourMapError):
  """Error raised when the ranges of a colour map are not sorted."""

class NumericColourMap(DataObject):
  """Numeric colour maps map numeric values to a colour. The colours can
  either be smoothly interpolated or within bands. See below update functions
  for examples.

  Notes
  -----
  For interpolated colours there must be the same number of colours as
  intervals.

  For solid colour maps there must be n-1 colours where n is intervals.

  Tip: The 'cm' module in matplotlib can generate compatible colour maps.

  Raises
  ------
  InvalidColourMapError
    If on save the ranges array contains less than two values.

  See Also
  --------
  mapteksdk.data.primitives.PrimitiveAttributes.set_colour_map() :
    Colour a topology object by a colour map.

  Examples
  --------
  Create a colour map which would colour primitives with a value
  between 0 and 50 red, between 50 and 100 green and between 100 and 150
  blue.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import NumericColourMap
  >>> project = Project()
  >>> with project.new("legends/colour_map", NumericColourMap) as new_map:
  >>>     new_map.ranges = [0, 50, 100, 150]
  >>>     new_map.colours = [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
  >>>     new_map.interpolated = False

  Create a colour map which similar to above, but smoothly transitions
  from red to green to blue.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import NumericColourMap
  >>> project = Project()
  >>> with project.new("legends/interpolated_map", NumericColourMap) as new_map:
  >>>     new_map.ranges = [0, 75, 150]
  >>>     new_map.colours = [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
  >>>     new_map.interpolated = True

  Colour a surface using a colour map by the "order" point_attribute.
  This uses the colour map created in the first example so make sure
  to run that example first.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Surface
  >>> points = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
  ...           [0.5, 0.5, 0.5], [0.5, 0.5, -0.5]]
  >>> facets = [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4],
  ...           [0, 1, 5], [1, 2, 5], [2, 3, 5], [3, 0, 5]]
  ... order = [20, 40, 60, 80, 100, 120, 140, 75]
  >>> project = Project()
  >>> colour_map_id = project.find_object("legends/colour_map")
  >>> with project.new("surfaces/ordered_surface", Surface) as surface:
  ...     surface.points = points
  ...     surface.facets = facets
  ...     surface.point_attributes["order"] = order
  ...     surface.point_attributes.set_colour_map("order", colour_map_id)

  Edit the colour map associated with the surface created in the previous
  example so make sure to run that first.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import NumericColourMap
  >>> project = Project()
  >>> with project.edit("surfaces/ordered_surface") as my_surface:
  >>>   with project.edit(my_surface.get_colour_map()) as cm:
  >>>     pass # Edit the colour map here.

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    is_new = not object_id
    if is_new:
      object_id = ObjectID(Modelling().NewNumericColourMap())
    super().__init__(object_id, lock_type)
    self.ranges = None
    self.colours = None
    self.upper_cutoff = None
    self.lower_cutoff = None
    self.interpolated = True
    if not is_new:
      self.get_properties()

  @classmethod
  def static_type(cls):
    """Return the type of numeric colour maps as stored in a Project.

    This can be used for determining if the type of an object is a numeric
    colour map.

    """
    return Modelling().NumericColourMapType()

  def get_properties(self):
    """Load properties from the Project. This resets all properties back
    to their state when save() was last called, undoing any changes
    which have been made.

    """
    # Get the numeric colour map number of entries
    count = Modelling().ReadNumericColourMap(
      self._lock.lock, 0, None, None, None, None)
    # Create an array of float to hold the ranges
    ranges = (ctypes.c_float*(count+1))()
    # Create array to hold colours
    colours = (ctypes.c_uint8*count*8)()
    # Low count array
    lowcut = (ctypes.c_uint8*4)()
    # up count array
    upcut = (ctypes.c_uint8*4)()

    # Read colour map from model
    Modelling().ReadNumericColourMap(
      self._lock.lock, count, ctypes.byref(colours), ctypes.byref(ranges),
      ctypes.byref(lowcut), ctypes.byref(upcut))
    # Assign to object properties
    self.colours = np.array(colours).reshape((-1, 4))

    # Infer whether this colour map is solid or interpolated
    # For 3 range values, (technically) 2 intervals:
    # A solid array will look like this:
    # [[1,2,3,4],[1,2,3,4],[5,6,7,8],[5,6,7,8]]
    # i.e. [[start],[end],[start],[end]] >> [start == end != start == end]
    # An interpolated array will look like this:
    # [[1,2,3,4],[5,6,7,8],[5,6,7,8],[9,10,11,12]]
    # i.e. [[start],[end],[start],[end]] >> [start != end == start != end]
    new_colours = self.colours[1::2]
    self.interpolated = not np.array_equal(new_colours, self.colours[::2])
    # When colours are read back they are given twice each (start/end),
    # so only take every second element from the array.
    # When interpolated the first and last start/end should be different.
    first_colour = self.colours[0]
    self.colours = new_colours
    if self.interpolated:
      # The first element was removed above, re-insert it now at index 0
      self.colours = np.insert(self.colours, 0, first_colour, axis=0)
    self.ranges = np.array(ranges)
    self.upper_cutoff = np.array(upcut)
    self.lower_cutoff = np.array(lowcut)

  @property
  def interpolated(self):
    """If True, the colour map is saved with interpolated colours between each
    range. If False, the colour map is saved with solid boundaries.

    """
    return self.__interpolated

  @interpolated.setter
  def interpolated(self, value):
    self.__interpolated = value

  @property
  def intervals(self):
    """Returns the number of intervals in the colour map.

    Returns
    -------
    int
      Number of intervals in the colour map.

    Notes
    -----
    This is the length of the ranges array.

    """
    return self.ranges.shape[0]

  @property
  def colours(self):
    """The list of the colours in the colour map.
    If the colour map contains N colours, this is of the form:
    [[r1, g1, b1, a1], [r2, g2, b2, a2], ..., [rN, gN, bN, aN]].

    If interpolated = True, the length of this list (N) should
    be equal to the length of the ranges list.
    If interpolated = False, the length of this list (N) should
    be equal to the length of the ranges list minus one.

    Notes
    -----
    On save, if the colours array is too large, the excess colours are
    silently discarded.

    On save, if the colours array is too small when compared
    with the ranges array, the behaviour varies:
    If the colour map is interpolated:
    - If the size is one too few, the upper limit is appended.
    - If the size it two too few, the lower limit is prepended
    and the upper limit is appended.
    - Otherwise the colours are padded with the last colour in the map.

    If the colour map is solid the colours array is padded with the
    last colour in the map.

    """
    return self.__colours

  @colours.setter
  def colours(self, colours):
    if colours is None:
      base_array = np.array([[0, 255, 0]])
      self.__colours = np.repeat(base_array, self.intervals, axis=0)
    else:
      self.__colours = convert_array_to_rgba(colours, len(colours))

  @property
  def ranges(self):
    """List of numbers used to define where colour transitions occur
    in the colour map.
    For example, if ranges = [0, 50, 100] and the colour map is solid,
    then between 0 and 50 the first colour would be used and between
    50 and 100 the second colour would be used.

    If the colour map is interpolated, then the first colour would be
    used at 0 and between 0 and 50 the colour would slowly change to
    the second colour (reaching the second colour at 50). Then between
    50 and 100 the colour would slowly transition from the second
    colour to the third colour.

    Raises
    ------
    InvalidColourMapError
      If set to have fewer than two values.
    UnsortedRangesError
      If ranges is not sorted.
    ValueError
      If set to an array containing a non-numeric value.

    Notes
    -----
    This array dictates the intervals value and also controls the
    final length of the colours array when saving.

    """
    return self.__ranges

  @ranges.setter
  def ranges(self, ranges):
    if ranges is None:
      self.__ranges = np.array([], dtype=ctypes.c_float)
    else:
      if len(ranges) < 2:
        raise InvalidColourMapError(
          "Ranges must contain at least two values.")
      ranges = trim_pad_1d_array(
        ranges).astype(ctypes.c_float)
      if not np.all(ranges[:-1] <= ranges[1:]):
        raise UnsortedRangesError("Ranges must be sorted in ascending order.")
      self.__ranges = ranges

  @property
  def upper_cutoff(self):
    """Colour to use for values which are above the highest range in the
    ranges array.

    For example, if ranges = [0, 50, 100] then this colour is used for any
    value greater than 100.
    The default value is Red ([255, 0, 0])

    Notes
    -----
    Set the alpha value to 0 to make this colour invisible.

    """
    return self.__upper_cutoff

  @upper_cutoff.setter
  def upper_cutoff(self, upper_cutoff):
    if upper_cutoff is not None:
      self.__upper_cutoff = convert_to_rgba(upper_cutoff)
    else:
      self.__upper_cutoff = np.array([255, 0, 0, 255], ctypes.c_uint8)

  @property
  def lower_cutoff(self):
    """Colour to use for values which are below the lowest range in the
    ranges array.

    For example, if ranges = [0, 50, 100] then this colour is used for any
    value lower than 0.
    The default value is blue ([0, 0, 255, 255]).

    Returns
    -------
    ndarray
      Array of the form [red, green, blue, alpha] defining the colour to
      use for values which are below the colour map.

    Notes
    -----
    Set the alpha value to 0 to make these items invisible.

    """
    return self.__lower_cutoff

  @lower_cutoff.setter
  def lower_cutoff(self, lower_cutoff):
    if lower_cutoff is not None:
      self.__lower_cutoff = convert_to_rgba(lower_cutoff)
    else:
      self.__lower_cutoff = np.array([0, 0, 255, 255], ctypes.c_uint8)

  def save(self):
    """Saves the changes to the numeric colour map.

    Raises
    ------
    CannotSaveInReadOnlyModeError
      If the colour map is opened in read only mode.
    InvalidColourMapError
      If the ranges array contains less than two values.

    """
    if isinstance(self._lock, WriteLock):
      # Check all objects are ready to save
      range_count = self.ranges.shape[0]
      colour_count = self.colours.shape[0]
      difference = range_count - colour_count
      if self.interpolated:
        if range_count < 2:
          raise InvalidColourMapError(
            "Interpolated colour maps must contain at least two ranges.")
        # Assert that ranges == colours
        if difference < 0 or difference > 2:
          # colours array is too large, trim number of elements
          # or
          # The colour array is too small. To prevent errors, it will be
          # padded with the final colour (Assuming there is at least one colour)
          # to get it to the correct length.
          if colour_count == 0:
            self.colours = convert_array_to_rgba(self.colours, range_count)
          else:
            self.colours = convert_array_to_rgba(self.colours,
                                                 range_count,
                                                 self.colours[-1])
        elif difference == 1:
          # If its out by one element, copy upper_cutoff to the end
          # of the colours array.
          self.colours = np.append(self.colours, [self.upper_cutoff], axis=0)
        elif difference == 2:
          # If its out by 2, copy upper_cutoff to end, and lower_cutoff to
          # start of colours array
          self.colours = np.append(self.colours, [self.upper_cutoff], axis=0)
          self.colours = np.insert(
            self.colours, 0, self.lower_cutoff, axis=0)

        # Should be safe to save now:
        self._save_interpolated_map(
          self.intervals,
          self.colours,
          self.ranges,
          self.lower_cutoff,
          self.upper_cutoff)
      else:
        if range_count < 2:
          raise InvalidColourMapError(
            "Solid colour maps must contain at least two ranges.")
        # Assert that ranges == colours + 1 (for solid colour boundaries)
        if difference != 1:
          # colours array is too large, trim number of elements
          # or
          # The colour array is too small. To prevent errors, it will be
          # padded with the final colour (assuming there is at least one colour)
          # to get it to the correct length.
          if self.colours.shape[0] != 0:
            self.colours = convert_array_to_rgba(self.colours,
                                                 range_count - 1,
                                                 self.colours[-1])
          else:
            self.colours = convert_array_to_rgba(self.colours, range_count - 1)
        # Should be safe to save now:
        self._save_solid_map(self.intervals,
                             self.colours,
                             self.ranges,
                             self.lower_cutoff,
                             self.upper_cutoff)
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  def _save_solid_map(self, intervals, colours, ranges,
                      lower_cutoff, upper_cutoff):
    """Save the colour map as a solid colour map to the Project.

    Parameters
    ----------
    intervals : int
      The number of intervals in the colour map.
    colours : numpy.ndarray
      Array of colours as ctypes.c_uint8. The shape should be
      (intervals - 1, 4).
    ranges : numpy.ndarray
      Array of ranges as ctypes.c_float. The shape should be (intervals, ).
    lower_cutoff : numpy.ndarray
      The lower cutoff colour represented as four ctypes.c_uint8. The shape
      should be (4, ).
    upper_cutoff : numpy.ndarray
      The upper cutoff colour represented as four ctypes.c_uint8. The shape
      should be (4, ).

    """
    c_colours = (ctypes.c_uint8 * ((intervals - 1) * 4))()
    c_ranges = (ctypes.c_float * intervals)()
    c_lower_cutoff = (ctypes.c_uint8 * 4)()
    c_upper_cutoff = (ctypes.c_uint8 * 4)()
    c_colours[:] = colours.ravel()
    c_ranges[:] = ranges.ravel()
    c_lower_cutoff[:] = lower_cutoff.ravel()
    c_upper_cutoff[:] = upper_cutoff.ravel()
    Modelling().UpdateNumericColourMapSolid(self._lock.lock,
                                            intervals,
                                            c_colours,
                                            c_ranges,
                                            c_lower_cutoff,
                                            c_upper_cutoff)

  def _save_interpolated_map(self, intervals, colours, ranges,
                             lower_cutoff, upper_cutoff):
    """Save the colour map as an interpolated colour map to the Project.

    Parameters
    ----------
    intervals : int
      The number of intervals in the colour map.
    colours : numpy.ndarray
      Array of colours as ctypes.c_uint8. The shape should be
      (intervals, 4).
    ranges : numpy.ndarray
      Array of ranges as ctypes.c_float. The shape should be (intervals, ).
    lower_cutoff : numpy.ndarray
      The lower cutoff colour represented as four ctypes.c_uint8. The shape
      should be (4, ).
    upper_cutoff : numpy.ndarray
      The upper cutoff colour represented as four ctypes.c_uint8. The shape
      should be (4, ).

    """
    c_colours = (ctypes.c_uint8 * (intervals * 4))()
    c_ranges = (ctypes.c_float * intervals)()
    c_lower_cutoff = (ctypes.c_uint8 * 4)()
    c_upper_cutoff = (ctypes.c_uint8 * 4)()
    c_colours[:] = colours.ravel()
    c_ranges[:] = ranges.ravel()
    c_lower_cutoff[:] = lower_cutoff.ravel()
    c_upper_cutoff[:] = upper_cutoff.ravel()

    Modelling().UpdateNumericColourMapInterpolated(self._lock.lock,
                                                   intervals,
                                                   c_colours,
                                                   c_ranges,
                                                   c_lower_cutoff,
                                                   c_upper_cutoff)

class StringColourMap(DataObject):
  """Colour maps which maps colours to strings rather than numbers.

  Raises
  ------
  InvalidColourMapError
    If on save the legends array is empty.

  Warnings
  --------
  Colouring objects other than PointSets and DenseBlockModels
  using string colour maps may not be supported by applications
  (but may be supported in the future). If it is not supported the
  object will either be coloured red or the viewer
  will crash when attempting to view the object.

  Notes
  -----
  The indices of these values are related to the
  colours given for the same indices and the arrays must
  have the same number of elements.

  Set value for a (alpha) to 0 to make out of
  bounds items invisible.

  Examples
  --------
  Create a string colour map which maps "Gold" to yellow,
  "Silver" to grey and "Iron" to red.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import StringColourMap
  >>> project = Project()
  >>> with project.new("legends/map", StringColourMap) as new_map:
  >>>     new_map.legend = ["Gold", "Silver", "Iron"]
  >>>     new_map.colours = [[255, 255, 0], [100, 100, 100], [255, 0, 0]]

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    is_new = not object_id
    if is_new:
      object_id = ObjectID(Modelling().NewStringColourMap())
    super().__init__(object_id, lock_type)
    self.legend = None
    self.colours = None
    self.cutoff = None
    if not is_new:
      self.get_properties()

  @classmethod
  def static_type(cls):
    """Return the type of string colour maps as stored in a Project.

    This can be used for determining if the type of an object is a string
    colour map.

    """
    return Modelling().StringColourMapType()

  def get_properties(self):
    """Load properties from the Project. This resets all properties back
    to their state when save() was last called, undoing any changes
    which have been made.

    """
    # Get the number of entries
    count = Modelling().ReadStringColourMap(
      self._lock.lock, 0, None, 0, None, None)
    if count > 0:
      # Get the length required to store all of the strings
      buffer_len = Modelling().ReadStringColourMap(
        self._lock.lock, count, None, 0, None, None)
      # Create array to hold legend strings
      legend = ctypes.create_string_buffer(buffer_len)
      # Create array to hold colours
      colours = (ctypes.c_uint8*4*count)()
      # Out of bounds colour
      cutoff = (ctypes.c_uint8*4)()

      # Read colour map from model
      Modelling().ReadStringColourMap(
        self._lock.lock, count, legend, buffer_len,
        ctypes.byref(colours), ctypes.byref(cutoff))
      # Assign to object properties
      self.colours = np.array(colours).reshape((-1, 4))
      # Convert string buffer to byte array
      # split on null terminator \x00
      self.legend = np.array(bytearray(legend).decode(
        'utf-8').split('\x00'))[:-1] # Drop the final null delimiter
      self.cutoff = np.array(cutoff)

  @property
  def intervals(self):
    """Returns the number of intervals in the colour map.
    This is the length of the legend array.

    """
    return self.legend.shape[0]

  @property
  def legend(self):
    """1D numpy array of string values defining a legend that matches the
    colours array.

    The string colour_map.legend[i] is mapped to colour_map.colours[i].

    Raises
    ------
    TypeError
      If set to an array which does not contain only strings.
    InvalidColourMapError
      If set to an array with zero elements.

    Notes
    -----
    There must be no duplicates to avoid exceptions.
    The number of elements must match the colours array.

    """
    return self.__legend

  @legend.setter
  def legend(self, legend):
    if legend is None:
      self.__legend = np.array([], str)
    else:
      if isinstance(legend, list):
        if len(legend) == 0:
          raise InvalidColourMapError("Legend must contain at least one value.")
        # if provided as list, convert to numpy array
        legend = trim_pad_1d_array(legend)
      # ensure we've been provided an array of strings
      if isinstance(legend, np.ndarray) and legend.dtype.kind in {'U', 'S'}:
        if legend.shape[0] == 0:
          raise InvalidColourMapError("Legend must contain at least one value.")
        self.__legend = legend
      else:
        raise TypeError("Unsupported type. Expected numpy array of strings")

  @property
  def colours(self):
    """The list of colours in the colour map.

    Notes
    -----
    Must be the same number of elements as the legend array
    and/or as indicated by the intervals attribute.

    On save, if the colours list is larger than the legend list it will be
    trimmed to the length of the legend.
    If the colours list is shorter than the legends list it will be
    padded with green ([0, 255, 0, 255]).

    """
    return self.__colours

  @colours.setter
  def colours(self, colours):
    if colours is None:
      self.__colours = np.array([[0, 255, 0, 255] * self.intervals],
                                ctypes.c_uint8)
    else:
      self.__colours = convert_array_to_rgba(colours, len(colours))

  @property
  def cutoff(self):
    """The colour to use for values which don't match any value in legends.

    Notes
    -----
    Set the alpha value to 0 to make these items invisible.

    Default is red: [255, 0, 0, 255]

    Examples
    --------
    If the legend = ["Gold", "Silver"] then this property defines the colour
    to use for values which are not in the legend (ie: anything which is
    not "Gold" or "Silver"). For example, it would define what colour to
    represent 'Iron' or 'Emerald'.

    """
    return self.__cutoff

  @cutoff.setter
  def cutoff(self, cutoff):
    if cutoff is not None:
      self.__cutoff = convert_to_rgba(cutoff)
    else:
      self.__cutoff = np.array([255, 0, 0, 255], ctypes.c_uint8)

  def save(self):
    """Saves the changes to the string colour map.

    Raises
    ------
    CannotSaveInReadOnlyModeError
      If the colour map is opened in read only mode.
    InvalidColourMapError
      If the legends array is empty.

    """
    if isinstance(self._lock, WriteLock):
      # Check all objects are ready to save
      if self.legend.shape[0] == 0:
        raise InvalidColourMapError("Legend must contain at least one value.")

      # Assert that legend count == colour count.
      self.colours = convert_array_to_rgba(self.colours, self.intervals)

      # Get the maximum length string from the array to allow setup of buffers
      max_string_length = np.max(np.vectorize(len)(self.legend))
      # Create string buffers allowing for additional null character on max len
      # Create one buffer for each legend value
      string_buffers = [ctypes.create_string_buffer(int(max_string_length+1))
                        for i in range(self.intervals)]
      # Get the pointers for each buffer
      string_pointers = (ctypes.c_char_p * self.intervals) \
                        (*map(ctypes.addressof, string_buffers))
      # Populate the buffers with the legend values
      for i in range(self.intervals):
        string_pointers[i] = self.legend[i].encode('utf-8')

      c_colours = (ctypes.c_uint8 * (self.intervals * 4))()
      c_colours[:] = self.colours.ravel()

      c_cutoff = (ctypes.c_uint8 * 4)()
      c_cutoff[:] = self.cutoff.ravel()

      Modelling().UpdateStringColourMap(
        self._lock.lock,
        self.intervals,
        ctypes.byref(string_pointers), # char**
        c_colours,
        c_cutoff)
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error
