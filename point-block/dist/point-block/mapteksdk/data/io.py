"""Functions for importing and exporting data."""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import logging
import os

from ..capi import DataEngine, Vulcan
from .objectid import ObjectID
from .units import DistanceUnit
from ..internal.util import default_type_error_message

log = logging.getLogger("mapteksdk.data.io")

def import_00t(path, unit=DistanceUnit.metre):
  """Import a Maptek Vulcan Triangulation file (00t) into the project.

  Parameters
  ----------
  path : str
    Path to file to import.
  unit : DistanceUnit
    The unit used when exporting the file.

  Returns
  -------
  ObjectID
    The ID of the imported object.
  None
    If there was an error importing the object.

  Raises
  ------
  FileNotFoundError
    If the file does not exist.
  TypeError
    If the unit is not an instance of DistanceUnit.
  RuntimeError
    If there is a problem importing the file.

  Notes
  -----
  The imported object is not automatically placed inside a container.
  A call to project.add_object() is required to add it to a container.

  """
  log.info("Importing Vulcan Triangulation (00t): %s", path)
  if not isinstance(unit, DistanceUnit):
    raise TypeError(default_type_error_message("unit", unit, DistanceUnit))

  if not os.path.isfile(path):
    raise FileNotFoundError(f"Could not find file: {path}")

  imported_object = Vulcan().Read00tFile(
    path.encode('utf-8'), unit.value)

  if imported_object.value == 0:
    message = Vulcan().ErrorMessage().decode('utf-8')
    log.error(
      "A problem occurred when importing the 00t: %s. %s", path, message)
    raise RuntimeError(message)
  return ObjectID(imported_object)


def export_00t(object_id, path, unit=DistanceUnit.metre):
  """Export the object referenced by the object ID to a Maptek
  Vulcan Triangulation file (00t).

  Parameters
  ----------
  object_id : ObjectID
    The ID of the object to export to the 00t file.
  path : str
    Where to save the exported 00t.
  unit : DistanceUnit
    Unit to use when exporting the file.

  Returns
  -------
  bool
    True if successful otherwise False.

  Raises
  ------
  TypeError
    If the unit is not an instance of DistanceUnit.
  RuntimeError
    If there is a problem exporting the file.

  """
  log.info("Exporting Vulcan Triangulation (00t): %s", path)
  if not isinstance(unit, DistanceUnit):
    raise TypeError(default_type_error_message("unit", unit, DistanceUnit))

  result = Vulcan().Write00tFile(object_id.handle,
                                 path.encode('utf-8'),
                                 unit.value)
  if not result:
    # This may be because the type of object can't be exported to a 00t or
    # because there was a problem trying to read the object or write to the
    # 00t.
    message = Vulcan().ErrorMessage().decode('utf-8')
    log.error("The 00t could not be exported: %s. %s", path, message)
    raise RuntimeError(message)
  return result


def import_bmf(path, unit=DistanceUnit.metre):
  """Import a Maptek Block Model File (bmf) into the project.

  Parameters
  ----------
  path : str
    Path to file to import.
  unit : DistanceUnit
    Unit to use when importing the file.

  Returns
  -------
  ObjectID
    The ID of the imported object.
  None
    If there was an error importing the object.

  Raises
  ------
  TypeError
    If the unit is not an instance of DistanceUnit.
  FileNotFoundError
    If the file does not exist.
  RuntimeError
    If there is a problem importing the file.

  """
  log.info("Importing Vulcan Block Model (bmf): %s", path)

  if not isinstance(unit, DistanceUnit):
    raise TypeError(default_type_error_message("unit", unit, DistanceUnit))

  if not os.path.isfile(path):
    raise FileNotFoundError(f"Could not find file: {path}")

  imported_object = Vulcan().ReadBmfFile(path.encode('utf-8'),
                                         unit.value)
  if imported_object.value == 0:
    message = Vulcan().ErrorMessage().decode('utf-8')
    log.error("A problem occurred when importing the BMF: %s", message)
    raise RuntimeError(message)
  return ObjectID(imported_object)


def export_bmf(object_id, path, unit=DistanceUnit.metre):
  """Export a block model to a Maptek Block Model File (bmf).

  Parameters
  ----------
  object_id : ObjectID
    The block model to export as a bmf file.
  path : str
    Where to save the exported bmf file.
  unit : DistanceUnit
    Unit to use when exporting the file.

  Returns
  -------
  bool
    True if successful otherwise False.

  Raises
  ------
  TypeError
    If the unit is not an instance of DistanceUnit.
  RuntimeError
    If there is a problem exporting the file.

  """
  log.info("Exporting Vulcan Block Model (bmf): %s", path)
  if not isinstance(unit, DistanceUnit):
    raise TypeError(default_type_error_message("unit", unit, DistanceUnit))

  result = Vulcan().WriteBmfFile(object_id.handle,
                                 path.encode('utf-8'),
                                 unit.value)
  if not result:
    # This may be because the type of object can't be exported to a bmf or
    # because there was a problem trying to read the object or write to the
    # bmf.
    message = Vulcan().ErrorMessage().decode('utf-8')
    log.error("The BMF could not be exported to %s. %s", path, message)
    raise RuntimeError(message)
  return result


def import_maptekobj(path):
  """Import a Maptek Object file (maptekobj) into the project.

  Parameters
  ----------
  path : str
    Path to file to import.

  Returns
  -------
  ObjectID
    The ID of the imported object.
  None
    If there was an error importing the object.

  Raises
  ------
  FileNotFoundError
    If the file does not exist.
  RuntimeError
    If there is a problem importing the file.

  """
  log.info("Importing Maptek Object file (maptekobj): %s", path)

  if not os.path.isfile(path):
    raise FileNotFoundError(f"Could not find file: {path}")

  imported_object = DataEngine().ReadMaptekObjFile(
    path.encode('utf-8'))
  if imported_object.value == 0:
    last_error = DataEngine().ErrorMessage().decode("utf-8")
    log.error("A problem occurred (%s) when importing %s", last_error, path)
    raise RuntimeError(last_error)

  return ObjectID(imported_object)


def export_maptekobj(object_id, path):
  """Export an object to a Maptek Object file (maptekobj).

  Parameters
  ----------
  object_id : ObjectID
    The ID of the object to export to a maptekobj file.

  path : str
    Where to save the exported maptekobj file.

  Returns
  -------
  bool
    True if successful otherwise False.

  Raises
  ------
  RuntimeError
    If there is a problem exporting the file.

  """
  log.info("Exporting Maptek Object file (maptekobj): %s", path)
  result = DataEngine().CreateMaptekObjFile(
    path.encode('utf-8'), object_id.handle)
  if not result:
    last_error = DataEngine().ErrorMessage().decode("utf-8")
    log.error("A problem occurred (%s) when importing %s", last_error, path)
    raise RuntimeError(last_error)
  return result
