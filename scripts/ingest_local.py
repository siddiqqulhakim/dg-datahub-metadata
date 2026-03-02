#!/usr/bin/env python3
"""
ingest_local.py — Push all governance metadata to a local DataHub instance
===========================================================================
Reads every YAML file under metadata/ and emits the appropriate
Metadata Change Proposals (MCPs) to DataHub via the REST emitter.

Ingestion order (dependency-safe):
  1. Tags
  2. Domains
  3. Glossary nodes + terms
  4. Datasets  (raw → bronze → silver → gold)
  5. Data Products

Usage:
  python scripts/ingest_local.py
  python scripts/ingest_local.py --gms-url http://localhost:8080
  python scripts/ingest_local.py --gms-url http://localhost:8080 --token <pat>
  python scripts/ingest_local.py --dry-run        # validate only, no network calls
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import yaml
from rich.console import Console
from rich.table import Table

from datahub.emitter.mce_builder import make_data_platform_urn, make_dataset_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    AuditStampClass,
    DataProductPropertiesClass,
    DatasetLineageTypeClass,
    DatasetPropertiesClass,
    DomainsClass,
    DomainPropertiesClass,
    EditableDatasetPropertiesClass,
    GlobalTagsClass,
    GlossaryNodeInfoClass,
    GlossaryTermAssociationClass,
    GlossaryTermInfoClass,
    GlossaryTermsClass,
    OwnerClass,
    OwnershipClass,
    OwnershipSourceClass,
    OwnershipSourceTypeClass,
    OwnershipTypeClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemaMetadataClass,
    StringTypeClass,
    NumberTypeClass,
    DateTypeClass,
    BooleanTypeClass,
    OtherSchemaClass,
    SubTypesClass,
    TagAssociationClass,
    TagPropertiesClass,
    UpstreamClass,
    UpstreamLineageClass,
)

console = Console()

ACTOR = "urn:li:corpuser:datahub"
METADATA_DIR = Path("metadata")

# ── Type string → DataHub schema field type ───────────────────────────────────
def _field_type(type_str: str) -> SchemaFieldDataTypeClass:
    t = (type_str or "").upper()
    if t in ("STRING", "VARCHAR", "CHAR", "TEXT", "NVARCHAR"):
        return SchemaFieldDataTypeClass(type=StringTypeClass())
    if t in ("INTEGER", "INT", "SMALLINT", "TINYINT", "BIGINT",
             "DECIMAL", "FLOAT", "DOUBLE", "NUMBER", "NUMERIC"):
        return SchemaFieldDataTypeClass(type=NumberTypeClass())
    if t in ("DATE",):
        return SchemaFieldDataTypeClass(type=DateTypeClass())
    if t in ("BOOLEAN", "BOOL"):
        return SchemaFieldDataTypeClass(type=BooleanTypeClass())
    # TIMESTAMP, VARIANT, ARRAY, etc.
    return SchemaFieldDataTypeClass(type=StringTypeClass())


def _audit_stamp() -> AuditStampClass:
    return AuditStampClass(
        time=int(time.time() * 1000),
        actor=ACTOR,
    )


def _ownership(owners_list: list[dict]) -> OwnershipClass:
    owners = []
    for o in owners_list:
        raw_type = o.get("type", "DATAOWNER")
        type_map = {
            "DATAOWNER": OwnershipTypeClass.DATAOWNER,
            "STEWARD": OwnershipTypeClass.DATAOWNER,        # closest available enum
            "TECHNICAL_OWNER": OwnershipTypeClass.TECHNICAL_OWNER,
            "BUSINESS_OWNER": OwnershipTypeClass.BUSINESS_OWNER,
        }
        owners.append(OwnerClass(
            owner=o.get("id", "urn:li:corpuser:unknown"),
            type=type_map.get(raw_type, OwnershipTypeClass.DATAOWNER),
            source=OwnershipSourceClass(type=OwnershipSourceTypeClass.MANUAL),
        ))
    return OwnershipClass(owners=owners)


def _global_tags(tags_list: list[dict]) -> GlobalTagsClass:
    return GlobalTagsClass(tags=[
        TagAssociationClass(tag=t["urn"]) for t in tags_list if "urn" in t
    ])


def _glossary_terms(terms_list: list[dict]) -> GlossaryTermsClass:
    return GlossaryTermsClass(
        terms=[GlossaryTermAssociationClass(urn=t["urn"]) for t in terms_list if "urn" in t],
        auditStamp=_audit_stamp(),
    )


# ═════════════════════════════════════════════════════════════════════════════
# EMITTER WRAPPER
# ═════════════════════════════════════════════════════════════════════════════
class LocalIngester:
    def __init__(self, gms_url: str, token: str = "", dry_run: bool = False):
        self.dry_run = dry_run
        self.emitter = None
        if not dry_run:
            self.emitter = DatahubRestEmitter(
                gms_server=gms_url,
                token=token or None,
            )
        self.emitted = 0
        self.errors: list[str] = []

    def emit(self, mcp: MetadataChangeProposalWrapper, label: str = ""):
        if self.dry_run:
            console.print(f"  [dim][DRY-RUN] {mcp.entityUrn}  {mcp.aspectName}[/dim]")
            self.emitted += 1
            return
        try:
            self.emitter.emit(mcp)
            console.print(f"  [green]✓[/green] {label or mcp.entityUrn}  [dim]{mcp.aspectName}[/dim]")
            self.emitted += 1
        except Exception as e:
            msg = f"FAILED {mcp.entityUrn} [{mcp.aspectName}]: {e}"
            console.print(f"  [red]✗[/red] {msg}")
            self.errors.append(msg)

    def emit_all(self, mcps: Iterable[tuple[MetadataChangeProposalWrapper, str]]):
        for mcp, label in mcps:
            self.emit(mcp, label)


# ═════════════════════════════════════════════════════════════════════════════
# TAGS
# ═════════════════════════════════════════════════════════════════════════════
def ingest_tags(ingester: LocalIngester):
    console.print("\n[bold cyan]━━ 1/5  Tags[/bold cyan]")
    tags_file = METADATA_DIR / "tags" / "tags.yaml"
    if not tags_file.exists():
        console.print("  [yellow]tags/tags.yaml not found — skipping[/yellow]")
        return

    data = yaml.safe_load(tags_file.read_text(encoding="utf-8"))
    for tag in data.get("tags", []):
        urn = tag.get("urn", "")
        if not urn:
            continue
        mcp = MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=TagPropertiesClass(
                name=tag.get("name", ""),
                description=tag.get("description", ""),
                colorHex=tag.get("colorHex"),
            ),
        )
        ingester.emit(mcp, tag.get("name", urn))


# ═════════════════════════════════════════════════════════════════════════════
# DOMAINS
# ═════════════════════════════════════════════════════════════════════════════
def ingest_domains(ingester: LocalIngester):
    console.print("\n[bold cyan]━━ 2/5  Domains[/bold cyan]")
    domain_dir = METADATA_DIR / "domains"
    if not domain_dir.exists():
        return

    for f in sorted(domain_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        urn = data.get("urn", "")
        if not urn:
            continue

        # Domain properties
        ingester.emit(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=DomainPropertiesClass(
                    name=data.get("name", ""),
                    description=data.get("description", ""),
                ),
            ),
            data.get("name", urn),
        )

        # Ownership
        if data.get("owners"):
            ingester.emit(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=_ownership(data["owners"]),
                ),
                f"{data.get('name', urn)} [ownership]",
            )


# ═════════════════════════════════════════════════════════════════════════════
# GLOSSARY
# ═════════════════════════════════════════════════════════════════════════════
def ingest_glossary(ingester: LocalIngester):
    console.print("\n[bold cyan]━━ 3/5  Glossary[/bold cyan]")
    glossary_dir = METADATA_DIR / "glossary"
    if not glossary_dir.exists():
        return

    for f in sorted(glossary_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))

        # Emit nodes first
        for node in data.get("nodes", []):
            urn = node.get("urn", "")
            if not urn:
                continue
            ingester.emit(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=GlossaryNodeInfoClass(
                        definition=node.get("description", ""),
                        name=node.get("name", ""),
                        parentNode=node.get("parentNode"),
                    ),
                ),
                node.get("name", urn),
            )

        # Emit terms
        for term in data.get("terms", []):
            urn = term.get("urn", "")
            if not urn:
                continue
            ingester.emit(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=GlossaryTermInfoClass(
                        name=term.get("name", ""),
                        definition=str(term.get("definition", "")).strip(),
                        parentNode=term.get("parentNode"),
                        sourceRef=term.get("customProperties", {}).get("source"),
                        termSource="INTERNAL",
                    ),
                ),
                term.get("name", urn),
            )

            # Ownership on terms
            if term.get("owners"):
                ingester.emit(
                    MetadataChangeProposalWrapper(
                        entityUrn=urn,
                        aspect=_ownership(term["owners"]),
                    ),
                    f"{term.get('name', urn)} [ownership]",
                )


# ═════════════════════════════════════════════════════════════════════════════
# DATASETS
# ═════════════════════════════════════════════════════════════════════════════
def _build_schema(fields_yaml: list[dict]) -> SchemaMetadataClass:
    fields = []
    for f in fields_yaml:
        fields.append(SchemaFieldClass(
            fieldPath=f.get("name", ""),
            type=_field_type(f.get("type", "STRING")),
            nativeDataType=f.get("nativeDataType", f.get("type", "STRING")),
            description=f.get("description", ""),
            nullable=f.get("nullable", True),
            isPartOfKey="field.primary_key" in str(f.get("tags", [])),
        ))
    return SchemaMetadataClass(
        schemaName="governance",
        platform=make_data_platform_urn("snowflake"),
        version=0,
        fields=fields,
        hash="",
        platformSchema=OtherSchemaClass(rawSchema=""),
    )


def ingest_datasets(ingester: LocalIngester):
    console.print("\n[bold cyan]━━ 4/5  Datasets  (raw → bronze → silver → gold)[/bold cyan]")
    for layer in ("raw", "bronze", "silver", "gold"):
        layer_dir = METADATA_DIR / "datasets" / layer
        if not layer_dir.exists():
            continue
        for f in sorted(layer_dir.glob("*.yaml")):
            _ingest_single_dataset(ingester, f, layer)


def _ingest_single_dataset(ingester: LocalIngester, f: Path, layer: str):
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    urn = data.get("urn", "")
    if not urn:
        console.print(f"  [yellow]Skipping {f.name} — no urn[/yellow]")
        return

    name = data.get("name", f.stem)
    console.print(f"\n  [bold]{layer.upper()}[/bold]  {name}")

    # ── DatasetProperties ─────────────────────────────────────────────────
    custom = data.get("customProperties", {}) or {}
    ingester.emit(
        MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=DatasetPropertiesClass(
                name=name,
                description=str(data.get("description", "")).strip(),
                customProperties={k: str(v) for k, v in custom.items()},
                externalUrl=None,
            ),
        ),
        f"{name} [properties]",
    )

    # ── Ownership ─────────────────────────────────────────────────────────
    if data.get("owners"):
        ingester.emit(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=_ownership(data["owners"]),
            ),
            f"{name} [ownership]",
        )

    # ── Domain ────────────────────────────────────────────────────────────
    if data.get("domain"):
        ingester.emit(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=DomainsClass(domains=[data["domain"]]),
            ),
            f"{name} [domain]",
        )

    # ── Tags ─────────────────────────────────────────────────────────────
    if data.get("tags"):
        ingester.emit(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=_global_tags(data["tags"]),
            ),
            f"{name} [tags]",
        )

    # ── Glossary Terms ────────────────────────────────────────────────────
    if data.get("glossaryTerms"):
        ingester.emit(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=_glossary_terms(data["glossaryTerms"]),
            ),
            f"{name} [glossaryTerms]",
        )

    # ── Schema ────────────────────────────────────────────────────────────
    schema_data = data.get("schema", {}) or {}
    fields_yaml = schema_data.get("fields", [])
    if fields_yaml:
        ingester.emit(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=_build_schema(fields_yaml),
            ),
            f"{name} [schema]",
        )

    # ── Lineage ───────────────────────────────────────────────────────────
    lineage = data.get("lineage", {}) or {}
    upstreams_yaml = lineage.get("upstreams", [])
    if upstreams_yaml:
        upstreams = [
            UpstreamClass(
                dataset=u["dataset"],
                type=DatasetLineageTypeClass.TRANSFORMED,
            )
            for u in upstreams_yaml if u.get("dataset")
        ]
        if upstreams:
            ingester.emit(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=UpstreamLineageClass(upstreams=upstreams),
                ),
                f"{name} [lineage]",
            )

    # ── SubType (layer label) ─────────────────────────────────────────────
    ingester.emit(
        MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=SubTypesClass(typeNames=[layer.capitalize()]),
        ),
        f"{name} [subType:{layer}]",
    )


# ═════════════════════════════════════════════════════════════════════════════
# DATA PRODUCTS
# ═════════════════════════════════════════════════════════════════════════════
def ingest_data_products(ingester: LocalIngester):
    console.print("\n[bold cyan]━━ 5/5  Data Products[/bold cyan]")
    dp_dir = METADATA_DIR / "data-products"
    if not dp_dir.exists():
        return

    for f in sorted(dp_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        urn = data.get("urn", "")
        if not urn:
            continue

        name = data.get("name", f.stem)
        assets = [
            a["urn"] for a in data.get("outputAssets", []) if a.get("urn")
        ]

        ingester.emit(
            MetadataChangeProposalWrapper(
                entityUrn=urn,
                aspect=DataProductPropertiesClass(
                    name=data.get("displayName") or name,
                    description=str(data.get("description", "")).strip(),
                    assets=[
                        __import__(
                            "datahub.metadata.schema_classes",
                            fromlist=["DataProductAssociationClass"]
                        ).DataProductAssociationClass(destinationUrn=a)
                        for a in assets
                    ],
                    customProperties={
                        k: str(v)
                        for k, v in (data.get("customProperties") or {}).items()
                    },
                ),
            ),
            name,
        )

        if data.get("owners"):
            ingester.emit(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=_ownership(data["owners"]),
                ),
                f"{name} [ownership]",
            )

        if data.get("domain"):
            ingester.emit(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=DomainsClass(domains=[data["domain"]]),
                ),
                f"{name} [domain]",
            )

        if data.get("tags"):
            ingester.emit(
                MetadataChangeProposalWrapper(
                    entityUrn=urn,
                    aspect=_global_tags(data["tags"]),
                ),
                f"{name} [tags]",
            )


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Ingest all governance metadata YAMLs into a local DataHub instance."
    )
    parser.add_argument(
        "--gms-url",
        default="http://localhost:8080",
        help="DataHub GMS URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--token",
        default="",
        help="DataHub Personal Access Token (leave blank for local no-auth)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be emitted without making any network calls.",
    )
    parser.add_argument(
        "--metadata-dir",
        default="metadata",
        help="Root metadata directory (default: metadata)",
    )
    args = parser.parse_args()

    global METADATA_DIR
    METADATA_DIR = Path(args.metadata_dir)

    console.print(f"\n[bold blue]🚀 DataHub Local Ingestion[/bold blue]")
    console.print(f"   GMS URL     : [cyan]{args.gms_url}[/cyan]")
    console.print(f"   Metadata dir: [cyan]{METADATA_DIR}[/cyan]")
    console.print(f"   Dry run     : [cyan]{args.dry_run}[/cyan]")

    ingester = LocalIngester(
        gms_url=args.gms_url,
        token=args.token,
        dry_run=args.dry_run,
    )

    # Test connectivity (skip for dry-run)
    if not args.dry_run:
        try:
            ingester.emitter.test_connection()
            console.print(f"\n[green]✅ Connected to DataHub at {args.gms_url}[/green]")
        except Exception as e:
            console.print(f"\n[red]❌ Cannot connect to DataHub at {args.gms_url}: {e}[/red]")
            console.print("[yellow]Tip: Make sure DataHub is running → datahub docker quickstart[/yellow]")
            sys.exit(1)

    start = time.time()

    ingest_tags(ingester)
    ingest_domains(ingester)
    ingest_glossary(ingester)
    ingest_datasets(ingester)
    ingest_data_products(ingester)

    elapsed = time.time() - start

    # Summary
    table = Table(title="\nIngestion Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("MCPs emitted", str(ingester.emitted))
    table.add_row("Errors", f"[red]{len(ingester.errors)}[/red]" if ingester.errors else "[green]0[/green]")
    table.add_row("Duration", f"{elapsed:.1f}s")
    console.print(table)

    if ingester.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for e in ingester.errors:
            console.print(f"  [red]✗[/red] {e}")
        sys.exit(1)
    else:
        console.print(f"\n[bold green]✅ All metadata ingested successfully![/bold green]")
        console.print(f"   Browse at: [link=http://localhost:9002]http://localhost:9002[/link]")


if __name__ == "__main__":
    main()

