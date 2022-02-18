"""Operations available in Vulcan GeologyCore.

Operations exposes functionality from within an application that can be
invoked from Python functions. These typically correspond to menu items that
are available in the application, but their inputs can be populated from Python
without requiring the user to fill them out.

"""

###############################################################################
#
# (C) Copyright 2021, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

from mapteksdk.common import convert_to_rgba
from mapteksdk.internal.transaction import (request_transaction,
                                            RequestTransactionWithInputs)
# pylint: disable=unused-import
# Import general operations so that they can be imported from this module.
from mapteksdk.operations import (TooOldForOperation,
                                  PickFailedError, SelectablePrimitiveType,
                                  Primitive, open_new_view, opened_views,
                                  active_view, active_view_or_new_view,
                                  coordinate_pick, object_pick,
                                  primitive_pick, write_report,
                                  _decode_selection)
from mapteksdk.pointstudio.operations import TriangulationOutput


COMMAND_PREFIX = 'Maptek.GeologyCore.Python.Commands'

def topographic_triangulation(
    scans,
    trim_edges_to_maximum_length=None,
    output_option=TriangulationOutput.SINGLE_SURFACE,
    relimit_to_polygon=None,
    edge_constraints=None,
    destination=''):
  """Create triangulations (surfaces) of a group of scans.

  This works in the XY plane, that is, it triangulates straight down.
  This means that if there are areas of undercut walls, these will not
  be modelled accurately.

  This option is typically used once scans have been registered and filtered.

  Parameters
  ----------
  scans : list
    The list of scan objects to triangulate.
  trim_edges_to_maximum_length : float or None
    If not None, then long, incorrectly generated boundary triangles will be
    eliminated. A maximum length is specified, which prevents triangles
    greater than this being created.
    This option is only applicable to boundary triangles; large voids in the
    centre of the data will still be modelled.
  output_option : TriangulationOutput
    If SINGLE_SURFACE, then this creates a single surface from the selected
    objects/scans.
    If SURFACE_PER_OBJECT, then this creates a single surface for each
    selected object/scan.
    If SPLIT_ALONG_EDGE_CONSTRAINTS, then splits the triangulation into
    separate objects based on any lines or polygons provided by
    edge_constraints.
  relimit_to_polygon : ObjectID or None
    Constrains the model to a polygon, for example a pit boundary.
    The output_option must be RELIMIT_TO_POLYGON to use this.
  edge_constraints : list or None
    The lines and polygons to use when splitting the triangulation into
    separate objects. The output_option must be SPLIT_ALONG_EDGE_CONSTRAINTS
    to use this.
  destination : str
    An optional path to the container to store the resulting triangulations.
    The empty string will use a default path.
  """

  if relimit_to_polygon and \
      output_option is not TriangulationOutput.RELIMIT_TO_POLYGON:
    raise ValueError('If providing a polygon to relimit to, the output_option '
                     'should be RELIMIT_TO_POLYGON')

  if edge_constraints and \
      output_option is not TriangulationOutput.SPLIT_ALONG_EDGE_CONSTRAINTS:
    raise ValueError('If providing the edges for edge constraints, the '
                     'output_option should be SPLIT_ALONG_EDGE_CONSTRAINTS')

  inputs = [
    ('selection',
     RequestTransactionWithInputs.format_selection(
       scans + (edge_constraints or []))),
  ]

  if destination:
    inputs.append(('destination', destination))

  if trim_edges_to_maximum_length is None:
    inputs.append(('trimBoundaryTriangles', 'false'))
  else:
    inputs.extend([
      ('trimBoundaryTriangles', 'true'),
      ('trimBoundaryTriangles/maximumEdgeLength',
       str(trim_edges_to_maximum_length)),
    ])

  if output_option is TriangulationOutput.SINGLE_SURFACE:
    inputs.extend([
      ('singleSurface', 'true'),
      ('singleSurfacePerObject', 'false'),
      ('relimitToPolygon', 'false'),
      ('splitAlongEdgeConstraints', 'false'),
    ])
  elif output_option is TriangulationOutput.SURFACE_PER_OBJECT:
    inputs.extend([
      ('singleSurface', 'true'),
      ('singleSurfacePerObject', 'false'),
      ('relimitToPolygon', 'false'),
      ('splitAlongEdgeConstraints', 'false'),
    ])
  elif output_option is TriangulationOutput.SPLIT_ALONG_EDGE_CONSTRAINTS:
    inputs.extend([
      ('singleSurface', 'false'),
      ('singleSurfacePerObject', 'false'),
      ('relimitToPolygon', 'false'),
      ('splitAlongEdgeConstraints', 'true'),
    ])
  elif output_option is TriangulationOutput.RELIMIT_TO_POLYGON:
    inputs.extend([
      ('singleSurface', 'false'),
      ('singleSurfacePerObject', 'false'),
      ('relimitToPolygon', 'true'),
      ('splitAlongEdgeConstraints', 'false'),
      ('relimitToPolygon/relimitPolygon', repr(relimit_to_polygon)),
    ])

  request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_Triangulation2DTransaction',
    command_name='{0}.TopographicTriangulation'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

