"""Container data types.

Containers are objects which hold other objects. They are used to organise
data into a hierarchical structure. A container may have children objects,
each of which has a name. Containers may contain other containers, allowing
for an arbitrarily nested structure.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import logging

from ..capi import DataEngine, Modelling
from ..internal.lock import LockType
from .base import DataObject
from .objectid import ObjectID
from .errors import CannotSaveInReadOnlyModeError
# pylint: disable=too-many-instance-attributes

log = logging.getLogger("mapteksdk.data")

class Container(DataObject):
  """Plain container object that nests other objects.

  It is used to organise data in a hierarchical structure.
  It is similar to a directory or folder concept in file systems.
  This type of container can not be viewed. If you are looking to create a
  container then you likely want to create a VisualContainer.

  Parameters
  ----------
  object_id : ObjectID
    The ID of the object to open. If None make a new container.

  lock_type : LockType
    The type of lock to place on the object. Default is Read.

  """
  # pylint: disable=too-few-public-methods
  def __init__(self, object_id=None, lock_type=LockType.READ):
    if not object_id:
      object_id = self._create_object()

    super().__init__(object_id, lock_type)

  def _create_object(self):
    """Creates a new instance of this object in the project."""
    raise NotImplementedError(
      "Creating a new Container isn't supported.\n"
      "Consider if a VisualContainer() would suit your needs.")

  @classmethod
  def static_type(cls):
    """Return the type of container as stored in a Project.

    This can be used for determining if the type of an object is a container.

    """
    return DataEngine().ContainerType()

  def save(self):
    """Saves the object to the Project."""


class VisualContainer(Container):
  """A container whose content is intended to be spatial in nature and can be
  viewed.

  This is the typical container object that users create and see in the
  explorer.

  The container can be added to a view. Any applicable children in the
  container will also appear in the view.

  """
  # pylint: disable=too-few-public-methods
  def _create_object(self):
    return ObjectID(Modelling().NewVisualContainer())

  @classmethod
  def static_type(cls):
    """Return the type of visual container as stored in a Project.

    This can be used for determining if the type of an object is a visual
    container.

    """
    return Modelling().VisualContainerType()

  def save(self):
    if self.lock_type is LockType.READ:
      error = CannotSaveInReadOnlyModeError()
      log.error(error)
      raise error

class StandardContainer(VisualContainer):
  """Class for standard containers (such as cad and surfaces)."""
  def _create_object(self):
    return ObjectID(Modelling().NewStandardContainer())

  @classmethod
  def static_type(cls):
    """Return the type of standard container as stored in a Project."""
    return Modelling().StandardContainerType()

class ChildView:
  """Provides a view onto the children of a container.

  Iterating over the view will provide both the name and the ID of the
  objects like the items() function.
  The container object does not need to remain open to access data in this
  view. It has cached the data itself.
  Use Project.get_children() to get a view of the children of a container.

  Parameters
  ----------
  children : list
    List of children to be viewed in the form name, ID.

  """

  def __init__(self, children):
    self.children = children

  def names(self):
    """Returns the names of the children.

    Returns
    -------
    list
      List of names of children.

    """
    return [name for name, _ in self.children]

  def ids(self):
    """Returns the object IDs of the children.

    Returns
    -------
    list
      List of ObjectIDs of the children.

    """
    return [object_id for _, object_id in self.children]

  def items(self):
    """Return the (name, object ID) pair for each child.

    Returns
    -------
    list
      List of tuples in the form (name, object ID).

    """
    return self.children

  def __getitem__(self, index):
    return self.children[index]

  def __len__(self):
    return len(self.children)

  def __iter__(self):
    return iter(self.children)
