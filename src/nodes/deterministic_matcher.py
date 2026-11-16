"""Node 4: Deterministic Matching Engine.
Industry standard best practice: Keep deterministic code boundaries for exact IDs,
amounts, and clean vendor matches; reserve LLM inference strictly for ambiguous cases.
"""

from typing import Dict, Any, List, Set
from src.models import AuditEntry, ExtractedRecord, ReconciliationMatch, MatchStatus
from src.events import global_event_bus


def deterministic_matching_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Performs zero-hallucination deterministic matching on exact IDs and amounts."""
    audit_entries: List[AuditEntry] = state.get("audit_entries", [])
    canonical_records: List[ExtractedRecord] = state.get("canonical_records", [])

    matched_audit_ids: Set[str] = set()
    matched_record_ids: Set[str] = set()
    matches: List[ReconciliationMatch] = state.get("matches", [])

    global_event_bus.emit(
        event_type="DETERMINISTIC_MATCHING_STARTED",
        stage="4_DeterministicMatching",
        message=f"Starting deterministic rule matching across {len(audit_entries)} audit entries and {len(canonical_records)} canonical bills.",
        data={"audit_entries_count": len(audit_entries), "canonical_records_count": len(canonical_records)}
    )

    # Index records by invoice_id and by (vendor, amount)
    records_by_inv_id: Dict[str, ExtractedRecord] = {}
    for r in canonical_records:
        if r.invoice_id:
            records_by_inv_id[r.invoice_id.strip().upper()] = r

    # Pass 1: Exact Invoice ID Match
    for audit in audit_entries:
        if audit.audit_id in matched_audit_ids:
            continue
        if audit.reported_invoice_id:
            clean_inv = audit.reported_invoice_id.strip().upper()
            if clean_inv in records_by_inv_id:
                rec = records_by_inv_id[clean_inv]
                if rec.record_id not in matched_record_ids:
                    amount_diff = abs(audit.reported_amount - rec.amount)
                    if amount_diff <= 0.05:  # Exact amount match with penny tolerance
                        match = ReconciliationMatch(
                            match_id=f"match_{len(matches)+1}",
                            audit_id=audit.audit_id,
                            record_id=rec.record_id,
                            match_status=MatchStatus.EXACT_MATCH,
                            match_type="DETERMINISTIC_INVOICE_ID",
                            confidence_score=1.0,
                            audit_amount=audit.reported_amount,
                            record_amount=rec.amount,
                            amount_difference=amount_diff,
                            reasoning_rationale=f"Deterministic exact match on invoice ID '{audit.reported_invoice_id}' and amount ${rec.amount:.2f}.",
                            requires_human_review=False
                        )
                        matches.append(match)
                        matched_audit_ids.add(audit.audit_id)
                        matched_record_ids.add(rec.record_id)

                        global_event_bus.emit(
                            event_type="DETERMINISTIC_MATCH_FOUND",
                            stage="4_DeterministicMatching",
                            message=f"Match Found [Exact ID]: {audit.reported_vendor} (Audit: ${audit.reported_amount:.2f} == Bill: ${rec.amount:.2f}, ID: {audit.reported_invoice_id})",
                            data={"audit_id": audit.audit_id, "record_id": rec.record_id, "invoice_id": audit.reported_invoice_id}
                        )

    # Pass 2: Exact Vendor + Exact Amount Match
    for audit in audit_entries:
        if audit.audit_id in matched_audit_ids:
            continue
        for rec in canonical_records:
            if rec.record_id in matched_record_ids:
                continue
            if audit.reported_vendor.lower() == rec.normalized_vendor.lower():
                amount_diff = abs(audit.reported_amount - rec.amount)
                if amount_diff <= 0.05:
                    match = ReconciliationMatch(
                        match_id=f"match_{len(matches)+1}",
                        audit_id=audit.audit_id,
                        record_id=rec.record_id,
                        match_status=MatchStatus.EXACT_MATCH,
                        match_type="DETERMINISTIC_VENDOR_AMOUNT",
                        confidence_score=0.98,
                        audit_amount=audit.reported_amount,
                        record_amount=rec.amount,
                        amount_difference=amount_diff,
                        reasoning_rationale=f"Deterministic exact match on normalized vendor '{rec.normalized_vendor}' and amount ${rec.amount:.2f}.",
                        requires_human_review=False
                    )
                    matches.append(match)
                    matched_audit_ids.add(audit.audit_id)
                    matched_record_ids.add(rec.record_id)

                    global_event_bus.emit(
                        event_type="DETERMINISTIC_MATCH_FOUND",
                        stage="4_DeterministicMatching",
                        message=f"Match Found [Vendor+Amount]: {rec.normalized_vendor} (${rec.amount:.2f})",
                        data={"audit_id": audit.audit_id, "record_id": rec.record_id}
                    )
                    break

    unmatched_audit = [a for a in audit_entries if a.audit_id not in matched_audit_ids]
    unmatched_records = [r for r in canonical_records if r.record_id not in matched_record_ids]

    global_event_bus.emit(
        event_type="DETERMINISTIC_MATCHING_COMPLETED",
        stage="4_DeterministicMatching",
        message=f"Deterministic matching finished: {len(matched_audit_ids)} entries matched. {len(unmatched_audit)} audit entries and {len(unmatched_records)} bills routed to LLM Reconciliation Agent.",
        data={
            "matched_count": len(matched_audit_ids),
            "unmatched_audit_count": len(unmatched_audit),
            "unmatched_records_count": len(unmatched_records)
        }
    )

    return {
        "matches": matches,
        "unmatched_audit_entries": unmatched_audit,
        "unmatched_canonical_records": unmatched_records
    }
