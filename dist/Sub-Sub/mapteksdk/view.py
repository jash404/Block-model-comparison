"""Interaction with a view in an applicable Maptek application.

The first step is opening a new view which returns a view controller for the
new view. From there you can control the view by adding/removing objects,
hiding/showing objects and querying what objects are in the view.

>>> from mapteksdk.project import Project
>>> import mapteksdk.operations as operations
>>> project = Project()
>>> view = operations.open_new_view()
>>> view.add_objects([project.find_object('/cad')])
"""

###############################################################################
#
# (C) Copyright 2021, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes
import typing

from mapteksdk.capi.viewer import Viewer, ViewerErrorCodes
from mapteksdk.data import ObjectID
from mapteksdk.internal.comms import Message, Request


class ViewNoLongerExists(RuntimeError):
  """Exception for when a view is expected but it no longer exists.

  The most common occurrence for this exception is when the view has been
  closed.
  """


class ObjectFilter:
  """Describes different ways to filter what objects are returned by
  a ViewController."""

  DEFAULT = 0
  """Default - return all object except transient and background objects but
  ignoring visibility, and selection

  Transient objects are objects that are in the view for previewing an operation
  or providing additional clarity while a tool in the application is running.
  """

  VISIBLE_ONLY = 1 << 0
  """Only return objects that are visible in the view."""

  HIDDEN_ONLY = 1 << 1
  """Only return objects that are hidden in the view."""

  SELECTED_ONLY = 1 << 2
  """Only return objects that are selected and are in the view."""


