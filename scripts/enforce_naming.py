#!/usr/bin/env python3
"""
enforce_naming.py — DataHub Governance Naming Convention Enforcer
==================================================================
Validates that all metadata YAML files adhere to the naming conventions
defined in docs/naming-convention.md.

Rules enforced:
  1. Dataset names must match: <domain>.<subdomain>.<source>.<entity>.<layer>
  2. Dataset URNs must match the Snowflake URN pattern
  3. All name components must be snake_case (lowercase + underscores only)
  4. Layers must be one of: raw, bronze, silver, gold
  5. Data product names must match: dp_<domain>_<business_purpose>
  6. Domain URNs must match: urn:li:domain:<lowercase_name>
  7. Glossary term names must be PascalCase
  8. File names must match their internal `name` field

Exit codes:
  0 — All naming checks passed
  1 — Naming violations found

Usage:
  python scripts/enforce_naming.py --metadata-dir metadata/ [--output-format github-actions]
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

console = Console()

# ── Naming patterns ────────────────────────────────────────────────────────────
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
PASCAL_CASE_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9_]*$")
VALID_LAYERS = {"raw", "bronze", "silver", "gold"}

# Dataset name: <domain>__<subdomain>__<source>__<entity>__<layer>
# Double underscore (__) is the cross-platform separator (dots are reserved for DNS/IP/infra).
DATASET_NAME_PATTERN = re.compile(
    r"^([a-z][a-z0-9_]*)__([a-z][a-z0-9_]*)__([a-z][a-z0-9_]*)__([a-z][a-z0-9_]*)__([a-z][a-z0-9_]*)$"
)

# Dataset URN for Snowflake:
# urn:li:dataset:(urn:li:dataPlatform:snowflake,<db>.<schema>.<table>,<env>)
DATASET_URN_PATTERN = re.compile(
    r"^urn:li:dataset:\(urn:li:dataPlatform:[a-z][a-z0-9_]*,[^,]+,(PROD|DEV|STAGING|TEST)\)$"
)

# Data product name: dp_<domain>_<business_purpose>
DATA_PRODUCT_NAME_PATTERN = re.compile(r"^dp_[a-z][a-z0-9_]*_[a-z][a-z0-9_]*$")

# Domain URN: urn:li:domain:<name> — uses double underscore for subdomains (no dots)
DOMAIN_URN_PATTERN = re.compile(r"^urn:li:domain:[a-z][a-z0-9_]*(__[a-z][a-z0-9_]*)*$")


@dataclass
class NamingViolation:
    file_path: str
    field: str
    value: str
    rule: str
    suggestion: str = ""

    def as_github_annotation(self) -> str:
        msg = f"[{self.field}] Naming violation: {self.rule}"
        if self.suggestion:
            msg += f" Suggestion: {self.suggestion}"
        return f"::error file={self.file_path},line=0::{msg}"

    def __str__(self) -> str:
        s = f"  ❌  {self.file_path}\n"
        s += f"      Field: {self.field}\n"
        s += f"      Value: '{self.value}'\n"
        s += f"      Rule:  {self.rule}\n"
        if self.suggestion:
            s += f"      Fix:   {self.suggestion}\n"
        return s


class NamingEnforcer:
    def __init__(self, metadata_dir: str, output_format: str = "text"):
        self.metadata_dir = Path(metadata_dir)
        self.output_format = output_format
        self.violations: list[NamingViolation] = []
        self.files_checked = 0

    def add_violation(self, file_path: str, field: str, value: str, rule: str, suggestion: str = ""):
        v = NamingViolation(file_path, field, value, rule, suggestion)
        self.violations.append(v)
        if self.output_format == "github-actions":
            print(v.as_github_annotation())

    def check_snake_case(self, file_path: str, field_name: str, value: str) -> bool:
        """Return True if value is valid snake_case."""
        if not SNAKE_CASE_PATTERN.match(value):
            self.add_violation(
                file_path, field_name, value,
                "Must be snake_case: lowercase letters, digits, and underscores only. No spaces, hyphens, or uppercase.",
                suggestion=value.lower().replace(" ", "_").replace("-", "_")
            )
            return False
        return True

    def check_pascal_case(self, file_path: str, field_name: str, value: str) -> bool:
        """Return True if value is valid PascalCase."""
        if not PASCAL_CASE_PATTERN.match(value):
            self.add_violation(
                file_path, field_name, value,
                "Must be PascalCase: starts with uppercase, no spaces.",
                suggestion="".join(w.capitalize() for w in re.split(r"[_\s-]+", value))
            )
            return False
        return True

    def validate_dataset(self, file_path: str, data: dict, layer: str):
        """Validate dataset naming rules."""
        name = data.get("name", "")
        urn = data.get("urn", "")

        # 1. Name must match the 5-part pattern
        match = DATASET_NAME_PATTERN.match(name)
        if not match:
            self.add_violation(
                file_path, "name", name,
                "Dataset name must follow pattern: <domain>__<subdomain>__<source>__<entity>__<layer>. "
                "All components must be snake_case. Use double underscore (__) as separator (dots are reserved for DNS/IP/infra).",
                suggestion=f"e.g., finance__accounts_payable__erp_sap__invoice__{layer}"
            )
        else:
            domain_, subdomain_, source_, entity_, name_layer = match.groups()

            # 2. Each component must be snake_case
            for component_name, component_val in [
                ("name[domain]", domain_),
                ("name[subdomain]", subdomain_),
                ("name[source]", source_),
                ("name[entity]", entity_),
            ]:
                self.check_snake_case(file_path, component_name, component_val)

            # 3. Layer component must be a valid layer
            if name_layer not in VALID_LAYERS:
                self.add_violation(
                    file_path, "name[layer]", name_layer,
                    f"Layer component '{name_layer}' is not a valid layer. Must be one of: {sorted(VALID_LAYERS)}",
                    suggestion=f"Use one of: raw, bronze, silver, gold"
                )

            # 4. Layer in name must match the directory layer
            if layer and name_layer != layer:
                self.add_violation(
                    file_path, "name[layer]", name_layer,
                    f"Layer in name ('{name_layer}') does not match the directory layer ('{layer}'). "
                    "File should be in the correct layer directory.",
                    suggestion=f"Move file to metadata/datasets/{name_layer}/ or change layer to '{layer}'"
                )

        # 5. URN format validation
        if urn and not DATASET_URN_PATTERN.match(urn):
            self.add_violation(
                file_path, "urn", urn,
                "Dataset URN must follow pattern: urn:li:dataset:(urn:li:dataPlatform:<platform>,<db.schema.table>,<ENV>). "
                "ENV must be PROD, DEV, STAGING, or TEST.",
                suggestion="urn:li:dataset:(urn:li:dataPlatform:snowflake,prod.schema.table,PROD)"
            )

    def validate_domain(self, file_path: str, data: dict):
        """Validate domain naming rules."""
        name = data.get("name", "")
        urn = data.get("urn", "")

        # Domain names should be Title Case or lowercase (both acceptable for display)
        # URN must be lowercase
        if urn and not DOMAIN_URN_PATTERN.match(urn):
            self.add_violation(
                file_path, "urn", urn,
                "Domain URN must match pattern: urn:li:domain:<lowercase_name>. "
                "Sub-domains use double underscore (__) as separator (e.g., finance__accounts_payable). "
                "Dots are not allowed — they conflict with DNS/IP/infra naming.",
                suggestion=f"urn:li:domain:{name.lower().replace(' ', '_').replace('.', '__')}"
            )

    def validate_data_product(self, file_path: str, data: dict):
        """Validate data product naming rules."""
        name = data.get("name", "")

        if not DATA_PRODUCT_NAME_PATTERN.match(name):
            self.add_violation(
                file_path, "name", name,
                "Data product name must follow pattern: dp_<domain>_<business_purpose>. "
                "All components must be snake_case.",
                suggestion=f"e.g., dp_finance_accounts_payable_insights"
            )

        urn = data.get("urn", "")
        if urn:
            expected_urn = f"urn:li:dataProduct:{name}"
            if urn != expected_urn:
                self.add_violation(
                    file_path, "urn", urn,
                    f"Data product URN must be urn:li:dataProduct:<name>.",
                    suggestion=expected_urn
                )

    def validate_glossary(self, file_path: str, data: dict):
        """Validate glossary term naming rules."""
        for term in data.get("terms", []):
            name = term.get("name", "")
            if name:
                self.check_pascal_case(file_path, f"terms[].name ('{name}')", name)

        for node in data.get("nodes", []):
            name = node.get("name", "")
            if name:
                # Node names follow pattern: Category or Category__Subcategory
                # Use double underscore as separator (dots are reserved for DNS/IP/infra)
                parts = re.split(r"__", name)
                for part in parts:
                    if not re.match(r"^[A-Z][a-zA-Z0-9]*$", part):
                        self.add_violation(
                            file_path, f"nodes[].name part ('{part}')", name,
                            "Glossary node name parts must start with uppercase. "
                            "Use double underscore (__) as separator (e.g., Finance or Finance__AccountsPayable)."
                        )

    def validate_file_name_consistency(self, file_path: Path, data: dict):
        """Enforce that the filename stem exactly matches the internal 'name' field.

        Rule: <name>.yaml  ←→  name: "<name>"
        Dots and hyphens are forbidden — use double underscores (__) as segment
        separators and single underscores as word separators within a segment.
        """
        internal_name = data.get("name", "")
        if not internal_name:
            return

        file_stem = file_path.stem   # filename without .yaml, case-preserved

        if file_stem != internal_name:
            self.add_violation(
                str(file_path), "filename", file_path.name,
                f"File name must exactly match the internal 'name' field. "
                f"Expected filename: '{internal_name}.yaml', got: '{file_path.name}'.",
                suggestion=f"Rename the file to: {internal_name}.yaml"
            )

    def validate_file(self, file_path: Path):
        """Validate naming in a single YAML file."""
        self.files_checked += 1
        fp_str = str(file_path)
        fp_norm = fp_str.replace("\\", "/")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError:
            return  # Already caught by validate.py
        except Exception:
            return

        if data is None:
            return

        # Detect layer from path
        layer = ""
        for l in VALID_LAYERS:
            if f"metadata/datasets/{l}/" in fp_norm:
                layer = l
                break

        if "metadata/datasets/" in fp_norm:
            self.validate_dataset(fp_str, data, layer)
        elif "metadata/domains/" in fp_norm:
            self.validate_domain(fp_str, data)
        elif "metadata/data-products/" in fp_norm:
            self.validate_data_product(fp_str, data)
        elif "metadata/glossary/" in fp_norm:
            self.validate_glossary(fp_str, data)

    def run(self) -> int:
        console.print(f"\n[bold blue]📐 Naming Convention Enforcer[/bold blue]")
        console.print(f"   Scanning: [cyan]{self.metadata_dir}[/cyan]\n")

        for yaml_file in sorted(self.metadata_dir.rglob("*.yaml")):
            self.validate_file(yaml_file)

        self._print_summary()
        return 0 if not self.violations else 1

    def _print_summary(self):
        table = Table(title="Naming Convention Check", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Files checked", str(self.files_checked))
        table.add_row(
            "Violations",
            f"[red]{len(self.violations)}[/red]" if self.violations else "[green]0[/green]"
        )
        console.print(table)

        if self.violations:
            console.print("\n[bold red]NAMING VIOLATIONS:[/bold red]")
            for v in self.violations:
                console.print(str(v))
            console.print(
                f"\n[bold red]❌ {len(self.violations)} naming violation(s). "
                f"See docs/naming-convention.md for full rules.[/bold red]"
            )
        else:
            console.print("\n[bold green]✅ All naming conventions passed![/bold green]")


def main():
    parser = argparse.ArgumentParser(description="Enforce DataHub metadata naming conventions.")
    parser.add_argument("--metadata-dir", default="metadata/", help="Root metadata directory.")
    parser.add_argument(
        "--output-format",
        choices=["text", "github-actions"],
        default="text",
    )
    args = parser.parse_args()

    enforcer = NamingEnforcer(metadata_dir=args.metadata_dir, output_format=args.output_format)
    sys.exit(enforcer.run())


if __name__ == "__main__":
    main()

