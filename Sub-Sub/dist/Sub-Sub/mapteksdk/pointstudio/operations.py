"""Operations available in PointStudio.

Operations exposes functionality from within an application that can be
invoked from Python functions. These typically correspond to menu items that
are available in the application, but their inputs can be populated from Python
without requiring the user to fill them out.

Available operations from PointStudio include contouring, triangulating a
surface, simplifying a surface, filtering points.
"""

###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import enum
import numpy

from mapteksdk.common import convert_to_rgba
from mapteksdk.data.colourmaps import NumericColourMap
from mapteksdk.internal.transaction import (request_transaction,
                                            RequestTransactionWithInputs)
# pylint: disable=unused-import
# Import operations which were moved to mapteksdk.operations for
# backwards compatability.
from mapteksdk.operations import (_decode_selection, TooOldForOperation,
                                  PickFailedError, SelectablePrimitiveType,
                                  Primitive, open_new_view, opened_views,
                                  active_view, active_view_or_new_view,
                                  coordinate_pick, object_pick,
                                  primitive_pick, write_report)

COMMAND_PREFIX = 'Maptek.PointStudio.Python.Commands'

class DistanceMeasurementTarget(enum.Enum):
  """If there are multiple objects to measure the distance to this specifies
  how it should be done."""
  CLOSEST_OBJECT = 1
  AVERAGE = 2


class DistanceType(enum.Enum):
  """Specifies whether distances should be considered as a signed or absolute.
  """
  SIGNED = 1
  ABSOLUTE = 2


class TriangulationOutput(enum.Enum):
  """Specifies what the output of a triangulation should be."""
  SINGLE_SURFACE = 1
  SURFACE_PER_OBJECT = 2
  SPLIT_ALONG_EDGE_CONSTRAINTS = 3  # The edges will be specified separately.
  RELIMIT_TO_POLYGON = 4  # The polygon will be specified separately.


class MaskOperation(enum.Enum):
  """Specifies how an operation should act with existing data.

  This is typically used for filtering operations.
  """
  AND = 1
  OR = 2
  REPLACE = 3

  def format_to_operation_string(self):
    """Format the value as expected by an operation input."""
    if self is self.AND:
      return 'And'
    if self is self.OR:
      return 'Or'
    if self is self.REPLACE:
      return 'Replace'

    raise ValueError('Unknown value %s' % self.value)


def colour_by_distance_from_object(objects_to_colour,
                                   base_objects,
                                   measurement_target,
                                   distance_type,
                                   legend):
  """Colour points based on their (signed) distance from a base or reference
  objects.

  This is useful for comparing triangulations of as-built surfaces against
  design models to highlight nonconformance. It can also be used to visualise
  areas of change between scans of the same area, for example a slow moving
  failure in an open pit mine.

  Parameters
  ----------
  objects_to_colour : list
    The list of objects to colour.
  base_objects : list
    The list of base or reference objects to measure the distance from.
  measurement_target : DistanceMeasurementTarget
    If CLOSEST_OBJECT then colouring is based on the closest base object to
    that point.
    If AVERAGE then colour is based on the average distance to every base
    object.
  distance_type : DistanceType
    If SIGNED then colouring will depend on which side of the base objects it is
    on.
    If ABSOLUTE then colouring will depend on the absolute distance.
  legend : ObjectID
    A numeric 1D colour map to use as the legend for colouring the object.
  """

  if not legend.is_a(NumericColourMap):
    raise TypeError('The legend must be a numeric colour map')

  format_selection = RequestTransactionWithInputs.format_selection

  inputs = [
    ('selection', format_selection(objects_to_colour)),
    # The typo of objects below is required and is expected by the transaction.
    ('baseObects', format_selection(base_objects)),
    ('legend', repr(legend)),
    ('Closest object',
     measurement_target is DistanceMeasurementTarget.CLOSEST_OBJECT),
    ('Average', measurement_target is DistanceMeasurementTarget.AVERAGE),
    ('Signed', distance_type is DistanceType.SIGNED),
    ('Absolute', distance_type is DistanceType.ABSOLUTE),
  ]

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_ColourDistanceFromSurfaceTransaction',
    command_name='{0}.ColourByDistance'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

  for output in outputs.value:
    if output['idPath'] == 'distance':
      mean_distance = float(output.get('value', 'NaN'))
      break
  else:
    mean_distance = None

  return {
    'selection': _decode_selection(outputs),
    'mean_distance': mean_distance,
  }


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
  ----------
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
    ('majorColour', _format_colour(major_contour_colour)),
    ('majorInterval', str(major_contour_intervals)),
  ]

  if minor_contour_intervals is not None:
    inputs.extend([
      ('useMinorContours', 'true'),
      ('useMinorContours/minorInterval', str(minor_contour_intervals)),
      ('useMinorContours/minorColour',
       _format_colour(minor_contour_colour)),
    ])

  if destination_path:
    inputs.append(('destination', destination_path))

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_ContourFacetNetworkTransaction',
    command_name='{0}.ContourSurface'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

  return _decode_selection(outputs)

