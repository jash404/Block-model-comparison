"""ConnectorType subclasses dependent on the data module."""
###############################################################################
#
# (C) Copyright 2021, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import csv
from typing import Iterable

from ..data.objectid import ObjectID
from ..data.base import DataObject
from ..internal.util import default_type_error_message
from ..workflows.connector_type import ConnectorType

class WorkflowSelection(ConnectorType):
  """Class representing a read-only list of ObjectIDs. Pass this to
  declare_input_connector for input connectors expecting a selection -
  the lists of objects given by the 'Maptek Database Object' connectors of
  many components.

  Iterating over this object will iterate over the ObjectIDs in the
  selection.

  You should not access the contents of this object until after
  Project() has been called.

  Parameters
  ----------
  selection_string : str
    String representing the selection.

  Raises
  ------
  OSError
    If the contents are accessed before Project() has been called.
  ValueError
    If part of the selection cannot be converted to an ObjectID.

  Warnings
  --------
  Ensure the ObjectIDs passed to this class are from the same
  project as is opened with Project() otherwise the ObjectIDs may refer to a
  completely different object.

  Notes
  -----
  This class does not support object paths which contain quotation marks
  or commas.

  Examples
  --------
  Script which takes a selection of objects and returns their centroid
  via a list output connector. This script would have one input
  connector "Selection" which accepts a selection. There is also one output
  connector "Centroid" which will be set to the centroid of all of the points
  in the objects in the selection. Note that this script does not honour
  point selection.

  >>> from mapteksdk.project import Project
  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  WorkflowSelection,
  ...                                  Point3DConnectorType)
  >>> import numpy as np
  >>> parser = WorkflowArgumentParser(
  ...     description="Get the centroid of objects with points")
  >>> parser.declare_input_connector(
  ...     "selection",
  ...     WorkflowSelection,
  ...     description="Objects to find the centroid of.")
  >>> parser.declare_output_connector(
  ...     "Centroid",
  ...     Point3DConnectorType,
  ...     description="The centroid of the points in the objects.")
  >>> parser.parse_arguments() # Must call before Project().
  >>> project = Project() # Must call before get_ids().
  >>> sums = np.zeros(3)
  >>> count = 0
  >>> for oid in parser["selection"]:
  ...     with project.read(oid) as read_object:
  ...         if not hasattr(read_object, "points"): continue
  ...         sums += np.sum(read_object.points, axis=0)
  ...         count += read_object.point_count
  >>> result = sums / count
  >>> parser.set_output("Centroid", result)
  >>> parser.flush_output()

  """
  def __init__(self, selection_string):
    if not isinstance(selection_string, str):
      raise TypeError(default_type_error_message("workflow selection",
                                                 selection_string,
                                                 str))
    self.selection = list(csv.reader([selection_string],
                                     skipinitialspace=True))[0]
    for i, item in enumerate(self.selection):
      # If we have an OID without a comma, then it was probably
      # unquoted and was split on commas. So fuse the three parts
      # together.
      # Also check for orphans which will need the same treatment for
      # orphan paths as they contain the OID.
      if item.startswith(("OID", "\\orphan")) and "," not in item:
        try:
          # :TODO: Jayden Boskell 04-06-2021 SDK-507 Escape the commas on
          # the workflows side. This code may still need to be kept for
          # backwards compatability.
          if ")" in self.selection[i + 1]:
            self.selection[i:i+2] = [", ".join([self.selection[i],
                                                self.selection[i + 1]])]
          else:
            self.selection[i:i+3] = [", ".join([self.selection[i],
                                                self.selection[i + 1],
                                                self.selection[i + 2]])]
        except IndexError as error:
          # This is not expected to happen.
          raise RuntimeError("Failed to parse partial Object ID: "
                             f"{item}") from error
    self.selection_ids = None

  @classmethod
  def type_string(cls):
    return "DataEngineObject"

  @classmethod
  def from_string(cls, string_value):
    return WorkflowSelection(string_value)

  @classmethod
  def to_json(cls, value):
    # If passed a string, use it as the selection.
    if isinstance(value, str):
      return [value]
    # If not given an iterable, insert it into a list.
    if not isinstance(value, Iterable):
      value = [value]
    results = []
    for item in value:
      if isinstance(item, str):
        results.append(item)
      elif isinstance(item, ObjectID):
        results.append(str(item.path))
      elif isinstance(item, DataObject):
        results.append(str(item.id.path))
      else:
        raise TypeError(default_type_error_message("selection", item,
                                                   "selection"))
    return results

  @property
  def ids(self):
    """Return the IDs in the selection as a list.
    This must be called after Project() has been called. Object IDs only have
    meaning within a Project.

    Returns
    -------
    list of ObjectID
      ObjectIDs in the selection.

    Raises
    ------
    ValueError
      If any string cannot be converted to an ObjectID.
    OSError
      If called before Project() is called.

    """
    result = []
    for item in self.selection:
      if item.startswith("'") and item.endswith("'"):
        item = item[1:-1]
      try:
        # pylint: disable=protected-access;reason="No other way to convert."
        result.append(ObjectID._from_string(item))
      except ValueError:
        result.append(ObjectID.from_path(item))
    return result
    # The ObjectID constructor needs the DLLs so will fail with an OSError
    # if they aren't loaded.

  def __getitem__(self, key):
    if self.selection_ids is None:
      self.selection_ids = self.ids
    return self.selection_ids[key]

  def __len__(self):
    if self.selection_ids is None:
      self.selection_ids = self.ids
    return len(self.selection_ids)

  def __iter__(self):
    if self.selection_ids is None:
      self.selection_ids = self.ids
    return iter(self.selection_ids)