def boundary_edges(selection, merge_boundaries=False):
  """Finds boundary edges for objects in the selection.

  This creates either a single edge network or multiple polylines which
  represent the edges of the objects in the selection.

  Parameters
  ----------
  selection : list
    List of paths or object ids of the objects to find the boundary edges
    for.
  merge_boundaries : bool
    If True, all boundary edges are combined into a single edge network.
    If False, each boundary edge is a polygon. They are coloured green for
    edges around the perimeter of the object and red if they are edges
    around holes in the object.

  Returns
  -------
  WorkflowSelection
    Selection containing the created objects.
    If merge_boundaries is True, this will contain between zero and
    len(selection) objects.
    if merge_boundaries is False, this can contain any number of objects.

  Raises
  ------
  TransactionFailed
    If no object in selection is a Surface or Discontinuity.

  Warnings
  --------
  This operation will enter an infinite loop if all objects in the selection
  are surfaces which do not contain boundary edges.

  """
  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(selection)),
    ('Combine output', 'true' if merge_boundaries else 'false')
  ]

  outputs = request_transaction(
    server='cadServer',
    transaction='mtp::cadS_FindBoundaryEdgesTransaction',
    command_name='{0}.Boundaries'.format(COMMAND_PREFIX),
    inputs=inputs)

  return _decode_selection(outputs)

def contour_surface(surfaces, lower_limit, upper_limit,
                    major_contour_intervals=15.0,
                    major_contour_colour=(0, 255, 255, 255),
                    minor_contour_intervals=None,
                    minor_contour_colour=(255, 0, 127, 255),
                    destination_path=None):
  """Create contours from surfaces (triangulations), which are then saved into
  an edge network object.

  Parameters
  ----------
  surfaces : list
    The list of surfaces to contour.
  lower_limit : float
    The minimum value of the contours (the lowest elevation).
  upper_limit : float
    The maximum value of the contours (the highest elevation).
  major_contour_intervals : float
    The difference in elevation between major contour lines.
  major_contour_colour : sequence
    The colour of the major contour lines. This may be a RGB colour
    [red, green, blue] or a RGBA colour [red, green, blue, alpha].
  minor_contour_intervals : float or None
    If None then no minor contours lines will be included.
    The difference in elevation between minor contour lines between
    the major contour lines.
  minor_contour_colour : sequence
    The colour of the minor contour lines. This may be a RGB colour
    [red, green, blue] or a RGBA colour [red, green, blue, alpha].
    This is only relevant if minor_contour_intervals is not None.
  destination_path : str
    The path to where the contours should be written.
    If None then the default path will be used.

  Returns
  -------
  list
    The list of edge networks created that contain the resulting the contour
    lines if there are no minor contour lines. Otherwise a list of containers
    each containing the set of major and minor contour lines will be provided.

  Raises
  ------
  ValueError
    If a colour cannot be converted to a valid RGBA colour.
  ValueError
    If lower_limit is greater than upper_limit. You may have simply passed the
    arguments in the wrong way around.
  """

  if lower_limit > upper_limit:
    raise ValueError(f'The lower limit is greater ({lower_limit:.3f}) than '
                     f'the upper limit ({upper_limit:.3f})')

  def _format_colour(colour):
    """Format a single colour for use as the value for a workflow input."""
    rgba_colour = convert_to_rgba(colour)
    return '({},{},{},{})'.format(*rgba_colour)

  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(surfaces)),
    ('lowerLimit', '(0.0, 0.0, %f)' % lower_limit),
    ('upperLimit', '(0.0, 0.0, %f)' % upper_limit),
    ('manualContours', 'true'),
    ('manualContours/majorColour', _format_colour(major_contour_colour)),
    ('manualContours/majorInterval', str(major_contour_intervals)),
  ]

  if minor_contour_intervals is not None:
    inputs.extend([
      ('manualContours/minorContours', 'true'),
      ('manualContours/minorContours/minorInterval',
       str(minor_contour_intervals)),
      ('manualContours/minorContours/minorColour',
       _format_colour(minor_contour_colour)),
    ])

  if destination_path:
    inputs.append(('destination', destination_path))

  outputs = request_transaction(
    server='sdpServer',
    transaction='::sdpS_ContourFacetNetworkTransaction',
    command_name='{0}.ContourSurface'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

  return _decode_selection(outputs)

def loop_surface_straight(selection, destination=None):
  """Create a Surface from a series of loops using "straight loop ordering".

  This creates a single Surface with the loops connected based on
  their orientation.

  Parameters
  ----------
  selection : list
    List of Surfaces or Polygons to use to generate the loop surface.
    Each must contain loops.
  destination : str
    Path to place the destination object. If not specified,
    this will use the default destination of the menu item.

  Returns
  -------
  WorkflowSelection
    Selection containing the created Surface.

  """
  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(selection)),
    ('straightLoopOrdering', 'true'),
    ('iterativeLoopOrdering', 'false'),
  ]

  if destination:
    inputs.append(('destination', destination))

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_TriangulateLoopSetTransaction',
    command_name='{0}.TriangulateLoopSet'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

  return _decode_selection(outputs)


def loop_surface_iterative(selection, destination=None):
  """Creates Surfaces from a series of loops using "iterative loop ordering".

  This joins nearby loops with similar orientations. This can create
  multiple surfaces and may wrap around corners if needed.

  Unlike loop_surface_straight this may ignore loops if they are not
  sufficiently close to another loop.

  Parameters
  ----------
  selection : list
    List of Surfaces or Polygons to use to generate the loop surfaces.
    Each must contain loops.
  destination : str
    Path to place the destination object. If not specified,
    this will use the default destination of the menu item.

  Returns
  -------
  WorkflowSelection
    Selection containing the created Surface(s).

  """
  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(selection)),
    ('straightLoopOrdering', 'false'),
    ('iterativeLoopOrdering', 'true'),
  ]

  if destination:
    inputs.append(('destination', destination))

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_TriangulateLoopSetTransaction',
    command_name='{0}.TriangulateLoopSet'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

  return _decode_selection(outputs)