class ViewController:
  """Provides access onto a specified view.

  This allows for objects to be added/removed/shown and hidden.
  """
  def __init__(self, view_id: ObjectID):
    # In PointStudio 2020.1, there are no safe-guards in place to confirm that
    # the given view_id is infact an ID for a view and it exists. This will
    # simply crash.
    maximum_length = 256
    server_name = ctypes.create_string_buffer(maximum_length)
    Viewer().GetServerName(
      view_id.native_handle, server_name, maximum_length)
    if not server_name.value:
      error_message = Viewer().ErrorMessage()
      if Viewer().ErrorCode() == ViewerErrorCodes.VIEW_NO_LONGER_EXISTS:
        raise ViewNoLongerExists(error_message)
      raise ValueError(error_message)

    self.server_name = server_name.value.decode('utf-8')

    # Like the DataObject class provide the ability to query the ID of the
    # view controller.
    self.id = view_id

  def __repr__(self):
    return type(self).__name__  + f'({self.id}, "{self.server_name}")'

  @property
  def window_title(self):
    """Return the window title (the name of the view) as seen in the application."""

    class WindowTitle(Request):
      """Defines message for querying what window title of a view."""

      class Response(Message):
        """The response containing the window title."""
        title: str

      message_name: typing.ClassVar[str] = 'WindowTitle'
      response_type = Response

      view_name: str

    request = WindowTitle()
    request.view_name = self.server_name

    # The viewer server doesn't know its title as its the uiServer that
    # is responsible for that.
    response = request.send(destination='uiServer')
    return response.title

  def close(self):
    """Close the view.

    Avoid closing views that you didn't open, as such avoid closing the view
    if it came from a non-empty active view. This is because you may close a
    view that was being used by another tool in the application.

    A case where closing the view is a good idea is if the script creates one
    and is interactive and long-running. Think about when the script is done if
    the person running the script would miss seeing what is in the view, would
    find it a hassle to have to close it themself or if the content is no
    longer relevant after the script has exited.

    Examples
    --------
    Opens a new view then closes it.

    >>> import mapteksdk.operations as operations
    >>> project = Project()
    >>> view = operations.open_new_view()
    >>> input('Press enter to finish')
    >>> view.close()
    """
    class DestroyView(Message):
      """This message destroys (closes) the view."""
      message_name: typing.ClassVar[str] = 'DestroyView'

    DestroyView().send(destination=self.server_name)

  def objects_in_view(self, object_filter=ObjectFilter.DEFAULT):
    """Return a list of objects that are in the the view.

    Parameters
    ----------
    object_filter : ObjectFilter
      A filter that limits what objects are returned.

    Returns
    -------
    list
      A list of object IDs of objects that are in the view that meet the filter
      criteria.
    """

    # TODO: Support filtering by object types.
    # Essentially support user providing list of type index or classes with
    # static_type function that returns a type index or a mix of both.
    #
    # This should ideally handle values of the form: [Surface, Polygon,
    # Polyline]
    # However receiving a message containing it would be problemantic as its
    # not easy to map it back.

    class ObjectsInView(Request):
      """Defines message for querying what objects are in a view."""
      class Response(Message):
        """The response back with what objects are in a view."""
        objects: typing.List[ObjectID]

      message_name: typing.ClassVar[str] = 'ObjectsInView'
      response_type = Response

      object_filter: ctypes.c_uint32  # ObjectFilter
      type_filter: typing.List[ctypes.c_uint16]

    request = ObjectsInView()
    request.object_filter = object_filter
    request.type_filter = []

    response = request.send(destination=self.server_name)
    return response.objects

  def add_objects(self, objects):
    """Adds the provided objects to the view.

    Parameters
    ----------
    objects : list
      A list of IDs of objects to add to the view.
    """

    class AddObjects(Message):
      """Message for the viewer for adding objects to it."""
      message_name: typing.ClassVar[str] = 'AddObjects'

      objects: typing.List[ObjectID]
      drop_point: (ctypes.c_double, ctypes.c_double) = (
        float('NaN'), float('NaN'))

    request = AddObjects()
    request.objects = objects
    request.send(destination=self.server_name)

  def remove_objects(self, objects):
    """Removes the provided objects from the view if present.

    Removing objects not in the view will do nothing.

    Parameters
    ----------
    objects : list
      A list of IDs of objects to remove from the view.
    """

    class RemoveObjects(Message):
      """Message for the viewer for removing objects from it."""
      message_name: typing.ClassVar[str] = 'RemoveObjects'

      objects: typing.List[ObjectID]

    request = RemoveObjects()
    request.objects = objects
    request.send(destination=self.server_name)

  def hide_objects(self, objects):
    """Hide the provided objects in the view.

    Hiding objects not in the view will do nothing.

    Parameters
    ----------
    objects : list
      A list of IDs of objects to hide.
    """

    if Viewer().version >= (1, 1):
      class HideObjects(Message):
        """Message for the viewer for hiding objects."""
        message_name: typing.ClassVar[str] = 'HideObjects'

        objects: typing.List[ObjectID]
        mouse: (ctypes.c_double, ctypes.c_double) = (
          float('NaN'), float('NaN'))
    else:
      class HideObjects(Message):
        """Message for the viewer for hiding objects."""
        message_name: typing.ClassVar[str] = 'HideObjects'

        objects: typing.List[ObjectID]

    request = HideObjects()
    request.objects = objects
    request.send(destination=self.server_name)

  def show_objects(self, objects):
    """Show the provided objects in the view (if hidden).

    If the objects are not in the view then they won't be shown.

    Parameters
    ----------
    objects : list
      A list of IDs of objects to hide.
    """

    class ShowObjects(Message):
      """Message for the viewer for showing objects."""
      message_name: typing.ClassVar[str] = 'ShowObjects'

      objects: typing.List[ObjectID]

    request = ShowObjects()
    request.objects = objects
    request.send(destination=self.server_name)

  @property
  def background_colour(self):
    """tuple: The background colour of the view window as a tuple
    containing red, green, blue, alpha values of the colour.
    Each value is an integer in the range [0, 255].

    When changing the background colour, the alpha is optional and
    the colour may be given as either a tuple, list or ndarray.
    """

    class RequestBackgroundColour(Request):
      """Query background colour of a view window."""
      class Response(Message):
        colour: ctypes.c_uint32

      message_name: typing.ClassVar[str] = 'BackgroundColour'
      response_type: typing.ClassVar[type] = Response

    request = RequestBackgroundColour()
    response = request.send(destination=self.server_name)

    alpha = (response.colour >> 24) & 0xFF
    blue = (response.colour >> 16) & 0xFF
    green = (response.colour >> 8) & 0xFF
    red = response.colour & 0xFF

    return (red, green, blue, alpha)

  @background_colour.setter
  def background_colour(self, new_colour):
    # This could be useful when detecting if really dark coloured objects are
    # in the view and switching the background so it is lighter colour to
    # give contrast between foreground and background.
    #
    # It could also be possible to implement a night-light like application
    # which reduces specific colours used in the background as the time of day
    # changes.

    class SetBackgroundColour(Message):
      """Sets the background colour of a view window."""
      message_name: typing.ClassVar[str] = 'SetBackgroundColour'

      colour: ctypes.c_uint32

    red, green, blue = new_colour[:3]
    if len(new_colour) == 4:
      alpha = new_colour[3]
    else:
      alpha = 255

    # Colour encoded as a 32-bit integer. This more than likely needs
    # to be packaged up as part of the comms module.
    colour = (alpha << 24) | (blue << 16) | (green << 8) | (red << 0)

    message = SetBackgroundColour()
    message.colour = colour
    message.send(destination=self.server_name)

  def _start_camera_transition(self, transition_time):
    """Enables the camera to smoothly transition to a new state

    transition_time : float
      The time the transition should last in seconds.
    """
    class StartTransition(Message):
      """Tells the viewer that it will be transitioning the camera to a new
      location.
      """
      message_name: typing.ClassVar[str] = 'StartTransition'

      axes_transition_mode: ctypes.c_int32 = 2
      transition_time: ctypes.c_double

    message = StartTransition()
    message.transition_time = transition_time
    message.send(destination=self.server_name)
