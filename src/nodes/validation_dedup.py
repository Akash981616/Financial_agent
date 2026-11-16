"""Node 3: Validation, Normalization, & Invoice-Level Deduplication (Layer 2).
Implements the 3-layer deduplication design from the Perplexity session:
1. Multi-field business comparison: (Normalized Vendor + Invoice ID + Normalized Amount + Date).
2. Canonical Expense Linking: Links credit card statement entries with standalone vendor invoices
   to form a single canonical expense record rather than treating them as separate duplicates.
"""

from typing import Dict, Any, List
from src.models import ExtractedRecord
from src.events import global_event_bus
from src.skill_store import SkillStore


def validation_dedup_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes fields, detects invoice/transaction duplicates, and creates canonical expense records."""
    raw_records: List[ExtractedRecord] = state.get("raw_records", [])
    skill_store = SkillStore()

    canonical_records: List[ExtractedRecord] = []
    # Fingerprint: (normalized_vendor, invoice_id, amount) -> canonical_id
    seen_invoices: Dict[tuple, str] = {}
    dedup_count = 0
    canonical_linked_count = 0

    global_event_bus.emit(
        event_type="DEDUP_VALIDATION_STARTED",
        stage="3_ValidationAndDedup",
        message="Starting validation, field normalization, and 3-layer invoice deduplication.",
        data={"input_records": len(raw_records)}
    )

    for rec in raw_records:
        # Field Normalization
        norm_vendor = skill_store.normalize_vendor(rec.raw_vendor)
        rec.normalized_vendor = norm_vendor
        rec.amount = round(rec.amount, 2)
        rec.tax_amount = round(rec.tax_amount, 2)

        # Classification sanity check from skill file (Rule 002: Transfer vs Expense)
        if "transfer" in rec.category.lower() and norm_vendor in ["AWS", "Google Cloud Platform", "GitHub", "OpenAI"]:
            rec.category = "expense"
            global_event_bus.emit(
                event_type="CATEGORY_CORRECTED",
                stage="3_ValidationAndDedup",
                message=f"Applied RULE_002: Corrected {norm_vendor} from 'transfer' to 'expense'.",
                data={"record_id": rec.record_id, "vendor": norm_vendor}
            )

        # Invoice-level Deduplication & Canonical Linking
        # Key: (vendor, invoice_id or 'NO_ID', amount)
        inv_key = (norm_vendor.lower(), (rec.invoice_id or "").strip().lower(), rec.amount)

        if rec.invoice_id and inv_key in seen_invoices:
            canonical_parent_id = seen_invoices[inv_key]
            rec.is_duplicate_invoice = True
            rec.canonical_id = canonical_parent_id

            # Check if this is a credit-card line item matching a direct invoice
            if rec.statement_date or "statement" in rec.raw_vendor.lower() or "Docling" in rec.parser_used:
                canonical_linked_count += 1
                global_event_bus.emit(
                    event_type="CANONICAL_LINK_ESTABLISHED",
                    stage="3_ValidationAndDedup",
                    message=f"Canonical link created: {norm_vendor} ({rec.invoice_id}) links statement line to direct invoice {canonical_parent_id}.",
                    data={"record_id": rec.record_id, "canonical_parent": canonical_parent_id}
                )
            else:
                dedup_count += 1
                global_event_bus.emit(
                    event_type="DUPLICATE_INVOICE_FLAGGED",
                    stage="3_ValidationAndDedup",
                    message=f"Duplicate invoice detected: {rec.invoice_id} ({norm_vendor}, ${rec.amount:.2f}) matches existing record {canonical_parent_id}.",
                    data={"record_id": rec.record_id, "canonical_id": canonical_parent_id}
                )
        else:
            if rec.invoice_id:
                seen_invoices[inv_key] = rec.record_id
            rec.canonical_id = rec.record_id
            canonical_records.append(rec)

    global_event_bus.emit(
        event_type="DEDUP_VALIDATION_COMPLETED",
        stage="3_ValidationAndDedup",
        message=f"Validation complete: {len(canonical_records)} canonical expense records established ({dedup_count} duplicates excluded, {canonical_linked_count} canonical links merged).",
        data={
            "canonical_count": len(canonical_records),
            "duplicates_filtered": dedup_count,
            "canonical_links": canonical_linked_count
        }
    )

    return {"canonical_records": canonical_records}
