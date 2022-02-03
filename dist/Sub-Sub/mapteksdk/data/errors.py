"""Generic errors raised by classes in this packages.

More specialised errors are placed in other modules.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

class ReadOnlyError(Exception):
  """Exception raised when operation fails due to being read-only"""
  def __init__(self, message=None):
    if message is None:
      message = "Operation is not available in read-only mode"
    super().__init__(message)

class CannotSaveInReadOnlyModeError(Exception):
  """Error raised when attempting to save an object in read only mode."""
  def __init__(self, message=None):
    if message is None:
      message = "Cannot save objects in read only mode"
    super().__init__(message)

class DegenerateTopologyError(Exception):
  """Error raised when creating an object with degenerate topology."""

class InvalidColourMapError(Exception):
  """Error raised when creating an invalid colour map."""

class RegistrationTypeNotSupportedError(Exception):
  """Error raised when a type of raster registration is not supported."""
  def __init__(self, unsupported_type):
    message = (f"Registration type: {unsupported_type} is not supported by "
               "the object.")
    super().__init__(message)

class AlreadyAssociatedError(Exception):
  """Error raised when a associating a Raster which is already associated.

  The Raster may be associated with another object or be already
  associated with the same object.

  """

class NonOrphanRasterError(Exception):
  """Error raised when associating a raster which is not an orphan."""
