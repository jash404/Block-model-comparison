"""Module containing the enum used to set the method used by generated
connectors to match their values.
"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################
import enum

class MatchAttribute(enum.Enum):
  """Enum of possible matching types for generated connectors.

  Examples
  --------
  This script creates one connector which uses each matching scheme.

  >>> from mapteksdk.workflows import (WorkflowArgumentParser, MatchAttribute,
  ...                                  WorkflowSelection, Point3DConnectorType,
  ...                                  BooleanConnectorType)
  >>> parser = WorkflowArgumentParser("Example attribute matching")
  >>> parser.declare_input_connector(
  ...     "selection",
  ...     WorkflowSelection,
  ...     connector_name="Selection",
  ...     matching=MatchAttribute.BY_NAME)
  >>> parser.declare_input_connector(
  ...     "centroid",
  ...     Point3DConnectorType,
  ...     connector_name="Centroid",
  ...     matching=MatchAttribute.BY_TYPE)
  >>> parser.declare_input_connector(
  ...     "overwrite",
  ...     BooleanConnectorType,
  ...     connector_name="Overwrite",
  ...     matching=MatchAttribute.DO_NOT_MATCH)
  >>> parser.parse_arguments()
  >>> # Do something useful with the arguments.

  """
  BY_TYPE = 0
  """The attribute will be matched by type.

  Matching by type is preferable when connecting the side connectors in
  workflows. This allows connectors with different names to be connected
  (e.g. an output connector of type MaptekDatabaseObject called
  "surfaces" to be connected to a MaptekDatabaseObject input connector
  called "selection").

  This does not work well with top connectors. If more than one connector share
  a type, then the matching is ambiguous.
  """
  BY_NAME = 1
  """The attribute will be matched by name.

  Matching by name is preferable when connecting the top connectors in
  workflows. This prevents incorrect matching when there are multiple
  attributes with the same type, however it means that the names
  of the input connector must exactly match the name of the output connector.
  This typically encourages poor naming conventions (for example,
  calling all connectors of type MaptekDatabaseObject "selection" when
  a more specific name would be more useful).

  This does not work well with side connectors, because the connection
  will fail if the names of the input and output connectors do not
  match.
  """
  DO_NOT_MATCH = 2
  """The attribute will not be matched.

  This means this connector ignores connections to other workflow components.
  The value is provided when the workflow is designed and cannot be changed
  at runtime.

  This is useful for configuration where it does not make sense
  for it to be generated by other components (e.g. a search width for a
  clustering algorithm). This can prevent errors due to accidental name or type
  clashes. Typically connectors which use this matching should have a default
  value supplied.
  """
