"""Rotation represented using quaternions.

This module provides a simple implementation of rotations using
quaternions. Currently it only contains the functionality required
for rotating markers.

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

import math

import numpy as np

from .util import default_type_error_message

class Rotation:
  """Class which represents rotations.

  Rotations are represented as quaternions - four floating point
  numbers Q0, Q1, Q2 and Q3.

  Parameters
  ----------
  q0 : float
    First element of the rotation. Q0 = cos(angle / 2).
    Default value is 1.
  q1 : float
    Second element of the rotation. Q1 = sin(angle / 2) * AxisX.
    Default value is 0.
  q2 : float
    Third element of the rotation. Q2 = sin(angle / 2) * AxisY.
    Default value is 0.
  q3 : float
    Fourth element of the rotation. Q3 = sin(angle / 2) * AxisZ.
    Default value is 0.

  Notes
  -----
  Quaternions are a way for representing rotations which is very efficient
  for computers. It is recommended to use the functions in this class instead
  of directly working with quaternions.

  """

  def __init__(self, q0=1, q1=0, q2=0, q3=0):
    self.q0 = q0
    self.q1 = q1
    self.q2 = q2
    self.q3 = q3

  @staticmethod
  def axis_rotation(angle, axis):
    """Returns a quaternion representing a rotation of angle
    radians around the specified axis.

    Parameters
    ----------
    angle : float
      The radians to rotate by. Positive indicates clockwise,
      negative indicates anticlockwise.(When looking in the
      direction of axis)
    axis : list
      A list containing three numbers representing the axis
      to rotate around. This is normalized before any calculations.

    Returns
    -------
    Rotation
      Rotation representing a rotation by the specified angle around the
      specified axis.

    Raises
    ------
    ValueError
      If axis does not have a length of 3.

    Notes
    -----
    Generally axis will either be [0, 0, 1], [0, 1, 0] or [0, 0, 1]
    representing the x, y and z axes respectively.

    """
    if len(axis) != 3:
      raise ValueError(f"Invalid Axis : {axis}.")

    # Normalize the axis.
    # If the axis is not normalized odd behaviours can be observed.
    # For example four rotations of 90 degrees not being
    # equivalent to one rotation of 360 degrees.
    axis_length = math.sqrt(axis[0] * axis[0]
                            + axis[1] * axis[1]
                            + axis[2] * axis[2])
    if not math.isclose(axis_length, 1):
      axis[0] = axis[0] / axis_length
      axis[1] = axis[1] / axis_length
      axis[2] = axis[2] / axis_length

    sin_scalar = math.sin(angle / 2)
    result = Rotation()
    result.q0 = math.cos(angle / 2)
    result.q1 = sin_scalar * axis[0]
    result.q2 = sin_scalar * axis[1]
    result.q3 = sin_scalar * axis[2]

    return result

  @staticmethod
  def create_from_orientation(dip, plunge, bearing):
    """Converts dip, plunge and bearing into a Rotation object.

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

    Returns
    -------
    Rotation
      Rotation equivalent to the passed dip, plunge and bearing.

    """
    # pylint: disable=too-many-locals;reason=The extra locals make it easier.
    # Based on code in: mdf/src/vulcan/api/Orientation.C
    dq0 = math.cos(-dip / 2)
    dq1 = math.sin(-dip / 2)

    pq0 = math.cos(-plunge / 2)
    pq2 = math.sin(-plunge / 2)

    bq0 = math.cos(-(bearing - (math.pi / 2)) / 2)
    bq3 = math.sin(-(bearing - (math.pi / 2)) / 2)

    dpq0 = pq0 * dq0
    dpq1 = pq0 * dq1
    dpq2 = pq2 * dq0
    dpq3 = -pq2 * dq1

    q0 = bq0 * dpq0 - bq3 * dpq3
    q1 = bq0 * dpq1 - bq3 * dpq2
    q2 = bq0 * dpq2 + bq3 * dpq1
    q3 = bq0 * dpq3 + bq3 * dpq0

    result = Rotation(q0, q1, q2, q3)
    result.normalize()

    return result

  def normalize(self):
    """Normalizes the quaternion if needed."""
    length = self.q0 * self.q0 + self.q1 * self.q1
    length += self.q2 * self.q2 + self.q3 * self.q3
    length = math.sqrt(length)

    if not math.isclose(length, 1):
      # If the length is close to 1, don't bother normalizing.
      self.q0 = self.q0 / length
      self.q1 = self.q1 / length
      self.q2 = self.q2 / length
      self.q3 = self.q3 / length

  def invert_rotation(self):
    """Returns a Rotation which undoes this rotation."""
    return Rotation(self.q0, -self.q1, -self.q2, -self.q3)

  @property
  def quaternion(self):
    """Returns the quaternion representing this rotation as a tuple.

    Returns
    -------
    tuple
      The tuple (q0, q1, q2, q3).

    """
    return (self.q0, self.q1, self.q2, self.q3)

  @property
  def orientation(self):
    """Returns the orientation representing this rotation as a tuple.

    Note that unlike quaternion, each time this function is called the
    orientation is recalculated from the quaternions.

    Returns
    -------
    tuple
      The tuple (dip, plunge, bearing)

    """
    # Code based on mdf/src/vulcan/api/Orientation.C
    x_axis = np.array([1, 0, 0])
    y_axis = np.array([0, 1, 0])
    z_axis = np.array([0, 0, 1])

    x_axis_dash_dash = self.rotate_vector(x_axis)
    x_axis_dash_dash = x_axis_dash_dash / np.linalg.norm(x_axis_dash_dash)
    y_axis_dash_dash = self.rotate_vector(y_axis)
    y_axis_dash_dash = y_axis_dash_dash / np.linalg.norm(y_axis_dash_dash)

    y_axis_dash = np.cross(z_axis, x_axis_dash_dash)
    y_length = np.linalg.norm(y_axis_dash)
    if y_length != 0:
      y_axis_dash = y_axis_dash / np.linalg.norm(y_axis_dash)

    x_axis_dash = np.cross(y_axis_dash, z_axis)
    x_length = np.linalg.norm(x_axis_dash)
    if x_length != 0:
      x_axis_dash = x_axis_dash / np.linalg.norm(x_axis_dash)

    # The dip is the rotation angle which takes the transformed X axis back
    # to the XY plane.
    dip = np.arccos(np.clip(np.dot(y_axis_dash_dash, y_axis_dash), -1.0, 1.0))
    # Clip ensures the value is between -1 and 1 so the result will not
    # be NaN.

    # Adjust the sign based on the z component.
    if -y_axis_dash_dash[2] < 0:
      dip = -abs(dip)
    elif -y_axis_dash_dash[2] > 0:
      dip = abs(dip)
    else:
      dip = 0

    # Plunge is the rotation angle which takes the transformed X axis
    # back to the XY plane.
    plunge = np.arccos(np.clip(np.dot(x_axis_dash_dash,
                                      x_axis_dash), -1.0, 1.0))

    # Adjust the sign.
    if x_axis_dash_dash[2] < 0:
      plunge = -abs(plunge)
    elif x_axis_dash_dash[2] > 0:
      plunge = abs(plunge)
    else:
      plunge = 0

    # Bearing is the final Z axis rotation angle that aligns the
    # twice-transformed X axis back to the world axis.
    bearing = math.atan2(x_axis_dash[0], x_axis_dash[1])

    return [dip, plunge, bearing]

  @property
  def angle(self):
    """Returns the angle of the rotation. If multiple rotations have
    been performed, this is the magnitude as if only one rotation had been
    performed to get the rotation to its current state.

    Returns
    -------
    double
      The magnitude of the the rotation in radians.

    """
    return 2 * math.acos(self.q0)

  def rotate(self, rhs):
    """Rotates this rotation by another rotation.

    Parameters
    ----------
    rhs : Rotation
      Rotation to apply to this Rotation.

    """
    lq0, lq1, lq2, lq3 = self.q0, self.q1, self.q2, self.q3
    rq0, rq1, rq2, rq3 = rhs.q0, rhs.q1, rhs.q2, rhs.q3

    new_q0 = lq0 * rq0 - (lq1 * rq1 + lq2 * rq2 + lq3 * rq3)
    new_q1 = (lq0 * rq1 + lq1 * rq0) + (lq2 * rq3 - lq3 * rq2)
    new_q2 = (lq0 * rq2 + lq2 * rq0) + (lq3 * rq1 - lq1 * rq3)
    new_q3 = (lq0 * rq3 + lq3 * rq0) + (lq1 * rq2 - lq2 * rq1)

    self.q0 = new_q0
    self.q1 = new_q1
    self.q2 = new_q2
    self.q3 = new_q3

    self.normalize()

  def rotate_by_axis(self, angle, axis):
    """Rotates by angle radians around the specified axis.

    Parameters
    ----------
    angle : float
      The radians to rotate by. Positive indicates clockwise,
      negative indicates anticlockwise (When looking in the
      direction of axis).
    axis : list
      List of length 3 representing Axis to rotate around.

    Notes
    ----
    Generally axis will either be [1, 0, 0], [0, 1, 0] or [0, 0, 1]
    representing the x, y and z axes respectively.

    """
    quaternion = self.axis_rotation(angle, axis)

    self.rotate(quaternion)

  def __rotation_helper(self, x, y, z):
    """Helper used to rotate things used by rotate_vector and
    rotate_vectors.

    Parameters
    ----------
    x : any
      X component(s) of the thing to rotate. Must support addition, subtraction
      and multiplication.
    y : any
      Y component(s) of the thing to rotate. Must support addition, subtraction
      and multiplication.
    z : any
      Z component(s) of the thing to rotate. Must support addition, subtraction
      and multiplication.

    Returns
    -------
    tuple
      Tuple containing x, y and z rotated by this rotation.

    """
    q0 = self.q1 * x + self.q2 * y + self.q3 * z
    q1 = self.q0 * x + (self.q2 * z - self.q3 * y)
    q2 = self.q0 * y + (self.q3 * x - self.q1 * z)
    q3 = self.q0 * z + (self.q1 * y - self.q2 * x)

    x = q0 * self.q1 + q1 * self.q0 - q2 * self.q3 + q3 * self.q2
    y = q0 * self.q2 + q1 * self.q3 + q2 * self.q0 - q3 * self.q1
    z = q0 * self.q3 - q1 * self.q2 + q2 * self.q1 + q3 * self.q0

    return x, y, z


  def rotate_vector(self, vector):
    """Rotates a vector by this Rotation and returns the rotated vector.

    This is not normalized so may need to be normalized before use.

    Parameters
    ----------
    vector : array_like
      Vector to rotate.

    Returns
    -------
    numpy.ndarray
      The rotated vector.

    Raises
    ------
    ValueError
      If vector does not have three components.

    """
    if len(vector) != 3:
      raise ValueError("Vectors must have three components.")
    x = vector[0]
    y = vector[1]
    z = vector[2]

    return np.array(self.__rotation_helper(x, y, z))

  def rotate_vectors(self, vectors):
    """As rotate_vector, however it can rotate multiple vectors at the same
    time.

    Parameters
    ----------
    vectors : ndarray
      A numpy array of shape (n, 3) consisting of n vectors to rotate about
      the origin

    Returns
    -------
    np.ndarray
      vectors rotated by this rotation.

    Raises
    ------
    TypeError
      If vectors is not an ndarray.
    ValueError
      If vectors is not the correct shape.

    """
    if not isinstance(vectors, np.ndarray):
      raise TypeError(default_type_error_message("vectors",
                                                 vectors,
                                                 np.ndarray))

    if len(vectors.shape) != 2:
      raise ValueError("vectors must have 2 dimensions, not: "
                       f"{len(vectors.shape)}.")

    if vectors.shape[1] != 3:
      raise ValueError("Vectors must have three components, not: "
                       f"{vectors.shape[1]}.")

    x = vectors[:, 0]
    y = vectors[:, 1]
    z = vectors[:, 2]

    return np.column_stack(self.__rotation_helper(x, y, z))
