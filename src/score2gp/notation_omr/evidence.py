"""Evidence extraction and candidate location shaping."""

from typing import Any, Iterable


def shape_candidate_evidence(
    raw_candidates: Iterable[Any],
    page_index: int,
    candidate_prefix: str,
    start_index: int = 1
) -> list[dict]:
    """
    Takes raw diagnostic candidates (objects or dicts) for a single page, sorts them
    geometrically, and shapes them into deterministic read-only candidate evidence
    with stable IDs.

    Returns the shaped candidates.
    """
    def get_bbox(c: Any) -> list[float]:
        return c["bbox"] if isinstance(c, dict) else c.bbox

    candidates = list(raw_candidates)
    # Sort geometrically: top, left, bottom, right
    candidates.sort(key=lambda c: (get_bbox(c)[1], get_bbox(c)[0], get_bbox(c)[3], get_bbox(c)[2]))

    shaped = []
    for i, cand in enumerate(candidates):
        candidate_id = f"{candidate_prefix}_{start_index + i:03d}"
        cand_dict = {
            "candidate_id": candidate_id,
            "page_index": page_index,
            "bbox": get_bbox(cand)
        }
        if isinstance(cand, dict):
            if "stem_bbox" in cand:
                cand_dict["stem_bbox"] = cand["stem_bbox"]
            for f in ("font_name", "glyph_ordinal", "origin_x", "origin_y", "source_method"):
                if f in cand:
                    cand_dict[f] = cand[f]
        else:
            if hasattr(cand, "stem_bbox"):
                cand_dict["stem_bbox"] = cand.stem_bbox
            for f in ("font_name", "glyph_ordinal", "origin_x", "origin_y", "source_method"):
                if hasattr(cand, f) and getattr(cand, f) is not None:
                    cand_dict[f] = getattr(cand, f)
        shaped.append(cand_dict)
    return shaped


# Recognition Adapter Seam Data Structures & Adapters (CRP-08)
from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Dict, Any


class SourceModality(Enum):
    TEXT = "text"
    VECTOR = "vector"
    RASTER = "raster"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class EvidenceRecord:
    candidate_id: str
    modality: SourceModality
    bbox: Tuple[float, float, float, float]
    page_index: int
    system_index: Optional[int] = None
    staff_index: Optional[int] = None
    raw_symbol: str = ""
    confidence: float = 1.0
    is_absent: bool = False
    is_ambiguous: bool = False
    is_conflicted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class CandidateAdapter:
    """Adapts raw diagnostic candidate objects/dicts into typed EvidenceRecord objects."""

    def adapt(self, candidate: Any) -> EvidenceRecord:
        if isinstance(candidate, dict):
            c_dict = candidate
        elif hasattr(candidate, "model_dump"):
            c_dict = candidate.model_dump()
        elif hasattr(candidate, "dict"):
            c_dict = candidate.dict()
        else:
            c_dict = getattr(candidate, "__dict__", {})

        cand_id = c_dict.get("candidate_id") or c_dict.get("id") or "cand_unknown"
        page_idx = c_dict.get("page_index") or c_dict.get("page") or 1
        sys_idx = c_dict.get("system_index")
        staff_idx = c_dict.get("staff_index")
        raw_sym = str(c_dict.get("raw_symbol") or c_dict.get("raw_text") or c_dict.get("text") or "")
        conf = float(c_dict.get("confidence", 1.0))
        absent = bool(c_dict.get("is_absent", False))
        ambiguous = bool(c_dict.get("is_ambiguous", False))
        conflicted = bool(c_dict.get("is_conflicted", False))

        raw_mod = c_dict.get("modality") or c_dict.get("source_stage") or c_dict.get("source_method")
        if isinstance(raw_mod, SourceModality):
            modality = raw_mod
        elif isinstance(raw_mod, str):
            val_lower = raw_mod.lower()
            if "vector" in val_lower or "line" in val_lower:
                modality = SourceModality.VECTOR
            elif "raster" in val_lower or "image" in val_lower:
                modality = SourceModality.RASTER
            elif "hybrid" in val_lower:
                modality = SourceModality.HYBRID
            else:
                modality = SourceModality.TEXT
        else:
            modality = SourceModality.TEXT

        raw_bbox = c_dict.get("bbox")
        if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
            bbox = (float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3]))
        elif isinstance(raw_bbox, dict):
            bbox = (
                float(raw_bbox.get("x0", 0.0)),
                float(raw_bbox.get("y0", 0.0)),
                float(raw_bbox.get("x1", 0.0)),
                float(raw_bbox.get("y1", 0.0)),
            )
        else:
            bbox = (0.0, 0.0, 0.0, 0.0)

        meta = {
            k: v
            for k, v in c_dict.items()
            if k not in (
                "candidate_id",
                "id",
                "page_index",
                "page",
                "system_index",
                "staff_index",
                "raw_symbol",
                "raw_text",
                "text",
                "confidence",
                "is_absent",
                "is_ambiguous",
                "is_conflicted",
                "modality",
                "source_stage",
                "source_method",
                "bbox",
            )
        }

        return EvidenceRecord(
            candidate_id=cand_id,
            modality=modality,
            bbox=bbox,
            page_index=int(page_idx),
            system_index=sys_idx,
            staff_index=staff_idx,
            raw_symbol=raw_sym,
            confidence=conf,
            is_absent=absent,
            is_ambiguous=ambiguous,
            is_conflicted=conflicted,
            metadata=meta,
        )


