"""Rotation support.

This module contains a mixin class which adds rotation functions to
inheriting objects. It is up to the inheriting object to apply the
rotation to the primitives and save the rotation.

"""

from .units import Axis
from ..internal.rotation import Rotation

class RotationMixin:
  """Mixin class designed to add rotation to a Topology object.

  Inheriting classes must implement _get_rotation which gets the
  rotation from the Project and they must provide their own code
  for saving the rotation to the Project.

  """
  __rotation = None

  @property
  def rotation(self):
    """Returns the magnitude of the rotation of the object in radians.

    This value is the total rotation of the object relative to its
    original position.

    Notes
    -----
    If the object has been rotated in multiple axes, this will not be the
    sum of the rotations performed. For example, a rotation
    of 90 degrees around the X axis, followed by a rotation of 90 degrees
    around the Y axis corresponds to a single rotation of 120 degrees so
    this function would return (2 * pi) / 3 radians.

    """
    return self._rotation.angle

  @property
  def _rotation(self):
    """The rotation of the object, represented as quaternions."""
    if self.__rotation is None:
      self.__rotation = self._get_rotation()
    return self.__rotation

  @_rotation.setter
  def _rotation(self, value):
    if value is not None and not isinstance(value, Rotation):
      raise TypeError("_rotation must be a rotation object")
    self.__rotation = value

  @property
  def _rotation_cached(self):
    """Returns true if the rotation has been cached.

    Returns
    -------
    bool
      True if rotation is cached, false otherwise.

    """
    return self.__rotation is not None

  @property
  def orientation(self):
    """The rotation of the object represented as Vulcan-style
    dip, plunge and bearing. This will return the tuple:
    (dip, plunge, bearing)

    The returned values are in radians.

    Notes
    -----
    This is a derived property. It is recalculated each time this
    is called.

    """
    return self._rotation.orientation

  def rotate(self, angle, axis):
    """Rotates the object by the specified angle around the specified
    axis.

    Parameters
    ----------
    angle : float
      The angle to rotate by in radians. Positive is clockwise,
      negative is anticlockwise (When looking in the direction of axis).
    axis : Axis
      The axis to rotate by.

    Examples
    --------
    Create a 2x2x2 dense block model which is rotated by pi / 4 radians
    (45 degrees) around the X axis.

    >>> import math
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import DenseBlockModel, Axis
    >>> project = Project()
    >>> with project.new("blockmodels/dense_rotated", DenseBlockModel(
    ...         x_res=1, y_res=1, z_res=1,
    ...         x_count=2, y_count=2, z_count=3)) as new_model:
    ...     new_model.rotate(math.pi / 4, Axis.X)

    If you want to specify the angle in degrees instead of radians, use
    the math.radians function. Additionally rotate can be called multiple
    times to rotate the block model in multiple axes. Both of these
    are shown in the below example. The resulting block model is
    rotated 32 degrees around the Y axis and 97 degrees around the Z
    axis.

    >>> import math
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import DenseBlockModel, Axis
    >>> project = Project()
    >>> with project.new("blockmodels/dense_rotated_degrees", DenseBlockModel(
    ...         x_res=1, y_res=1, z_res=1,
    ...         x_count=2, y_count=2, z_count=3)) as new_model:
    ...     new_model.rotate(math.radians(32), Axis.Y)
    ...     new_model.rotate(math.radians(97), Axis.Z)

    """
    if axis is Axis.X:
      rotation_axis = [1, 0, 0]
    elif axis is Axis.Y:
      rotation_axis = [0, 1, 0]
    elif axis is Axis.Z:
      rotation_axis = [0, 0, 1]
    else:
      raise ValueError(f"Invalid Axis: {axis}")
    self._rotation.rotate_by_axis(angle, rotation_axis)

  def rotate_2d(self, angle):
    """Rotates the object in two dimensions. This is equivalent
    to rotate with axis=Axis.Z

    Parameters
    ----------
    angle : float
      The angle to rotate by in radians. Positive is clockwise,
      negative is anticlockwise.

    """
    self.rotate(angle, Axis.Z)

  def set_rotation(self, angle, axis):
    """Overwrites the existing rotation with a rotation around the specified
    axis by the specified angle.

    This is useful for resetting the rotation to a known point.

    Parameters
    ----------
    angle : float
      Angle to set the rotation to in radians. Positive is clockwise,
      negative is anticlockwise.
    axis  : Axis
      Axis to rotate around.

    """
    rotation_axis = None
    if axis is Axis.X:
      rotation_axis = [1, 0, 0]
    elif axis is Axis.Y:
      rotation_axis = [0, 1, 0]
    elif axis is Axis.Z:
      rotation_axis = [0, 0, 1]
    else:
      raise ValueError(f"Invalid Axis: {axis}")

    self.__rotation = Rotation.axis_rotation(angle, rotation_axis)

  def set_rotation_2d(self, angle):
    """Overwrite the existing rotation with a simple 2d rotation.

    Parameters
    ----------
    angle : float
      Angle to set the rotation to in radians.

    """
    self.set_rotation(angle, Axis.Z)

  def set_orientation(self, dip, plunge, bearing):
    """Overwrite the existing rotation with a rotation defined by the
    specified dip, plunge and bearing.

    An orientation of (dip, plunge, bearing) radians is equivalent to rotating
    the model -dip radians around the X axis, -plunge radians around the Y axis
    and -(bearing - pi / 2) radians around the Z axis.

    Parameters
    ----------
    dip : float
      Relative rotation of the Y axis around the X axis in radians.
      This should be between -pi and pi (inclusive).
    plunge : float
      Relative rotation of the X axis around the Y axis in radians.
      This should be between -pi / 2 and pi / 2 (exclusive).
    bearing : float
      Absolute bearing of the X axis around the Z axis in radians.
      This should be between -pi and pi (inclusive).

    Raises
    ------
    TypeError
      If dip, plunge or bearing are not numbers.

    Examples
    --------
    Set orientation of a new 3x3x3 block model to be plunge = 45 degrees,
    dip = 30 degrees and bearing = -50 degrees

    >>> import math
    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import DenseBlockModel
    >>> project = Project()
    >>> with project.new("blockmodels/model_1", DenseBlockModel(
    ...         x_res=1, y_res=1, z_res=1,
    ...         x_count=3, y_count=3, z_count=3)) as new_model:
    >>>     new_model.set_orientation(math.radians(45),
    ...                               math.radians(30),
    ...                               math.radians(-50))

    Copy the rotation from one block model to another. Requires two
    block models.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import DenseBlockModel
    >>> project = Project()
    >>> with project.edit("blockmodels/model_1") as model_1:
    ...     with project.edit("blockmodels/model_2") as model_2:
    ...         model_2.set_orientation(*model_1.orientation)

    """
    self.__rotation = Rotation.create_from_orientation(dip, plunge, bearing)

  def _get_rotation(self):
    """Returns the rotation from the Project. This method must
    be provided by the class this is being mixed into.

    Returns
    -------
    Rotation
      Rotation of the object.

    """
    raise NotImplementedError
