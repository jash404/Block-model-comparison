"""Annotation data types.

These data types are useful for marking areas of interest.

Currently this includes:

- Text2D: Represents 2D text which always faces the view.
- Text3D: Represents 3D text.
- Marker: 3D object which can be used to represent a place, route, sign, etc.

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
from ..capi import Modelling
from ..common import trim_pad_2d_array, trim_pad_1d_array, convert_to_rgba
from ..internal.rotation import Rotation
from ..internal.lock import WriteLock, LockType
from ..internal.util import default_type_error_message
from .base import Topology, DataObject
from .errors import CannotSaveInReadOnlyModeError
from .objectid import ObjectID
from .facets import Surface
from .rotation import RotationMixin

# pylint: disable=too-many-lines
# pylint: disable=too-many-instance-attributes
log = logging.getLogger("mapteksdk.data")

class HorizontalAlignment(enum.Enum):
  """Enum used to represent the horizontal alignment options for 2D and 3D Text.

  """
  LEFT = 0
  CENTRED = 1
  RIGHT = 2

class VerticalAlignment(enum.Enum):
  """Enum used to represent the vertical alignment options for 2D and 3D text.

  """
  # Top correspond to CapLine.
  TOP = 3
  # Centred corresponds to BaseCapMean.
  CENTRED = 6
  # Bottom corresponds to BaseLineOfLastLine.
  BOTTOM = 4
  # The other options are less useful so they aren't revealed on
  # the Python side.

class FontStyle(enum.Flag):
  """Enum representing the possible font styles. This is a flag enum
  so the values can be combined via bitwise operators.

  """
  REGULAR = 0
  """The Regular font style."""
  BOLD = 1
  """The Bold font style."""
  ITALIC = 2
  """The Italic font style."""

class Text(Topology):
  """The abstract base class representing text at a fixed location
  in space. This class cannot be instantiated directly - use
  Text2D or Text3D instead.

  Parameters
  ----------
  object_id : ObjectID
    Object ID to use for this object. Default is None,
    indicating a new text object should be created.

  lock_type : LockType
    The type of lock to place on the object once it has been
    created. Default is LockType.READWRITE which allows read
    and write access to the text.

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    is_new = not object_id
    if is_new:
      object_id = self._create_object()

    super().__init__(object_id, lock_type)
    self.__location = None
    self.__colour = None
    self.__text = None
    self.__size = None
    self.__vertical_alignment = None
    self.__horizontal_alignment = None
    self.__font_style = None
    if is_new:
      # Create a new text object.
      # Colour and size are automatically assigned on creation.
      self.location = None
      self.text = ""
      self.colour = self._get_text_colour()
      self.size = self._get_text_size()
    else:
      self.location = self._get_points()
      self.colour = self._get_text_colour()
      self.size = self._get_text_size()
      self.text = self._get_text()

  def _create_object(self):
    """Creates a new instance of this object in the project."""
    raise NotImplementedError(
      "Creating Text isn't supported.\n"
      "Consider if a Text2D or Text3D would suit your needs.")

  def _invalidate_properties(self):
    """Invalidates the properties."""
    self.__location = None
    self.text = None
    self.colour = None
    self.size = None
    self.__horizontal_alignment = None
    self.__vertical_alignment = None
    self.__font_style = None

  @property
  def text(self):
    """The text displayed by this object.

    Raises
    ------
    TypeError
      If you attempt to set the text to a non-string value.

    """
    return self.__text

  @text.setter
  def text(self, new_text):
    if new_text is not None:
      if not isinstance(new_text, str):
        raise TypeError(default_type_error_message("new_text", new_text, str))
      self.__text = new_text
    else:
      self.__text = ""

  @property
  def size(self):
    """The size of the text. The default size is 16."""
    return self.__size

  @size.setter
  def size(self, new_size):
    if new_size is not None:
      self.__size = new_size
    else:
      self.__size = 16

  @property
  def location(self):
    """Location of the text as point ([x,y,z])."""
    return self.__location

  @location.setter
  def location(self, location):
    if location is None:
      self.__location = np.array([0, 0, 0])
    else:
      # Ensure location stored as 1D array of float64 [x,y,z]
      self.__location = trim_pad_1d_array(location, 3, 0)

  @property
  def colour(self):
    """The colour of the text represented as an RGBA colour.

    You can set the colour to be a RGB or greyscale colour -
    it will automatically be converted to RGBA.

    """
    return self.__colour

  @colour.setter
  def colour(self, colour):
    if colour is None:
      self.__colour = np.array([255, 255, 255, 255])
    else:
      self.__colour = convert_to_rgba(colour)

  @property
  def vertical_alignment(self):
    """The vertical alignment of the text.

    See the VerticalAlignment enum for valid values.

    Raises
    ------
    TypeError
      If attempting to set to a value which is not from the VerticalAlignment
      enum.
    ValueError
      If an unsupported vertical alignment is read from the Project.

    Examples
    --------
    Setting 3D text to be center aligned.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Text3D, VerticalAlignment
    >>> project = Project()
    >>> with project.new("cad/centre", Text3D) as new_text_3d:
    ...     new_text_3d.text = "Centre"
    ...     new_text_3d.vertical_alignment = VerticalAlignment.CENTRED

    """
    if self.__vertical_alignment is None:
      self.__vertical_alignment = self._get_text_vertical_alignment()
    return self.__vertical_alignment

  @vertical_alignment.setter
  def vertical_alignment(self, new_alignment):
    if not isinstance(new_alignment, VerticalAlignment):
      raise TypeError(default_type_error_message("vertical alignment",
                                                 new_alignment,
                                                 VerticalAlignment))
    self.__vertical_alignment = new_alignment

  @property
  def horizontal_alignment(self):
    """The horizontal alignment of the text.

    See the HorizontalAlignment enum for valid values.

    Raises
    ------
    TypeError
      If attempting to set to a value which is not from the HorizontalAlignment
      enum.
    ValueError
      If an unsupported horizontal alignment is read from the Project.

    Examples
    --------
    Setting 3D text to be left aligned.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Text3D, HorizontalAlignment
    >>> project = Project()
    >>> with project.new("cad/left", Text3D) as new_text_3d:
    ...     new_text_3d.text = "Left"
    ...     new_text_3d.horizontal_alignment = HorizontalAlignment.LEFT

    """
    if self.__horizontal_alignment is None:
      self.__horizontal_alignment = self._get_text_horizontal_alignment()
    return self.__horizontal_alignment

  @horizontal_alignment.setter
  def horizontal_alignment(self, new_alignment):
    if not isinstance(new_alignment, HorizontalAlignment):
      raise TypeError(default_type_error_message("horizontal_alignment",
                                                 new_alignment,
                                                 HorizontalAlignment))
    self.__horizontal_alignment = new_alignment

  @property
  def font_style(self):
    """The font style of the text.

    See FontStyles enum for the possible values. Note that this is a
    flag enum and flags can be combined using the | operator.

    Raises
    ------
    TypeError
      If set to a value which is not a part of FontStyles.

    Examples
    --------
    Set text to be italic.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Text3D, FontStyle
    >>> project = Project()
    >>> with project.new("cad/italic", Text3D) as new_text:
    ...     new_text.text = "This text is italic"
    ...     new_text.font_style = FontStyle.ITALIC

    Set text to be bold and italic.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Text3D, FontStyle
    >>> project = Project()
    >>> with project.new("cad/bolditalic", Text3D) as new_text:
    ...     new_text.text = "This text is bold and italic"
    ...     new_text.font_style = FontStyle.BOLD | FontStyle.ITALIC

    Print if the text created in the above example is bold.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Text3D, FontStyle
    >>> project = Project()
    >>> with project.read("cad/bolditalic") as read_text:
    ...     if read_text.font_style & FontStyle.BOLD:
    ...         print("This text is bold.")
    This text is bold.

    """
    if self.__font_style is None:
      self.__font_style = self._get_text_font_style()
    return self.__font_style

  @font_style.setter
  def font_style(self, new_style):
    if not isinstance(new_style, FontStyle):
      raise TypeError(default_type_error_message("font style",
                                                 new_style,
                                                 HorizontalAlignment))
    self.__font_style = new_style

  def save(self):
    if isinstance(self._lock, WriteLock):
      # Ensure location stored as 2D, single element array [[x,y,z]]
      store_location = trim_pad_2d_array(array_to_check=self.location,
                                         elements_to_keep=1,
                                         values=3)
      self._save_points(store_location)
      self._save_annotation_text(self.text)
      if self.colour is not None:
        self._save_annotation_text_colour(self.colour)
      self._save_annotation_text_size(self.size)
      if self.__vertical_alignment is not None:
        self._save_text_vertical_alignment(self.vertical_alignment)
      if self.__horizontal_alignment is not None:
        self._save_text_horizontal_alignment(self.horizontal_alignment)
      if self.__font_style is not None:
        self._save_text_font_style(self.font_style)

      self._reconcile_changes()
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

  def _get_text_vertical_alignment(self):
    """Load the vertical alignment from the Project.

    Returns
    -------
    VerticalAlignment
      The vertical alignment of the text.

    Raises
    ------
    RuntimeError
      If loading vertical alignment failed.
    ValueError
      If the vertical alignment is not supported.

    """
    alignment_id = Modelling().GetTextVerticalAlignment(self._lock.lock)
    if alignment_id == 255:
      raise RuntimeError("Failed to load vertical alignment.")
    return VerticalAlignment(alignment_id)

  def _save_text_vertical_alignment(self, vertical_alignment):
    """Saves the horizontal alignment to the Project.

    Parameters
    ----------
    vertical_alignment : VerticalAlignment
      The Vertical alignment to set for the object.

    Raises
    ------
    TypeError
      If self does not support vertical alignment.
    RuntimeError
      If an error occurred while setting the vertical alignment.

    """
    Modelling().SetTextVerticalAlignment(self._lock.lock,
                                         vertical_alignment.value)

  def _get_text_horizontal_alignment(self):
    """Load the horizontal alignment from the Project.

    Returns
    -------
    HorizontalAlignment
      The horizontal alignment of the text.

    Raises
    ------
    RuntimeError
      If loading horizontal alignment failed.
    ValueError
      If the horizontal alignment is not supported.

    """
    alignment_id = Modelling().GetTextHorizontalAlignment(self._lock.lock)
    if alignment_id == 255:
      raise RuntimeError("Failed to load horizontal alignment.")
    return HorizontalAlignment(alignment_id)

  def _save_text_horizontal_alignment(self, horizontal_alignment):
    """Saves the horizontal alignment to the Project.

    Parameters
    ----------
    horizontal_alignment : HorizontalAlignment
      The Horizontal alignment to set for the object.

    Raises
    ------
    TypeError
      If self does not support horizontal alignment.
    RuntimeError
      If an error occurred while setting the horizontal alignment.

    """
    Modelling().SetTextHorizontalAlignment(self._lock.lock,
                                           horizontal_alignment.value)

  def _get_text_font_style(self):
    """Gets the text style from the Project.

    Returns
    -------
    FontStyle
      The FontStyle of the text.

    Raises
    ------
    ValueError
      If the font style is unsupported.

    """
    return FontStyle(Modelling().GetTextFontStyle(self._lock.lock))

  def _save_text_font_style(self, new_style):
    """Saves the text style in the project.

    Parameters
    ----------
    new_style : FontStyle
      The new style to save to the project.

    Raises
    ------
    ValueError
      If style is not supported by the project.

    """
    Modelling().SetTextFontStyle(self._lock.lock, new_style.value)

