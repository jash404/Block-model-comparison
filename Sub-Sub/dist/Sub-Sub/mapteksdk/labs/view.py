"""Manipulation of views.

This module contains a view controller class with additional functionality
which is still a work-in-progress. It is being provided through labs for
earlier feedback.

To use the labs version of the ViewController, you can:

>>> from mapteksdk.project import Project
>>> from mapteksdk.labs.view import enable_labs_on_view_controller
>>> import mapteksdk.operations as operations
>>> project = Project()
>>> view = operations.open_new_view()
>>> enable_labs_on_view_controller(view)
>>> camera = view.camera()
>>> print(camera.origin, camera.artificial_scale)
"""
###############################################################################
#
# (C) Copyright 2021, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import typing

from mapteksdk.view import ViewController
from mapteksdk.internal.comms import Message, InlineMessage, Request


class RigidTransform(InlineMessage):
  """Represents a rigid body (6 degree of freedom) transformation in 3D space.
  """
  rotation: (ctypes.c_double, ctypes.c_double, ctypes.c_double,
             ctypes.c_double)
  translation: (ctypes.c_double, ctypes.c_double, ctypes.c_double)


class Camera(Message):
  """Response back for the Camera request."""
  origin: (ctypes.c_double, ctypes.c_double, ctypes.c_double)
  artificial_scale: (ctypes.c_double, ctypes.c_double, ctypes.c_double)
  rigid_transform: RigidTransform
  angular_field_of_view: ctypes.c_double
  linear_field_of_view: ctypes.c_double
  perspective_factor: ctypes.c_double


class LabsViewController(ViewController):
  """Provides access onto a specified view, with additional work-in progress
  features.
  """

  def camera(self):
    """Return the current camera (i.e position/orientation) for the view."""

    class RequestCamera(Request):
      """Requests the current camera for a view."""
      message_name: typing.ClassVar[str] = 'Camera'
      response_type = Camera

    request = RequestCamera()

    # This returns the message type. We need to decide if we want to have our
    # own type or at least convert this to a named tuple.
    return request.send(destination=self.server_name)

  def set_camera(self, new_camera, smoothly=True):
    """Change the current camera of the view.

    Parameters
    ----------
    new_camera : Camera
      The new camera to use for the view.
    smoothly : bool
      Whether the camera should smoothly transition to the new state, or if it
      should change instantaneously.
    """

    class SetCamera(Message):
      """A message for a viewerServer to change its camera."""
      message_name: typing.ClassVar[str] = 'SetCamera'

      origin: (ctypes.c_double, ctypes.c_double, ctypes.c_double)
      artificial_scale: (ctypes.c_double, ctypes.c_double, ctypes.c_double)
      rigid_transform: RigidTransform
      angular_field_of_view: ctypes.c_double
      linear_field_of_view: ctypes.c_double
      perspective_factor: ctypes.c_float
      prevent_automove_on_future_add_objects: bool

    if smoothly:
      self._start_camera_transition(transition_time=2.0)

    message = SetCamera()
    message.origin = new_camera.origin
    message.artificial_scale = new_camera.artificial_scale
    message.rigid_transform = new_camera.rigid_transform
    message.angular_field_of_view = new_camera.angular_field_of_view
    message.linear_field_of_view = new_camera.linear_field_of_view
    message.perspective_factor = new_camera.perspective_factor
    message.prevent_automove_on_future_add_objects = True
    message.send(destination=self.server_name)

  def change_camera(self, change_function, smoothly=True):
    """Change a part of the camera.

    The part that is changed is based on what the change_function does.
    It is called with the current state of the camera and should make the
    appropriate modifications to it

    Parameters
    ----------
    change_function : callable
      A function that will be passed the current state of the camera and
      should modify it and return the modified version back.
    smoothly : bool
      Whether the camera should smoothly transition to the new state, or if it
      should change instantaneously.
    """
    current_camera = self.camera()
    new_camera = change_function(current_camera)
    return self.set_camera(new_camera, smoothly)


def enable_labs_on_view_controller(view_controller) -> LabsViewController:
  """Enables the labs functionality on the given view controller.

  Returns
  -------
  LabsViewController
    The provided view controller with labs functionality enabled.

  Raises
  ------
  TypeError
    If the labs functionality has already been enabled.
  TypeError
    If the object is not a view controller.
  """
  if isinstance(view_controller, ViewController):
    view_controller.__class__ = LabsViewController

    # Returning the view controller means that writing the code is slightly
    # more functional and can benefit IDEs like Visual Studio Code as it
    # can pick-up what type the controller is.
    #
    # In this case you would write:
    #   view = enable_labs_on_view_controller(view)
    # Alternatively, you can provide explicit type information in your
    # code by writing:
    #    enable_labs_on_view_controller(view)
    #    view: LabsViewController
    # This will often have a better success rate.
    return view_controller

  if isinstance(view_controller, LabsViewController):
    # The given view controller already has the labs functionality enabled.
    # There is nothing more to do here.
    return view_controller

  raise TypeError('The provided object was not a view controller')
