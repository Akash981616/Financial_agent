"""Versioned Skill Store for Financial Reconciliation Agent.
Encapsulates iterative domain learnings, edge case handling, vendor aliases,
and classification rules derived from historical run evaluations.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class SkillStore:
    def __init__(self, filepath: Optional[str] = None):
        if filepath is None:
            self.filepath = Path(__file__).resolve().parent.parent / "data" / "skill_file.json"
        else:
            self.filepath = Path(filepath)
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Loads versioned rules from persistent skill file."""
        if self.filepath.exists():
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = self._default_rules()
            self.save()

    def save(self):
        """Persists rules to disk."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def _default_rules(self) -> Dict[str, Any]:
        return {
            "version": "1.4.0",
            "last_updated": "2026-11-16",
            "vendor_aliases": {
                "amazon web services": "AWS",
                "aws inc": "AWS",
                "amzn aws": "AWS",
                "google cloud": "Google Cloud Platform",
                "google llc": "Google Cloud Platform",
                "gcp": "Google Cloud Platform",
                "github inc": "GitHub",
                "github enterprise": "GitHub",
                "openai llc": "OpenAI",
                "openai api": "OpenAI",
                "stripe payments": "Stripe",
                "datadog inc": "Datadog",
                "slack technologies": "Slack"
            },
            "edge_case_rules": [
                {
                    "rule_id": "RULE_001_PRIOR_MONTH_STATEMENT",
                    "description": "Credit card statements often bill prior-month charges. If a transaction date is in Month M-1 but statement date or payment date is in Month M, reconcile against Month M audit entries.",
                    "applies_to": "credit_card",
                    "action": "allow_date_window_expansion_days_35"
                },
                {
                    "rule_id": "RULE_002_TRANSFER_VS_EXPENSE",
                    "description": "Legitimate SaaS subscriptions often list 'Autopay ACH Transfer' on bank feeds. Check vendor name before classifying as internal transfer.",
                    "applies_to": "classification",
                    "action": "reclassify_as_expense_if_vendor_is_known_saas"
                },
                {
                    "rule_id": "RULE_003_TAX_INCLUSION",
                    "description": "Some audit reports list total amount inclusive of VAT/sales tax, whereas invoices show base amount separately. Compare both subtotal and total.",
                    "applies_to": "matching",
                    "action": "check_subtotal_and_total_tolerance_0.1"
                },
                {
                    "rule_id": "RULE_004_CANONICAL_LINKING",
                    "description": "If both a credit card statement line item and a standalone PDF invoice exist for the same transaction, link both to a single canonical expense rather than reporting a duplicate.",
                    "applies_to": "deduplication",
                    "action": "merge_to_canonical_expense"
                }
            ],
            "confidence_thresholds": {
                "auto_accept": 0.88,
                "flag_human_review": 0.65
            }
        }

    def normalize_vendor(self, raw_vendor: str) -> str:
        """Normalizes vendor names using the aliases map."""
        cleaned = raw_vendor.strip().lower()
        return self.data.get("vendor_aliases", {}).get(cleaned, raw_vendor.strip())

    def get_rules(self) -> List[Dict[str, Any]]:
        return self.data.get("edge_case_rules", [])

    def get_thresholds(self) -> Dict[str, float]:
        return self.data.get("confidence_thresholds", {"auto_accept": 0.85, "flag_human_review": 0.60})

    def append_rule(self, rule_id: str, description: str, action: str):
        """Appends a newly learned rule from review feedback."""
        rules = self.data.setdefault("edge_case_rules", [])
        rules.append({
            "rule_id": rule_id,
            "description": description,
            "action": action
        })
        self.save()
