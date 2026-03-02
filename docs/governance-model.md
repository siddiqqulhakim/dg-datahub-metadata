# Data Governance Model

## Overview

This document defines the data governance philosophy, roles, responsibilities, and operating model for the DataHub Metadata-as-Code programme.

---

## 1. Philosophy: Metadata-as-Code

### What is Metadata-as-Code?

Metadata-as-Code (MaC) applies software engineering practices to the management of data governance artefacts. Instead of managing metadata through point-and-click interfaces, all governance objects are defined in YAML files that live in Git:

| Traditional Approach | Metadata-as-Code |
|---|---|
| Manual UI updates | YAML files in Git |
| No audit trail | Full git history |
| Hard to review | Pull Request reviews |
| Inconsistent quality | Automated validation |
| Environment drift | CI/CD deployment |
| Single person bottleneck | Collaborative ownership |

### Core Principles

1. **Single Source of Truth**: Git is the authoritative store for all governance metadata. If it's not in Git, it doesn't exist.

2. **No Manual Production Changes**: All metadata reaching the production DataHub instance must pass through the CI/CD pipeline. Direct UI edits to production metadata are prohibited.

3. **Peer Review for All Changes**: Every metadata change — no matter how small — must be reviewed by at least one member of the governance team via Pull Request.

4. **Automated Quality Gates**: Validation scripts block any malformed, incomplete, or policy-violating metadata from being merged.

5. **Traceability**: Every deployed state of metadata is traceable to a specific git commit, PR, and reviewer.

6. **Scalability**: The model must scale to 500+ datasets and 50+ contributors without bottlenecks.

---

## 2. Governance Structure

### Organisational Units

```
Data Governance Council (strategic)
    │
    ├── Domain Data Owners (per-domain accountability)
    │       ├── Finance Domain Owner
    │       ├── Marketing Domain Owner
    │       ├── Operations Domain Owner
    │       └── Engineering Domain Owner
    │
    ├── Data Stewards (operational governance)
    │       └── One per domain, manages day-to-day metadata quality
    │
    ├── Data Platform Team (technical governance)
    │       ├── Platform Engineering (pipelines, infrastructure)
    │       └── Data Certification Board (Gold certification approvals)
    │
    └── Compliance & Security
            └── DPO / Compliance Lead (PII, GDPR, SOX oversight)
```

---

## 3. Roles and Responsibilities

### 3.1 Data Owner (`DATAOWNER`)

**Who:** Senior business leader accountable for a data domain or dataset.

**Responsibilities:**
- Final accountability for data quality and fitness for purpose
- Approves certification of Gold datasets
- Escalation point for data access disputes
- Approves changes to domain definition and structure

**Metadata obligation:** Must be named as `DATAOWNER` in all domain and dataset YAML files.

---

### 3.2 Data Steward (`STEWARD`)

**Who:** Operational data steward, typically a senior analyst or data engineer in the domain team.

**Responsibilities:**
- Proposes and maintains dataset, glossary, and domain metadata
- Reviews and approves metadata PRs from domain team members
- Ensures naming conventions are followed
- Manages glossary term lifecycle (proposal → review → approval)
- Conducts quarterly metadata quality reviews

**Metadata obligation:** Must be named as `STEWARD` in all artefact YAML files.

---

### 3.3 Technical Owner (`TECHNICAL_OWNER`)

**Who:** The engineering team or individual responsible for the data pipeline.

**Responsibilities:**
- Maintains ingestion recipes and transformation logic
- Ensures lineage metadata is up to date
- Responds to technical incidents (SLA breaches, pipeline failures)
- Reviews and approves schema changes

**Metadata obligation:** Recommended on all dataset YAML files. Required on Gold datasets.

---

### 3.4 Governance Lead

**Who:** Senior member of `@data-platform/governance-team`.

**Responsibilities:**
- Reviews and approves all PRs to the governance repository
- Maintains governance standards and documentation
- Mediates disputes about metadata ownership
- Manages the CODEOWNERS file

---

### 3.5 Data Certification Board

**Who:** Cross-functional group (`@data-platform/data-certification-board`) including data owners, stewards, and platform engineers.

