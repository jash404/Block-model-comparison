"""Representation of the objects within a Project.

Many of the types within this package can be used to create a new object
of that type through Project.new(). Classes defined in this module are yielded
when opening an object via Project.read() and Project.edit().

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

from .points import PointSet
from .edges import EdgeNetwork, Polygon, Polyline
from .facets import Surface
from .geotechnical import Discontinuity
from .blocks import DenseBlockModel, SubblockedBlockModel
from .cells import GridSurface
from .scans import Scan
from .annotations import (Text2D, Text3D, Marker, VerticalAlignment,
                          HorizontalAlignment, FontStyle)
from .images import (Raster, RasterRegistrationTwoPoint,
                     RasterRegistrationNone,
                     RasterRegistrationUnsupported,
                     RasterRegistrationMultiPoint)
from .base import DataObject, Topology
from .colourmaps import NumericColourMap, StringColourMap, UnsortedRangesError
from .containers import Container, VisualContainer, StandardContainer
from .objectid import ObjectID
from .units import DistanceUnit, Axis
from .errors import (CannotSaveInReadOnlyModeError, DegenerateTopologyError,
                     InvalidColourMapError)
from .coordinate_systems import (CoordinateSystem, LocalTransform,
                                 LocalTransformNotSupportedError)