# Paired-Staff Evidence Fusion (CRP-09)
from .staff_geometry import SystemTopology


@dataclass
class PairedStaffEvidenceFusion:
    system_index: int
    page_number: int
    notation_candidates: List[Dict[str, Any]] = field(default_factory=list)
    tab_candidates: List[Dict[str, Any]] = field(default_factory=list)
    ownership_status: str = "one_to_one"  # "one_to_one" | "ambiguous" | "unassociated"
    ambiguity_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_index": self.system_index,
            "page_number": self.page_number,
            "notation_candidate_count": len(self.notation_candidates),
            "tab_candidate_count": len(self.tab_candidates),
            "ownership_status": self.ownership_status,
            "ambiguity_reason": self.ambiguity_reason,
        }


class PairedStaffFusionEngine:
    """Associates notation, TAB, bars, and techniques by SystemTopology staff pairs."""

    def fuse(
        self,
        notation_candidates: List[Dict[str, Any]],
        tab_candidates: List[Dict[str, Any]],
        systems: List[SystemTopology],
    ) -> List[PairedStaffEvidenceFusion]:
        fusions: List[PairedStaffEvidenceFusion] = []

        sys_map = {sys.system_index: sys for sys in systems}

        for sys in systems:
            # Filter candidates strictly within this system and page boundary (Prevent cross-system snapping)
            sys_notation = [
                c
                for c in notation_candidates
                if c.get("system_index") == sys.system_index
                and (c.get("page_index") is None or c.get("page_index") == sys.page_number)
            ]
            sys_tab = [
                c
                for c in tab_candidates
                if c.get("system_index") == sys.system_index
                and (c.get("page_index") is None or c.get("page_index") == sys.page_number)
            ]

            status = "one_to_one"
            reason = None

            # Check ambiguity
            ambiguous_cands = [c for c in sys_notation + sys_tab if c.get("association_status") == "failed"]
            if ambiguous_cands:
                status = "ambiguous"
                reason = "ambiguous_candidate_association"

            fusions.append(
                PairedStaffEvidenceFusion(
                    system_index=sys.system_index,
                    page_number=sys.page_number,
                    notation_candidates=sys_notation,
                    tab_candidates=sys_tab,
                    ownership_status=status,
                    ambiguity_reason=reason,
                )
            )

        return fusions
