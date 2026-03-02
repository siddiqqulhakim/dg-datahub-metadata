#!/usr/bin/env python3
"""
check_owners.py — DataHub Governance Ownership Completeness Checker
====================================================================
Validates that every metadata artefact (datasets, domains, data products,
glossary terms) has:
  1. At least one DATAOWNER (for datasets and data products)
  2. At least one STEWARD (for all artefact types)
  3. All owner URNs exist in the ownership registry (owners.yaml)
  4. Gold-layer datasets have explicit human owners (not just groups)
  5. No owner URNs referencing inactive/departed users

This script cross-references the ownership registry at:
  metadata/ownership/owners.yaml

Exit codes:
  0 — All ownership checks passed
  1 — Ownership errors found (merge blocked)

Usage:
  python scripts/check_owners.py \\
    --metadata-dir metadata/ \\
    --owners-registry metadata/ownership/owners.yaml \\
    [--output-format github-actions]
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class OwnershipIssue:
    file_path: str
    severity: str       # "error" | "warning"
    rule: str
    message: str

    def as_github_annotation(self) -> str:
        prefix = "::error" if self.severity == "error" else "::warning"
        return f"{prefix} file={self.file_path},line=0::[ownership.{self.rule}] {self.message}"

    def __str__(self) -> str:
        icon = "❌" if self.severity == "error" else "⚠️"
        return f"  {icon}  {self.file_path}\n      [{self.rule}] {self.message}"


class OwnershipChecker:
    def __init__(self, metadata_dir: str, owners_registry: str, output_format: str = "text"):
        self.metadata_dir = Path(metadata_dir)
        self.owners_registry_path = Path(owners_registry)
        self.output_format = output_format
        self.issues: list[OwnershipIssue] = []
        self.files_checked = 0

        # Loaded from owners.yaml
        self.known_user_urns: set[str] = set()
        self.known_group_urns: set[str] = set()
        self.active_user_urns: set[str] = set()
        self.all_known_urns: set[str] = set()

        # Counters
        self.datasets_checked = 0
        self.datasets_with_issues = 0

    def add_issue(self, file_path: str, severity: str, rule: str, message: str):
        issue = OwnershipIssue(str(file_path), severity, rule, message)
        self.issues.append(issue)
        if self.output_format == "github-actions":
            print(issue.as_github_annotation())

    def load_registry(self):
        """Load the ownership registry into memory."""
        if not self.owners_registry_path.exists():
            self.add_issue(
                str(self.owners_registry_path), "error",
                "registry_missing",
                f"Ownership registry not found at '{self.owners_registry_path}'. "
                "This file is required for ownership validation."
            )
            return

        try:
            with open(self.owners_registry_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.add_issue(
                str(self.owners_registry_path), "error",
                "registry_parse_error",
                f"Cannot parse ownership registry: {e}"
            )
            return

        for user in data.get("users", []):
            urn = user.get("urn", "")
            if urn:
                self.known_user_urns.add(urn)
                self.all_known_urns.add(urn)
                if user.get("active", True):
                    self.active_user_urns.add(urn)

        for group in data.get("groups", []):
            urn = group.get("urn", "")
            if urn:
                self.known_group_urns.add(urn)
                self.all_known_urns.add(urn)

        console.print(
            f"   Loaded registry: "
            f"[green]{len(self.known_user_urns)}[/green] users, "
            f"[green]{len(self.known_group_urns)}[/green] groups\n"
        )

    def check_owners_list(
        self,
        file_path: str,
        owners: list[dict[str, Any]],
        artefact_type: str,
        is_gold: bool = False,
    ):
        """
        Check an owners list for completeness and registry membership.

        artefact_type: 'dataset' | 'domain' | 'dataProduct' | 'glossaryTerm'
        """
        if not owners:
            self.add_issue(
                file_path, "error", "no_owners",
                f"Artefact has no owners defined. "
                f"Every {artefact_type} must have at least one owner."
            )
            return

        owner_types = {o.get("type", "") for o in owners}
        owner_urns = [o.get("id", "") for o in owners]

        # 1. DATAOWNER required for datasets and data products
        if artefact_type in ("dataset", "dataProduct"):
            if "DATAOWNER" not in owner_types:
                self.add_issue(
                    file_path, "error", "missing_dataowner",
                    f"No owner with type=DATAOWNER found. "
                    f"Every {artefact_type} requires at least one DATAOWNER."
                )

        # 2. STEWARD required for all artefacts
        if "STEWARD" not in owner_types:
            self.add_issue(
                file_path, "error", "missing_steward",
                f"No owner with type=STEWARD found. "
                f"Every {artefact_type} requires at least one STEWARD."
            )

        # 3. Validate all owner URNs exist in registry
        for urn in owner_urns:
            if not urn:
                self.add_issue(file_path, "error", "owner_empty_urn",
                               "An owner entry has an empty or missing 'id' (URN).")
                continue

            if self.all_known_urns and urn not in self.all_known_urns:
                self.add_issue(
                    file_path, "error", "owner_not_in_registry",
                    f"Owner URN '{urn}' is not in the ownership registry "
                    f"({self.owners_registry_path}). "
                    "Add this user/group to the registry before referencing them."
                )
                continue

            # 4. Check for inactive users
            if urn in self.known_user_urns and urn not in self.active_user_urns:
                self.add_issue(
                    file_path, "error", "owner_inactive",
                    f"Owner URN '{urn}' is marked as inactive (active: false) in the registry. "
                    "Replace with an active user or team."
                )

        # 5. Gold datasets: at least one human owner (corpuser, not just group)
        if is_gold:
            human_owners = [
                o for o in owners
                if "corpuser" in o.get("id", "")
            ]
            if not human_owners:
                self.add_issue(
                    file_path, "error", "gold_no_human_owner",
                    "Gold datasets must have at least one human owner (urn:li:corpuser:...). "
                    "Groups alone are not sufficient for Gold certification."
                )

        # 6. Gold datasets: recommend TECHNICAL_OWNER
        if is_gold:
            if "TECHNICAL_OWNER" not in owner_types:
                self.add_issue(
                    file_path, "warning", "gold_no_technical_owner",
                    "Gold datasets should have a TECHNICAL_OWNER defined "
                    "(the engineering team responsible for the pipeline)."
                )

    def check_dataset_file(self, file_path: Path, data: dict, layer: str):
        """Check ownership on a dataset file."""
        self.datasets_checked += 1
        is_gold = layer == "gold"
        errors_before = len(self.issues)

        self.check_owners_list(
            str(file_path),
            data.get("owners", []),
            artefact_type="dataset",
            is_gold=is_gold,
        )

        if len(self.issues) > errors_before:
            self.datasets_with_issues += 1

    def check_domain_file(self, file_path: Path, data: dict):
        """Check ownership on a domain file."""
        self.check_owners_list(str(file_path), data.get("owners", []), artefact_type="domain")

    def check_data_product_file(self, file_path: Path, data: dict):
        """Check ownership on a data product file."""
        self.check_owners_list(str(file_path), data.get("owners", []), artefact_type="dataProduct")

    def check_glossary_file(self, file_path: Path, data: dict):
        """Check ownership on all glossary terms in a file."""
        for term in data.get("terms", []):
            name = term.get("name", "unknown")
            owners = term.get("owners", [])
            if not owners:
                self.add_issue(
                    str(file_path), "error", "glossary_term_no_owner",
                    f"Glossary term '{name}' has no owners. "
                    "Every term must have at least one STEWARD."
                )
            else:
                owner_types = {o.get("type", "") for o in owners}
                if "STEWARD" not in owner_types:
                    self.add_issue(
                        str(file_path), "warning", "glossary_term_no_steward",
                        f"Glossary term '{name}' has no STEWARD owner."
                    )
                for owner in owners:
                    urn = owner.get("id", "")
                    if urn and self.all_known_urns and urn not in self.all_known_urns:
                        self.add_issue(
                            str(file_path), "error", "glossary_owner_not_in_registry",
                            f"Term '{name}' references unknown owner URN '{urn}'."
                        )

    def validate_file(self, file_path: Path):
        """Route a file to the appropriate checker."""
        self.files_checked += 1
        fp_norm = str(file_path).replace("\\", "/")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            return

        if data is None:
            return

        # Detect layer from path
        layer = ""
        for l in ("raw", "bronze", "silver", "gold"):
            if f"metadata/datasets/{l}/" in fp_norm:
                layer = l
                break

        if "metadata/datasets/" in fp_norm:
            self.check_dataset_file(file_path, data, layer)
        elif "metadata/domains/" in fp_norm:
            self.check_domain_file(file_path, data)
        elif "metadata/data-products/" in fp_norm:
            self.check_data_product_file(file_path, data)
        elif "metadata/glossary/" in fp_norm:
            self.check_glossary_file(file_path, data)

    def generate_ownership_report(self) -> dict:
        """Generate a report of ownership coverage statistics."""
        error_count = sum(1 for i in self.issues if i.severity == "error")
        warning_count = sum(1 for i in self.issues if i.severity == "warning")
        return {
            "files_checked": self.files_checked,
            "datasets_checked": self.datasets_checked,
            "datasets_with_issues": self.datasets_with_issues,
            "error_count": error_count,
            "warning_count": warning_count,
            "registry_users": len(self.known_user_urns),
            "registry_groups": len(self.known_group_urns),
        }

    def run(self) -> int:
        console.print(f"\n[bold blue]👤 Ownership Completeness Checker[/bold blue]")
        console.print(f"   Scanning:  [cyan]{self.metadata_dir}[/cyan]")
        console.print(f"   Registry:  [cyan]{self.owners_registry_path}[/cyan]\n")

        # Load registry first
        self.load_registry()

        # Walk all YAML files
        for yaml_file in sorted(self.metadata_dir.rglob("*.yaml")):
            # Skip the registry itself
            if yaml_file.resolve() == self.owners_registry_path.resolve():
                continue
            self.validate_file(yaml_file)

        self._print_summary()

        error_count = sum(1 for i in self.issues if i.severity == "error")
        return 0 if error_count == 0 else 1

    def _print_summary(self):
        report = self.generate_ownership_report()

        table = Table(title="Ownership Check Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Files checked", str(report["files_checked"]))
        table.add_row("Datasets checked", str(report["datasets_checked"]))
        table.add_row("Datasets with issues", str(report["datasets_with_issues"]))
        table.add_row("Registry users", str(report["registry_users"]))
        table.add_row("Registry groups", str(report["registry_groups"]))
        table.add_row(
            "Errors",
            f"[red]{report['error_count']}[/red]" if report["error_count"] else "[green]0[/green]"
        )
        table.add_row(
            "Warnings",
            f"[yellow]{report['warning_count']}[/yellow]" if report["warning_count"] else "[green]0[/green]"
        )
        console.print(table)

        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]

        if errors:
            console.print("\n[bold red]OWNERSHIP ERRORS:[/bold red]")
            for issue in errors:
                console.print(str(issue))

        if warnings:
            console.print("\n[bold yellow]OWNERSHIP WARNINGS:[/bold yellow]")
            for issue in warnings:
                console.print(str(issue))

        if not errors:
            console.print("\n[bold green]✅ All ownership checks passed![/bold green]")
        else:
            console.print(
                f"\n[bold red]❌ {len(errors)} ownership error(s) found. "
                "All datasets must have valid owners before merging.[/bold red]"
            )


def main():
    parser = argparse.ArgumentParser(description="Check ownership completeness across all metadata.")
    parser.add_argument("--metadata-dir", default="metadata/", help="Root metadata directory.")
    parser.add_argument(
        "--owners-registry",
        default="metadata/ownership/owners.yaml",
        help="Path to the ownership registry YAML file.",
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "github-actions"],
        default="text",
    )
    args = parser.parse_args()

    checker = OwnershipChecker(
        metadata_dir=args.metadata_dir,
        owners_registry=args.owners_registry,
        output_format=args.output_format,
    )
    sys.exit(checker.run())


if __name__ == "__main__":
    main()

