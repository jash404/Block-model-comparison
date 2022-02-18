"""Read/write lock functionality for project operations.

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

from enum import IntEnum
from ..capi import DataEngine

class LockType(IntEnum):
  """Used to set mode for object instance to be read-only or read-write."""
  READ = 1
  READWRITE = 2

class ReadLock:
  """Provides a read lock over MDF objects to allow reading from objects
  within the Project.

  Parameters
  ----------
  handle : T_ObjectHandle
    The handle for the object to open for reading.

  """
  def __init__(self, handle):
    self.handle = handle
    self._lock = DataEngine().ReadObject(handle)
    if not self._lock:
      last_error = DataEngine().ErrorMessage().decode("utf-8")
      raise ValueError('Could not open object for read [%s].' % last_error)

  def __enter__(self):
    return self

  @property
  def is_closed(self):
    """Return True if the lock has been closed (the lock has been released)."""
    return not bool(self._lock)

  @property
  def lock(self):
    """Return the underlying handle to the lock."""
    if not self._lock:
      raise ValueError("Can't access a closed object.")
    return self._lock

  def close(self):
    """Close and dispose of object read lock."""
    if not self.is_closed:
      DataEngine().CloseObject(self.lock)
      self._lock = None

  def __exit__(self, exc_type, exc_value, traceback):
    self.close()

class WriteLock:
  """Provides a write lock over MDF objects to allow writing to objects
  within the Project.

  Parameters
  ----------
  handle : T_ObjectHandle
    The handle for the object to open for writing (and reading).

  """
  def __init__(self, handle):
    self.handle = handle
    self._lock = DataEngine().EditObject(handle)
    if not self._lock:
      last_error = DataEngine().ErrorMessage().decode("utf-8")
      raise ValueError('Could not open object for edit (write) [%s].' %
                       last_error)

  def __enter__(self):
    return self

  @property
  def is_closed(self):
    """Return True if the lock has been closed (the lock has been released)."""
    return not bool(self._lock)

  @property
  def lock(self):
    """Return the underlying handle to the lock."""
    if not self._lock:
      raise ValueError("Can't access a closed object.")
    return self._lock

  def close(self):
    """Close and dispose of object write lock."""
    if not self.is_closed:
      DataEngine().CloseObject(self.lock)
      self._lock = None

  def __exit__(self, exc_type, exc_value, traceback):
    self.close()
