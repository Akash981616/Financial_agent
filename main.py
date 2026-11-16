"""Interactive CLI Runner for Financial Reconciliation Agent with Live Event Streaming.
Streams events to terminal with Rich styling and prints complete reconciliation audit report.
"""

import sys
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from src.graph import build_financial_reconciliation_graph
from src.events import global_event_bus
from src.models import ReconciliationEvent
from data.sample_data import get_sample_reconciliation_payload

console = Console()


def cli_event_listener(event: ReconciliationEvent):
    """Formats and prints live lifecycle events to console."""
    badge_colors = {
        "INGESTION_STARTED": "bold cyan",
        "FILE_INGESTED": "cyan",
        "DUPLICATE_FILE_DETECTED": "bold yellow",
        "INGESTION_COMPLETED": "bold green",
        "EXTRACTION_ROUTED": "magenta",
        "RECORD_EXTRACTED": "dim white",
        "CATEGORY_CORRECTED": "bold magenta",
        "CANONICAL_LINK_ESTABLISHED": "bold blue",
        "DUPLICATE_INVOICE_FLAGGED": "bold yellow",
        "DETERMINISTIC_MATCH_FOUND": "bold green",
        "LLM_RECONCILIATION_STARTED": "bold magenta",
        "LLM_EVALUATING_ENTRY": "blue",
        "LLM_MATCH_ACCEPTED": "bold green",
        "LLM_FLAGGED_FOR_REVIEW": "bold yellow",
        "DISCREPANCY_MISSING_BILL": "bold red",
        "DISCREPANCY_EXTRA_BILL": "bold red",
        "VALIDATION_COMPLETED": "bold blue",
        "HUMAN_REVIEW_QUEUED": "bold yellow",
        "HUMAN_REVIEW_RESOLVED": "bold cyan",
        "REPORT_GENERATED": "bold green"
    }

    style = badge_colors.get(event.event_type, "white")
    console.print(f"[{style}][{event.stage}][/] [bold]{event.event_type}:[/] {event.message}")


def run_pipeline():
    console.print(Panel.fit(
        "[bold cyan]LangGraph Financial Reconciliation Multi-Agent System[/bold cyan]\n"
        "[dim]Architecture: Docling PDF Parser • 3-Layer Deduplication • Deterministic/LLM Hybrid • F1 Benchmark[/dim]",
        border_style="cyan"
    ))

    # Register live event listener
    global_event_bus.register_listener(cli_event_listener)

    # Load realistic sample payload
    payload = get_sample_reconciliation_payload()

    console.print("\n[bold yellow]>>> Compiling LangGraph StateGraph & Executing Run...[/bold yellow]\n")
    start_time = time.time()

    graph = build_financial_reconciliation_graph()
    thread_config = {"configurable": {"thread_id": payload["run_id"]}}
    result = graph.invoke(payload, config=thread_config)

    elapsed = time.time() - start_time
    console.print(f"\n[bold green]✓ Pipeline completed in {elapsed:.2f} seconds![/bold green]\n")

    # Display Reconciled Matches Table
    matches_table = Table(title="Reconciliation Match Ledger", header_style="bold cyan")
    matches_table.add_column("Audit ID", style="dim")
    matches_table.add_column("Vendor", style="bold")
    matches_table.add_column("Audit Amount", justify="right")
    matches_table.add_column("Bill Amount", justify="right")
    matches_table.add_column("Status", style="green")
    matches_table.add_column("Method")
    matches_table.add_column("Confidence", justify="right")
    matches_table.add_column("Rationale", style="dim")

    for m in result.get("matches", []):
        matches_table.add_row(
            m.audit_id,
            m.reasoning_rationale.split(":")[0][:20],
            f"${m.audit_amount:.2f}",
            f"${m.record_amount or 0.0:.2f}",
            m.match_status.value,
            m.match_type,
            f"{m.confidence_score:.2f}",
            m.reasoning_rationale[:45] + "..."
        )
    console.print(matches_table)

    # Display Discrepancies Table
    disc_table = Table(title="Detected Financial Anomalies & Discrepancies", header_style="bold red")
    disc_table.add_column("Type", style="bold red")
    disc_table.add_column("Entity", style="yellow")
    disc_table.add_column("Amount", justify="right")
    disc_table.add_column("Date")
    disc_table.add_column("Audit Risk / Reason", style="white")

    for d in result.get("discrepancies", []):
        disc_table.add_row(
            d.get("type", "UNKNOWN"),
            d.get("vendor", "N/A"),
            f"${d.get('amount', 0.0):.2f}",
            d.get("date", "N/A"),
            d.get("reason", "")
        )
    console.print(disc_table)

    # Display F1 Evaluation Metrics
    f1_data = result.get("f1_metrics", {})
    f1_table = Table(title="Stage-wise F1 Evaluation Framework (Perplexity Ground-Truth)", header_style="bold magenta")
    f1_table.add_column("Evaluation Stage", style="bold")
    f1_table.add_column("Precision", justify="right")
    f1_table.add_column("Recall", justify="right")
    f1_table.add_column("F1 Score", justify="right", style="bold green")

    for stage_key, label in [
        ("ocr_extraction", "1. OCR / Table Extraction (Docling)"),
        ("classification", "2. Transaction Classification"),
        ("matching", "3. Bill-to-Audit Matching"),
        ("anomaly_detection", "4. Anomaly Detection (Missing Bills)")
    ]:
        m = f1_data.get(stage_key, {})
        f1_table.add_row(
            label,
            f"{m.get('precision', 0.0):.1%}",
            f"{m.get('recall', 0.0):.1%}",
            f"{m.get('f1_score', 0.0):.1%}"
        )
    console.print(f1_table)

    console.print(Panel(
        f"[bold]System Overall F1 Score:[/] [bold green]{f1_data.get('overall_f1', 0.0):.1%}[/bold green] | "
        f"[bold]Human Escalation Rate:[/] [bold yellow]{f1_data.get('human_review_rate', 0.0):.1%}[/bold yellow] | "
        f"[bold]Net Variance Balance:[/] [bold cyan]${result.get('summary', {}).get('net_variance', 0.0):,.2f}[/bold cyan]",
        title="Executive Performance Summary",
        border_style="green"
    ))

    # Print final Markdown Report
    console.print("\n[bold cyan]=== Final Executive Markdown Report ===[/bold cyan]\n")
    console.print(Markdown(result.get("final_report", "")))


if __name__ == "__main__":
    run_pipeline()
