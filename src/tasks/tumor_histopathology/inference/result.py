"""Per-patient classification result container with JSON serialization.

Kept in its own module so both the runner and the export layer can import it
without a circular dependency.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PatientResult:
    patnr: str
    classification_status: str
    latest_p_dat: str = ""
    report_count: int = 0
    usable_report_count: int = 0
    source_row_indices: List[int] = field(default_factory=list)
    all_report_dates: List[str] = field(default_factory=list)

    predicted_tumor_category: Optional[str] = None
    predicted_output_column: Optional[str] = None
    certainty: str = ""
    reasoning: str = ""
    supporting_evidence: List[dict] = field(default_factory=list)
    historical_diagnoses_mentioned: List[dict] = field(default_factory=list)
    uncertainty_reasons: List[str] = field(default_factory=list)

    no_tumor_information: bool = False
    parse_failed: bool = False
    llm_failed: bool = False
    context_truncated: bool = False
    category_ambiguous: bool = False
    multiple_categories: bool = False
    parse_repair_applied: str = ""

    manual_review_required: bool = False
    manual_review_reasons: List[str] = field(default_factory=list)

    error_message: str = ""
    raw_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatientResult":
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)