class Text2D(Text):
  """Allows creation of text at a fixed location in space.

  Examples
  --------
  Creating a new 2D text object at the origin.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Text2D
  >>> project = Project()
  >>> with project.new("cad/text", Text2D) as new_text:
  >>>     new_text.location = [0, 0, 0]
  >>>     new_text.text = "Hello World"

  Editing an existing 2D text object to be size 16 and magenta.

  >>> from mapteksdk.project import Project
  >>> project = Project()
  >>> with project.edit("cad/text") as text:
  >>>     text.colour = [255, 0, 255]
  >>>     text.size = 16

  """

  @classmethod
  def static_type(cls):
    """Return the type of 2D text as stored in a Project.

    This can be used for determining if the type of an object is a 2D text.

    """
    return Modelling().Text2DType()

  def _create_object(self):
    return ObjectID(Modelling().New2DText())

class Text3D(Text):
  """Allows creation of three dimensional text at a fixed location and size in
  space.

  """
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    super().__init__(object_id, lock_type)
    self.__direction = None
    self.__up_direction = None
    self.__always_visible = None
    self.__facing = None
    self.__camera_facing = None
    self.__viewer_facing = None

  class Facing(enum.Enum):
    """Enum representing the possible facing values for 3D text."""
    NO_FACING = 0
    """The text will not be camera or viewer facing. Depending on the angle
    it is viewed from, it may be upsidedown, back-to-front or both.

    """
    CAMERA_FACING = 1
    """The text will rotate to always face towards the camera. Regardless of
    the angle it is viewed at, the text will never be upsidedown or
    back-to-front.

    This causes direction and up direction of the text to be ignored.

    """
    VIEWER_FACING = 2
    """The text will automatically flip so that it never appears upsidedown.
    Viewer facing text can still be back-to-front.

    """

  @classmethod
  def static_type(cls):
    """Return the type of 3D text as stored in a Project.

    This can be used for determining if the type of an object is a 3D text.

    """
    return Modelling().Text3DType()

  def _invalidate_properties(self):
    super()._invalidate_properties()
    self.__direction = None
    self.__up_direction = None
    self.__facing = None
    self.__always_visible = None
    self.__camera_facing = None
    self.__viewer_facing = None

  def save(self):
    if self.__direction is not None:
      self._save_text_direction(self.direction)
    if self.__up_direction is not None:
      self._save_text_up_direction(self.up_direction)
    if self.__always_visible is not None:
      self._save_text_is_always_visible(self.always_visible)

    # Convert the facing enum back to the associated enum values.
    # Note that If camera_facing is set to True, the value of viewer_facing
    # is ignored.
    if self.__facing is not None:
      if self.__facing is Text3D.Facing.CAMERA_FACING:
        self.__camera_facing = True
        self.__viewer_facing = False
      elif self.__facing is Text3D.Facing.VIEWER_FACING:
        self.__viewer_facing = True
        self.__camera_facing = False
      else:
        self.__camera_facing = False
        self.__viewer_facing = False

    # Save the adjusted camera and viewer facing if needed.
    if self.__camera_facing is not None:
      self._save_text_is_camera_facing(self.__camera_facing)
    if self.__viewer_facing is not None:
      self._save_text_always_viewer_facing(self.__viewer_facing)

    super().save()

  @property
  def direction(self):
    """The 3D direction vector of the text.

    This is the direction vector from the start of the first character
    to the end of the last character.

    """
    if self.__direction is None:
      self.__direction = np.array(self._get_text_direction(), ctypes.c_double)
    return self.__direction

  @direction.setter
  def direction(self, new_direction):
    if new_direction is None:
      self.__direction = None
    else:
      new_direction = trim_pad_1d_array(new_direction, 3, 0
                                        ).astype(ctypes.c_double)
      self.__direction = new_direction

  @property
  def up_direction(self):
    """The 3D direction vector of the text.

    This is the direction vector from the bottom of the text to the top.

    """
    if self.__up_direction is None:
      self.__up_direction = np.array(self._get_text_up_direction(),
                                     ctypes.c_double)
    return self.__up_direction

  @up_direction.setter
  def up_direction(self, new_up_direction):
    if new_up_direction is None:
      self.__up_direction = None
    else:
      new_up_direction = trim_pad_1d_array(new_up_direction, 3, 0
                                           ).astype(ctypes.c_double)
      self.__up_direction = new_up_direction

  @property
  def always_visible(self):
    """If the text will be visible through other objects.

    If set to true, the 3D text will be visible with a faded out appearance
    when there are objects between the text and the view. This is False
    by default.

    Raises
    ------
    TypeError
      If set to a value which is not a bool.

    """
    if self.__always_visible is None:
      self.__always_visible = self._get_text_is_always_visible()
    return self.__always_visible

  @always_visible.setter
  def always_visible(self, is_always_visible):
    if not isinstance(is_always_visible, bool):
      # I feel like I have typed out this exact error message out a lot.
      # Maybe it would be worthwhile to factor it out.
      raise TypeError(default_type_error_message("always_visible",
                                                 is_always_visible,
                                                 bool))
    self.__always_visible = is_always_visible

  @property
  def facing(self):
    """Where the text will face.

    By default this is Text3D.Facing.VIEWER_FACING which causes the text
    to never appear upside down, even when viewed from the back.

    See the values of the Text3D.Facing enum for possible options.

    Raises
    ------
    TypeError
      If set to a value which is not Text3D.Facing.

    Examples
    --------
    Set text containing a smiley face to be always camera facing so
    that it will always be smiling even when viewed from the back.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Text3D
    >>> project = Project()
    >>> with project.new("cad/smile", Text3D) as new_text:
    ...     new_text.text = ":)"
    ...     new_text.facing = Text3D.Facing.CAMERA_FACING

    """
    if self.__facing is None:
      # Convert the loaded camera/viewer facing values to the enum.
      self.__camera_facing = self._get_text_is_camera_facing()
      self.__viewer_facing = self._get_text_always_viewer_facing()

      if self.__camera_facing:
        self.__facing = Text3D.Facing.CAMERA_FACING
      elif self.__viewer_facing:
        self.__facing = Text3D.Facing.VIEWER_FACING
      else:
        self.__facing = Text3D.Facing.NO_FACING

    return self.__facing

  @facing.setter
  def facing(self, new_facing):
    if not isinstance(new_facing, Text3D.Facing):
      raise TypeError(default_type_error_message("facing",
                                                 new_facing,
                                                 Text3D.Facing))
    self.__facing = new_facing

  def _create_object(self):
    return ObjectID(Modelling().New3DText())

  def _get_text_direction(self):
    """Returns the direction of the 3D Text."""
    return Modelling().GetText3DDirection(self._lock.lock)

  def _save_text_direction(self, direction):
    """Saves the direction of the 3D Text."""
    Modelling().SetText3DDirection(self._lock.lock, *direction)

  def _get_text_up_direction(self):
    """Returns the up direction of the 3D Text."""
    return Modelling().GetText3DUpDirection(self._lock.lock)

  def _save_text_up_direction(self, up_direction):
    """Saves the up direction of the 3D Text"""
    Modelling().SetText3DUpDirection(self._lock.lock, *up_direction)

  def _get_text_is_always_visible(self):
    """Returns if this 3D text is always visible."""
    return Modelling().GetText3DIsAlwaysVisible(self._lock.lock)

  def _save_text_is_always_visible(self, always_visible):
    """Saves if this 3D text is always visible."""
    Modelling().SetText3DIsAlwaysVisible(self._lock.lock,
                                         always_visible)

  def _get_text_always_viewer_facing(self):
    """Returns if this 3D text is always viewer facing."""
    return Modelling().GetText3DIsAlwaysViewerFacing(self._lock.lock)

  def _save_text_always_viewer_facing(self, is_always_viewer_facing):
    """Saves if this 3D text is always viewer facing."""
    Modelling().SetText3DIsAlwaysViewerFacing(self._lock.lock,
                                              is_always_viewer_facing)

  def _get_text_is_camera_facing(self):
    """Returns if this text is always camera facing."""
    return Modelling().GetText3DIsCameraFacing(self._lock.lock)

  def _save_text_is_camera_facing(self, camera_facing):
    """Saves if this text is viewer facing."""
    Modelling().SetText3DIsCameraFacing(self._lock.lock,
                                        camera_facing)

