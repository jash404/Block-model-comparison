"""Logging for the Python SDK.

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

import logging
import os
import sys

def configure_log(logger,
                  file_path=None,
                  file_log_level=logging.INFO,
                  console_log_level=logging.WARNING,
                  use_file=True,
                  use_console=False,
                  propagate=False):
  r"""Configure the logger instance.

  Set-up handlers for writing to a log file and the console.

  Parameters
  ----------
  logger : logging.Logger
    The logger to configure.
  file_path : str
    Optional full path to log file or
    default = None .
  file_log_level : enum
    Minimum log level for logging to file.
  console_log_level : enum
    Minimum log level for logging to console.
  use_file : bool
    True if wishing to output logs to file.
  use_console : bool
    True if wishing to output logs to console.
  propagate : bool
    True if the log entries should be propogated to the root logger.
    This will cause all log entries to be logged twice, once by the
    passed logger and once by the root logger.

  Notes
  -----
  If file_path = None (ie Default) then the log is saved to:
  AppData\\\Roaming\\\Maptek\\\pythonsdk\\\log.txt.

  """
  if __debug__:
    # This constant is true if Python was not started with an -O option.
    #
    # Therefore this is the default behaviour, so we should reconsider if this
    # is useful.
    file_log_level = logging.DEBUG
    console_log_level = logging.WARNING
    use_console = True

  # The handlers won't receive messages if the loggers level is higher than
  # the handler's level.
  if use_console:
    logger.setLevel(min(file_log_level, console_log_level))
  else:
    logger.setLevel(file_log_level)

  formatter = logging.Formatter(
    '%(asctime)s | %(name)s | %(levelname)s | %(message)s')

  if use_file:
    if file_path is None:
      user_appdata = os.getenv('APPDATA')
      file_path = os.path.join(user_appdata, 'Maptek', 'pythonsdk', 'log.txt')
    # Make the file and any containing folders.
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'a'):
      os.utime(file_path, None)
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(file_log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

  if use_console:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

  logger.propagate = propagate
