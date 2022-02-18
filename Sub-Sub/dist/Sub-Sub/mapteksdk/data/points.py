"""Point data types.

This module contains data types where the most complicated primitive they
use is points. Though many other objects use points, the types defined
here only use points.

Currently there is only one such data type (PointSet).

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

from contextlib import contextmanager
import logging

import pandas as pd

from ..capi import Modelling
from ..internal.lock import WriteLock, LockType
from .base import Topology
from .primitives import PointProperties
from .objectid import ObjectID
# pylint: disable=too-many-lines
# pylint: disable=too-many-instance-attributes
log = logging.getLogger("mapteksdk.data")

class PointSet(PointProperties, Topology):
  """A pointset is a set of three dimensional points.

  """
  # pylint: disable=too-many-instance-attributes
  def __init__(self, object_id=None, lock_type=LockType.READWRITE):
    if object_id:
      super().__init__(object_id, lock_type)
      self._invalidate_properties()
    else:
      object_id = ObjectID(Modelling().NewPointSet())
      super().__init__(object_id, lock_type)

  @classmethod
  def static_type(cls):
    """Return the type of point set as stored in a Project.

    This can be used for determining if the type of an object is a point set.

    """
    return Modelling().PointSetType()

  def _invalidate_properties(self):
    """Invalidates the properties of the object. The next time a property
    is requested they will be loaded from what is currently saved in the
    project.

    This is called during initialisation and when operations performed
    invalidate the properties (such as primitive is removed and the changes
    are saved right away).

    """
    PointProperties._invalidate_properties(self)

  @contextmanager
  def dataframe(self, save_changes=True, attributes=None):
    """Provides context managed representation of the entire PointSet as a
    Pandas Dataframe.

    Parameters
    ----------
    save_changes : bool
      If save_changes = False then any changes to the data frame will not
      be propagated to the point set.
      If save_changes = True (default) and the point set is opened for editing,
      all changes made to the dataframe will be propogated to the point set when
      the with block finishes.
      This is ignored if the point set is opened in read mode - in that case
      changes to the Dataframe will never be made to the point set.
    attributes : iterable
      List of names of point attributes to include as extra columns in the
      DataFrame. If None (default) all existing point properties are included
      in the Dataframe. For better performance, only include the point
      attributes you want in the DataFrame.

    Yields
    ------
    pandas.DataFrame
      DataFrame representing the PointSet. Columns include:
      ['X', 'Y', 'Z', 'R', 'G', 'B', 'A', 'Visible', 'Selected']
      Any point attributes included in the DataFrame are
      inserted after Selected.

    Raises
    ------
    KeyError
      If attributes contains an attribute name which doesn't exist.
    KeyError
      If the X, Y or Z columns of the data frame are dropped.

    Notes
    -----
    If save_changes is True, dropping the R, G or B column will cause
    the red, green or blue component of the colour to be set to 0.
    Dropping the A column will cause the alpha of all points to be
    set to 255.
    Dropping the Visible column will cause all points to be set to
    be visible.
    Dropping the Selected column will cause all points to be set to
    be not selected.
    Dropping a primitive attribute column will cause that primitive
    attribute to be deleted.

    Examples
    --------
    Use pandas to hide all points with Z less than 15.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import PointSet
    >>> project = Project()
    >>> with project.new("cad/my_points", PointSet) as new_set:
    ...     new_set.points = [[1, 2, 3], [5, 5, 16], [-1, -6, -16]]
    ...     with new_set.dataframe() as frame:
    ...         frame.loc[frame.Z < 15, "Visible"] = False
    >>>     print(new_set.point_visibility)
    [False True False]

    Calculate and print the mean 'redness' of points using pandas.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import PointSet
    >>> project = Project()
    >>> with project.new("cad/my_other_points", PointSet) as new_set:
    ...     new_set.points = [[1, 2, 3], [5, 5, 16], [-1, -6, -16]]
    ...     new_set.point_colours = [[100, 0, 0], [150, 0, 0], [200, 50, 50]]
    >>> with project.read("cad/my_other_points") as read_set:
    ...     with read_set.dataframe() as frame:
    ...         print(frame.loc[:, 'R'].mean())
    150.0

    Populate a point property with if the x value of the point is
    negative or positive.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import PointSet
    >>> project = Project()
    >>> with project.new("cad/positive_points", PointSet) as new_set:
    ...     new_set.points = [[-1, 3, 9], [1, 4, -5], [-5, 2, 3]]
    ...     new_set.point_attributes['negative_x'] = [False] * 3
    ...     with new_set.dataframe() as frame:
    ...         frame.loc[frame.X < 0, 'negative_x'] = True
    ...         frame.loc[frame.X >= 0, 'negative_x'] = False
    ...     print(new_set.point_attributes['negative_x'])
    [True False True]

    When extracting the values of points as a pandas dataframe, you
    can set it to not save changes. This way you can make changes
    to the Dataframe without changing the original point set.
    In the below example, all points with red greater than or equal
    to 200 have their red set to zero in the dataframe and prints them.
    However when the with statement ends, the points are left unchanged
    - when the points colours are printed, they are the same as before
    the dataframe.
    Use this to work with a temporary copy of your data.

    >>> from mapteksdk.project import Project
    >>> from mapteksdk.data import PointSet
    >>> project = Project()
    >>> with project.new("cad/my_nice_points", PointSet) as new_set:
    ...     new_set.points = [[1, 2, 3], [5, 5, 16], [-1, -6, -16]]
    ...     new_set.point_colours = [[100, 0, 0], [150, 0, 0], [200, 50, 50]]
    ...     with new_set.dataframe(save_changes=False) as frame:
    ...         frame.loc[frame.R >= 200, 'R'] = 0
    ...         print(frame.loc[:, 'R'])
    ...     print(new_set.point_colours)
    0    100
    1    150
    2      0
    Name: R, dtype: uint8
    [[100   0   0 255]
     [150   0   0 255]
     [200  50  50 255]]

    """
    log.info("Access pandas dataframe of %r, %s", self, self.id)
    if attributes is None:
      attributes = list(self.point_attributes.names)
    df_pointset = self._get_pandas(attributes)
    try:
      yield df_pointset
    finally:
      if save_changes and isinstance(self._lock, WriteLock):
        log.info("Write pandas dataframe changes to %r, %s", self, self.id)
        self._put_pandas(df_pointset, attributes)
      else:
        log.info("Read-only finished with pandas dataframe of %s, %s", self,
                 self.id)
      del df_pointset

  def _get_pandas(self, included_names):
    """Provides representation of entire PointSet as a Pandas Dataframe.

    Parameters
    ----------
    included_names : iterable
      iterable of attribute names to include in the DataFrame.

    """
    # Putting the columns into a dictionary allows pandas to maintain
    # the data types when creating the dataframe.
    frame_dictionary = {
      "X" : self.points[:, 0],
      "Y" : self.points[:, 1],
      "Z" : self.points[:, 2],
      "R" : self.point_colours[:, 0],
      "G" : self.point_colours[:, 1],
      "B" : self.point_colours[:, 2],
      "A" : self.point_colours[:, 3],
      "Visible" : self.point_visibility,
      "Selected" : self.point_selection
    }

    # Add the primitive attributes to the dictionary.
    for name in included_names:
      frame_dictionary[name] = self.point_attributes[name]
    return pd.DataFrame(frame_dictionary)

  def _put_pandas(self, point_collection, included_names):
    """Stores pandas dataframe back into numpy arrays for the object.

    If the R, G or B columns are not present, the corresponding component
    of the colour will be set to 0.
    If the A column is not present, the alpha of all points will be set to 255.
    If the Visible column is not present, all points will be made visible.
    If the Selected column is not present, all points will be set to
    not selected.
    If a primitive attribute is in included_names but is not in
    the DataFrame the primitive attribute will be deleted.

    Parameters
    ----------
    point_collection : pandas.DataFrame
      Pandas dataframe created by _get_pandas.
    include_names : iterable
      Iterable of primitive attributes to include.

    Raises
    ------
    KeyError
      If X, Y or Z columns have been dropped.

    """
    try:
      self.points = point_collection[['X', 'Y', 'Z']].values
    except KeyError as error:
      # Provide a specific error message if the caller dropped
      # the X, Y or Z columns.
      message = ("Dropping or renaming the 'X', 'Y' or 'Z' columns is "
                 f"not supported. Columns: {point_collection.columns.tolist()}")
      raise KeyError(message) from error
    if "R" in point_collection.columns:
      self.point_colours[:, 0] = point_collection["R"].values
    else:
      self.point_colours[:, 0] = 0
    if "G" in point_collection.columns:
      self.point_colours[:, 1] = point_collection["G"].values
    else:
      self.point_colours[:, 1] = 0
    if "B" in point_collection.columns:
      self.point_colours[:, 2] = point_collection["B"].values
    else:
      self.point_colours[:, 2] = 0
    if "A" in point_collection.columns:
      self.point_colours[:, 3] = point_collection["A"].values
    else:
      self.point_colours[:, 3] = 255

    if "Visible" in point_collection.columns:
      self.point_visibility = point_collection["Visible"].values
    else:
      self.point_visibility[:] = True
    if "Selected" in point_collection.columns:
      self.point_selection = point_collection["Selected"].values
    else:
      self.point_selection[:] = False

    names_to_delete = []
    for name in included_names:
      if name in point_collection.columns:
        typed_values = point_collection[name].values
        self.point_attributes[name] = typed_values
      else:
        names_to_delete.append(name)

    # By default this is a KeyView of the attributes dictionary
    # so deleting the attribute inside the loop will raise an exception
    # due to the size of the collection changing during iteration.
    for name in names_to_delete:
      self.point_attributes.delete_attribute(name)

  def save(self):
    self._save_point_properties()
    self._reconcile_changes()
