"""Errors raised by the project module."""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

class DeleteRootError(Exception):
  """Error raised when you attempt to delete the root container."""

class ObjectDoesNotExistError(Exception):
  """Error raised when attempting an operation on an object which
  does not exist.

  """

class ProjectConnectionFailureError(Exception):
  """Error raised when connecting to the project fails."""

class ApplicationTooOldError(Exception):
  """Error raised when connecting to an application which is too old."""