class Marker(Topology, RotationMixin):
  """Provides a visual representation for a sign. This can
  be used to mark locations.

  Parameters
  ----------
  object_id : ObjectID
    Object id to use for this object. Default is None,
    indicating a new 2D text object should be created.

  lock_type : LockType
    The type of lock to place on the object once it has been
    created. Default is LockType.READWRITE which allows read
    and write access to the 2D text.

  Examples
  --------
  Create a red diamond-shaped Marker with white text at [1, 2, 3].

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Marker
  >>> project = Project()
  >>> with project.new("cad/diamond", Marker) as new_marker:
  >>>     new_marker.text = "White"
  >>>     new_marker.marker_colour = [255, 0, 0]
  >>>     new_marker.text_colour = [255, 255, 255]
  >>>     new_marker.shape = Marker.Shape.DIAMOND
  >>>     new_marker.location = [1, 2, 3]

  Rotate an existing marker by 45 degrees.

  >>> import math
  >>> from mapteksdk.project import Project
  >>> project = Project()
  >>> with project.edit("cad/diamond") as marker:
  >>>     marker.rotate_2d(math.radians(45))

  """

  class Shape(enum.IntEnum):
    """Different shapes or styles that a marker can be.

    A marker can have a custom shape where a Surface provides the shape.
    """

    A_FRAME_OPEN = 0
    """This shape is similar to a crime scene evidence marker or a cleaning
    in progress sign with the name of the marker on both surfaces.
    """

    DIAMOND = 1
    """An 8 facet diamond with the name appearing on all surfaces."""

    CUBE = 2
    """A cube with name on all the sides excluding top and bottom."""

    VERTICAL_SIGN = 3
    """A simple vertical billboard."""

    A_FRAME_SIGN = 4
    """A triangular prism billboard similar to A_FRAME_OPEN but solid and
       placed on a pole."""

    THREE_SIDED_SIGN = 5
    """A triangular prism billboard with the triangle in the XY plane"""

    HORIZONTAL_SIGN = 6
    """A billboard aligned with the XY plane."""

    ZEBRA_SCALE = 7
    """A striped scale bar."""

    CHECKERED_SCALE = 8
    """A scale bar in checkerboard pattern."""

    U_SCALE = 9
    """A U-Shaped scale bar in uniform colour."""

    PRONE_HUMAN = 10
    """A prone human shaped marker."""

    UPRIGHT_HUMAN = 11
    """An upright human shaped marker with a pedestal."""

    COMPASS_ROSE = 12
    """A 3D compass rose marker."""

    CUSTOM = 255
    """The marker can be a custom shape set by providing a Surface to
    Marker.SetCustomShape().
    """

  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    is_new = not object_id
    if is_new:
      object_id = ObjectID(Modelling().NewMarker())

    super().__init__(object_id, lock_type)
    self.__location = None
    self.__marker_colour = None
    self.__text_colour = None
    if is_new:
      self.location = None
      self.custom_shape_object = None
      self.marker_colour = None
      self.shape = Marker.Shape.A_FRAME_OPEN
      self.size = 1.0
      self.text = ""
      self.text_colour = [0, 0, 0, 255]
      self._rotation = Rotation()
    else:
      # If object already existed, populate the properties.
      self.get_properties()

  @classmethod
  def static_type(cls):
    """Return the type of marker as stored in a Project.

    This can be used for determining if the type of an object is a marker.

    """
    return Modelling().MarkerType()

  def _invalidate_properties(self):
    """Invalidates the properties."""
    self.__custom_shape_object = None
    self.__location = None
    self.marker_colour = None
    self.shape = None
    self.size = None
    self.text = None
    self.text_colour = None
    self._rotation = None

  def get_properties(self):
    """Load properties from the Project. This resets all properties back
    to their state when save() was last called, undoing any changes
    which have been made.

    """
    custom_shape_object = ObjectID(
      Modelling().GetMarkerGeometry(self._lock.lock))
    if custom_shape_object:
      self.custom_shape_object = custom_shape_object
    self.location = self._get_points()
    self.marker_colour = self._get_marker_colour()
    self.shape = Marker.Shape(Modelling().GetMarkerStyle(
      self._lock.lock))
    self.size = Modelling().GetAnnotationSize(
      self._lock.lock)
    self.text = self._get_text()
    self.text_colour = self._get_text_colour()
    self._rotation = self._get_rotation()

  @property
  def shape(self):
    """What shape the marker takes in a view. Must be from the
    Marker.Shape enum.

    """
    return self.__shape

  @shape.setter
  def shape(self, shape_type):
    self.__shape = shape_type
    if shape_type != Marker.Shape.CUSTOM:
      self.__custom_shape_object = None

  @property
  def custom_shape_object(self):
    """The ObjectID of the surface used for the custom marker shape.
    For best results the surface should be centred at [0, 0, 0] and should
    fit within a unit sphere centred at the origin.

    Notes
    -----
    Set this to None to remove the custom shape of the marker.

    Raises
    ------
    TypeError
      If set to a value which cannot be converted to an ObjectID.
    ValueError
      If set to an ObjectID which is not for a Surface.

    Examples
    --------
    Creating a tetrahedron shaped marker at [10, 10, 10] using a
    custom surface.

    >>> import math
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Marker, Surface
    >>> x = 1 / math.sqrt(2)
    >>> points = [[1, 0, -x], [-1, 0, -x], [0, 1, x], [0, -1, x]]
    >>> facets = [[2, 0, 1], [0, 3, 1], [2, 1, 3], [0, 2, 3]]
    >>> project = Project()
    >>> with project.new("surfaces/tetra_base", Surface) as new_tetrahedron:
    ...     new_tetrahedron.points = points
    ...     new_tetrahedron.facets = facets
    >>> with project.new("cad/tetra_marker", Marker) as new_marker:
    ...     new_marker.text = "tetrahedron"
    ...     new_marker.custom_shape_object = new_tetrahedron
    ...     new_marker.location = [10, 10, 10]

    """
    return self.__custom_shape_object

  @custom_shape_object.setter
  def custom_shape_object(self, surface):
    if surface is None:
      self.__custom_shape_object = None
      self.shape = Marker.Shape.A_FRAME_OPEN
      return
    # If we get a DataObject extract the object id.
    if isinstance(surface, DataObject):
      surface = surface.id
    if isinstance(surface, ObjectID):
      if surface.is_a(Surface):
        self.__custom_shape_object = surface
        self.shape = Marker.Shape.CUSTOM
        return
      # Given an object id which is not a surface.
      raise ValueError("Invalid value for custom_shape_object. "
                      f"It must be a Surface not a {surface.type_name}")
    raise TypeError(default_type_error_message("custom_shape_object",
                                               surface,
                                               Surface))

  @property
  def location(self):
    """Position of the marker as a point ([x,y,z])."""
    return self.__location

  @location.setter
  def location(self, location):
    if location is None:
      self.__location = np.array([0, 0, 0])
    else:
      # Ensure location stored as 1D array of float64 [x,y,z]
      self.__location = trim_pad_1d_array(location, 3, 0)

  @property
  def size(self):
    """The size of the marker in meters. The default is 1.0.

    For a marker with a custom shape, the actual size of the marker is
    the size of the custom shape object multiplied by this property.

    Raises
    ------
    ValueError
      If set to a value which cannot be converted to a float.
    TypeError
      If set to a type which cannot be converted to a float.

    """
    return self.__size

  @size.setter
  def size(self, value):
    if value is None:
      value = 1.0
    self.__size = float(value)

  @property
  def text_colour(self):
    """The colour of the text on the marker, represented as
    an RGBA colour. Colour may be set to a RGB, RGBA or
    greyscale colour.

    See Also
    --------
    marker_colour : The colour of the marker itself.

    """
    return self.__text_colour

  @text_colour.setter
  def text_colour(self, colour):
    if colour is None:
      self.__text_colour = [0, 0, 0, 255]
    else:
      self.__text_colour = convert_to_rgba(colour)

  @property
  def marker_colour(self):
    """The colour of the marker, represented as an RGBA colour
    (However when setting the colour you may use a greyscale
    or RGB colour).

    See Also
    --------
    text_colour : The colour of the text on the marker.

    Notes
    -----
    marker.marker_colour = None will set the marker colour
    to the default yellow ([255, 255, 0, 255]).

    Marker colour is currently ignored by markers with
    custom shapes, however it is intended to be implemented
    in the future.

    The alpha value of the marker colour is currently ignored,
    though may be supported in the future. It is recommended
    to either set marker colour to be an RGB colour or to set
    the alpha value to 255.

    """
    return self.__marker_colour

  @marker_colour.setter
  def marker_colour(self, colour):
    if colour is None:
      self.__marker_colour = np.array([255, 255, 0, 255])
    else:
      self.__marker_colour = convert_to_rgba(colour)

  def _get_rotation(self):
    quaternion = (ctypes.c_double * 4)()
    Modelling().GetMarkerRotation(self._lock.lock,
                                  ctypes.byref(quaternion))
    return Rotation(quaternion[0], quaternion[1],
                    quaternion[2], quaternion[3])

  def _get_marker_colour(self):
    """Get marker colour.

    Parameters
    ----------
    read_lock : ReadLock
      Active read lock for this object.

    Returns
    -------
    ndarray
      A 1D array of [R,G,B,A] uint8.

    Notes
    -----
    C API note: Specific to markers only.

    """
    col = (ctypes.c_uint8*4)
    buffer = col()
    Modelling().GetMarkerColour(self._lock.lock,
                                ctypes.byref(buffer))
    return np.array([buffer[0], buffer[1], buffer[2], buffer[3]])

  def save(self):
    if isinstance(self._lock, WriteLock):
      # convert location array to 2D to store
      self._save_points(trim_pad_2d_array(self.location, 1, 3, 0))
      self._save_annotation_text(self.text)

      if self.text_colour is not None:
        self._save_annotation_text_colour(self.text_colour)

      if self.size is not None:
        Modelling().SetAnnotationSize(self._lock.lock, self.size)

      # Marker specific C API calls:
      if self.marker_colour is not None:
        # Convert marker colour list property to format for MDF C API
        rgba_colour = (ctypes.c_uint8 * len(self.marker_colour)) \
                      (*self.marker_colour.astype(ctypes.c_uint8))
        Modelling().SetMarkerColour(self._lock.lock, rgba_colour)

      if self._rotation_cached:
        Modelling().SetMarkerRotation(self._lock.lock,
                                      ctypes.c_double(self._rotation.q0),
                                      ctypes.c_double(self._rotation.q1),
                                      ctypes.c_double(self._rotation.q2),
                                      ctypes.c_double(self._rotation.q3))

      if self.__custom_shape_object:
        Modelling().SetMarkerGeometry(
          self._lock.lock, self.__custom_shape_object.handle)
      elif self.shape is not None:
        Modelling().SetMarkerStyle(self._lock.lock,
                                   self.shape.value)

      self._reconcile_changes()
    else:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error
