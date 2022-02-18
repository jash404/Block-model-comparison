"""The ConnectorType interface.

Classes which implement this interface can be passed to WorkflowArgumentParser
as connector types.

"""
###############################################################################
#
# (C) Copyright 2021, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

class ConnectorType:
  """Interface for classes representing connector types.

  Classes which implement this interface can be passed as types for
  WorkflowArgumentParser.declare_input_connector() and
  WorkflowArgumentParser.declare_output_connector().

  """
  @classmethod
  def type_string(cls):
    """The string representation of the type to report to the Workflow
    as the type for the Connector.

    Returns
    -------
    str
      String representation of the type to report to the workflow.

    """
    raise NotImplementedError

  @classmethod
  def from_string(cls, string_value):
    """Convert a string value from an input connector to the corresponding
    python type and returns it.

    Returns
    -------
    any
      The python representation of the string value.

    Raises
    ------
    TypeError
      If string_value is not a supported type.
    ValueError
      If string_value is the correct type but an invalid value.

    """
    raise NotImplementedError

  @classmethod
  def to_json(cls, value):
    """Converts the value to a json-serializable value.

    This is used to convert python values to json values to be passed
    to the workflow for output connectors.

    Returns
    -------
    json-serializable
      Json serializable representation of value.

    Raises
    ------
    TypeError
      If value is not a supported type.
    ValueError
      If value is the correct type but an invalid value.

    """
    raise NotImplementedError

  @classmethod
  def to_default_json(cls, value):
    """Converts the value to a json serializable default.

    This allows for specifying a different representation for default
    values. The output of this function should not include lists.

    Overwrite this function to raise an error to indicate that default
    values are not supported.

    By default this calls to_json.

    Returns
    -------
    str
      String representation of value.

    Raises
    ------
    TypeError
      If value is not a supported type.
    ValueError
      If value is the correct type but an invalid value.

    """
    return cls.to_json(value)
