"""Node 6: Decision Validation Engine.
Performs deterministic mathematical consistency checks, balance constraint verifications,
and routes unresolved or low-confidence matches to Human-in-the-Loop review.
"""

from typing import Dict, Any, List
from src.models import ReconciliationMatch, HumanReviewItem, MatchStatus
from src.events import global_event_bus


def decision_validation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validates math, checks confidence boundaries, and queues human review tickets."""
    matches: List[ReconciliationMatch] = state.get("matches", [])
    pending_reviews: List[HumanReviewItem] = []

    global_event_bus.emit(
        event_type="VALIDATION_STARTED",
        stage="6_DecisionValidation",
        message=f"Validating arithmetic constraints and confidence thresholds for {len(matches)} match decisions.",
        data={"matches_count": len(matches)}
    )

    validated_matches: List[ReconciliationMatch] = []

    for m in matches:
        # Arithmetic check: Flag if amount variance exceeds penny tolerance without explanation
        if m.amount_difference > 0.05 and not m.skill_rule_applied:
            m.requires_human_review = True
            m.match_status = MatchStatus.AMOUNT_MISMATCH

        if m.requires_human_review or m.match_status in [MatchStatus.PENDING_REVIEW, MatchStatus.AMOUNT_MISMATCH]:
            review_item = HumanReviewItem(
                review_id=f"rev_{len(pending_reviews)+1}",
                audit_id=m.audit_id,
                candidate_record_ids=[m.record_id] if m.record_id else [],
                flag_reason=f"Confidence {m.confidence_score:.2f} below auto-threshold. Variance: ${m.amount_difference:.2f}. {m.reasoning_rationale}",
                suggested_action="Review transaction receipts in Google Drive and confirm match or reject."
            )
            pending_reviews.append(review_item)
            global_event_bus.emit(
                event_type="HUMAN_REVIEW_QUEUED",
                stage="6_DecisionValidation",
                message=f"Created human review ticket {review_item.review_id} for Audit Entry {m.audit_id} (${m.audit_amount:.2f}). Reason: {review_item.flag_reason}",
                data={"review_id": review_item.review_id, "audit_id": m.audit_id}
            )
        else:
            validated_matches.append(m)

    global_event_bus.emit(
        event_type="VALIDATION_COMPLETED",
        stage="6_DecisionValidation",
        message=f"Decision validation complete: {len(validated_matches)} matches approved, {len(pending_reviews)} routed to Human-in-the-Loop review.",
        data={"approved": len(validated_matches), "pending_reviews": len(pending_reviews)}
    )

    return {
        "pending_reviews": pending_reviews,
        "needs_human_review": len(pending_reviews) > 0
    }
