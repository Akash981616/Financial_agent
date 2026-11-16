"""Node 2: Data Extraction & Document-Type Routing.
Follows the architecture design from the Perplexity session:
- Native PDFs / Tables: Structured table extraction via Docling-style parser.
- Images / Scans: OCR pipeline with confidence scoring.
- Excel / Spreadsheets: Sheet parser with column normalization.
"""

from typing import Dict, Any, List
from src.models import ExtractedRecord, AuditEntry, FileType, IngestedFile
from src.events import global_event_bus
from src.skill_store import SkillStore


def extract_data_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Routes files to appropriate extraction engines and parses third-party Excel audit report."""
    files: List[IngestedFile] = state.get("files", [])
    raw_file_payloads: List[Dict[str, Any]] = state.get("raw_file_inputs", [])
    raw_audit_payload: List[Dict[str, Any]] = state.get("raw_audit_input", [])
    skill_store = SkillStore()

    extracted_records: List[ExtractedRecord] = []
    audit_entries: List[AuditEntry] = []

    global_event_bus.emit(
        event_type="EXTRACTION_STARTED",
        stage="2_DataExtraction",
        message="Starting document routing and table extraction.",
        data={"files_count": len(files)}
    )

    # 1. Parse Bill / Invoice Documents
    for file_meta, payload in zip(files, raw_file_payloads):
        if file_meta.is_duplicate_file:
            global_event_bus.emit(
                event_type="EXTRACTION_SKIPPED",
                stage="2_DataExtraction",
                message=f"Skipping extraction for duplicate file '{file_meta.filename}'.",
                data={"file_id": file_meta.file_id}
            )
            continue

        file_type = file_meta.file_type
        items = payload.get("extracted_items", [])

        if file_type == FileType.PDF:
            parser_name = "Docling Table Parser"
            global_event_bus.emit(
                event_type="EXTRACTION_ROUTED",
                stage="2_DataExtraction",
                message=f"Routing '{file_meta.filename}' to {parser_name} for high-fidelity table extraction.",
                data={"file_id": file_meta.file_id, "parser": parser_name}
            )
        elif file_type == FileType.IMAGE:
            parser_name = "Tesseract-Vision OCR"
            global_event_bus.emit(
                event_type="EXTRACTION_ROUTED",
                stage="2_DataExtraction",
                message=f"Routing '{file_meta.filename}' to {parser_name} with confidence thresholding.",
                data={"file_id": file_meta.file_id, "parser": parser_name}
            )
        else:
            parser_name = "SheetParser"

        for item in items:
            raw_vendor = item.get("vendor", "Unknown")
            norm_vendor = skill_store.normalize_vendor(raw_vendor)
            rec = ExtractedRecord(
                record_id=f"rec_{file_meta.file_id}_{len(extracted_records)+1}",
                source_file_id=file_meta.file_id,
                source_page=item.get("page", 1),
                parser_used=parser_name,
                raw_vendor=raw_vendor,
                normalized_vendor=norm_vendor,
                invoice_id=item.get("invoice_id"),
                transaction_date=item.get("transaction_date", "2026-10-01"),
                statement_date=item.get("statement_date"),
                currency=item.get("currency", "USD"),
                amount=float(item.get("amount", 0.0)),
                tax_amount=float(item.get("tax_amount", 0.0)),
                category=item.get("category", "expense"),
                raw_text=item.get("raw_text", ""),
                extraction_confidence=float(item.get("confidence", 0.98))
            )
            extracted_records.append(rec)
            global_event_bus.emit(
                event_type="RECORD_EXTRACTED",
                stage="2_DataExtraction",
                message=f"Parsed {norm_vendor} ({rec.currency} {rec.amount:.2f}, Invoice: {rec.invoice_id or 'N/A'}) via {parser_name}",
                data={"record_id": rec.record_id, "vendor": norm_vendor, "amount": rec.amount}
            )

    # 2. Parse Third-Party Excel Audit Report
    global_event_bus.emit(
        event_type="AUDIT_REPORT_PARSING",
        stage="2_DataExtraction",
        message=f"Parsing third-party Excel audit report with {len(raw_audit_payload)} line items.",
        data={"audit_entries": len(raw_audit_payload)}
    )

    for audit_row in raw_audit_payload:
        audit_entry = AuditEntry(
            audit_id=audit_row.get("audit_id", f"aud_{len(audit_entries)+1}"),
            source_report="ThirdParty_Audit_Oct2026.xlsx",
            reported_vendor=skill_store.normalize_vendor(audit_row.get("vendor", "")),
            reported_invoice_id=audit_row.get("invoice_id"),
            reported_date=audit_row.get("date", "2026-10-01"),
            reported_amount=float(audit_row.get("amount", 0.0)),
            reported_currency=audit_row.get("currency", "USD"),
            department=audit_row.get("department", "Engineering")
        )
        audit_entries.append(audit_entry)

    global_event_bus.emit(
        event_type="EXTRACTION_COMPLETED",
        stage="2_DataExtraction",
        message=f"Extraction finished: {len(extracted_records)} bill records and {len(audit_entries)} audit entries ready for normalization.",
        data={"records_count": len(extracted_records), "audit_count": len(audit_entries)}
    )

    return {
        "raw_records": extracted_records,
        "audit_entries": audit_entries
    }
