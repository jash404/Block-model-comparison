"""Basic connector type subclasses.

These can be passed to WorkflowArgumentParser.declare_input_connector
and WorkflowArgumentParser.declare_output_connector to determine which
type of data the connector should accept. The names of these classes
match the names of the connectors types as displayed in workflows.

"""
###############################################################################
#
# (C) Copyright 2021, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import csv
import datetime
from typing import Iterable

import numpy as np

from .connector_type import ConnectorType
from ..internal.util import default_type_error_message

def python_type_to_connector_type(python_type):
  """Returns the corresponding ConnectorType subclass for a Python type.

  This only contains mappings for the ConnectorType subclasses
  defined in this file.

  Parameters
  ----------
  python_type : Type
    The Python type to match to a basic connector type.

  Returns
  -------
  ConnectorType
    The corresponding ConnectorType subclass from this file.

  Raises
  ------
  KeyError
    If there was no corresponding ConnectorType subclass.

  """
  type_mapping = {
    str: StringConnectorType,
    int: IntegerConnectorType,
    float: DoubleConnectorType,
    bool: BooleanConnectorType,
    list: CSVStringConnectorType,
    datetime.datetime: DateTimeConnectorType,
    None: AnyConnectorType
  }
  return type_mapping[python_type]

class AnyConnectorType(ConnectorType):
  """Connector type representing no connector type set.

  This corresponds to the connector type being blank on the workflows
  side. Input connectors of this type will accept any value from other
  connectors and the string representation of that value will be returned.
  Output connectors of this type will accept any value which can be converted
  into a string.

  """
  @classmethod
  def type_string(cls):
    return ""

  @classmethod
  def from_string(cls, string_value):
    return string_value

  @classmethod
  def to_json(cls, value):
    return str(value)

class StringConnectorType(ConnectorType):
  """Connector type corresponding to String on the workflows side
  and str on the Python side.

  This can be passed to declare_input_connector or declare_output_connector
  to declare the connector type as String. Passing the python type str
  is equivalent to passing this class.

  Examples
  --------
  This example sets the output connector "reversed" to contain a reversed
  version of the string from the input connector "string"

  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  StringConnectorType)
  >>> parser = WorkflowArgumentParser()
  >>> parser.declare_input_connector("string", StringConnectorType)
  >>> parser.declare_output_connector("reversed", StringConnectorType)
  >>> parser.parse_arguments()
  >>> parser.set_output("reversed", parser["string"][::-1])

  """
  @classmethod
  def type_string(cls):
    return "String"

  @classmethod
  def from_string(cls, string_value):
    return string_value

  @classmethod
  def to_json(cls, value):
    return str(value)

class IntegerConnectorType(ConnectorType):
  """Connector type corresponding to Integer on the workflows side and
  int on the Python side. Passing the connector type as int is equivalent to
  passing this to declare_input/output_connector.

  Examples
  --------
  This example creates a workflow component with an Integer
  input and output connector. The output connector "new_count" is set to the
  value of the input connector "count" plus one.

  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  IntegerConnectorType)
  >>> parser = WorkflowArgumentParser()
  >>> parser.declare_input_connector("count", IntegerConnectorType)
  >>> parser.declare_output_connector("new_count", IntegerConnectorType)
  >>> parser.parse_arguments()
  >>> parser.set_output("new_count", parser["count"] += 1)

  """
  @classmethod
  def type_string(cls):
    return "Integer"

  @classmethod
  def from_string(cls, string_value):
    return int(string_value)

  @classmethod
  def to_json(cls, value):
    return int(value)

class DoubleConnectorType(ConnectorType):
  """Connector type corresponding to Double on the workflows side and
  float on the Python side. Passing the connector type as float is equivalent
  to passing this to declare_input/output_connector.

  Examples
  --------
  This example sets the value of the output connector "x_over_2" to the value
  of the input connector "x" divided by two.

  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  DoubleConnectorType)
  >>> parser = WorkflowArgumentParser()
  >>> parser.declare_input_connector("x", DoubleConnectorType)
  >>> parser.declare_output_connector("x_over_2", DoubleConnectorType)
  >>> parser.parse_arguments()
  >>> parser.set_output("x_over_2", parser["x"] / 2)

  """
  @classmethod
  def type_string(cls):
    return "Double"

  @classmethod
  def from_string(cls, string_value):
    return float(string_value)

  @classmethod
  def to_json(cls, value):
    return float(value)

class BooleanConnectorType(ConnectorType):
  """Connector type corresponding to Boolean on the workflows side and
  bool on the Python side. Passing the connector type as bool is equivalent
  to passing this to declare_input/output_connector.

  Examples
  --------
  This example sets the output connector "not x" to be the inverse of the
  value passed to the "x" input connector.

  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  IntegerConnectorType)
  >>> parser = WorkflowArgumentParser()
  >>> parser.declare_input_connector("x", BooleanConnectorType)
  >>> parser.declare_output_connector("not x", BooleanConnectorType)
  >>> parser.parse_arguments()
  >>> parser.set_output("not x", not parser["x"])

  """
  @classmethod
  def type_string(cls):
    return "Boolean"

  @classmethod
  def from_string(cls, string_value):
    return bool(string_value)

  @classmethod
  def to_json(cls, value):
    return bool(value)

