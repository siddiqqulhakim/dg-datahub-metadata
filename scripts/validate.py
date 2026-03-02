#!/usr/bin/env python3
"""
validate.py — DataHub Governance Metadata Validator
=====================================================
Validates all YAML metadata files against:
  1. YAML parse validity
  2. Required fields per kind (domain, dataset, glossary, tag, policy, data-product)
  3. Business rules (PII tag required, gold certification required, etc.)
  4. Cross-reference integrity (tags exist in catalogue, glossary terms defined)
  5. Description length minimums
  6. Duplicate URN detection

Exit codes:
  0 — All checks passed
  1 — Validation errors found (merge should be blocked)
  2 — Internal script error

Usage:
  python scripts/validate.py --metadata-dir metadata/ [--verbose] [--output-format github-actions]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

console = Console()

# ── Minimum description lengths ───────────────────────────────────────────────
MIN_DESCRIPTION_LENGTH = 50
GOLD_MIN_DESCRIPTION_LENGTH = 150

# ── Valid tag URNs loaded from the tag catalogue ───────────────────────────────
REQUIRED_PII_TAG = "urn:li:tag:sensitivity.pii"
LAYER_TAGS = {
    "raw": "urn:li:tag:layer.raw",
    "bronze": "urn:li:tag:layer.bronze",
    "silver": "urn:li:tag:layer.silver",
    "gold": "urn:li:tag:layer.gold",
}
VALID_KINDS = {"domain", "dataset", "glossary", "tags", "ownership_registry", "policies", "dataProduct"}
VALID_OWNERSHIP_TYPES = {"DATAOWNER", "STEWARD", "TECHNICAL_OWNER", "BUSINESS_OWNER"}
VALID_CERTIFICATION_STATUSES = {"CERTIFIED", "UNCERTIFIED", "BRONZE", "SILVER", "GOLD"}

# ── Required fields per kind ───────────────────────────────────────────────────
REQUIRED_FIELDS: dict[str, list[str]] = {
    "domain": ["urn", "name", "description", "owners"],
    "dataset": ["urn", "name", "description", "domain", "owners", "tags", "schema"],
    "glossary": ["version", "kind"],
    "tags": ["version", "kind", "tags"],
    "ownership_registry": ["version", "kind", "users"],
    "policies": ["version", "kind", "policies"],
    "dataProduct": ["urn", "name", "description", "domain", "owners", "outputAssets"],
}

# ── Fields required specifically on GOLD datasets ─────────────────────────────
GOLD_REQUIRED_FIELDS = ["certification", "glossaryTerms", "lineage", "freshness"]


class ValidationError:
    def __init__(self, file_path: str, line: int, field: str, message: str, level: str = "error"):
        self.file_path = file_path
        self.line = line
        self.field = field
        self.message = message
        self.level = level  # "error" | "warning"

    def as_github_annotation(self) -> str:
        prefix = "::error" if self.level == "error" else "::warning"
        return f"{prefix} file={self.file_path},line={self.line}::[{self.field}] {self.message}"

    def __repr__(self) -> str:
        icon = "❌" if self.level == "error" else "⚠️"
        return f"{icon}  {self.file_path}:{self.line}  [{self.field}]  {self.message}"


class MetadataValidator:
    def __init__(self, metadata_dir: str, verbose: bool = False, output_format: str = "text"):
        self.metadata_dir = Path(metadata_dir)
        self.verbose = verbose
        self.output_format = output_format
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []
        self.seen_urns: dict[str, str] = {}          # urn → first file that defined it
        self.valid_tag_urns: set[str] = set()
        self.valid_glossary_urns: set[str] = set()
        self.valid_owner_urns: set[str] = set()
        self.files_checked = 0
        self.files_passed = 0

    def add_error(self, file_path: str, line: int, field: str, message: str):
        err = ValidationError(str(file_path), line, field, message, level="error")
        self.errors.append(err)
        if self.output_format == "github-actions":
            print(err.as_github_annotation())

    def add_warning(self, file_path: str, line: int, field: str, message: str):
        warn = ValidationError(str(file_path), line, field, message, level="warning")
        self.warnings.append(warn)
        if self.output_format == "github-actions":
            print(warn.as_github_annotation())

    def load_tag_catalogue(self):
        """Pre-load all valid tag URNs from the tags YAML file."""
        tags_file = self.metadata_dir / "tags" / "tags.yaml"
        if not tags_file.exists():
            self.add_error(str(tags_file), 0, "tags_catalogue", "tags/tags.yaml not found — cannot validate tag references.")
            return
        try:
            with open(tags_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            for tag in data.get("tags", []):
                if "urn" in tag:
                    self.valid_tag_urns.add(tag["urn"])
        except yaml.YAMLError as e:
            self.add_error(str(tags_file), 0, "yaml_parse", f"Failed to parse tags catalogue: {e}")

    def load_glossary_catalogue(self):
        """Pre-load all valid glossary term URNs."""
        glossary_dir = self.metadata_dir / "glossary"
        if not glossary_dir.exists():
            return
        for file_path in glossary_dir.glob("*.yaml"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                for term in data.get("terms", []):
                    if "urn" in term:
                        self.valid_glossary_urns.add(term["urn"])
            except yaml.YAMLError:
                pass

    def load_owner_registry(self):
        """Pre-load all valid owner URNs from the ownership registry."""
        owners_file = self.metadata_dir / "ownership" / "owners.yaml"
        if not owners_file.exists():
            self.add_error(str(owners_file), 0, "ownership_registry",
                           "ownership/owners.yaml not found — cannot validate owner references.")
            return
        try:
            with open(owners_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            for user in data.get("users", []):
                if "urn" in user:
                    self.valid_owner_urns.add(user["urn"])
            for group in data.get("groups", []):
                if "urn" in group:
                    self.valid_owner_urns.add(group["urn"])
        except yaml.YAMLError as e:
            self.add_error(str(owners_file), 0, "yaml_parse", f"Failed to parse ownership registry: {e}")

    def validate_urn_uniqueness(self, file_path: str, urn: str):
        """Detect duplicate URNs across all files."""
        if urn in self.seen_urns:
            self.add_error(file_path, 0, "urn.duplicate",
                           f"Duplicate URN '{urn}' — first defined in '{self.seen_urns[urn]}'.")
        else:
            self.seen_urns[urn] = file_path

    def validate_urn_format(self, file_path: str, urn: str, kind: str):
        """Validate that the URN follows expected DataHub patterns."""
        patterns = {
            "domain": r"^urn:li:domain:[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$",
            "dataset": r"^urn:li:dataset:\(urn:li:dataPlatform:[a-z][a-z0-9_]*,.+,(PROD|DEV|STAGING|TEST)\)$",
            "dataProduct": r"^urn:li:dataProduct:dp_[a-z][a-z0-9_]*$",
        }
        if kind in patterns:
            if not re.match(patterns[kind], urn):
                self.add_error(file_path, 0, "urn.format",
                               f"URN '{urn}' does not match expected pattern for kind '{kind}'. "
                               f"Expected: {patterns[kind]}")

    def validate_owners(self, file_path: str, owners: list[dict], is_gold: bool = False):
        """Validate owner list completeness and referential integrity."""
        if not owners:
            self.add_error(file_path, 0, "owners.missing", "No owners defined. Every artefact must have at least one owner.")
            return

        owner_types = {o.get("type") for o in owners}

        # Every dataset must have a DATAOWNER
        if "DATAOWNER" not in owner_types:
            self.add_error(file_path, 0, "owners.no_dataowner",
                           "No owner with type=DATAOWNER found. Every dataset requires at least one DATAOWNER.")

        # Every dataset must have a STEWARD
        if "STEWARD" not in owner_types:
            self.add_error(file_path, 0, "owners.no_steward",
                           "No owner with type=STEWARD found. Every dataset requires at least one STEWARD.")

        # Validate owner type values
        for owner in owners:
            owner_type = owner.get("type", "")
            if owner_type not in VALID_OWNERSHIP_TYPES:
                self.add_error(file_path, 0, "owners.invalid_type",
                               f"Invalid ownership type '{owner_type}'. Must be one of: {VALID_OWNERSHIP_TYPES}")

            # Validate owner URN exists in registry
            owner_id = owner.get("id", "")
            if owner_id and self.valid_owner_urns and owner_id not in self.valid_owner_urns:
                self.add_warning(file_path, 0, "owners.unknown_urn",
                                 f"Owner URN '{owner_id}' is not in the ownership registry (ownership/owners.yaml).")

    def validate_description(self, file_path: str, description: Any, is_gold: bool = False):
        """Validate description presence and length."""
        if not description:
            self.add_error(file_path, 0, "description.missing",
                           "Description is required. Provide a meaningful description.")
            return

        desc_str = str(description).strip()
        min_len = GOLD_MIN_DESCRIPTION_LENGTH if is_gold else MIN_DESCRIPTION_LENGTH

        if len(desc_str) < min_len:
            level = "error" if is_gold else "warning"
            msg = (f"Description is too short ({len(desc_str)} chars). "
                   f"Minimum is {min_len} chars{'for Gold datasets' if is_gold else ''}.")
            if level == "error":
                self.add_error(file_path, 0, "description.too_short", msg)
            else:
                self.add_warning(file_path, 0, "description.too_short", msg)

        placeholder_patterns = [r"^TODO", r"^TBD", r"^FIXME", r"^placeholder", r"^description here"]
        for pattern in placeholder_patterns:
            if re.match(pattern, desc_str, re.IGNORECASE):
                self.add_error(file_path, 0, "description.placeholder",
                               f"Description looks like a placeholder: '{desc_str[:60]}...'")
                break

    def validate_tags(self, file_path: str, tags: list[dict], has_pii_fields: bool = False, layer: str = ""):
        """Validate tag references and business rules."""
        if not tags:
            self.add_warning(file_path, 0, "tags.missing", "No tags defined. Consider adding layer and source tags.")
            return

        tag_urns = {t.get("urn", "") for t in tags}

        # Validate all tag URNs exist in catalogue
        if self.valid_tag_urns:
            for tag_urn in tag_urns:
                if tag_urn and tag_urn not in self.valid_tag_urns:
                    self.add_error(file_path, 0, "tags.undefined",
                                   f"Tag '{tag_urn}' is not defined in metadata/tags/tags.yaml.")

        # PII datasets must have the sensitivity.pii tag
        if has_pii_fields and REQUIRED_PII_TAG not in tag_urns:
            self.add_error(file_path, 0, "tags.pii_required",
                           f"Dataset has PII fields (contains_pii=true or pii fields in schema) "
                           f"but is missing the mandatory '{REQUIRED_PII_TAG}' tag.")

        # Layer tag must match the directory layer
        if layer and layer in LAYER_TAGS:
            expected_layer_tag = LAYER_TAGS[layer]
            if expected_layer_tag not in tag_urns:
                self.add_warning(file_path, 0, "tags.layer_missing",
                                 f"Expected layer tag '{expected_layer_tag}' for layer '{layer}' not found in tags list.")

    def validate_dataset(self, file_path: str, data: dict, layer: str):
        """Validate a dataset YAML file."""
        is_gold = layer == "gold"
        file_path_str = str(file_path)

        # Required fields
        for field in REQUIRED_FIELDS["dataset"]:
            if field not in data or data[field] is None:
                self.add_error(file_path_str, 0, f"required.{field}",
                               f"Required field '{field}' is missing or null.")

        # URN uniqueness and format
        if "urn" in data:
            self.validate_urn_uniqueness(file_path_str, data["urn"])
            self.validate_urn_format(file_path_str, data["urn"], "dataset")

        # Domain must be set
        if not data.get("domain"):
            self.add_error(file_path_str, 0, "domain.missing",
                           "Dataset must be assigned to a domain (field: domain).")

        # Description
        self.validate_description(file_path_str, data.get("description"), is_gold=is_gold)

        # Owners
        self.validate_owners(file_path_str, data.get("owners", []), is_gold=is_gold)

        # Detect PII from schema fields or customProperties
        has_pii_fields = False
        custom_props = data.get("customProperties", {}) or {}
        if str(custom_props.get("contains_pii", "false")).lower() == "true":
            has_pii_fields = True

        # Check schema fields for PII tags
        schema = data.get("schema", {}) or {}
        for field in schema.get("fields", []):
            field_tags = [t.get("urn", "") for t in field.get("tags", [])]
            if any("sensitivity.pii" in t or "pii." in t for t in field_tags):
                has_pii_fields = True
                break

        # Tags
        self.validate_tags(file_path_str, data.get("tags", []),
                           has_pii_fields=has_pii_fields, layer=layer)

        # Gold-specific checks
        if is_gold:
            for req_field in GOLD_REQUIRED_FIELDS:
                if req_field not in data or data[req_field] is None:
                    self.add_error(file_path_str, 0, f"gold.required.{req_field}",
                                   f"Gold datasets require the '{req_field}' field.")

            # Certification must have status=CERTIFIED
            cert = data.get("certification", {}) or {}
            if cert.get("status") != "CERTIFIED":
                self.add_error(file_path_str, 0, "gold.certification.status",
                               f"Gold datasets must have certification.status=CERTIFIED. "
                               f"Found: '{cert.get('status', 'NOT SET')}'.")

            cert_required = ["certifiedBy", "certifiedDate"]
            for field in cert_required:
                if not cert.get(field):
                    self.add_error(file_path_str, 0, f"gold.certification.{field}",
                                   f"Gold certification must include '{field}'.")

            # Gold must have at least one glossary term
            if not data.get("glossaryTerms"):
                self.add_error(file_path_str, 0, "gold.glossaryTerms.missing",
                               "Gold datasets must reference at least one glossary term.")

            # Validate glossary term URNs exist
            for term in data.get("glossaryTerms", []):
                term_urn = term.get("urn", "")
                if term_urn and self.valid_glossary_urns and term_urn not in self.valid_glossary_urns:
                    self.add_warning(file_path_str, 0, "glossaryTerms.undefined",
                                     f"Glossary term '{term_urn}' is not defined in any glossary file.")

            # Gold must have freshness SLA
            freshness = data.get("freshness", {}) or {}
            if not freshness.get("sla"):
                self.add_error(file_path_str, 0, "gold.freshness.sla",
                               "Gold datasets must define freshness.sla.")

            # Gold must NOT contain raw PII
            if has_pii_fields:
                tags_urns = {t.get("urn", "") for t in data.get("tags", [])}
                if REQUIRED_PII_TAG in tags_urns:
                    self.add_error(file_path_str, 0, "gold.pii_not_allowed",
                                   "Gold datasets must not contain raw PII. "
                                   "Apply hashing/masking in the bronze layer.")

    def validate_domain(self, file_path: str, data: dict):
        """Validate a domain YAML file."""
        for field in REQUIRED_FIELDS["domain"]:
            if field not in data or data[field] is None:
                self.add_error(str(file_path), 0, f"required.{field}",
                               f"Required field '{field}' is missing.")

        if "urn" in data:
            self.validate_urn_uniqueness(str(file_path), data["urn"])
            self.validate_urn_format(str(file_path), data["urn"], "domain")

        self.validate_description(str(file_path), data.get("description"))
        self.validate_owners(str(file_path), data.get("owners", []))

    def validate_data_product(self, file_path: str, data: dict):
        """Validate a data product YAML file."""
        for field in REQUIRED_FIELDS["dataProduct"]:
            if field not in data or data[field] is None:
                self.add_error(str(file_path), 0, f"required.{field}",
                               f"Required field '{field}' is missing.")

        if "urn" in data:
            self.validate_urn_uniqueness(str(file_path), data["urn"])
            self.validate_urn_format(str(file_path), data["urn"], "dataProduct")

        self.validate_description(str(file_path), data.get("description"), is_gold=True)
        self.validate_owners(str(file_path), data.get("owners", []))

    def validate_glossary(self, file_path: str, data: dict):
        """Validate a glossary YAML file — check for duplicate term names."""
        seen_names: dict[str, int] = {}
        for term in data.get("terms", []):
            name = term.get("name", "")
            if name in seen_names:
                self.add_error(str(file_path), 0, "glossary.duplicate_name",
                               f"Duplicate glossary term name '{name}' in this file.")
            else:
                seen_names[name] = 1

            # Term names must be PascalCase
            if name and not re.match(r"^[A-Z][a-zA-Z0-9_]*$", name):
                self.add_error(str(file_path), 0, "glossary.naming",
                               f"Glossary term name '{name}' must be PascalCase (e.g., AccountsPayable).")

            # Every term must have a definition
            if not term.get("definition") or len(str(term.get("definition", "")).strip()) < 50:
                self.add_error(str(file_path), 0, "glossary.definition",
                               f"Term '{name}' has a missing or too-short definition (< 50 chars).")

            # Every term must have at least one owner
            if not term.get("owners"):
                self.add_error(str(file_path), 0, "glossary.no_owner",
                               f"Term '{name}' has no owners defined.")

    def validate_file(self, file_path: Path):
        """Load and validate a single YAML file."""
        self.files_checked += 1
        file_path_str = str(file_path)

        # Parse YAML
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.add_error(file_path_str, 0, "yaml.parse_error",
                           f"YAML parse error: {e}")
            return
        except Exception as e:
            self.add_error(file_path_str, 0, "file.read_error", f"Cannot read file: {e}")
            return

        if data is None:
            self.add_warning(file_path_str, 0, "file.empty", "File is empty or contains only comments.")
            return

        kind = data.get("kind", "")

        # Route to type-specific validator
        if "metadata/datasets/raw/" in file_path_str.replace("\\", "/"):
            self.validate_dataset(file_path, data, layer="raw")
        elif "metadata/datasets/bronze/" in file_path_str.replace("\\", "/"):
            self.validate_dataset(file_path, data, layer="bronze")
        elif "metadata/datasets/silver/" in file_path_str.replace("\\", "/"):
            self.validate_dataset(file_path, data, layer="silver")
        elif "metadata/datasets/gold/" in file_path_str.replace("\\", "/"):
            self.validate_dataset(file_path, data, layer="gold")
        elif "metadata/domains/" in file_path_str.replace("\\", "/"):
            self.validate_domain(file_path, data)
        elif "metadata/glossary/" in file_path_str.replace("\\", "/"):
            self.validate_glossary(file_path, data)
        elif "metadata/data-products/" in file_path_str.replace("\\", "/"):
            self.validate_data_product(file_path, data)
        elif kind == "domain":
            self.validate_domain(file_path, data)
        elif kind == "dataset":
            layer = data.get("customProperties", {}).get("layer", "")
            self.validate_dataset(file_path, data, layer=layer)
        elif kind == "dataProduct":
            self.validate_data_product(file_path, data)
        elif kind == "glossary":
            self.validate_glossary(file_path, data)

        errors_before = len(self.errors)
        if len(self.errors) == errors_before:
            self.files_passed += 1

    def run(self) -> int:
        """Execute full validation. Returns exit code."""
        console.print(f"\n[bold blue]🔍 DataHub Metadata Validator[/bold blue]")
        console.print(f"   Scanning: [cyan]{self.metadata_dir}[/cyan]\n")

        # Pre-load catalogues for cross-reference checks
        self.load_tag_catalogue()
        self.load_glossary_catalogue()
        self.load_owner_registry()

        # Walk all YAML files
        for yaml_file in sorted(self.metadata_dir.rglob("*.yaml")):
            if self.verbose:
                console.print(f"  Checking [dim]{yaml_file}[/dim]")
            self.validate_file(yaml_file)

        # Save report
        self._save_report()

        # Print summary
        self._print_summary()

        error_count = len(self.errors)
        return 0 if error_count == 0 else 1

    def _save_report(self):
        """Save validation results to a JSON report."""
        os.makedirs("reports", exist_ok=True)
        report = {
            "files_checked": self.files_checked,
            "files_passed": self.files_passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [
                {"file": e.file_path, "line": e.line, "field": e.field, "message": e.message}
                for e in self.errors
            ],
            "warnings": [
                {"file": w.file_path, "line": w.line, "field": w.field, "message": w.message}
                for w in self.warnings
            ],
        }
        with open("reports/validation-report.json", "w") as f:
            json.dump(report, f, indent=2)

    def _print_summary(self):
        """Print a rich formatted summary."""
        table = Table(title="Validation Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Files checked", str(self.files_checked))
        table.add_row("Files passed", str(self.files_passed))
        table.add_row("Errors", f"[red]{len(self.errors)}[/red]" if self.errors else "[green]0[/green]")
        table.add_row("Warnings", f"[yellow]{len(self.warnings)}[/yellow]" if self.warnings else "[green]0[/green]")
        console.print(table)

        if self.errors:
            console.print("\n[bold red]ERRORS:[/bold red]")
            for err in self.errors:
                console.print(f"  [red]✗[/red] {err.file_path}  [dim][{err.field}][/dim]  {err.message}")

        if self.warnings and self.verbose:
            console.print("\n[bold yellow]WARNINGS:[/bold yellow]")
            for warn in self.warnings:
                console.print(f"  [yellow]⚠[/yellow] {warn.file_path}  [dim][{warn.field}][/dim]  {warn.message}")

        if not self.errors:
            console.print("\n[bold green]✅ All validations passed![/bold green]")
        else:
            console.print(f"\n[bold red]❌ {len(self.errors)} error(s) found. Fix before merging.[/bold red]")


def main():
    parser = argparse.ArgumentParser(
        description="Validate DataHub governance metadata YAML files."
    )
    parser.add_argument("--metadata-dir", default="metadata/", help="Root metadata directory.")
    parser.add_argument("--verbose", action="store_true", help="Show verbose output including warnings.")
    parser.add_argument(
        "--output-format",
        choices=["text", "github-actions"],
        default="text",
        help="Output format for errors (github-actions emits ::error annotations).",
    )
    args = parser.parse_args()

    validator = MetadataValidator(
        metadata_dir=args.metadata_dir,
        verbose=args.verbose,
        output_format=args.output_format,
    )
    sys.exit(validator.run())


if __name__ == "__main__":
    main()

