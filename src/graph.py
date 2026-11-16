"""LangGraph Workflow Graph Definition for Financial Reconciliation Agent.
Constructs a stateful, event-emitting, checkpointed StateGraph connecting:
1. Ingestion (SHA-256 Layer 1 Dedup)
2. Extraction (Docling PDF Tables, OCR, Sheet Parser)
3. Validation & Layer 2 Dedup (Canonical Expense Linking)
4. Deterministic Matching (Exact zero-hallucination matches)
5. LLM Reconciliation Agent (Reasoning on ambiguous cases + skill rules)
6. Decision Validation (Arithmetic & Confidence thresholding)
7. Human-in-the-Loop Review (Conditional escalation)
8. Report Generator & F1 Score Evaluation
"""

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.models import (
    IngestedFile,
    ExtractedRecord,
    AuditEntry,
    ReconciliationMatch,
    HumanReviewItem,
    ReconciliationEvent
)
from src.nodes.ingestion import ingestion_node
from src.nodes.extraction import extract_data_node
from src.nodes.validation_dedup import validation_dedup_node
from src.nodes.deterministic_matcher import deterministic_matching_node
from src.nodes.llm_reconciliation import llm_reconciliation_node
from src.nodes.decision_validator import decision_validation_node
from src.nodes.human_review import human_review_node
from src.nodes.report_generator import report_generator_node


class FinancialReconciliationState(TypedDict, total=False):
    run_id: str
    month: str
    raw_file_inputs: List[Dict[str, Any]]
    raw_audit_input: List[Dict[str, Any]]
    ground_truth: Dict[str, Any]
    human_review_decisions: Dict[str, Any]

    # Pipeline Artifacts
    files: List[IngestedFile]
    raw_records: List[ExtractedRecord]
    audit_entries: List[AuditEntry]
    canonical_records: List[ExtractedRecord]
    matches: List[ReconciliationMatch]
    unmatched_audit_entries: List[AuditEntry]
    unmatched_canonical_records: List[ExtractedRecord]
    discrepancies: List[Dict[str, Any]]
    pending_reviews: List[HumanReviewItem]
    resolved_reviews: List[HumanReviewItem]
    needs_human_review: bool

    # Final Outputs
    final_report: str
    summary: Dict[str, Any]
    f1_metrics: Dict[str, Any]


def should_route_to_human_review(state: FinancialReconciliationState) -> str:
    """Conditional router based on validation decisions."""
    if state.get("needs_human_review", False):
        return "human_review"
    return "report_generator"


def build_financial_reconciliation_graph(checkpointer: Optional[Any] = None) -> Any:
    """Builds and compiles the production LangGraph state graph."""
    builder = StateGraph(FinancialReconciliationState)

    # 1. Add Workflow Nodes
    builder.add_node("ingestion", ingestion_node)
    builder.add_node("extraction", extract_data_node)
    builder.add_node("validation_dedup", validation_dedup_node)
    builder.add_node("deterministic_matcher", deterministic_matching_node)
    builder.add_node("llm_reconciliation", llm_reconciliation_node)
    builder.add_node("decision_validator", decision_validation_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("report_generator", report_generator_node)

    # 2. Add Transitions & Edges
    builder.add_edge(START, "ingestion")
    builder.add_edge("ingestion", "extraction")
    builder.add_edge("extraction", "validation_dedup")
    builder.add_edge("validation_dedup", "deterministic_matcher")
    builder.add_edge("deterministic_matcher", "llm_reconciliation")
    builder.add_edge("llm_reconciliation", "decision_validator")

    # Conditional Branching: Validate -> Human Review vs Direct Report Generation
    builder.add_conditional_edges(
        "decision_validator",
        should_route_to_human_review,
        {
            "human_review": "human_review",
            "report_generator": "report_generator"
        }
    )

    builder.add_edge("human_review", "report_generator")
    builder.add_edge("report_generator", END)

    # 3. Checkpointing for persistence & auditability
    memory = checkpointer if checkpointer is not None else MemorySaver()
    compiled_app = builder.compile(checkpointer=memory)
    return compiled_app