class CSVStringConnectorType(ConnectorType):
  """Connector type coresponding to CSV String on the workflows side
  and list on the Python side. Passing the connector type as list is
  equivalent to passing this to declare_input/output_connector.

  Examples
  --------
  This example filters out every second element in the list from the
  input connector "values" and sets the filtered list to the output connector
  "second_values".

  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  CSVStringConnectorType)
  >>> parser = WorkflowArgumentParser()
  >>> parser.declare_input_connector("values", CSVStringConnectorType)
  >>> parser.declare_output_connector("second_values", CSVStringConnectorType)
  >>> parser.parse_arguments()
  >>> parser.set_output("second_values", parser["values"][::2])

  """
  @classmethod
  def type_string(cls):
    return "List"

  @classmethod
  def from_string(cls, string_value):
    if not isinstance(string_value, str):
      raise TypeError(default_type_error_message("string_value",
                                                 string_value,
                                                 str))
    # Strip off the first and last character if they are brackets.
    if string_value.startswith("[") and string_value.endswith("]"):
      string_value = string_value[1:-1]
    elif string_value.startswith("(") and string_value.endswith(")"):
      string_value = string_value[1:-1]

    # Use csv reader to parse the comma separated string and take the first
    # line. This should work as long as there are no new lines in the list.
    return list(csv.reader([string_value], skipinitialspace=True))[0]

  @classmethod
  def to_json(cls, value):
    return list(value)

  @classmethod
  def to_default_json(cls, value):
    if not isinstance(value, Iterable):
      # Can't pass typing.Iterable here because it is not a type.
      raise TypeError(default_type_error_message("list default",
                                                 value,
                                                 list))
    return ",".join([str(x) for x in value])

class DateTimeConnectorType(ConnectorType):
  """Connector type corresponding to Date Time on the Workflows side
  and datetime.datetime on the Python side. Passing the connector type as
  datetime.datetime is equivalent to passing this to
  declare_input/output_connector.

  This does not currently support defaults.

  Examples
  --------
  This example adds 24 hours to the time from the input connector "today" and
  sets that time to the output connector "tomorrow".
  Note that this may not give the same time on the next day due to
  daylight savings start/ending.

  >>> import datetime
  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  DateTimeConnectorType)
  >>> parser = WorkflowArgumentParser()
  >>> parser.declare_input_connector("today", DateTimeConnectorType)
  >>> parser.declare_output_connector("tomorrow", DateTimeConnectorType)
  >>> parser.parse_arguments()
  >>> tomorrow = parser["today"] + datetime.timedelta(days=1)
  >>> parser.set_output("tomorrow", tomorrow)

  """
  @classmethod
  def type_string(cls):
    return "DateTime"

  @classmethod
  def from_string(cls, string_value):
    if not isinstance(string_value, str):
      raise TypeError(default_type_error_message("string_value",
                                                 string_value,
                                                 str))
    string_value = string_value.strip('"\'')
    return datetime.datetime.fromisoformat(string_value)

  @classmethod
  def to_json(cls, value):
    if isinstance(value, str):
      try:
        datetime.datetime.fromisoformat(value)
      except ValueError as error:
        message = f"Invalid datetime string: {value}. Must be ISO-8601 format."
        raise ValueError(message) from error
      return value
    try:
      return value.isoformat()
    except AttributeError as error:
      raise TypeError(default_type_error_message("value",
                                                 value,
                                                 datetime.datetime)) from error

  @classmethod
  def to_default_json(cls, value):
    raise TypeError("Default value for datetime is not supported.")

class Point3DConnectorType(ConnectorType):
  """Connector type representing a 3D point in workflows.

  An input connector of this type will return a numpy array of floats with
  shape (3, ) representing the point in the form [X, Y, Z].

  Default values can be specified using any iterable as long as its length
  is three and all values can be converted to floats, though list or numpy
  arrays are generally preferable.

  Given a script called "script.py" with an input connector of type
  Point3DConnectorType called "point", to pass the point [1.2, 3.4, -1.3]
  via the command line you would type:

  >>> py script.py --point=(1.2,3.4,-1.3)

  Examples
  --------
  This example sets the output connector "inverted_point" to the inverse of the
  point from the input connector "point".

  >>> from mapteksdk.workflows import (WorkflowArgumentParser,
  ...                                  Point3DConnectorType)
  >>> parser = WorkflowArgumentParser()
  >>> parser.declare_input_connector("point", Point3DConnectorType)
  >>> parser.declare_output_connector("inverted_point", Point3DConnectorType)
  >>> parser.parse_arguments()
  >>> parser.set_output("inverted_point", -parser["point"])

  """
  @classmethod
  def type_string(cls):
    return "Point3D"

  @classmethod
  def from_string(cls, string_value):
    if not isinstance(string_value, str):
      raise TypeError(default_type_error_message("string_value",
                                                 string_value,
                                                 str))
    ordinates = string_value.strip("()").split(",")
    point = np.zeros((3,), float)
    point[:] = ordinates
    return point

  @classmethod
  def to_json(cls, value):
    middle = ", ".join([str(float(x)) for x in value])
    return f"({middle})"
