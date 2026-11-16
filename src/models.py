"""Pydantic Models and Data Structures for Financial Reconciliation Agent.
Follows industry standards: strict typing, validation, and JSON-serializable models.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


class FileType(str, Enum):
    PDF = "PDF"
    IMAGE = "IMAGE"
    EXCEL = "EXCEL"
    CSV = "CSV"


class MatchStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    LLM_MATCHED = "LLM_MATCHED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_BILL = "MISSING_BILL"
    EXTRA_AUDIT_ENTRY = "EXTRA_AUDIT_ENTRY"
    DUPLICATE_EXPENSE = "DUPLICATE_EXPENSE"
    PENDING_REVIEW = "PENDING_REVIEW"
    RESOLVED_MANUAL = "RESOLVED_MANUAL"


class IngestedFile(BaseModel):
    file_id: str
    filename: str
    file_type: FileType
    sha256_hash: str
    size_bytes: int
    is_duplicate_file: bool = False
    original_file_id: Optional[str] = None
    ingested_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ExtractedRecord(BaseModel):
    record_id: str
    source_file_id: str
    source_page: int = 1
    parser_used: str  # e.g., "Docling", "OCR-Vision", "ExcelParser"
    raw_vendor: str
    normalized_vendor: str
    invoice_id: Optional[str] = None
    transaction_date: str  # YYYY-MM-DD
    statement_date: Optional[str] = None
    currency: str = "USD"
    amount: float
    tax_amount: float = 0.0
    category: str = "expense"  # expense, transfer, fee, refund
    raw_text: Optional[str] = None
    extraction_confidence: float = 1.0
    is_duplicate_invoice: bool = False
    canonical_id: Optional[str] = None


class AuditEntry(BaseModel):
    audit_id: str
    source_report: str
    reported_vendor: str
    reported_invoice_id: Optional[str] = None
    reported_date: str  # YYYY-MM-DD
    reported_amount: float
    reported_currency: str = "USD"
    department: Optional[str] = "Engineering"
    expected_category: Optional[str] = "expense"


class ReconciliationMatch(BaseModel):
    match_id: str
    audit_id: str
    record_id: Optional[str] = None
    match_status: MatchStatus
    match_type: str  # "DETERMINISTIC", "LLM_REASONED", "MANUAL_REVIEW"
    confidence_score: float
    audit_amount: float
    record_amount: Optional[float] = None
    amount_difference: float = 0.0
    reasoning_rationale: str = ""
    skill_rule_applied: Optional[str] = None
    requires_human_review: bool = False
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HumanReviewItem(BaseModel):
    review_id: str
    audit_id: str
    candidate_record_ids: List[str] = Field(default_factory=list)
    flag_reason: str
    suggested_action: str
    status: str = "PENDING"  # PENDING, RESOLVED, REJECTED
    reviewer_decision: Optional[str] = None
    reviewer_notes: Optional[str] = None
    resolved_at: Optional[str] = None


class ReconciliationEvent(BaseModel):
    event_id: str
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    stage: str
    data: Dict[str, Any] = Field(default_factory=dict)
    message: str


class F1MetricCategory(BaseModel):
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0


class SystemEvaluationMetrics(BaseModel):
    ocr_extraction: F1MetricCategory = Field(default_factory=F1MetricCategory)
    classification: F1MetricCategory = Field(default_factory=F1MetricCategory)
    matching: F1MetricCategory = Field(default_factory=F1MetricCategory)
    anomaly_detection: F1MetricCategory = Field(default_factory=F1MetricCategory)
    overall_f1: float = 0.0
    human_review_rate: float = 0.0