**Responsibilities:**
- Signs off on Gold dataset certification requests
- Conducts 6-monthly recertification reviews
- Defines and maintains certification criteria

---

### 3.6 Security / DPO

**Who:** `@security/data-security-team` and DPO (`compliance.lead`).

**Responsibilities:**
- Reviews all policy YAML changes
- Reviews PII tag additions and removals
- Ensures GDPR Article 30 records of processing are maintained
- Approves data retention policy configurations

---

## 4. Metadata Governance Domains

Each data domain has:
- One `DATAOWNER` (a named individual)
- One or more `STEWARD`s
- A domain YAML file at `metadata/domains/<domain>.yaml`
- A dedicated GitHub team for PR reviews

| Domain | Owner | Steward | GitHub Team |
|---|---|---|---|
| Finance | `john.smith` | `mary.johnson` | `@finance/data-stewards` |
| Marketing | `alice.chen` | `bob.taylor` | `@marketing/data-stewards` |
| Operations | `emma.wilson` | `frank.brown` | `@operations/data-stewards` |
| Engineering | `carlos.rodriguez` | `diana.lee` | `@engineering/data-stewards` |

---

## 5. Governance Workflow

### 5.1 Adding a New Dataset

```
1. Data Engineer creates feature branch
2. Adds YAML to metadata/datasets/<layer>/
3. Runs local validation (validate.py + enforce_naming.py + check_owners.py)
4. Opens PR targeting `develop`
5. CI runs automated checks
6. Governance Team reviews and approves
7. PR merges to develop → auto-deploys to Dev DataHub
8. PR to staging → deploys to Staging DataHub
9. Release tag → deploys to Production DataHub
```

### 5.2 Adding a Glossary Term

```
1. Domain Steward proposes term in the appropriate glossary file
2. Opens PR targeting `develop`
3. Governance Team + relevant Domain Owner reviews definition
4. If regulatory term: Compliance Lead must approve
5. PR merges → term deployed to all environments on promotion
```

### 5.3 Certifying a Dataset (Gold)

```
1. Technical Owner verifies lineage is complete and accurate
2. Data Steward adds certification block to the dataset YAML
3. Data Quality score ≥ 95 for 90-day period must be evidenced
4. PR opened targeting `develop`
5. CODEOWNERS triggers: Governance Team + Certification Board
6. Both groups must approve
7. PR merges → certified status deployed
```

---

## 6. Policy Enforcement Matrix

| Rule | How Enforced | Blocked At |
|---|---|---|
| No dataset without owner | `check_owners.py` | PR validation |
| No dataset without description | `validate.py` | PR validation |
| No dataset without domain | `validate.py` | PR validation |
| PII must have sensitivity.pii tag | `validate.py` | PR validation |
| Gold must be certified | `validate.py` | PR validation |
| Naming convention compliance | `enforce_naming.py` | PR validation |
| All changes via PR | Branch protection | GitHub |
| Governance approval required | CODEOWNERS | GitHub |
| Production via release tag only | Workflow trigger | GitHub Actions |
| Security review on policies | CODEOWNERS | GitHub |

---

## 7. Metadata Lifecycle

```
DRAFT → ACTIVE → DEPRECATED → ARCHIVED

DRAFT:      Created, under review, not deployed to production
ACTIVE:     Deployed to production, in active use
DEPRECATED: Flagged for removal, consumers should migrate
ARCHIVED:   Removed from production, retained in Git for audit
```

**Deprecation process:**
1. Add `deprecated: true` and `deprecationNote` to the dataset YAML
2. Notify consumers via the governance Slack channel
3. Allow 90 days for consumer migration
4. Remove dataset YAML and open removal PR

---

## 8. Compliance Integration

### GDPR

- All PII datasets tagged with `sensitivity.pii`
- PII field-level tagging required for individual columns
- Data subject rights managed via the access policy YAML
- Retention periods defined in `customProperties.retention_days`

### SOX

- Financial datasets tagged with `compliance.sox`
- Full lineage to source systems required
- Audit log maintained via Git history
- Change control enforced via PR approval workflow

### Data Retention

- `retention_days` must be set in all dataset `customProperties`
- Automated deletion pipelines reference this value
- Retention periods reviewed annually as part of the certification process

