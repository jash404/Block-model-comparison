"""Common functions used by the SDK specifically for use with C API modules.

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

class CApiError(Exception):
  """Base class for errors raised by the C API. This class should not be
  raised directly - raise a subclass instead.

  """

class CApiFunctionNotSupportedError(CApiError):
  """Error raised when a function in the C API is not supported by the current
  C API version.

  """

class CApiDllLoadFailureError(CApiError):
  """Error raised when one of the DLLs fails to load."""

class CApiUnknownError(CApiError):
  """Error raised when an unknown error occurs in the CAPI."""

def singleton(class_reference):
  """Provides an implementation of the singleton pattern.

  Notes
  -----
  Usage: @singleton above class

  """
  instances = {}
  def get_instance():
    """Gets (or creates) the only instance of a singleton class."""
    if class_reference not in instances:
      instances[class_reference] = class_reference()
    return instances[class_reference]
  return get_instance

def get_string(target_handle, dll_function):
  """Try/catch block for C API functions that return a string
  with parameter pattern of Tint32u (handle, *buffer, size).

  Parameters
  ----------
  target_handle : c_uint64, T_ObjectHandle, T_NodePathHandle, etc
    Suitable type of native handle (), supporting
    a *.value property.
  dll_function : function
    A function of Tint32u (handle, *buffer, size).

  Returns
  -------
  str: Result as string or None on failure (e.g. not supported by dll).

  """
  try:
    value_size = 64
    while value_size > 0:
      value_buffer = ctypes.create_string_buffer(value_size)
      result_size = dll_function(target_handle, value_buffer, value_size)
      if result_size is None:
        # probably not supported by dll version
        return None
      value_size = -1 if result_size <= value_size else result_size
    return value_buffer.value.decode("utf-8")
  except OSError:
    result = None
  return result

def declare_dll_functions(dll, functions, log):
  """Helper function for declaring all of the functions in
  a dll based on a dictionary of functions known to exist.

  Parameters
  ----------
  dll : dll
    The dll to declare the functions on. Generally this is the
    callers self.dll.

  functions: dict
    A dictionary containing the function declarations for the capi,
    with one entry for each function to declare.
    The key for each entry should be a string containing the name
    of the function in the capi header
    The value for each entry should be a tuple containing two elements -
    the first element is the return type and
    the second element is the list of arguments for the function.
    EG: The function "LibraryExampleFunction" which returns
    a uint_16 and takes a c_char_p and a uint_16 as arguments would
    be written in as:
    "LibraryFunctionName" : (uint_16, [c_char_p, uint_16])
    Note that the types in the dictionary should be the python ctypes.

  log : log
    Log to use to report errors (eg: function cannot be found).

  Notes
  -----
  A function with a return type of the string constant "deleted"
  is ignored by this function.

  """
  # For each function, declare its restype and argtypes based
  # on the values in the dictionary/tuple.
  for name, parameters in functions.items():
    if parameters[0] == "deleted":
      # Function was deleted, move onto the next one.
      continue
    try:
      # Declare the function with the return and arg types.
      dll_function = getattr(dll, name)
      dll_function.restype = parameters[0]
      dll_function.argtypes = parameters[1]
    except AttributeError:
      log.debug(f"{name} not supported in DLL version.")

def raise_if_version_too_old(feature, current_version, required_version):
  """Raises a CapiVersionNotSupportedError if current_version is less
  than required_version.

  Parameters
  ----------
  feature : str
    The feature name to include in the error message.
  current_version : tuple
    The current version of the C Api.
  required_version : tuple
    The version of the C Api required to access the new feature.

  Raises
  ------
  CApiVersionNotSupportedError
    If current_version < required_version. The text of the error is:
    f"{feature} is not supported in C Api version: {current_version}. "
    f"Requires version: {required_version}."

  """
  if current_version < required_version:
    raise CApiFunctionNotSupportedError(
      f"{feature} is not supported in C Api version: {current_version}. "
      f"Requires version: {required_version}")
