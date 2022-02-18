"""Base class for C API wrappers.

Warnings
--------
Vendors and clients should not develop scripts or applications against
this module. The contents may change at any time without warning.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import ctypes

class WrapperBase:
  """Base class for C API wrappers.

  Contains code shared by all C API wrappers.

  Notes
  -----
  *Reminder*
  Changing the C API for the Python SDK, this can break the C# SDK.
  When changing the C API remember to make the coresponding changes
  to the C# SDK.

  When to change the major version of the C API
  This should be incremented after a change to the C API interface which
  is not backwards-compatible. Note that the major version does not and
  should not be incremented more than once per user-facing release.
  When the major version number is incremented, the minor version
  number should be set to zero.

  When to change the minor version number of the C API
  This should be incremented after a backwards compatible-change
  to the C API interface. This does not need to be done more than once
  per release (Either user facing or internal).

  To avoid conflicts when updating the version number, perform the update in
  its own commit and cherry pick that commit in other jobs which change
  the C API.

  Adding handling for a new major version of the C API
  1: Increment the C API version number in authorisation/CApiVersion.H.
  2: In each wrapper class, in the capi_functions declaration add
     a comment stating the new version number after the changes
     from the previous version number then add a blank dictionary
     to contain the changes in the new version.
  3: Update the minimum/maximum supported versions as required.

  Adding a new function to the C API
  1: Make the required changes to the C API.
  2: Change the version number of the C API if required (see above)
  3: Add the new function to the newest version of the C API in
     capi_functions.
     (Never edit the capi_functions for any version of the C API
      other than the newest - doing so will break backwards
      compatability)
  4: Write a wrapper function for the new function. This function
     should behave correctly if the new function is called from
     an older but still supported version of the C API (Typically
     this should ignore the call, return a safe default value
     or raise an exception. Choose whichever is most appropriate).

  Changing a function in the C API (no function definition changes)
  1: Make the required changes in the C API.
  2: Document any visible changes in behaviour including the
     version number in the relevant docstrings.

  Changing a function in the C API (function definition changes)
  This is the same as for new. Make sure to use the same function
  name - definitions in later versions of the C API override older ones.
  Remember to update the wrappers with extra code to ensure compatability
  with previous versions of the C API.

  Deleting a function in the C API
  This is the same as editing, except you set the return type of
  the function to "deleted" (no capital letters) of the function
  to delete.
  Note that a future version can un-delete a function by including
  a non-deleted function with the same name.

  Deprecating support for a version
  1: Update the minimum supported version as required.
  2: Merge the dictionary for the deprecated version of the C API
     into the oldest still supported version such that it contains
     the exact definitions of the C API in the oldest supported version
     of the C API.
  3: Remove/update any wrapper functions which supports the
     deprecated version.

  """
  def capi_functions(self, version):
    """Returns a dictionary containing the functions present in the C API for
    the specified version.

    Parameters
    ----------
    version : int
      Which version of the C API to return the functions declarations for. Note
      that the version expected by this function is the major version number,
      not the tuple.

    Returns
    -------
    dict
      Dictionary containing the function definition. The key is the function
      name as written in the C API header file and the value is a tuple
      containing two elements. The first is the return type and the second
      is a list of argument types. This matches the format expected by
      declare_dll_function.

    Raises
    ------
    RuntimeError
      If the specified C API version is not supported by this version
      of the Python SDK.

    See Also
    --------
    util.declare_dll_functions : Declares functions on a dll using return
      value of this function.

    Notes
    -----
    This function does not support the minor version numbers - those
    differences should be handled by wrapper functions.

    """
    raise NotImplementedError

  @staticmethod
  def method_prefix():
    """Returns the method prefix which is appended to function names
    by getattr.

    For example, in dataengine.py this function returns "DataEngine". Calling
    DataEngine.Function() would add this prefix to the function to get
    "DataEngineFunction" as the function to call in the CAPI.

    Returns
    -------
    str
      Prefix added by getattr.

    """
    raise NotImplementedError

  def _dll(self):
    """Returns the dll which this class wraps.

    Returns
    -------
    ctypes.cdll
      The dll this class wraps.

    """
    raise NotImplementedError

  @staticmethod
  def oldest_supported_version():
    """Returns the oldest C API version supported by the SDK.
    If the SDK attempts to connect to a version with a earlier
    version number than this an exception will be raised.

    Returns
    -------
    tuple
      A tuple with two elements representing the oldest
      supported version in the form (major, minor)

    """
    return (0, 0)

  @staticmethod
  def newest_supported_major_version():
    """Returns the highest major version number the SDK supports.
    Attempting to connect to an application with a higher major
    version number than returned by this function will cause an
    error to be raised.

    Returns
    -------
    int
      The highest major version number the SDK supports.

    Notes
    -----
    Ideally, if this function returns v, then the SDK should
    be able to support all C APIs with major version v including
    future versions. If a change would result in breaking this
    property, then the major version number should be incremented.

    """
    return 1

  def check_version_is_supported(self, version):
    """Raises a RuntimeError if version is not a supported version.

    If version is older than the oldest supported version or
    has a major version newer than the newest supported version it
    is considered not supported.

    """
    oldest_version = self.oldest_supported_version()
    newest_version = self.newest_supported_major_version()
    error_message = ""
    if version < oldest_version:
      error_message = ("The application is too old to be supported by the "
                       f"SDK.\nApplication C API version: {version}"
                       f"\nOldest supported version {oldest_version}")
    elif version[0] > newest_version:
      error_message = ("The application is too new to be supported by the "
                       f"SDK.\nApplication C API version: {version}"
                       f"\nNewest supported version {newest_version}")

    if error_message:
      raise RuntimeError(error_message)

  def load_version_information(self):
    """Loads the version information from the dll. The version
    is represented as a tuple of (major, minor). Versions can
    be compared using the < and > operators.

    Returns
    -------
    tuple
      Tuple containing two elements representing the version number.

    """
    try:
      major_version_function = getattr(self.dll,
                                       self.method_prefix() + "CApiVersion")
      major_version_function.restype = ctypes.c_uint32
      minor_version_function = getattr(self.dll,
                                       self.method_prefix() + "CApiMinorVersion")
      minor_version_function.restype = ctypes.c_uint32
      major = major_version_function()
      minor = minor_version_function()
      return (major, minor)
    except AttributeError:
      # The dll version not being found means version 0.0
      return (0, 0)

  def __getattr__(self, name):
    """This function is called if a attribute which does not exist
    is requested from the dll.

    If there is a function message_prefix + name in the dll, that function
    is automatically returned. Effectively this automatically
    generates the trivial wrapper functions which require no special
    handling.

    """
    existing_function = getattr(self._dll(), self.method_prefix() + name)
    if existing_function:
      return existing_function
    raise AttributeError
