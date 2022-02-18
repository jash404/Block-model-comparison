"""Interface for the MDF modelling library.

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

# pylint: disable=line-too-long
# pylint: disable=invalid-name
import ctypes
import logging

import numpy as np

from .types import (T_ReadHandle, T_ObjectHandle, T_TypeIndex,
                    T_MessageHandle)
from .util import (singleton, declare_dll_functions, raise_if_version_too_old,
                   CApiUnknownError, CApiDllLoadFailureError)
from .dataengine import DataEngine
from .wrapper_base import WrapperBase

@singleton
class Modelling(WrapperBase):
  """Modelling - wrapper for mdf_modelling.dll"""
  def __init__(self):
    self.log = logging.getLogger("mapteksdk.capi.modelling")
    self.dll = None

    try:
      self.dll = ctypes.cdll.mdf_modelling
      self.log.debug("Loaded: mdf_modelling.dll")
    except OSError as os_error:
      self.log.critical("Fatal: Cannot load mdf_modelling.dll")
      raise CApiDllLoadFailureError("Fatal: Cannot load mdf_modelling.dll") from os_error

    if self.dll:
      if DataEngine().dll:
        try:
          self.dll.ModellingPreDataEngineInit()
        except:
          self.log.critical('Fatal: ModellingPreDataEngineInit Not available')
          raise

      self.version = self.load_version_information()
      declare_dll_functions(self.dll, self.capi_functions(self.version), self.log)
      self.log.info("Loaded dll version: %s", self.version)

  def _dll(self):
    return self.dll

  @staticmethod
  def method_prefix():
    return "Modelling"

  def capi_functions(self, version):
    self.check_version_is_supported(version)
    functions_changed_in_version = \
    [
      # Functions changed in version 0.
      # Format:
      # "name" : (return_type, arg_types)
      {"ModellingPreDataEngineInit" : (ctypes.c_void_p, None),
       "ModellingSpatialType" : (T_TypeIndex, None),
       "ModellingStandardContainerType" : (T_TypeIndex, None),
       "ModellingVisualContainerType" : (T_TypeIndex, None),
       "ModellingTopologyType" : (T_TypeIndex, None),
       "ModellingPointSetType" : (T_TypeIndex, None),
       "ModellingEdgeNetworkType" : (T_TypeIndex, None),
       "ModellingEdgeChainType" : (T_TypeIndex, None),
       "ModellingEdgeLoopType" : (T_TypeIndex, None),
       "ModellingText2DType" : (T_TypeIndex, None),
       "ModellingText3DType" : (T_TypeIndex, None),
       "ModellingMarkerType" : (T_TypeIndex, None),
       "ModellingFacetNetworkType" : (T_TypeIndex, None),
       "ModellingCellNetworkType" : (T_TypeIndex, None),
       "ModellingRegularCellNetworkType" : (T_TypeIndex, None),
       "ModellingIrregularCellNetworkType" : (T_TypeIndex, None),
       "ModellingSparseIrregularCellNetworkType" : (T_TypeIndex, None),
       "ModellingSparseRegularCellNetworkType" : (T_TypeIndex, None),
       "ModellingDenseCellNetworkType" : (T_TypeIndex, None),
       "ModellingBlockNetworkType" : (T_TypeIndex, None),
       "ModellingBlockNetworkSubblockedType" : (T_TypeIndex, None),
       "ModellingBlockNetworkHarpType" : (T_TypeIndex, None),
       "ModellingBlockNetworkDenseType" : (T_TypeIndex, None),
       "ModellingBlockNetworkSparseType" : (T_TypeIndex, None),
       "ModellingNumericColourMapType" : (T_TypeIndex, None),
       "ModellingStringColourMapType" : (T_TypeIndex, None),
       "ModellingImageType" : (T_TypeIndex, None),
       "ModellingNewVisualContainer" : (T_ObjectHandle, None),
       "ModellingNewStandardContainer" : (T_ObjectHandle, None),
       "ModellingNewBlockNetworkDense" : (T_ObjectHandle, [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ]),
       "ModellingNewBlockNetworkSparse" : (T_ObjectHandle, [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ]),
       "ModellingNewBlockNetworkSubblocked" : (T_ObjectHandle, [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ]),
       "ModellingNewBlockNetworkHarp" : (T_ObjectHandle, [ctypes.c_double, ctypes.c_double, ctypes.c_uint32, ctypes.c_uint32, ]),
       "ModellingNewIrregularCellNetwork" : (T_ObjectHandle, [ctypes.c_uint64, ctypes.c_uint64, ]),
       "ModellingNewSparseIrregularCellNetwork" : (T_ObjectHandle, [ctypes.c_uint64, ctypes.c_uint64, ctypes.POINTER(ctypes.c_bool), ]),
       "ModellingNewEdgeNetwork" : (T_ObjectHandle, None),
       "ModellingNewEdgeChain" : (T_ObjectHandle, None),
       "ModellingNewEdgeLoop" : (T_ObjectHandle, None),
       "ModellingNewFacetNetwork" : (T_ObjectHandle, None),
       "ModellingNew2DText" : (T_ObjectHandle, None),
       "ModellingNewMarker" : (T_ObjectHandle, None),
       "ModellingNewPointSet" : (T_ObjectHandle, None),
       "ModellingNewNumericColourMap" : (T_ObjectHandle, None),
       "ModellingNewStringColourMap" : (T_ObjectHandle, None),
       "ModellingNewImage" : (T_ObjectHandle, None),
       "ModellingSetPointCount" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingSetEdgeCount" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingSetFacetCount" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingSetBlockCount" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingAppendPoints" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingAppendEdges" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingAppendFacets" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingRemovePoint" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingRemovePoints" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_uint32, ]),
       "ModellingRemoveEdge" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingRemoveEdges" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_uint32, ]),
       "ModellingRemoveFacet" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingRemoveFacets" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_uint32, ]),
       "ModellingRemoveCell" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingRemoveBlock" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingReconcileChanges" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingGetDisplayedAttribute" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint32, ]),
       "ModellingGetDisplayedAttributeType" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetDisplayedPointAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, T_ObjectHandle, ]),
       "ModellingSetDisplayedEdgeAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, T_ObjectHandle, ]),
       "ModellingSetDisplayedFacetAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, T_ObjectHandle, ]),
       "ModellingPointCoordinatesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointCoordinatesBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointToEdgeIndexBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointToFacetIndexBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeToPointIndexBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeToPointIndexBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetToPointIndexBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetToPointIndexBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetTo3FacetIndexBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockIndicesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockIndicesBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeCurveOffsetBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeCurveOffsetBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointSelectionBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointSelectionBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearPointSelection" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeSelectionBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeSelectionBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearEdgeSelection" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetSelectionBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetSelectionBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearFacetSelection" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockSelectionBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockSelectionBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearBlockSelection" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeVisibilityBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeVisibilityBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearEdgeVisibility" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointVisibilityBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointVisibilityBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearPointVisibility" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockVisibilityBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockVisibilityBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearBlockVisibility" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockSizesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockSizesBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockCentroidsBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockCentroidsBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockVolumesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingGridToBlockIndicesBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingHarpCentreZBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingHarpCentreZBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingHarpCornerOffsetsTopBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingHarpCornerOffsetsTopBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingHarpCornerOffsetsBottomBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingHarpCornerOffsetsBottomBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingGetDisplayedColourMap" : (T_ObjectHandle, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingUpdateNumericColourMapInterpolated" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingUpdateNumericColourMapSolid" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingReadNumericColourMap" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingUpdateStringColourMap" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingReadStringColourMap" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingPointColourBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingPointColourBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearPointColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetUniformPointColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingEdgeColourBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingEdgeColourBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearEdgeColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetUniformEdgeColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingFacetColourBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetColourBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearFacetColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetUniformFacetColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingSetEdgeNetworkEdgeThickness" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_float, ]),
       "ModellingSetEdgeNetworkStipplePattern" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingSetEdgeNetworkArrowHead" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_bool, ctypes.c_float, ctypes.c_float, ]),
       "ModellingBlockColourBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockColourBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearBlockColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetUniformBlockColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingGetEffectiveBlockColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_void_p, ]),
       "ModellingBlockHighlightBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingBlockHighlightBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingClearBlockHighlight" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetUniformBlockHighlight" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint8, ]),
       "ModellingSetDisplayedBlockAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, T_ObjectHandle, ]),
       "ModellingListPointAttributeNames" : (ctypes.c_uint64, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint64, ]),
       "ModellingListEdgeAttributeNames" : (ctypes.c_uint64, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint64, ]),
       "ModellingListFacetAttributeNames" : (ctypes.c_uint64, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint64, ]),
       "ModellingListBlockAttributeNames" : (ctypes.c_uint64, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint64, ]),
       "ModellingPointAttributeType" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeType" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeType" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeType" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingDeletePointAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingDeleteEdgeAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingDeleteFacetAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingDeleteBlockAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetNetworkSolidUnion" : (T_ObjectHandle, [ctypes.POINTER(T_ReadHandle), ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetNetworkSolidSubtraction" : (T_ObjectHandle, [ctypes.POINTER(T_ReadHandle), ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetNetworkSolidIntersection" : (T_ObjectHandle, [ctypes.POINTER(T_ReadHandle), ctypes.POINTER(T_ReadHandle), ]),
       "ModellingFacetNetworkClipSolid" : (T_ObjectHandle, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ]),
       "ModellingPointAttributeBoolBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeBoolBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt8uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt8uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt8sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt8sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt16uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt16uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt16sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt16sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt32uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt32uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt32sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt32sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt64uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt64uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt64sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeInt64sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeFloat32BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeFloat32BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeFloat64BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeFloat64BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeStringBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingPointAttributeStringBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeBoolBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeBoolBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt8uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt8uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt8sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt8sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt16uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt16uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt16sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt16sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt32uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt32uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt32sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt32sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt64uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt64uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt64sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeInt64sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeFloat32BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeFloat32BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeFloat64BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeFloat64BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeStringBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingEdgeAttributeStringBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeBoolBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeBoolBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt8uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt8uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt8sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt8sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt16uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt16uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt16sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt16sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt32uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt32uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt32sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt32sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt64uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt64uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt64sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeInt64sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeFloat32BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeFloat32BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeFloat64BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeFloat64BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeStringBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingFacetAttributeStringBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeBoolBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeBoolBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt8uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt8uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt8sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt8sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt16uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt16uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt16sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt16sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt32uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt32uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt32sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt32sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt64uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt64uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt64sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeInt64sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeFloat32BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeFloat32BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeFloat64BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeFloat64BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeStringBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingBlockAttributeStringBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingAttributeGetString" : (ctypes.c_uint32, [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ]),
       "ModellingAttributeSetString" : (ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ]),
       "ModellingSetBlockTransform" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ]),
       "ModellingReadBlockTransform" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingGetAnnotationPosition" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingSetAnnotationPosition" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double, ]),
       "ModellingGetAnnotationText" : (ctypes.c_uint64, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint64, ]),
       "ModellingSetAnnotationText" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingGetAnnotationSize" : (ctypes.c_double, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetAnnotationSize" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ]),
       "ModellingGetAnnotationTextColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingSetAnnotationTextColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingGetMarkerRotation" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingSetMarkerRotation" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ]),
       "ModellingGetMarkerColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingSetMarkerColour" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingGetMarkerStyle" : (ctypes.c_int32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetMarkerStyle" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_int32, ]),
       "ModellingSetMarkerGeometry" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), T_ObjectHandle, ]),
       "ModellingGetMarkerGeometry" : (T_ObjectHandle, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetMarkerSprite" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), T_ObjectHandle, ]),
       "ModellingGetMarkerSprite" : (T_ObjectHandle, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetImageData" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ]),
       "ModellingReadPointCount" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingReadEdgeCount" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingReadFacetCount" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingReadBlockCount" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingReadCellCount" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingReadBlockDimensions" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingReadExtent" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingReadBlockSize" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingProcessObjectSelectionChanges" : (ctypes.c_void_p, [T_MessageHandle, ]),
       "ModellingProcessPrimitiveSelectionChanges" : (ctypes.c_void_p, [T_MessageHandle, ]),
       "ModellingGetFeatureCount" : (ctypes.c_uint32, None),
       "ModellingGetFeatureName" : (ctypes.c_uint32, [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ]),
       "ModellingGetDisplayedFeature" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingCanApplyFeature" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),
       "ModellingSetDisplayedFeature" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint32, ]),},
      # Functions changed in version 1.
      {"ModellingCApiVersion" : (ctypes.c_uint32, None),
       "ModellingCApiMinorVersion" : (ctypes.c_uint32, None),
       "ModellingNew3DText" : (T_ObjectHandle, None),
       "ModellingReadCellDimensions" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]),
       "ModellingCellToPointIndexBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingCellSelectionBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingCellSelectionBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingCellVisibilityBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingCellVisibilityBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingCellColourBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingCellColourBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetDisplayedCellAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, T_ObjectHandle, ]),
       "ModellingListCellAttributeNames" : (ctypes.c_uint64, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint64, ]),
       "ModellingCellAttributeType" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingDeleteCellAttribute" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeBoolBeginR" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeBoolBeginRW" : (ctypes.POINTER(ctypes.c_bool), [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt8uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt8uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt8sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt8sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt16uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt16uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt16sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt16sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt32uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt32uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt32sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt32sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt64uBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt64uBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt64sBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeInt64sBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeFloat32BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeFloat32BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeFloat64BeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeFloat64BeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeStringBeginR" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingCellAttributeStringBeginRW" : (ctypes.c_void_p, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ]),
       "ModellingGetTextVerticalAlignment" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetTextVerticalAlignment" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint8, ]),
       "ModellingGetTextHorizontalAlignment" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetTextHorizontalAlignment" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint8, ]),
       "ModellingGetText3DDirection" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingSetText3DDirection" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double, ]),
       "ModellingGetText3DUpDirection" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingSetText3DUpDirection" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ctypes.c_double, ]),
       "ModellingGetText3DIsAlwaysVisible" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetText3DIsAlwaysVisible" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_bool, ]),
       "ModellingGetText3DIsAlwaysViewerFacing" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetText3DIsAlwaysViewerFacing" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_bool, ]),
       "ModellingGetText3DIsCameraFacing" : (ctypes.c_bool, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetText3DIsCameraFacing" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_bool, ]),
       "ModellingGetTextFontStyle" : (ctypes.c_uint16, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingSetTextFontStyle" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_uint16, ]),
       "ModellingGetAssociatedRasterCount" : (ctypes.c_uint32, [ctypes.POINTER(T_ReadHandle), ]),
       "ModellingGetAssociatedRasters" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.POINTER(T_ObjectHandle), ]),
       "ModellingAssociateRaster" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), T_ObjectHandle, ctypes.c_uint8, ctypes.c_void_p, ]),
       "ModellingDissociateRaster" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), T_ObjectHandle, ]),
       "ModellingRasterSetControlTwoPoint" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ]),
       "ModellingGetRasterRegistrationType" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingRasterGetRegistration" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingTangentPlaneType" : (T_TypeIndex, None),
       "ModellingNewTangentPlane" : (T_ObjectHandle, None),
       "ModellingSetTangentPlaneFromPoints" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_uint32, ]),
       "ModellingTangentPlaneGetOrientation" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ctypes.c_void_p, ]),
       "ModellingTangentPlaneSetOrientation" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ctypes.c_double, ]),
       "ModellingTangentPlaneGetLength" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingTangentPlaneSetLength" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_double, ]),
       "ModellingTangentPlaneGetArea" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingTangentPlaneGetLocation" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingTangentPlaneSetLocation" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_void_p, ]),
       "ModellingGetCoordinateSystem" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,]),
       "ModellingSetCoordinateSystem" : (ctypes.c_uint8, [ctypes.POINTER(T_ReadHandle), ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,]),

        # Functions added in version 1.5.
       "ModellingErrorCode" : (ctypes.c_uint32, None),
       "ModellingErrorMessage" : (ctypes.c_char_p, None),
       },
    ]

    # Dictionary which will contain the functions which should be available
    # in the specified version of the C API.
    function_dict = {}

    # Generate the dictionary for the specified version.
    for changes in functions_changed_in_version[:version[0] + 1]:
      function_dict.update(changes)

    return function_dict

  # Manually generated wrapper functions.
  def New3DText(self):
    """Wrapper for making a new 3d Text object."""
    raise_if_version_too_old(
      "Creating 3D Text",
      current_version=self.version,
      required_version=(1, 0))
    return self.dll.ModellingNew3DText()

  def ReadCellDimensions(self, lock):
    """Wrapper for reading the dimensions of a cell network"""
    raise_if_version_too_old(
      "Reading dimensions of a cell network",
      current_version=self.version,
      required_version=(1, 1))

    major_dimension_count = ctypes.c_uint32()
    minor_dimension_count = ctypes.c_uint32()
    self.dll.ModellingReadCellDimensions(lock,
                                         ctypes.byref(major_dimension_count),
                                         ctypes.byref(minor_dimension_count))
    return (major_dimension_count.value, minor_dimension_count.value)

  def GetTextVerticalAlignment(self, lock):
    """Wrapper for getting vertical alignment of text."""
    raise_if_version_too_old(
      "Reading dimensions of a cell network",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingGetTextVerticalAlignment(lock)

  def SetTextVerticalAlignment(self, lock, vertical_alignment):
    """Wrapper for setting text vertical alignment.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting vertical alignment of text.",
      current_version=self.version,
      required_version=(1, 2))

    result = self.dll.ModellingSetTextVerticalAlignment(lock,
                                                        vertical_alignment)
    if result != 0:
      message = "Failed to set vertical alignment."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetTextHorizontalAlignment(self, lock):
    """Wrapper for getting horizontal alignment."""
    raise_if_version_too_old(
      "Reading horizontal alignment of text",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingGetTextHorizontalAlignment(lock)

  def SetTextHorizontalAlignment(self, lock, horizontal_alignment):
    """Wrapper for setting horizontal alignment.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting horizontal alignment of text",
      current_version=self.version,
      required_version=(1, 2))

    result = self.dll.ModellingSetTextHorizontalAlignment(lock,
                                                          horizontal_alignment)
    if result != 0:
      message = "Failed to set horizontal alignment."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def CellToPointIndexBeginR(self, lock):
    """Wrapper for getting read-only cell to point index."""
    raise_if_version_too_old(
      "Getting cells",
      current_version=self.version,
      required_version=(1, 3))
    return self.dll.ModellingCellToPointIndexBeginR(lock)

  def CellSelectionBeginR(self, lock):
    """Wrapper for getting read-only cell selection."""
    raise_if_version_too_old(
      "Reading Cell Selection",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellSelectionBeginR(lock)

  def CellSelectionBeginRW(self, lock):
    """Wrapper for getting read-only cell selection."""
    raise_if_version_too_old(
      "Editing Cell Selection",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellSelectionBeginRW(lock)

  def CellVisibilityBeginR(self, lock):
    """Wrapper for getting read-only cell Visibility."""
    raise_if_version_too_old(
      "Reading Cell Visibility",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellVisibilityBeginR(lock)

  def CellVisibilityBeginRW(self, lock):
    """Wrapper for getting read-only cell visibility."""
    raise_if_version_too_old(
      "Editing Cell Visibility",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellVisibilityBeginRW(lock)

  def CellColourBeginR(self, lock):
    """Wrapper for getting read-only cell colour."""
    raise_if_version_too_old(
      "Reading Cell Colour",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellColourBeginR(lock)

  def CellColourBeginRW(self, lock):
    """Wrapper for getting read-only cell colour."""
    raise_if_version_too_old(
      "Editing Cell Colour",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellColourBeginRW(lock)

  def SetDisplayedCellAttribute(self, lock, attribute_name, colour_map_id):
    """Wrapper for setting displayed cell attribute."""
    raise_if_version_too_old(
      "Assigning a colour map to a cell attribute",
      current_version=self.version,
      required_version=(1, 2))
    self.dll.ModellingSetDisplayedCellAttribute(lock,
                                                attribute_name,
                                                colour_map_id)

  def ListCellAttributeNames(self, lock, name_buffer, name_buffer_size):
    raise_if_version_too_old(
      "Listing cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingListCellAttributeNames(lock,
                                                    name_buffer,
                                                    name_buffer_size)

  def CellAttributeType(self, lock, attribute_type):
    raise_if_version_too_old(
      "Getting cell attribute type",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeType(lock, attribute_type)

  def DeleteCellAttribute(self, lock, attribute_name):
    raise_if_version_too_old(
      "Deleting cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingDeleteCellAttribute(lock, attribute_name)

  def CellAttributeBoolBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading boolean cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeBoolBeginR(lock, attribute_name)

  def CellAttributeBoolBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing boolean cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeBoolBeginRW(lock, attribute_name)

  def CellAttributeInt8uBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading unsigned 8 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt8uBeginR(lock, attribute_name)

  def CellAttributeInt8uBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing unsigned 8 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt8uBeginRW(lock, attribute_name)

  def CellAttributeInt8sBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading signed 8 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt8sBeginR(lock, attribute_name)

  def CellAttributeInt8sBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing signed 8 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt8sBeginRW(lock, attribute_name)

  def CellAttributeInt16uBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading unsigned 16 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt16uBeginR(lock, attribute_name)

  def CellAttributeInt16uBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing unsigned 16 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt16uBeginRW(lock, attribute_name)

  def CellAttributeInt16sBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading signed 16 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt16sBeginR(lock, attribute_name)

  def CellAttributeInt16sBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing signed 16 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt16sBeginRW(lock, attribute_name)

  def CellAttributeInt32uBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading unsigned 32 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt32uBeginR(lock, attribute_name)

  def CellAttributeInt32uBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing unsigned 32 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt32uBeginRW(lock, attribute_name)

  def CellAttributeInt32sBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading signed 32 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt32sBeginR(lock, attribute_name)

  def CellAttributeInt32sBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing signed 32 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt32sBeginRW(lock, attribute_name)

  def CellAttributeInt64uBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading unsigned 64 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt64uBeginR(lock, attribute_name)

  def CellAttributeInt64uBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing unsigned 64 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt64uBeginRW(lock, attribute_name)

  def CellAttributeInt64sBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading signed 64 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt64sBeginR(lock, attribute_name)

  def CellAttributeInt64sBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing signed 64 bit integer cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeInt64sBeginRW(lock, attribute_name)

  def CellAttributeFloat32BeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading 32 bit float cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeFloat32BeginR(lock, attribute_name)

  def CellAttributeFloat32BeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing 32 bit float cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeFloat32BeginRW(lock, attribute_name)

  def CellAttributeFloat64BeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading 64 bit float cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeFloat64BeginR(lock, attribute_name)

  def CellAttributeFloat64BeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing 64 bit float cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeFloat64BeginRW(lock, attribute_name)

  def CellAttributeStringBeginR(self, lock, attribute_name):
    raise_if_version_too_old(
      "Reading string cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeStringBeginR(lock, attribute_name)

  def CellAttributeStringBeginRW(self, lock, attribute_name):
    raise_if_version_too_old(
      "Writing string cell attributes",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingCellAttributeStringBeginRW(lock, attribute_name)

  def GetText3DDirection(self, lock):
    """Returns the direction of the 3D text.

    Parameters
    ----------
    lock : lock
      Lock on the Text3D to get the direction of.

    Returns
    -------
    list
      List representing the direction of the Text3D.

    Raises
    ------
    CApiInvalidLockError
      If lock is not Text3D.
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Getting Text3D direction",
      current_version=self.version,
      required_version=(1, 2))
    x = ctypes.c_double()
    y = ctypes.c_double()
    z = ctypes.c_double()
    result = self.dll.ModellingGetText3DDirection(lock,
                                                  ctypes.byref(x),
                                                  ctypes.byref(y),
                                                  ctypes.byref(z))
    if result != 0:
      message = "Failed to get 3D text direction."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return [x.value, y.value, z.value]

  def SetText3DDirection(self, lock, x, y, z):
    """Sets the direction of the 3D text.

    Parameters
    ----------
    lock : lock
      Lock on the Text3D on which the direction should be set.
    x : float
      X component of the direction.
    y : float
      Y component of the direction.
    z : float
      Z component of the direction.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting Text3D direction",
      current_version=self.version,
      required_version=(1, 2))
    result = self.dll.ModellingSetText3DDirection(lock, x, y, z)

    if result != 0:
      message = "Failed to set direction of 3D text."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetText3DUpDirection(self, lock):
    """Returns the up direction of the 3D text.

    Parameters
    ----------
    lock : lock
      Lock on the Text3D to get the up direction of.

    Returns
    -------
    list
      List representing the up direction of the Text3D.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Getting Text3D up direction",
      current_version=self.version,
      required_version=(1, 2))
    x = ctypes.c_double()
    y = ctypes.c_double()
    z = ctypes.c_double()
    result = self.dll.ModellingGetText3DUpDirection(lock,
                                                    ctypes.byref(x),
                                                    ctypes.byref(y),
                                                    ctypes.byref(z))
    if result != 0:
      message = "Failed to get up direction of 3D text."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return [x.value, y.value, z.value]

  def SetText3DUpDirection(self, lock, x, y, z):
    """Sets the up direction of the 3D text.

    Parameters
    ----------
    lock : lock
      Lock on the Text3D on which the up direction should be set.
    x : float
      X component of the up direction.
    y : float
      Y component of the up direction.
    z : float
      Z component of the up direction.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting Text3D up direction",
      current_version=self.version,
      required_version=(1, 2))
    result = self.dll.ModellingSetText3DUpDirection(lock, x, y, z)

    if result != 0:
      message = "Failed to set up direction of 3D text."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetText3DIsAlwaysVisible(self, lock):
    """Returns if the 3D text is always visible.

    Parameters
    ----------
    lock : lock
      Lock on the Text3D whose visibility should be returned.

    Returns
    -------
    bool
      If the text is always visible.

    """
    raise_if_version_too_old(
      "Getting if Text3D is always visible",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingGetText3DIsAlwaysVisible(lock)

  def SetText3DIsAlwaysVisible(self, lock, always_visible):
    """Sets if 3D text is always visible.

    Parameters
    ----------
    lock : lock
      Lock on the Text3D whose visibility should be set.
    always_visible : bool
      Value to set to always visible.

    Raises
    ------
    CAPIUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting if Text3D is always visible",
      current_version=self.version,
      required_version=(1, 2))
    result = self.dll.ModellingSetText3DIsAlwaysVisible(lock, always_visible)

    if result != 0:
      message = "Failed to set always visible of 3D text."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetText3DIsAlwaysViewerFacing(self, lock):
    """Returns if the 3D text is viewer facing.

    Parameters
    ----------
    lock : lock
      Lock on the 3D text to query if it is viewer facing.

    Returns
    -------
    bool
      If the 3D text is viewer facing.

    """
    raise_if_version_too_old(
      "Getting if Text3D is always viewer facing",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingGetText3DIsAlwaysViewerFacing(lock)

  def SetText3DIsAlwaysViewerFacing(self, lock, always_viewer_facing):
    """Sets if the 3D text is always viewer facing.

    Parameters
    ----------
    lock : lock
      Lock on the 3D text to set if it is viewer facing.
    always_viewer_facing : bool
      Value to set to always viewer facing.

    Raises
    ------
    CAPIUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting if Text3D is always viewer facing",
      current_version=self.version,
      required_version=(1, 2))
    result = self.dll.ModellingSetText3DIsAlwaysViewerFacing(
      lock,
      always_viewer_facing)

    if result != 0:
      message = "Failed to set always viewer facing of 3D text."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetText3DIsCameraFacing(self, lock):
    """Returns if the 3D text is camera facing.

    Parameters
    ----------
    lock : lock
      Lock on the 3D text to query if it is camera facing.

    Returns
    -------
    bool
      If the 3D text is camera facing.

    """
    raise_if_version_too_old(
      "Getting if Text3D is camera facing",
      current_version=self.version,
      required_version=(1, 2))
    return self.dll.ModellingGetText3DIsCameraFacing(lock)

  def SetText3DIsCameraFacing(self, lock, camera_facing):
    """Sets if 3D text is always camera facing.

    Parameters
    ----------
    lock : lock
      Lock on the 3D text on which to set the value of camera facing.
    camera_facing : bool
      Value to set to camera facing.

    Raises
    ------
    CAPIUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting if Text3D is camera facing",
      current_version=self.version,
      required_version=(1, 2))
    result = self.dll.ModellingSetText3DIsCameraFacing(lock, camera_facing)

    if result != 0:
      message = "Failed to set camera facing of 3D text."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetTextFontStyle(self, lock):
    """Returns the enum value for the font style.

    Parameters
    ----------
    lock : lock
      Lock on the 3D text for which the style should be returned.

    Returns
    -------
    int
      Enum value of the font style.

    """
    raise_if_version_too_old(
      "Getting font style",
      current_version=self.version,
      required_version=(1, 2))

    return self.dll.ModellingGetTextFontStyle(lock)

  def SetTextFontStyle(self, lock, new_style):
    """Sets the font style using the enum value.

    Parameters
    ----------
    lock : lock
      Lock on the 3D text for which the style should be set.
    new_style : int
      Style to set for the 3D text.

    Raises
    ------
    CAPIUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Setting font style",
      current_version=self.version,
      required_version=(1, 2))
    result = self.dll.ModellingSetTextFontStyle(lock, new_style)

    if result != 0:
      message = "Failed to set font style of 3D text."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetAssociatedRasterCount(self, lock):
    """Returns the count of raster objects associated with the topology object.

    Parameters
    ----------
    lock : Lock
      Lock on the topology object to query rasters for.

    Returns
    -------
    int
      The count of rasters associated with the object.

    """
    raise_if_version_too_old(
      "Getting associated raster count",
      current_version=self.version,
      required_version=(1, 2))

    return self.dll.ModellingGetAssociatedRasterCount(lock)

  def GetAssociatedRasters(self, lock):
    """Returns a dictionary of raster objects associated with the topology
    object. The dictionary keys are numeric, however may not be consecutive(
    For example, a object could have rasters with ids 0, 1, 5, 105 and 255).
    The values are the ids of the raster objects.

    Parameters
    ----------
    lock: Lock
      Lock on the topology object to query rasters.

    Returns
    -------
    dict
      Dictionary where key is raster index and value is object id.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old(
      "Getting associated rasters",
      current_version=self.version,
      required_version=(1, 2))

    raster_count = self.GetAssociatedRasterCount(lock)
    raster_indices = (ctypes.c_uint8 * raster_count)()
    raster_ids = (T_ObjectHandle * raster_count)()

    result = self.dll.ModellingGetAssociatedRasters(lock, raster_indices,
                                                    raster_ids)

    if result != 0:
      message = "Failed to get associated rasters."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return dict(zip(raster_indices, raster_ids))

  def AssociateRaster(self, lock, raster, desired_index):
    """Associates a raster with the locked object.

    This does not set any of the information required to generate
    the point to pixel mapping. Use SetRasterControlTwoPoint (or equivalent)
    to set that information.

    Parameters
    ----------
    lock : Lock
      Lock on the object to associate the raster to.
    raster : T_ObjectHandle
      Object handle of the raster to associate.
    desired_index : int
      Desired index to give the raster. Rasters with higher indices appear
      on top of rasters with lower indices.

    Returns
    -------
    int
      Raster index the raster was given.

    Raises
    ------
    CApiUnknownError
      If an unknown error occurs.

    """
    raise_if_version_too_old(
      "Getting associated rasters",
      current_version=self.version,
      required_version=(1, 2))

    final_index = ctypes.c_uint8()
    result = self.dll.ModellingAssociateRaster(
      lock,
      raster,
      desired_index,
      ctypes.byref(final_index))
    if result != 0:
      message = "Failed to associate raster."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return final_index

  def DissociateRaster(self, lock, raster):
    """Dissociates the raster with the locked object.

    Parameters
    ----------
    lock: Lock
      Lock on the topology object the raster should be dissociated from.
    raster : T_ObjectHandle
      Object handle of the raster which should be dissociated.

    Returns
    -------
    bool
      True if the raster was associated with the object,
      False otherwise.

    Raises
    ------
    CApiUnknownError
      If an unknown error occurs.

    """
    raise_if_version_too_old(
      "Getting associated rasters",
      current_version=self.version,
      required_version=(1, 3))

    result = self.dll.ModellingDissociateRaster(lock, raster)

    # A return code of 3 indicates the raster was not associated
    # with the object.
    if result == 3:
      return False

    if result != 0:
      message = "Failed to associate raster."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return True

  def RasterSetControlTwoPoint(self, lock, image_points, world_points, orientation):
    """Wrapper for associating a raster to a surface. This sets how the
    image points, world points and orientation will be used to project the
    raster onto a surface.

    This does not perform the actual association of the raster to the surface.
    You must call AssociateRaster to do that.
    Use RasterGetRegistration to query the image points, world points and
    orientation passed to this function.

    Parameters
    ----------
    lock : Lock
      Lock on the raster to set the two point control for.
    image_points : numpy.ndarray
      Array of shape (n, 2) representing the points on the image which
      match the points on the surface. Each row is of the form [X, Y].
    world_points : numpy.ndarray
      Array of shape (n, 3) representing the points in world space
      which match the points on the image. Each row is of the form [X, Y, Z].
    orientation : numpy.ndarray
      Orientation to use when projecting the raster onto the surface. This
      is a vector of the form [X, Y, Z].

    Raises
    ------
    ValueError
      If the number of image/world points is not valid for associating
      the raster to a surface or if orientation is not finite.

    """
    point_count = min(image_points.shape[0], world_points.shape[0])
    if point_count < 2:
      raise ValueError("Two point association requires at least two points, "
                         f"given: {point_count}")
    c_image_points = (ctypes.c_double * (point_count * 2))()
    c_image_points[:] = image_points.astype(ctypes.c_double, copy=False).ravel()
    c_world_points = (ctypes.c_double * (point_count * 3))()
    c_world_points[:] = world_points.astype(ctypes.c_double, copy=False).ravel()
    c_orientation = (ctypes.c_double * 3)()
    c_orientation[:] = orientation.astype(ctypes.c_double, copy=False).ravel()

    result = self.dll.ModellingRasterSetControlTwoPoint(
      lock,
      c_image_points,
      c_world_points,
      point_count,
      c_orientation)

    if result == 3:
      raise ValueError("Failed to set registration points. The orientation "
                       "was not finite")

    if result != 0:
      message = "Failed to set registration points."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetRasterRegistrationType(self, lock):
    """Query the type of registration used to associate a raster with a
    Topology Object.

    Parameters
    ----------
    lock : Lock
      Lock on the raster to get the registration type for.

    Returns
    -------
    int
      Int representing the registration type. In particular:
      0 = no registration information set.
      3 = Two point registration.
      6 = Multi point registration.
      8 = Panoramic photograph to scan.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    registration_type = ctypes.c_uint8()
    result = self.dll.ModellingGetRasterRegistrationType(
      lock,
      ctypes.byref(registration_type))

    if result != 0:
      message = "Failed to get registration type."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return registration_type.value

  def RasterGetRegistration(self, lock):
    """Wrapper for getting the point pairs used by certain types of raster
    registration to map world points to image points.

    In particular, this will return the point pairs passed to
    RasterSetControlTwoPoint.

    Parameters
    ----------
    lock : Lock
      Lock on the raster to read registration information from.

    Returns
    -------
    tuple
      A tuple of the following form:
      (image_points, world_points, point_count, orientation) where
      image_points, world_points and orientation are numpy arrays and
      point_count is the number of points in image_points and world_points.

    """
    raise_if_version_too_old(
      "Getting registration points",
      current_version=self.version,
      required_version=(1, 3))

    # Allocate enough for eight points by default. This should almost
    # always be enough points.
    pointCount = ctypes.c_uint32(8)

    # Each image point is represented as two doubles.
    imagePoints = (ctypes.c_double * (2 * pointCount.value))()
    # Each world point is represented as three doubles.
    worldPoints = (ctypes.c_double * (3 * pointCount.value))()
    # Orientation is always three floats.
    orientation = (ctypes.c_double * 3)()

    result = self.dll.ModellingRasterGetRegistration(
      lock, imagePoints, worldPoints, ctypes.byref(pointCount), orientation)

    if result == 5:
      # Buffer is too small. PointCount now contains the correct size.
      imagePoints = (ctypes.c_double * (2 * pointCount.value))()
      worldPoints = (ctypes.c_double * (3 * pointCount.value))()
      result = self.dll.ModellingRasterGetRegistration(
        lock, imagePoints, worldPoints, ctypes.byref(pointCount), orientation)

    if result != 0:
      message = "Failed to get registration points."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return imagePoints, worldPoints, pointCount.value, orientation

  def TangentPlaneType(self):
    """Returns the Type of Tangent Plane as stored in the project."""
    if self.version < (1, 3):
      return None
    return self.dll.ModellingTangentPlaneType()

  def NewTangentPlane(self):
    """Creates a new tangent plane and returns it."""
    raise_if_version_too_old("Creating a Discontinuity",
                             current_version=self.version,
                             required_version=(1, 3))
    return self.dll.ModellingNewTangentPlane()

  def SetTangentPlaneFromPoints(self, lock, points):
    """Sets the points of a tangent plane and re-triangulates it.

    Parameters
    ----------
    lock : Lock
      Lock on the tangent plane to assign points to.
    points : ndarray
      Numpy array of points to use.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Setting discontinuity points",
                             current_version=self.version,
                             required_version=(1, 3))
    point_count = points.shape[0]
    c_points = (ctypes.c_double * (point_count * 3))()
    final_points = points.astype(ctypes.c_double, copy=False).ravel()
    c_points[:] = final_points
    result = self.dll.ModellingSetTangentPlaneFromPoints(lock,
                                                         c_points,
                                                         point_count)

    if result != 0:
      message = "Failed to set discontinuity points"
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def TangentPlaneGetOrientation(self, lock):
    """Returns the orientation of the tangent plane.

    Parameters
    ----------
    Lock
      Lock on the tangent plane of which the orientation should be retrieved.

    Returns
    -------
    tuple
      The tuple (dip, dip direction). Both are in radians.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Getting discontinuity dip and dip direction",
                             current_version=self.version,
                             required_version=(1, 3))
    dip = ctypes.c_double()
    dip_direction = ctypes.c_double()

    result = self.dll.ModellingTangentPlaneGetOrientation(
      lock,
      ctypes.byref(dip),
      ctypes.byref(dip_direction))

    if result != 0:
      message = "Failed to get discontinuity orientation."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return (dip.value, dip_direction.value)

  def TangentPlaneSetOrientation(self, lock, dip, dip_direction):
    """Sets the orientation of the tangent plane.

    Parameters
    ----------
    Lock
      Write lock on the tangent plane of which the dip and dip direction
      should be set.
    dip
      Dip to assign to the tangent plane.
    dip_direction
      Dip direction to assign to the tangent plane.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Setting discontinuity dip and dip direction",
                             current_version=self.version,
                             required_version=(1, 3))
    result = self.dll.ModellingTangentPlaneSetOrientation(lock, dip,
                                                          dip_direction)
    if result != 0:
      message = "Failed to set discontinuity orientation."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def TangentPlaneGetLength(self, lock):
    """Returns the length of the tangent plane.

    Parameters
    ----------
    lock : Lock
      Lock on the tangent plane to get the length of.

    Returns
    -------
    float
      The length of the tangent plane.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Getting discontinuity length",
                             current_version=self.version,
                             required_version=(1, 3))
    length = ctypes.c_double()
    result = self.dll.ModellingTangentPlaneGetLength(lock,
                                                     ctypes.byref(length))

    if result != 0:
      message = "Failed to get discontinuity length."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return length.value

  def TangentPlaneSetLength(self, lock, new_length):
    """Sets the length of a tangent plane. This will scale the plane
    to the new length.

    Parameters
    ----------
    lock : Lock
      Lock on the tangent plane whose length should be set.
    new_length : float
      The new length to set to the tangent plane.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Getting discontinuity length",
                             current_version=self.version,
                             required_version=(1, 3))

    result = self.dll.ModellingTangentPlaneSetLength(lock, new_length)
    if result != 0:
      message = "Failed to set discontinuity length."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def TangentPlaneGetArea(self, lock):
    """Returns the area of a tangent plane.

    Parameters
    ----------
    lock : Lock
      Lock on the tangent plane whose area should be returned.

    Returns
    -------
    float
      The area of the tangent plane.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Getting discontinuity area",
                             current_version=self.version,
                             required_version=(1, 3))

    area = ctypes.c_double()
    result = self.dll.ModellingTangentPlaneGetArea(lock, ctypes.byref(area))

    if result != 0:
      message = "Failed to get discontinuity area."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return area.value

  def TangentPlaneGetLocation(self, lock):
    """Returns the location of a tangent plane.

    Parameters
    ----------
    lock : Lock
      Lock on the tangent plane whose location should be returned.

    Returns
    -------
    list
      The location of the tangent plane in the form [x, y, z].

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Getting discontinuity location",
                          current_version=self.version,
                          required_version=(1, 3))

    location = (ctypes.c_double * 3)()
    result = self.dll.ModellingTangentPlaneGetLocation(lock,
                                                       ctypes.byref(location))
    if result != 0:
      message = "Failed to get discontinuity location."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)
    return np.array(location)

  def TangentPlaneSetLocation(self, lock, x, y, z):
    """Sets the location of the tangent plane.

    Parameters
    ----------
    lock : Lock
      Lock on the tangent plane.
    x : float
      X component of the new location.
    y : float
      Y component of the new location.
    z : float
      Z component of the new location.

    Raises
    ------
    CApiUnknownError
      If an error occurs.

    """
    raise_if_version_too_old("Setting discontinuity location",
                             current_version=self.version,
                             required_version=(1, 3))

    location = (ctypes.c_double * 3)()
    location[0] = x
    location[1] = y
    location[2] = z

    result = self.dll.ModellingTangentPlaneSetLocation(lock,
                                                       ctypes.byref(location))
    if result != 0:
      message = "Failed to set discontinuity location."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def GetCoordinateSystem(self, lock):
    """Get the coordinate system of the object.

    Parameters
    ----------
    lock : Lock
      Lock on the object for which the coordinate system should be retrieved.

    Returns
    -------
    str
      "well known text" representation of the coordinate system. Or the
      blank string if the object does not have a coordinate system.
    numpy.ndarray
      11 floats representing the local transformation of the coordinate system.
      See set coordinate system for an explanation of what each float means.

    Raises
    ------
    FileNotFound
      If the proj database could not be found.
    CApiUnknownError
      If an unknown error occurs.

    """
    raise_if_version_too_old("Getting coordinate system",
                             current_version=self.version,
                             required_version=(1, 3))

    wkt_length = ctypes.c_uint32(0)
    local_transform = (ctypes.c_double * 11)()
    local_transform_length = ctypes.c_uint32(11)
    result = self.dll.ModellingGetCoordinateSystem(
      lock,
      None,
      ctypes.byref(wkt_length),
      ctypes.byref(local_transform),
      local_transform_length)

    if result == 0:
      # We gave it an empty buffer, but it returned success so the coordinate
      # system must not exist.
      return "", local_transform
    if result == 4:
      message = ("Failed to locate the proj db. The application may not "
                 "support coordinate systems.")
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise FileNotFoundError(message)

    # If the coordinate system is not empty, then result will be 5
    # and wkt_length will have been set to the length of the wkt string.
    if result != 5:
      message = "Failed to get size of coordinate system."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    buffer = ctypes.create_string_buffer(wkt_length.value)

    result = self.dll.ModellingGetCoordinateSystem(
      lock,
      buffer,
      ctypes.byref(wkt_length),
      ctypes.byref(local_transform),
      local_transform_length)

    if result != 0:
      message = "Failed to get coordinate system."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

    return bytearray(buffer).decode('utf-8'), local_transform

  def SetCoordinateSystem(self, lock, wkt_string, local_transform):
    """Set the coordinate system of an object.

    Parameters
    ----------
    lock : Lock
      Lock on the object for which the coordinate system should be set.
    wkt_string : str
      "Well known text" string representing the coordinate system to set.
    local_transform : numpy.ndarray
      Numpy ndarray of shape (11,) representing the local transform.
      Items are as follows:
      0: Horizontal origin X
      1: Horizontal origin Y
      2: Horizontal scale factor
      3: Horizontal rotation
      4: Horizontal shift X
      5: Horizontal shift Y
      6: Vertical shift
      7: Vertical origin X
      8: Vertical origin Y
      9: Vertical slope X
      10: Vertical slope Y

    Raises
    ------
    ValueError
      If the application could not understand the coordinate system.
    FileNotFoundError
      If the proj database could not be found.
    CApiUnknownError
      If an unknown error occurs.

    """
    raise_if_version_too_old("Setting coordinate system",
                             current_version=self.version,
                             required_version=(1, 3))

    byte_string = wkt_string.encode('utf-8')
    wkt_length = len(byte_string)
    transform = (ctypes.c_double * 11)()
    local_transform_length = ctypes.c_uint32(11)
    transform[:] = local_transform
    result = self.dll.ModellingSetCoordinateSystem(
      lock,
      byte_string,
      wkt_length,
      ctypes.byref(transform),
      local_transform_length)

    if result == 3:
      message = ("The application could not understand the coordinate system. "
                 "It is either not supported or invalid.")
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise ValueError(message)
    if result == 4:
      message = ("Failed to locate the proj db. The application "
                 "may not support coordinate systems.")
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise FileNotFoundError(message)
    if result != 0:
      message = "Failed to set coordinate system."
      self.log.error(message)
      self.log.info("Error code: %s", result)
      raise CApiUnknownError(message)

  def RaiseOnErrorCode(self):
    """Raises the last known error code returned by the modelling library.

    This should only be called after calling a C API function and that
    function expected an error. This typically means when the function returns
    a null pointer or null object ID when one isn't expected (like creating a
    object).

    Raises
    ------
    MemoryError
      If the cause for the error was due to memory pressure.
    CApiUnknownError
      If an error occurs.

    """

    class ErrorCodes:
      """The "null" error code"""
      NO_ERROR = 0

      """The shared memory region is out-of-memory."""
      OUT_OF_SHARED_MEMORY = 7

    if self.version < (1, 5):
      # In older versions we assume that there was no error.
      error_code = ErrorCodes.NO_ERROR
    else:
      error_code = Modelling().ErrorCode()


    if error_code == ErrorCodes.NO_ERROR:
      return

    error_message = self.dll.ModellingErrorMessage().decode('utf-8')

    if error_code == ErrorCodes.OUT_OF_SHARED_MEMORY:
      raise MemoryError(error_message)

    raise CApiUnknownError(error_message)