def fill_holes(surfaces):
  """Fills holes that may appear when editing a surface (triangulation).

  Parameters
  ----------
  surfaces : list
    The list of surfaces to have holes filled in.
  """

  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(surfaces)),
  ]

  request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_FillHolesTransaction',
    command_name='{0}.FillHoles'.format(COMMAND_PREFIX),
    inputs=inputs,
    )


def filter_by_polygon(scans,
                      polygon,
                      extrusion_direction=(0, 0, 1),
                      keep_points_inside=True,
                      filter_combination=MaskOperation.AND):
  """Filter scan data specified by a polygon and retain points inside or
  outside the polygon.

  Parameters
  ----------
  scans : list
    The list of scans to which the filter should be applied.
  polygon : ObjectID
    The polygons by which to filter
  extrusion_direction : list of three floats
    The direction of the polygon extrusions.
  keep_points_inside : bool
    If true then points inside the polygon region are kept, otherwise
    points outside the polygon region are kept.
  filter_combination : MaskOperation
    Specify how to combine this filter with any filter previously applied to
    the selected data.

  Raises
  ------
  ValueError
    If extrusion_direction is not a three dimensional vector.
  """
  format_selection = RequestTransactionWithInputs.format_selection

  if numpy.shape(extrusion_direction) != (3,):
    raise ValueError('The extrusion direction must be a vector with a X, Y '
                     'and Z component.')

  inputs = [
    ('selection', format_selection(scans)),
    ('polygon', repr(polygon)),
    ('direction', '({}, {}, {})'.format(*extrusion_direction)),
    ('Inside', 'true' if keep_points_inside else 'false'),
    ('Outside', 'false' if keep_points_inside else 'true'),
    ('maskOperation', filter_combination.format_to_operation_string()),
  ]

  request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_MaskByPolygonTransaction',
    command_name='{0}.FilterPolygon'.format(COMMAND_PREFIX),
    inputs=inputs,
    )


def filter_isolated_points(scans,
                           point_separation,
                           filter_combination=MaskOperation.AND):
  """Filter point that are a large distance from any other points. This can
  be useful for filtering dust particles or insects that may have been scanned.

  Parameters
  ----------
  scans : list
    The list of scans to which the filter should be applied.
  point_separation : float
    Points without a neighbouring point within this distance will be filtered.
    Any points separated by less than this distance will be retained.
    This distance should be in metres.
  filter_combination : MaskOperation
    Specify how to combine this filter with any filter previously applied to
    the selected data.
  """

  format_selection = RequestTransactionWithInputs.format_selection

  inputs = [
    ('selection', format_selection(scans)),
    ('pointSeparation', str(point_separation)),
    ('maskOperation', filter_combination.format_to_operation_string()),
  ]

  request_transaction(
    server='sdpServer',
    transaction='::sdpS_MaskOutlierTransaction',
    command_name='{0}.FilterIsolatedPoints'.format(COMMAND_PREFIX),
    inputs=inputs,
    )


