"""Node 8: Report Generator & Executive Summary.
Compiles reconciliation summary, category breakdown, identified anomalies,
and evaluates system F1 metrics against ground truth.
"""

from typing import Dict, Any, List
from datetime import datetime
from src.models import ReconciliationMatch, MatchStatus, HumanReviewItem, ExtractedRecord, AuditEntry
from src.events import global_event_bus
from src.eval_metrics import evaluate_run_performance


def report_generator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Compiles the final reconciliation report and computes F1 evaluation scores."""
    matches: List[ReconciliationMatch] = state.get("matches", [])
    discrepancies: List[Dict[str, Any]] = state.get("discrepancies", [])
    resolved: List[HumanReviewItem] = state.get("resolved_reviews", [])
    audit_entries: List[AuditEntry] = state.get("audit_entries", [])
    canonical_records: List[ExtractedRecord] = state.get("canonical_records", [])

    global_event_bus.emit(
        event_type="REPORT_GENERATION_STARTED",
        stage="8_ReportGenerator",
        message="Compiling final financial reconciliation report and computing F1 evaluation metrics.",
        data={"matches_count": len(matches), "discrepancies_count": len(discrepancies)}
    )

    exact_matches = [m for m in matches if m.match_status == MatchStatus.EXACT_MATCH]
    llm_matches = [m for m in matches if m.match_status == MatchStatus.LLM_MATCHED]
    manual_matches = [m for m in matches if m.match_status == MatchStatus.RESOLVED_MANUAL]
    amount_mismatches = [m for m in matches if m.match_status == MatchStatus.AMOUNT_MISMATCH]

    total_audited_amt = sum(a.reported_amount for a in audit_entries)
    total_reconciled_amt = sum(m.record_amount or 0.0 for m in matches if m.match_status in [MatchStatus.EXACT_MATCH, MatchStatus.LLM_MATCHED, MatchStatus.RESOLVED_MANUAL])
    unreconciled_amt = total_audited_amt - total_reconciled_amt

    # Compute Stage-wise F1 Metrics from the Perplexity Session
    f1_results = evaluate_run_performance(state)

    summary_data = {
        "run_id": state.get("run_id", "run_default"),
        "period": state.get("month", "2026-10"),
        "generated_at": datetime.utcnow().isoformat(),
        "total_audit_entries": len(audit_entries),
        "total_canonical_bills": len(canonical_records),
        "exact_matches_count": len(exact_matches),
        "llm_matches_count": len(llm_matches),
        "manual_resolutions_count": len(manual_matches),
        "amount_mismatch_count": len(amount_mismatches),
        "missing_bills_count": sum(1 for d in discrepancies if d["type"] == "MISSING_BILL"),
        "extra_bills_count": sum(1 for d in discrepancies if d["type"] == "EXTRA_BILL_NOT_AUDITED"),
        "total_audited_amount": round(total_audited_amt, 2),
        "total_reconciled_amount": round(total_reconciled_amt, 2),
        "net_variance": round(unreconciled_amt, 2),
        "overall_f1_score": f1_results.get("overall_f1", 0.0),
        "human_review_rate": f1_results.get("human_review_rate", 0.0)
    }

    # Generate Markdown Report
    lines = [
        f"# Executive Financial Reconciliation Report - {summary_data['period']}",
        f"**Run ID:** `{summary_data['run_id']}` | **Generated:** {summary_data['generated_at']}",
        "",
        "## 1. High-Level Financial Reconciliation Metrics",
        f"- **Total Third-Party Audit Line Items:** {summary_data['total_audit_entries']} (${summary_data['total_audited_amount']:,.2f})",
        f"- **Total Reconciled Amount:** ${summary_data['total_reconciled_amount']:,.2f}",
        f"- **Net Variance / Unreconciled Balance:** ${summary_data['net_variance']:,.2f}",
        f"- **Deterministic Exact Matches:** {summary_data['exact_matches_count']}",
        f"- **LLM Policy-Reasoned Matches:** {summary_data['llm_matches_count']}",
        f"- **Human-in-the-Loop Resolved Matches:** {summary_data['manual_resolutions_count']}",
        f"- **System Overall F1 Score:** {summary_data['overall_f1_score']:.1%}",
        f"- **Human Escalation Review Rate:** {summary_data['human_review_rate']:.1%}",
        "",
        "## 2. Reconciled Entries Breakdown",
        "| Audit ID | Vendor | Audit Amt | Bill Amt | Status | Match Method | Confidence | Notes |",
        "|---|---|---|---|---|---|---|---|"
    ]

    for m in matches:
        lines.append(f"| {m.audit_id} | {m.reasoning_rationale.split(':')[0]} | ${m.audit_amount:.2f} | ${m.record_amount or 0.0:.2f} | {m.match_status.value} | {m.match_type} | {m.confidence_score:.2f} | {m.reasoning_rationale[:60]}... |")

    lines.extend([
        "",
        "## 3. Discrepancies & Anomalies Detected",
        "| Type | Entity | Amount | Date | Reason / Risk |",
        "|---|---|---|---|---|"
    ])

    for d in discrepancies:
        lines.append(f"| {d['type']} | {d.get('vendor', 'N/A')} | ${d.get('amount', 0.0):.2f} | {d.get('date', 'N/A')} | {d.get('reason')} |")

    lines.extend([
        "",
        "## 4. Evaluated F1 Metrics Framework (CARL Quality Benchmark)",
        f"- **OCR / Table Extraction F1:** {f1_results['ocr_extraction']['f1_score']:.1%} (Precision: {f1_results['ocr_extraction']['precision']:.1%}, Recall: {f1_results['ocr_extraction']['recall']:.1%})",
        f"- **Transaction Classification F1:** {f1_results['classification']['f1_score']:.1%} (Precision: {f1_results['classification']['precision']:.1%}, Recall: {f1_results['classification']['recall']:.1%})",
        f"- **Bill-to-Audit Matching F1:** {f1_results['matching']['f1_score']:.1%} (Precision: {f1_results['matching']['precision']:.1%}, Recall: {f1_results['matching']['recall']:.1%})",
        f"- **Anomaly Detection F1:** {f1_results['anomaly_detection']['f1_score']:.1%} (Precision: {f1_results['anomaly_detection']['precision']:.1%}, Recall: {f1_results['anomaly_detection']['recall']:.1%})"
    ])

    report_md = "\n".join(lines)

    global_event_bus.emit(
        event_type="REPORT_GENERATED",
        stage="8_ReportGenerator",
        message=f"Reconciliation Report generated successfully. Overall F1: {summary_data['overall_f1_score']:.1%}, Net Variance: ${summary_data['net_variance']:,.2f}.",
        data=summary_data
    )

    return {
        "final_report": report_md,
        "summary": summary_data,
        "f1_metrics": f1_results
    }
