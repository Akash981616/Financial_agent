"""Sample Data Generator for Financial Reconciliation System.
Constructs realistic enterprise scenarios matching the Perplexity session:
- Multi-format ingestion (Native PDF tables via Docling, Image receipts via OCR, Excel audit report).
- Layer 1 Duplicate File (SHA-256 collision).
- Layer 2 Duplicate Invoice / Statement Canonical Linking.
- Prior-Month Credit Card Statement charge (Rule 001).
- Transfer vs Expense SaaS subscription (Rule 002).
- VAT / Tax Inclusion variation (Rule 003).
- Missing Bill Anomaly (Audit item with no Drive receipt).
- Extra Un-audited Bill Anomaly (Drive receipt omitted from audit).
"""

from typing import Dict, Any, List


def get_sample_reconciliation_payload() -> Dict[str, Any]:
    # Raw Google Drive file inputs
    raw_files = [
        {
            "file_id": "drv_001_aws_pdf",
            "filename": "AWS_Monthly_Billing_INV-1042.pdf",
            "file_type": "PDF",
            "content_bytes": b"%PDF-1.4 AWS Cloud Services Invoice INV-1042 Total: $125.50",
            "extracted_items": [
                {
                    "vendor": "Amazon Web Services Inc",
                    "invoice_id": "INV-1042",
                    "transaction_date": "2026-10-29",
                    "statement_date": "2026-11-02",
                    "currency": "USD",
                    "amount": 125.50,
                    "tax_amount": 0.0,
                    "category": "expense",
                    "confidence": 0.99
                }
            ]
        },
        {
            # Layer 1 duplicate file (Identical content bytes and hash)
            "file_id": "drv_002_aws_reupload",
            "filename": "AWS_Monthly_Billing_INV-1042_COPY.pdf",
            "file_type": "PDF",
            "content_bytes": b"%PDF-1.4 AWS Cloud Services Invoice INV-1042 Total: $125.50",
            "extracted_items": []
        },
        {
            "file_id": "drv_003_gcp_pdf",
            "filename": "Google_Cloud_Platform_Oct2026.pdf",
            "file_type": "PDF",
            "content_bytes": b"%PDF-1.4 Google Cloud Computing Charges 340.00 USD",
            "extracted_items": [
                {
                    "vendor": "Google LLC",
                    "invoice_id": "GCP-9901",
                    "transaction_date": "2026-10-15",
                    "currency": "USD",
                    "amount": 340.00,
                    "tax_amount": 0.0,
                    "category": "expense",
                    "confidence": 0.98
                }
            ]
        },
        {
            # Tests Rule 002: Transfer vs Expense (SaaS subscription labeled ACH Transfer)
            "file_id": "drv_004_github_img",
            "filename": "GitHub_Enterprise_Receipt.png",
            "file_type": "IMAGE",
            "content_bytes": b"\x89PNG\r\n\x1a\n GitHub Inc Autopay ACH Transfer $210.00",
            "extracted_items": [
                {
                    "vendor": "GitHub Enterprise",
                    "invoice_id": "GH-ENT-55",
                    "transaction_date": "2026-10-18",
                    "currency": "USD",
                    "amount": 210.00,
                    "tax_amount": 0.0,
                    "category": "transfer",  # Initially misclassified by basic OCR
                    "confidence": 0.94
                }
            ]
        },
        {
            # Tests Rule 001: Prior-month credit card statement charge
            "file_id": "drv_005_datadog_pdf",
            "filename": "Corporate_Card_Statement_Datadog.pdf",
            "file_type": "PDF",
            "content_bytes": b"%PDF-1.4 Corporate Amex: Datadog Monitoring $520.00",
            "extracted_items": [
                {
                    "vendor": "Datadog Inc",
                    "invoice_id": "DD-8842",
                    "transaction_date": "2026-09-28",  # Prior month transaction date
                    "statement_date": "2026-10-05",    # Current month statement date
                    "currency": "USD",
                    "amount": 520.00,
                    "tax_amount": 0.0,
                    "category": "expense",
                    "confidence": 0.97
                }
            ]
        },
        {
            # Tests Rule 003: Tax inclusion
            "file_id": "drv_006_dinner_receipt",
            "filename": "Team_Engineering_Dinner.jpg",
            "file_type": "IMAGE",
            "content_bytes": b"\xff\xd8\xff Restaurant subtotal $100.00 tax $10.00 total $110.00",
            "extracted_items": [
                {
                    "vendor": "The Bistro Restaurant",
                    "invoice_id": "BST-441",
                    "transaction_date": "2026-10-20",
                    "currency": "USD",
                    "amount": 100.00,
                    "tax_amount": 10.00,
                    "category": "expense",
                    "confidence": 0.91
                }
            ]
        },
        {
            # Extra Bill in Drive not reported in third-party audit report
            "file_id": "drv_007_stripe_pdf",
            "filename": "Stripe_Processing_Fees_Oct.pdf",
            "file_type": "PDF",
            "content_bytes": b"%PDF-1.4 Stripe Merchant Fees $85.00",
            "extracted_items": [
                {
                    "vendor": "Stripe Payments",
                    "invoice_id": "STRIPE-FEE-01",
                    "transaction_date": "2026-10-31",
                    "currency": "USD",
                    "amount": 85.00,
                    "tax_amount": 0.0,
                    "category": "fee",
                    "confidence": 0.99
                }
            ]
        }
    ]

    # Third-party Excel audit report rows
    raw_audit_entries = [
        {
            "audit_id": "aud_001_aws",
            "vendor": "AWS",
            "invoice_id": "INV-1042",
            "date": "2026-10-29",
            "amount": 125.50,
            "department": "Engineering"
        },
        {
            "audit_id": "aud_002_gcp",
            "vendor": "Google Cloud",
            "invoice_id": "GCP-9901",
            "date": "2026-10-15",
            "amount": 340.00,
            "department": "Infrastructure"
        },
        {
            "audit_id": "aud_003_github",
            "vendor": "GitHub",
            "invoice_id": "GH-ENT-55",
            "date": "2026-10-18",
            "amount": 210.00,
            "department": "DevOps"
        },
        {
            # Reconciles via Rule 001 Prior-Month Charge
            "audit_id": "aud_004_datadog",
            "vendor": "Datadog",
            "invoice_id": None,
            "date": "2026-10-05",
            "amount": 520.00,
            "department": "Security"
        },
        {
            # Reconciles via Rule 003 Tax Inclusion (Subtotal 100 + Tax 10 = 110)
            "audit_id": "aud_005_dinner",
            "vendor": "The Bistro Restaurant",
            "invoice_id": None,
            "date": "2026-10-20",
            "amount": 110.00,
            "department": "Engineering"
        },
        {
            # Missing Bill Anomaly: in audit report but bill missing from Google Drive
            "audit_id": "aud_006_openai",
            "vendor": "OpenAI",
            "invoice_id": "OAI-OCT-999",
            "date": "2026-10-25",
            "amount": 450.00,
            "department": "AI Research"
        }
    ]

    ground_truth = {
        "expected_bill_records_count": 6,
        "expected_expense_count": 5,
        "expected_matches_count": 5,
        "expected_anomalies_count": 2  # 1 missing bill (OpenAI) + 1 extra bill (Stripe)
    }

    return {
        "run_id": "reconcile_2026_10_prod",
        "month": "2026-10",
        "raw_file_inputs": raw_files,
        "raw_audit_input": raw_audit_entries,
        "ground_truth": ground_truth,
        "human_review_decisions": {
            "rev_1": {
                "action": "APPROVE_MATCH",
                "notes": "Verified restaurant receipt subtotal + VAT matches audit entry."
            }
        }
    }
