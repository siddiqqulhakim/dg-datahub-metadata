# Ownership Model

## Overview

Every data artefact (dataset, domain, glossary term, data product) must have at least one accountable owner. This document defines ownership types, responsibilities, and how ownership is structured in metadata YAML files.

---

## 1. Ownership Types

### `DATAOWNER`

**Description:** The business owner who is ultimately accountable for the data asset.

**Responsibilities:**
- Accountable for data quality and fitness for purpose
- Approves access to sensitive data
- Signs off on dataset certification (Gold)
- Named contact for data-related incidents
- Reviews domain and dataset metadata quarterly

**Must be:** A named individual (`urn:li:corpuser:...`) — not just a group.

**Required on:** All datasets and data products.

---

### `STEWARD`

**Description:** The operational steward who manages the data asset day-to-day.

**Responsibilities:**
- Proposes and maintains metadata (descriptions, glossary links, tags)
- Reviews PRs for their domain
- Ensures naming conventions are followed
- Conducts data quality reviews
- Manages the glossary term lifecycle for their domain
- Responds to metadata quality issues flagged by `validate.py`

**Must be:** A named individual (`urn:li:corpuser:...`) or a steward group.

**Required on:** All datasets, domains, data products, and glossary terms.

---

### `TECHNICAL_OWNER`

**Description:** The engineering team or individual responsible for the technical pipeline.

**Responsibilities:**
- Maintains ingestion recipes and dbt models
- Keeps lineage metadata accurate and up-to-date
- Responds to pipeline incidents
- Approves schema changes in PRs

**Can be:** A group (`urn:li:corpGroup:...`) or individual.

**Required on:** Gold datasets. Recommended on all others.

---

### `BUSINESS_OWNER`

**Description:** A secondary business owner who uses the data but is not the primary accountable party.

**Use when:** Multiple business units use a shared dataset and all need representation in metadata.

---

## 2. Ownership YAML Structure

### Dataset Ownership

```yaml
owners:
  # Primary business accountability — named individual required
  - type: DATAOWNER
    id: "urn:li:corpuser:john.smith"
    source: MANUAL

  # Operational steward — manages metadata day-to-day
  - type: STEWARD
    id: "urn:li:corpuser:mary.johnson"
    source: MANUAL

  # Engineering team — maintains the pipeline
  - type: TECHNICAL_OWNER
    id: "urn:li:corpGroup:finance-data-engineering"
    source: MANUAL
```

### Domain Ownership

```yaml
owners:
  - type: DATAOWNER
    id: "urn:li:corpuser:john.smith"
    source: MANUAL
  - type: STEWARD
    id: "urn:li:corpuser:mary.johnson"
    source: MANUAL
  - type: TECHNICAL_OWNER
    id: "urn:li:corpGroup:finance-data-engineering"
    source: MANUAL
```

### Glossary Term Ownership

```yaml
owners:
  - type: STEWARD
    id: "urn:li:corpuser:mary.johnson"
```

---

## 3. Ownership Requirements by Artefact Type

| Artefact | DATAOWNER | STEWARD | TECHNICAL_OWNER |
|---|---|---|---|
| Raw dataset | ✅ Required | ✅ Required | ✅ Recommended |
| Bronze dataset | ✅ Required | ✅ Required | ✅ Recommended |
| Silver dataset | ✅ Required | ✅ Required | ✅ Recommended |
| Gold dataset | ✅ Required | ✅ Required | ✅ **Required** |
| Domain | ✅ Required | ✅ Required | Optional |
| Data Product | ✅ Required | ✅ Required | ✅ Recommended |
| Glossary Term | — | ✅ Required | — |
| Tag | — | ✅ Recommended | — |
| Policy | — | ✅ Required | — |

---

## 4. Owner URN Formats

| Type | URN Format | Example |
|---|---|---|
| Individual user | `urn:li:corpuser:<username>` | `urn:li:corpuser:john.smith` |
| Group / Team | `urn:li:corpGroup:<group-name>` | `urn:li:corpGroup:finance-data-engineering` |

**Username convention:** `firstname.lastname` (lowercase, dot-separated).

---

## 5. Adding a New Owner to the Registry

Before referencing a new owner in any YAML file, they must be added to the ownership registry at `metadata/ownership/owners.yaml`:

```yaml
# Add under the `users:` section
- urn: "urn:li:corpuser:newuser.name"
  github_username: "newuser-name"
  display_name: "New User Name"
  email: "newuser.name@company.com"
  title: "Job Title"
  department: "Department Name"
  active: true
  roles:
    - STEWARD         # or DATAOWNER, TECHNICAL_OWNER
```

The `check_owners.py` script will fail if a dataset references an owner URN that is not in this registry.

---

## 6. Ownership Transfer

When a team member leaves or changes role, ownership must be transferred within **5 business days**:

1. Update `metadata/ownership/owners.yaml` — set `active: false` for the departing person
2. Update all dataset YAML files referencing the departed owner's URN
3. Add the replacement owner with the appropriate ownership type
4. Open a PR with the subject: `fix(ownership): transfer ownership from <old> to <new>`
5. Governance Team and the affected domain owner must approve

---

## 7. Shared Datasets (Multiple Domain Owners)

When a dataset spans multiple business domains, use multiple owner entries:

```yaml
owners:
  # Primary domain owner
  - type: DATAOWNER
    id: "urn:li:corpuser:john.smith"           # Finance — primary
    source: MANUAL

  # Secondary domain owner
  - type: BUSINESS_OWNER
    id: "urn:li:corpuser:emma.wilson"           # Operations — secondary consumer
    source: MANUAL

  # Steward from the primary domain
  - type: STEWARD
    id: "urn:li:corpuser:mary.johnson"
    source: MANUAL

  # Technical team
  - type: TECHNICAL_OWNER
    id: "urn:li:corpGroup:finance-data-engineering"
    source: MANUAL
```

---

## 8. Responsibilities Matrix

| Task | DATAOWNER | STEWARD | TECHNICAL_OWNER |
|---|---|---|---|
| Propose new dataset YAML | ○ | ✅ | ✅ |
| Review metadata PR (domain) | ✅ | ✅ | ○ |
| Approve Gold certification | ✅ | ○ | ○ |
| Manage glossary terms | ○ | ✅ | ○ |
| Maintain lineage | ○ | ○ | ✅ |
| Respond to pipeline incident | ○ | ○ | ✅ |
| Approve access requests | ✅ | ○ | ○ |
| Quarterly metadata review | ✅ | ✅ | ✅ |
| Ownership transfer approvals | ✅ | ○ | ○ |

✅ Primary responsibility   ○ Secondary / supporting