def filter_minimum_separation(scans,
                              minimum_distance,
                              filter_combination=MaskOperation.AND,
                              treat_scans_separately=False):
  """Filter point sets to give a more even distribution. Point density
  decreases as the distance from the scanner increases, so this option is able
  to reduce the number of points close to the scanner whilst retaining points
  further away.

  Data reduction can have a major impact on the number of points in an object
  and on the modelling processes.

  Parameters
  ----------
  scans : list
    The list of scans to which the filter should be applied.
  minimum_distance : float
    The average minimum separation between points in the object. This distance
    should be in metres.
  filter_combination : MaskOperation
    Specify how to combine this filter with any filter previously applied to
    the selected data.
  treat_scans_separately : bool
    Treat scans separately such that each scan is considered in isolation.
    Otherwise it works on all objects as a complete set which results in an
    even distribution of data for the entire set of objects.
  """

  format_selection = RequestTransactionWithInputs.format_selection

  inputs = [
    ('selection', format_selection(scans)),
    ('minimumDistance', str(minimum_distance)),
    ('maskOperation', filter_combination.format_to_operation_string()),
    ('Apply filter to selection as a whole',
     'false' if treat_scans_separately else 'true'),
  ]

  request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_MaskMinimumSeparationTransaction',
    command_name='{0}.FilterMinimumSeparation'.format(COMMAND_PREFIX),
    inputs=inputs,
    )


def filter_topography(scans,
                      search_cell_size,
                      keep_lower_points=True,
                      filter_combination=MaskOperation.AND,
                      treat_scans_separately=False):
  """Filter point sets to remove unwanted features. This enables equipment such
  as trucks and loaders to be filtered and retains only the relevant
  topographic surface of the mine.

  The topography filter divides the scan data into a horizontal grid with a
  defined cell size. Only the single lowest or highest point in the cell is
  retained.

  Data reduction can have a major impact on the number of points in an object
  and on the modelling processes.

  Parameters
  ----------
  scans : list
    The list of scans to which the filter should be applied.
  search_cell_size : float
    The size of the cells. A typical cell size is between 0.5 and 2 metres.
    If the cell size is too large it will have the effect of rounding edges.
  keep_lower_points : bool
    If true then lower points are kept, otherwise the upper points are kept.
    Upper points would only be used in an underground situation to retain the
    roof.
  filter_combination : MaskOperation
    Specify how to combine this filter with any filter previously applied to
    the selected data.
  treat_scans_separately : bool
    Treat scans separately such that each scan is considered in isolation.
    Otherwise it works on all objects as a complete set which results in an
    even distribution of data for the entire set of objects.
  """

  format_selection = RequestTransactionWithInputs.format_selection

  inputs = [
    ('selection', format_selection(scans)),
    ('searchCellSize', str(search_cell_size)),
    ('Lower points', 'true' if keep_lower_points else 'false'),
    ('Upper points', 'false' if keep_lower_points else 'true'),
    ('maskOperation', filter_combination.format_to_operation_string()),
    ('Apply filter to selection as a whole',
     'false' if treat_scans_separately else 'true'),
  ]

  request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_MaskHighLowTransaction',
    command_name='{0}.FilterTopography'.format(COMMAND_PREFIX),
    inputs=inputs,
    )


def simplify_by_distance_error(surfaces,
                               distance_error,
                               preserve_boundary_edges=False,
                               avoid_intersections=True):
  """Simplifies a facet network, reducing the number of facets while
  maintaining the surface shape.

  Triangulation simplification can introduce inconsistencies in the surface,
  such as triangles that overlap or cross.

  Parameters
  ----------
  surfaces : list
    The list of surfaces to simplify.
  distance_error : float
    The maximum allowable average error by which each simplified surface can
    deviate from its original surface.
  preserve_boundary_edges : bool
    Specify if the surface boundary should remain unchanged.
  avoid_intersections : bool
    Prevent self intersections in the resulting surface. This will offer
    some performance benefit at the cost that the resulting surface may not
    work with other tools until the self intersections are fixed.

  Returns
  ----------
  list
    The list of surfaces.
  """

  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(surfaces)),
    ('distanceError', str(distance_error)),
    ('preserveBoundaryEdges', str(preserve_boundary_edges).lower()),
    ('avoidIntersections', str(avoid_intersections).lower()),
  ]

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_SimplifyFacetNetworkPanelTransaction',
    command_name='{0}.SimplifyByDistanceError'.format(COMMAND_PREFIX),
    requester_icon='SimplifyTriangulationError',
    inputs=inputs,
    )

  return _decode_selection(outputs)


