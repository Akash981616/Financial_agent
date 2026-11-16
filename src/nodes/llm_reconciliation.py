"""Node 5: LLM Reconciliation Agent.
Handles ambiguous matches, prior-month charges, fuzzy vendor names, and tax splits.
Uses the persistent skill file to ground reasoning and assign confidence scores.
Emits detailed reasoning trace events.
"""

from typing import Dict, Any, List
from datetime import datetime
from src.models import AuditEntry, ExtractedRecord, ReconciliationMatch, MatchStatus
from src.events import global_event_bus
from src.skill_store import SkillStore


def parse_date(d_str: str) -> datetime:
    try:
        return datetime.strptime(d_str, "%Y-%m-%d")
    except Exception:
        return datetime(2026, 1, 1)


def llm_reconciliation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Reasoning agent evaluating ambiguous entries against domain policies and candidate bills."""
    unmatched_audit: List[AuditEntry] = state.get("unmatched_audit_entries", [])
    unmatched_records: List[ExtractedRecord] = state.get("unmatched_canonical_records", [])
    matches: List[ReconciliationMatch] = state.get("matches", [])
    discrepancies: List[Dict[str, Any]] = state.get("discrepancies", [])
    skill_store = SkillStore()
    thresholds = skill_store.get_thresholds()

    global_event_bus.emit(
        event_type="LLM_RECONCILIATION_STARTED",
        stage="5_LLMReconciliation",
        message=f"LLM Reconciliation Agent evaluating {len(unmatched_audit)} ambiguous audit entries.",
        data={"unmatched_audit_count": len(unmatched_audit), "candidate_records_count": len(unmatched_records)}
    )

    matched_record_ids = set()

    for audit in unmatched_audit:
        best_candidate: ExtractedRecord = None
        best_score = 0.0
        reasoning = ""
        applied_rule = None

        global_event_bus.emit(
            event_type="LLM_EVALUATING_ENTRY",
            stage="5_LLMReconciliation",
            message=f"Evaluating Audit Entry {audit.audit_id}: {audit.reported_vendor} (${audit.reported_amount:.2f}, {audit.reported_date})",
            data={"audit_id": audit.audit_id, "vendor": audit.reported_vendor, "amount": audit.reported_amount}
        )

        for rec in unmatched_records:
            if rec.record_id in matched_record_ids:
                continue

            score = 0.0
            reasons = []

            # 1. Vendor similarity or alias matching
            norm_audit_vendor = skill_store.normalize_vendor(audit.reported_vendor).lower()
            norm_rec_vendor = rec.normalized_vendor.lower()

            if norm_audit_vendor == norm_rec_vendor or norm_audit_vendor in norm_rec_vendor or norm_rec_vendor in norm_audit_vendor:
                score += 0.45
                reasons.append(f"Vendor match ('{audit.reported_vendor}' ~ '{rec.raw_vendor}')")
            elif any(alias in norm_rec_vendor for alias in ["aws", "amazon", "google", "cloud"]):
                score += 0.20
                reasons.append("Partial cloud infrastructure vendor overlap")

            # 2. Amount comparison (Exact, Tax included, or Penny variance)
            amt_diff = abs(audit.reported_amount - rec.amount)
            if amt_diff <= 0.05:
                score += 0.40
                reasons.append(f"Exact amount match (${rec.amount:.2f})")
            elif rec.tax_amount > 0 and abs(audit.reported_amount - (rec.amount + rec.tax_amount)) <= 0.05:
                # Rule 003: Tax inclusion
                score += 0.38
                applied_rule = "RULE_003_TAX_INCLUSION"
                reasons.append(f"Subtotal + Tax matches audit total (${rec.amount:.2f} + ${rec.tax_amount:.2f} = ${audit.reported_amount:.2f})")
            elif amt_diff / max(audit.reported_amount, 0.01) < 0.05:
                score += 0.20
                reasons.append(f"Close amount variance (${amt_diff:.2f})")

            # 3. Date window analysis & Prior-month charge handling (Rule 001)
            audit_dt = parse_date(audit.reported_date)
            rec_dt = parse_date(rec.transaction_date)
            days_diff = abs((audit_dt - rec_dt).days)

            if days_diff <= 7:
                score += 0.15
                reasons.append(f"Within 7 days window (diff: {days_diff}d)")
            elif days_diff <= 35 and (rec.statement_date or "credit card" in rec.raw_vendor.lower() or rec_dt < audit_dt):
                # Rule 001: Prior-month statement charge
                score += 0.15
                applied_rule = "RULE_001_PRIOR_MONTH_STATEMENT"
                reasons.append(f"Prior-month charge billed on current statement (transaction: {rec.transaction_date}, billed: {audit.reported_date})")

            if score > best_score:
                best_score = score
                best_candidate = rec
                reasoning = "; ".join(reasons)

        # Decision synthesis
        if best_candidate and best_score >= thresholds["auto_accept"]:
            match = ReconciliationMatch(
                match_id=f"match_{len(matches)+1}",
                audit_id=audit.audit_id,
                record_id=best_candidate.record_id,
                match_status=MatchStatus.LLM_MATCHED,
                match_type="LLM_REASONED",
                confidence_score=round(best_score, 2),
                audit_amount=audit.reported_amount,
                record_amount=best_candidate.amount,
                amount_difference=abs(audit.reported_amount - best_candidate.amount),
                reasoning_rationale=reasoning,
                skill_rule_applied=applied_rule,
                requires_human_review=False
            )
            matches.append(match)
            matched_record_ids.add(best_candidate.record_id)
            global_event_bus.emit(
                event_type="LLM_MATCH_ACCEPTED",
                stage="5_LLMReconciliation",
                message=f"LLM match auto-accepted (Confidence: {best_score:.2f}): {audit.reported_vendor} matched with {best_candidate.normalized_vendor}. Rationale: {reasoning}",
                data={"audit_id": audit.audit_id, "record_id": best_candidate.record_id, "confidence": best_score}
            )
        elif best_candidate and best_score >= thresholds["flag_human_review"]:
            # Route to human-in-the-loop review
            match = ReconciliationMatch(
                match_id=f"match_{len(matches)+1}",
                audit_id=audit.audit_id,
                record_id=best_candidate.record_id,
                match_status=MatchStatus.PENDING_REVIEW,
                match_type="LLM_AMBIGUOUS_CANDIDATE",
                confidence_score=round(best_score, 2),
                audit_amount=audit.reported_amount,
                record_amount=best_candidate.amount,
                amount_difference=abs(audit.reported_amount - best_candidate.amount),
                reasoning_rationale=f"Borderline match candidate ({reasoning}). Requires verification.",
                skill_rule_applied=applied_rule,
                requires_human_review=True
            )
            matches.append(match)
            global_event_bus.emit(
                event_type="LLM_FLAGGED_FOR_REVIEW",
                stage="5_LLMReconciliation",
                message=f"Borderline match flagged for human review (Confidence: {best_score:.2f}): {audit.reported_vendor} ~ {best_candidate.normalized_vendor}",
                data={"audit_id": audit.audit_id, "candidate_id": best_candidate.record_id, "confidence": best_score}
            )
        else:
            # Missing bill in Google Drive
            discrepancy = {
                "type": "MISSING_BILL",
                "audit_id": audit.audit_id,
                "vendor": audit.reported_vendor,
                "amount": audit.reported_amount,
                "date": audit.reported_date,
                "reason": "No corresponding bill found in Google Drive repository or statements."
            }
            discrepancies.append(discrepancy)
            global_event_bus.emit(
                event_type="DISCREPANCY_MISSING_BILL",
                stage="5_LLMReconciliation",
                message=f"Missing Bill Anomaly: Audit lists ${audit.reported_amount:.2f} for '{audit.reported_vendor}', but no document exists in Google Drive.",
                data={"audit_id": audit.audit_id, "vendor": audit.reported_vendor, "amount": audit.reported_amount}
            )

    # Check for leftover bills not in audit report (Extra / Unbilled expenses)
    for rec in unmatched_records:
        if rec.record_id not in matched_record_ids:
            discrepancy = {
                "type": "EXTRA_BILL_NOT_AUDITED",
                "record_id": rec.record_id,
                "vendor": rec.normalized_vendor,
                "amount": rec.amount,
                "date": rec.transaction_date,
                "reason": f"Bill '{rec.invoice_id or rec.record_id}' exists in Google Drive but not reported in third-party audit."
            }
            discrepancies.append(discrepancy)
            global_event_bus.emit(
                event_type="DISCREPANCY_EXTRA_BILL",
                stage="5_LLMReconciliation",
                message=f"Un-audited Bill Anomaly: Google Drive invoice for '{rec.normalized_vendor}' (${rec.amount:.2f}) was omitted from audit report.",
                data={"record_id": rec.record_id, "vendor": rec.normalized_vendor, "amount": rec.amount}
            )

    global_event_bus.emit(
        event_type="LLM_RECONCILIATION_COMPLETED",
        stage="5_LLMReconciliation",
        message=f"LLM Reconciliation finished. Discovered {len(discrepancies)} anomalies.",
        data={"discrepancies_count": len(discrepancies)}
    )

    return {
        "matches": matches,
        "discrepancies": discrepancies
    }
