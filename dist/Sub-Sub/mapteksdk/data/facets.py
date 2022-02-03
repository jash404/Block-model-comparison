"""Facet data types.

This contains objects which use facet primitives. Currently there is only one
such data type (Surface).

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import logging

from ..capi import Modelling
from ..internal.lock import LockType
from .base import Topology
from .containers import VisualContainer, StandardContainer
from .errors import (ReadOnlyError, RegistrationTypeNotSupportedError,
                     AlreadyAssociatedError, NonOrphanRasterError)
from .images import (Raster, RasterRegistration, RasterRegistrationMultiPoint,
                     RasterRegistrationTwoPoint)
from .objectid import ObjectID
from .primitives import PointProperties, EdgeProperties, FacetProperties

# pylint: disable=too-many-lines
# pylint: disable=too-many-instance-attributes
log = logging.getLogger("mapteksdk.data")

class Surface(PointProperties, EdgeProperties, FacetProperties, Topology):
  """Surfaces are represented by triangular facets defined by three points.
  This means a square or rectangle is represented by two facets, a cube
  is represented as twelve facets (six squares, each made of two facets).
  More complicated surfaces may require hundreds, thousands or more facets
  to be represented.

  Defining a surface requires the points and the facets to be defined - the
  edges are automatically populated when the object is saved. A facet
  is a three element long list where each element is the index of a point,
  for example the facet [0, 1, 4] would indicate the facet is the triangle
  between points 0, 1 and 4.

  Notes
  -----
  The edges of a facet network are derived from the points and
  facets and cannot be directly set.

  Examples
  --------
  Creating a pyramid with a square base.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.data import Surface
  >>> project = Project()
  >>> with project.new("surfaces/pyramid", Surface) as new_pyramid:
  >>>     new_pyramid.points = [[0, 0, 0], [2, 0, 0], [2, 2, 0],
  >>>                           [0, 2, 0], [1, 1, 1]]
  >>>     new_pyramid.facets = [[0, 1, 2], [0, 2, 3], [0, 1, 4], [1, 2, 4],
  >>>                           [2, 3, 4], [3, 0, 4]]

  """
  # pylint: disable=too-many-instance-attributes
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    is_new = not object_id
    if is_new:
      object_id = ObjectID(Modelling().NewFacetNetwork())
      assert object_id

    super().__init__(object_id, lock_type)

    if not is_new:
      self._invalidate_properties()

  @classmethod
  def static_type(cls):
    """Return the type of surface as stored in a Project.

    This can be used for determining if the type of an object is a surface.

    """
    return Modelling().FacetNetworkType()

  def associate_raster(self, raster, registration, desired_index=1):
    """Associates a raster to the surface using the specified registration.

    The RasterRegistration object passed to registration defines how the
    raster pixels are draped onto the surface.

    This edits both the surface and the raster so both objects must be
    open for read/write to call this function.

    Parameters
    ----------
    raster : Raster
      An open raster to associate with the surface.
    registration : RasterRegistration
      Registration object to use to associate the raster with the surface.
      This will be assigned to the raster's registration property.
    desired_index : int
      The desired raster index for the raster. Rasters with higher
      indices appear on top of rasters with lower indices. This is
      1 by default.
      This must be between 1 and 255 (inclusive).

    Returns
    -------
    int
      The raster index of the associated raster.
      If the raster is already associated with the object this will be
      the index given when it was first associated.

    Raises
    ------
    ValueError
      If the registration object is invalid.
    ValueError
      If the raster index cannot be converted to an integer.
    ValueError
      If the raster index is less than 1 or greater than 255.
    ReadOnlyError
      If the raster or the surface are open for read-only.
    RuntimeError
      If the raster could not be associated with the surface.
    TypeError
      If raster is not a Raster object.
    AlreadyAssociatedError
      If the Raster is already associated with this object or another object.
    NonOrphanRasterError
      If the Raster is not an orphan.

    Examples
    --------
    This example shows creating a simple square-shaped surface and associates
    a raster displaying cyan and white horizontal stripes to cover the surface.
    In particular note that the call to this function is inside both
    the with statements for creating the surface and creating the raster.
    And as the raster is immediately associated with an object there is no
    need to provide a path for it.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Surface, Raster, RasterRegistrationTwoPoint
    >>> project = Project()
    >>> with project.new("surfaces/simple-rows", Surface) as new_surface:
    ...     new_surface.points = [[-10, -10, 0], [10, -10, 0],
    ...                           [-10, 10, 0], [10, 10, 0]]
    ...     new_surface.facets = [[0, 1, 2], [1, 2, 3]]
    ...     new_surface.facet_colours = [[200, 200, 0], [25, 25, 25]]
    ...     with project.new(None, Raster(width=32, height=32
    ...             )) as new_raster:
    ...         image_points = [[0, 0], [new_raster.width,
    ...                                  new_raster.height]]
    ...         world_points = [[-10, -10, 0], [10, 10, 0]]
    ...         orientation = [0, 0, 1]
    ...         new_raster.pixels[:] = 255
    ...         new_raster.pixels_2d[::2] = [0, 255, 255, 255]
    ...         registration = RasterRegistrationTwoPoint(
    ...             image_points, world_points, orientation)
    ...         new_surface.associate_raster(new_raster, registration)

    A raster cannot be associated with more than one surface. Instead,
    to associate a raster with multiple surfaces the raster must be copied
    and then the copy is associated with each surface. The below
    example uses this to create six square surfaces side by side, each
    with a 2x2 black and white chess board pattern raster applied to them.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import Surface, Raster, RasterRegistrationTwoPoint
    >>> project = Project()
    >>> width = 32
    >>> height = 32
    >>> raster_path = "images/base_raster"
    >>> # Create a raster with a path.
    >>> with project.new(raster_path, Raster(width=width, height=height
    ...         )) as base_raster:
    ...     # This is a 2x2 chess black and white chess board pattern.
    ...     base_raster.pixels[:] = 255
    ...     base_raster.pixels_2d[0:16, 0:16] = [0, 0, 0, 255]
    ...     base_raster.pixels_2d[16:32, 16:32] = [0, 0, 0, 255]
    >>> # Create six surfaces each with a copy of the raster applied.
    >>> for i in range(6):
    ...     with project.new(f"checkered_surface_{i}", Surface) as surface:
    ...         surface.points = [[-10, -10, 0], [10, -10, 0],
    ...                           [-10, 10, 0], [10, 10, 0]]
    ...         surface.points[:, 0] += i * 20
    ...         surface.facets = [[0, 1, 2], [1, 2, 3]]
    ...         image_points = [[0, 0], [width, height]]
    ...         world_points = [surface.points[0], surface.points[3]]
    ...         orientation = [0, 0, 1]
    ...         registration = RasterRegistrationTwoPoint(
    ...             image_points, world_points, orientation)
    ...         # A copy of the raster is associated.
    ...         raster_id = project.copy_object(raster_path, None)
    ...         with project.edit(raster_id) as raster:
    ...             surface.associate_raster(raster, registration)

    """
    if isinstance(raster, ObjectID):
      raise TypeError("raster must be a Raster opened for read/write not "
                      "an ObjectID.")
    if not isinstance(raster, Raster):
      raise TypeError(f"Cannot associate {raster} of type {type(raster)} "
                      "because it is not a Raster.")
    if raster.lock_type is not LockType.READWRITE:
      raise ReadOnlyError("The raster must be open for read/write to be "
                          "associated with a surface.")
    if not isinstance(registration, RasterRegistration):
      raise TypeError("Registration must be RasterRegistration, "
                      f"not {type(registration)}")
    if self.lock_type is LockType.READ:
      raise ReadOnlyError("Cannot associate a raster with a read-only Surface.")
    # pylint: disable=protected-access;
    if raster._lock.is_closed:
      raise ValueError(
        "Cannot set registration information on a closed raster.")
    desired_index = int(desired_index)
    if desired_index < 1 or desired_index > 255:
      message = (f"Invalid raster index ({desired_index}). Raster index must "
                 "be greater than 0 and less than 255.")
      raise ValueError(message)
    raster_id = raster.id
    if raster_id in self.rasters.values():
      message = (
        "The Raster is already associated with this Surface. To edit "
        "the registration information, edit the registration property "
        "of the Raster directly. To change the raster index, the "
        "raster must be dissociated via dissociate_raster() "
        "before calling this function.")
      raise AlreadyAssociatedError(message)
    if not raster_id.is_orphan:
      # :TRICKY: Jayden Boskell 2021-09-27 SDK-542. AssociateRaster will
      # make a clone of the Raster if it is not an orphan. This won't clone
      # the registration information, resulting in the clone being
      # associated with the Surface with no registration information.
      # Raise an error to avoid this.
      # Note that if a Raster is created with a path in project.new
      # then it is an orphan until the object is closed and no error will
      # be raised.
      parent_id = raster_id.parent
      if parent_id.is_a((VisualContainer, StandardContainer)):
        raise NonOrphanRasterError(
          "Cannot associate a raster with a Project path. "
          "Call Project.copy_object() with a destination path of None and "
          "associate the copy instead.")
      raise AlreadyAssociatedError(
        "Cannot associate Raster because it is already associated with the "
        f"{parent_id.type_name} with path: '{parent_id.path}'. "
        "To associate the Raster with this object, first dissociate it from "
        "the other object and close the other object before calling this "
        "function. Alternatively create a copy by calling "
        "Project.copy_object() with a destination path of None.")

    supported_registrations = (RasterRegistrationTwoPoint,
                               RasterRegistrationMultiPoint)
    if isinstance(registration, supported_registrations):
      raster.registration = registration
      result = Modelling().AssociateRaster(self._lock.lock,
                                           raster.id.handle,
                                           desired_index)
      result = result.value
      if result == 0:
        raise RuntimeError("Failed to associate raster.")
      return result
    raise RegistrationTypeNotSupportedError(registration)

  def _invalidate_properties(self):
    """Invalidates the properties of the object. The next time a property
    is requested they will be loaded from what is currently saved in the
    project.

    This is called during initialisation and when operations performed
    invalidate the properties (such as primitive is removed and the changes
    are saved right away).

    """
    PointProperties._invalidate_properties(self)
    EdgeProperties._invalidate_properties(self)
    FacetProperties._invalidate_properties(self)

  def save(self):
    self._save_point_properties()
    self._save_edge_properties()
    self._save_facet_properties()
    self._reconcile_changes()