def simplify_by_triangle_count(surfaces,
                               triangle_count,
                               preserve_boundary_edges=False,
                               avoid_intersections=True):
  """Simplifies a facet network, reducing the number of facets while
  maintaining the surface shape.

  This should be used if there there is a specific number of triangles to which
  the triangulation must be restricted.

  Triangulation simplification can introduce inconsistencies in the surface,
  such as triangles that overlap or cross.

  Parameters
  ----------
  surfaces : list
    The list of surfaces to simplify.
  triangle_count : int
    The target number of triangles is the approximate number of triangles each
    simplified triangulation (surface) will contain.
  preserve_boundary_edges : bool
    Specify if the surface boundary should remain unchanged.
  avoid_intersections : bool
    Prevent self intersections in the resulting surface. This will offer
    some performance benefit at the cost that the resulting surface may not
    work with other tools until the self intersections are fixed.

  Returns
  ----------
  list
    The list of surfaces.
  """

  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(surfaces)),
    ('facetCount', str(triangle_count)),
    ('preserveBoundaryEdges', str(preserve_boundary_edges).lower()),
    ('avoidIntersections', str(avoid_intersections).lower()),
  ]

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_SimplifyFacetNetworkPanelTransaction',
    command_name='{0}.SimplifyByFacetCount'.format(COMMAND_PREFIX),
    requester_icon='SimplifyTriangulationCount',
    inputs=inputs,
    )

  return _decode_selection(outputs)


def despike(surfaces):
  """Remove spikes from a triangulation.

  The Despike option removes spikes caused by dust or vegetation that may
  appear when creating a data model. This modifies the objects in-place, i.e
  it does not create a copy of the data.

  If unwanted points remain after running the despike tool, these must be
  manually deleted or a supplementary tool may resolve the issues.

  Parameters
  ----------
  surfaces : list
    The list of surfaces to despike.

  Returns
  ----------
  list
    The list of surfaces.
  """

  # There were no surfaces to despike.
  if not surfaces:
    return []

  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(surfaces)),
    ]

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_FacetNetworkDespikerTransaction',
    command_name='{0}.Despike'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

  return _decode_selection(outputs)


def fix_surface(surfaces):
  """Automates fixing of common issues with surfaces (triangulation).

  The fixes it performs are:
  - Self intersections - Fixes cases where the surface intersects itself

  - Trifurcations - Fixes cases where the surface touches itself, creating a
    T-junction.

  - Facet normals - Orient facet normals to point in the same direction.
    This will be up for surfaces/topography and out for solids.

  - Vertical facets - Remove vertical facets and close the hole this produces
    by moving the points along the bottom of the vertical region up or the
    points along the top down, adding points as necessary to neighbouring
    non-vertical  facets to maintain a consistent surface.

  Parameters
  ----------
  surfaces : list
    The list of surfaces to fix.

  Returns
  ----------
  list
    The list of surfaces.
  """

  inputs = [
    ('selection', RequestTransactionWithInputs.format_selection(surfaces)),
    ('isFixingSelfIntersections', 'true'),
    ('isFixingTrifurcations', 'true'),
    ('isFixingFacetNormals', 'true'),
    ('collapseVerticalFacet', 'Down'),  # Up is the other option.
  ]

  outputs = request_transaction(
    server='sdpServer',
    transaction='mtp::sdpS_FixFacetNetworkTransaction',
    command_name='{0}.FixSurface'.format(COMMAND_PREFIX),
    inputs=inputs,
    )

  return _decode_selection(outputs)


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
