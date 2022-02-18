"""Low level module for working with transactions (menu commands).

The specific transactions which within the Python SDK are known as
operations are provided in per-application modules.

A connection to an existing application is required.

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

import ctypes
import itertools
import logging
import threading
import typing

from mapteksdk.internal.util import default_type_error_message
from mapteksdk.data.base import DataObject
from mapteksdk.data.objectid import ObjectID
from mapteksdk.capi.mcp import Mcpd
from mapteksdk.capi.util import (raise_if_version_too_old,
                                 CApiDllLoadFailureError)

from .comms import (InlineMessage, Message, JsonValue, ReceivedSerialisedText,
                    RepeatingField, Request, SerialisedText, SubMessage, Icon)

NEXT_OPERATION_ID = itertools.count(start=1)


class RequestTransactionWithInputs(Message):
  """Define the message known as RequestTransactionWithInputs.

  This message can be used to request a transaction in an application.
  """
  logger = logging.getLogger('mdf.transactions')

  message_name: typing.ClassVar[str] = 'RequestTransactionWithInputs'

  transaction_name: str
  operation_id: ctypes.c_int32 = 0
  operation_command: str
  requester_icon: Icon = ''
  can_confirm_immediately: bool = True
  confirm_immediately: bool = True
  run_silently: bool = True  # Only present in 1.2+.
  selection_contains_objects: bool = False
  selection_contains_point_primitives: bool = False
  selection_contains_edge_primitives: bool = False
  selection_contains_facet_primitives: bool = False
  transaction_inputs: JsonValue = []

  @classmethod
  def format_selection(cls, selection):
    """Format a list of objects suitable for use as the value of a selection
    in the transaction_inputs.

    This supports ObjectIDs, DataObjects and paths.

    Raises
    ------
    ValueError
      If the selection contains a path to a nonexistent object.
    TypeError
      If the selection contains an object which is not an ObjectID,
      DataObject or path.

    """
    actual_selection = []
    if isinstance(selection, str):
      # String is an iterable, but don't treat it as such here.
      # We don't want to try creating an object id for each character
      # in the string.
      selection = [selection]
    if not isinstance(selection, typing.Iterable):
      selection = [selection]
    for item in selection:
      if isinstance(item, ObjectID):
        actual_selection.append(item)
      elif isinstance(item, DataObject):
        actual_selection.append(item.id)
      elif isinstance(item, str):
        actual_selection.append(ObjectID.from_path(item))
      else:
        raise TypeError(default_type_error_message("selection",
                                                   item,
                                                   "ObjectID or DataObject"))
    return ','.join('"%r"' % obj for obj in actual_selection)


class RequestTransactionWithInputsV13(Message):
  """Define the message known as RequestTransactionWithInputs.

  This message can be used to request a transaction in an application.

  This version is needed by PointStudio 2021.1 and later. It approximately
  corresponds to version 1.3 of the API.
  """
  logger = logging.getLogger('mdf.transactions')

  message_name: typing.ClassVar[str] = 'RequestTransactionWithInputs'
  transaction_name: str
  operation_id: ctypes.c_int32 = 0
  operation_command: str
  requester_icon: Icon = ''
  can_confirm_immediately: bool = True
  confirm_immediately: bool = True
  run_silently: bool = True  # Only present in 1.2+.
  pass_all_errors_back_to_requestor: bool = True # Only present in 1.3+
  selection_contains_objects: bool = False
  selection_contains_point_primitives: bool = False
  selection_contains_edge_primitives: bool = False
  selection_contains_facet_primitives: bool = False
  transaction_inputs: JsonValue = []

class OperationCompleted(Message):
  """Define the message known as OperationCompleted.

  This message is sent when a specified transaction has completed.

  It uses the operation_id sent when the transaction was requested to
  determine what request it corresponds with.
  """

  message_name: typing.ClassVar[str] = 'OperationCompleted'

  operation_id: ctypes.c_int32
  operation_command: str
  outputs: JsonValue
  completed_okay: bool

  def send(self, destination):
    raise TypeError("This type of message is a response only. It shouldn't be "
                    "sent.")


class OperationCompletedV13(Message):
  """Define the message known as OperationCompleted.

  This message is sent when a specified transaction has completed.

  It uses the operation_id sent when the transaction was requested to
  determine what request it corresponds with.

  This version is needed by PointStudio 2021.1 and later. It approximately
  corresponds to version 1.3 of the API.
  """

  message_name: typing.ClassVar[str] = 'OperationCompleted'

  operation_id: ctypes.c_int32
  operation_command: str
  outputs: JsonValue
  completed_okay: bool

  # This is only present in 1.3+
  error_message: ReceivedSerialisedText

  def send(self, destination):
    raise TypeError("This type of message is a response only. It shouldn't be "
                    "sent.")


class TransactionInformation(Message):
  """Define the message known as TransactionInformation.

  This message can be used to query information about a transaction
  like what its inputs and outputs are.

  The response to the message is ReturnedTransactionInformation.
  """
  message_name: typing.ClassVar[str] = 'TransactionInformation'

  transaction_name: str
  requester_icon: Icon = ''
  operation_command: str


class ReturnedTransactionInformation(Message):
  """Message representing a response to another message. As this message
  is a response, it cannot be sent.

  """
  message_name: typing.ClassVar[str] = "ReturnedTransactionInformation"

  command_name: str
  transaction_information: JsonValue

  def send(self, destination):
    raise TypeError("This type of message is a response only. It shouldn't be "
                    "sent.")


class TransactionFailed(ValueError):
  def __init__(self, server, transaction, message):
    """General exception raised when a transaction fails to complete."""
    super().__init__(f'Transaction {server}::{transaction} failed to complete '
                     f'successfully. {message}')

class NoProjectError(RuntimeError):
  """Error raised when this module is used without connecting to an application.

  """


class Qualifiers:
  """A factory of qualifiers."""

  @staticmethod
  def label(message):
    qualifier = Qualifier()
    qualifier.key = 'Label'
    qualifier.cumulative = False

    text = SerialisedText("%s", message)
    qualifier.parameters = Qualifier.Parameters(text)
    return qualifier

  @staticmethod
  def title(message):
    qualifier = Qualifier()
    qualifier.key = 'Title'
    qualifier.cumulative = False

    text = SerialisedText("%s", message)
    qualifier.parameters = Qualifier.Parameters(text)
    return qualifier

  @staticmethod
  def message(message):
    qualifier = Qualifier()
    qualifier.key = 'Message'
    qualifier.cumulative = True

    text = SerialisedText("%s", message)
    qualifier.parameters = Qualifier.Parameters(text)
    return qualifier


class Qualifier(InlineMessage):
  """A qualifier is used to attribute a quality to a transaction."""

  class Parameters(SubMessage):
    """The parameters or values of a qualifier."""

    values: RepeatingField[typing.Any]

    def __init__(self, *args):
      self.values = args

  key: str
  cumulative: bool
  parameters: Parameters


class QualifierSet(SubMessage):
  """A set of qualifiers often used with a transaction to qualify it."""
  values: RepeatingField[Qualifier]


class TransactionRequest(Request):
  """Requests a transaction, which is the encapsulation of the concept of a
  transaction between two processes for the provision of specific data or
  specific events.

  For transactions that correspond with menu commands in an application then
  request_transaction() is a far superior option, as it uses the workflow
  system and it is easier to provide inputs and receive outputs.
  """

  class RemoteTransaction(InlineMessage):
    """The response back after requesting a transaction."""
    thread_id: ctypes.c_uint16
    transaction_manager_address: bool
    transaction_address: ctypes.c_uint64
    transaction_token: ctypes.c_uint64
    top_level_transaction_address: ctypes.c_uint64
    top_level_transaction_token: ctypes.c_uint64

  message_name: typing.ClassVar[str] = 'TransactionRequest'
  response_type = RemoteTransaction

  transaction: str
  qualifiers: QualifierSet

  # This optionally has a context that can be provided.
  # At this time we don't have a use for this.
  # context: Context = None


def request_transaction(server, transaction, command_name, inputs, wait=True,
                        requester_icon='', confirm_immediately=True):
  """Request a transaction on the given server.

  Parameters
  ----------
  server : str
    The name of the server that serves the transaction. Or at least the server
    that can launch it.
  transaction : str
    The name of the transaction.
  command_name : str
    A name of the command that the transaction represents. The name is a list
    of names separated by a full stop and loosely forms a hierarchy.
    Examples:
      Maptek.PointStudio.Python.Commands.Despike
      Maptek.PointStudio.Python.Commands.SimplifyByDistanceError
      Maptek.Common.Python.Commands.NewView
  inputs : list
    A list of (name, value) pairs that provide the values for the transaction.
  wait : bool
    If True then the function waits until the transaction is complete before
    returning, otherwise it won't wait and it will return immediately.
  requester_icon : str
    The behaviour of transactions can change depending on the icon provided.
    This is typically done as a way to reduce code duplication where having
    two transactions with a small difference would be unnecessary.
  confirm_immediately : bool
    If the transaction should be confirmed immediately. Default is True.

  Returns
  ----------
  list
    The outputs of the transaction.

  Raises
  ------
  TransactionFailed
    If the transaction was unable to complete successfully.
  """

  # We could loosen the following if we checked the version and removed the
  # run_silently field in that case.
  try:
    raise_if_version_too_old(
      "Running operations",
      current_version=Mcpd().version,
      required_version=(1, 2))
  except CApiDllLoadFailureError as error:
    raise NoProjectError(
      "Failed to load the required DLLs. You must connect to an application "
      "via Project() before using this module.") from error

  is_new_version = Mcpd().version >= (1, 3)
  if is_new_version:
    request_type = RequestTransactionWithInputsV13
    response_type = OperationCompletedV13
  else:
    request_type = RequestTransactionWithInputs
    response_type = OperationCompleted

  request = request_type()
  request.transaction_name = transaction
  request.requester_icon = requester_icon
  if wait:
    request.operation_id = next(NEXT_OPERATION_ID)
  else:
    request.operation_id = 0
  request.operation_command = command_name
  request.confirm_immediately = confirm_immediately
  request.transaction_inputs = [
    {'name': name, 'value': value} for name, value in inputs
    ]

  if not wait:
    request.send(server)
    return

  # The process is as follows:
  # - Register a callback for receiving the completed message.
  # - Request the transaction.
  # - Wait for the transaction to complete.

  completed = threading.Event()
  information = None

  def on_message_received(message_handle):
    """Called when the message of the expected name is received.

    The message is read out and the correpsonding Python message object is
    created.
    """

    nonlocal information
    information = response_type.from_handle(message_handle)
    Mcpd().dll.McpFreeMessage(message_handle)

    if information.operation_id == request.operation_id:
      completed.set()

  on_message_callback = Mcpd().dll.Callback(on_message_received)

  callback_handle = Mcpd().dll.McpAddCallbackOnMessage(
    response_type.message_name.encode('utf-8'),
    on_message_callback,
  )

  # Request the transaction.
  request.send(server)

  # Wait for the transaction to be completed.
  while not completed.is_set():
    Mcpd().dll.McpServicePendingEvents()

  Mcpd().dll.McpRemoveCallback(callback_handle)

  # Read the result.
  response = information

  assert response.operation_id == request.operation_id
  assert response.operation_command == request.operation_command

  if not response.completed_okay:
    if is_new_version:
      error_message = response.error_message
    else:
      error_message = SerialisedText("%s", 'Check application for error')
    raise TransactionFailed(server, transaction, error_message)

  return response.outputs
