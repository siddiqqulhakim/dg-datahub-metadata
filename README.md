# DataHub Governance — Metadata-as-Code Repository

[![Validate Metadata](https://github.com/your-org/datahub-governance/actions/workflows/validate-metadata.yml/badge.svg)](https://github.com/your-org/datahub-governance/actions/workflows/validate-metadata.yml)
[![Deploy Dev](https://github.com/your-org/datahub-governance/actions/workflows/deploy-dev.yml/badge.svg?branch=develop)](https://github.com/your-org/datahub-governance/actions/workflows/deploy-dev.yml)
[![Deploy Prod](https://github.com/your-org/datahub-governance/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/your-org/datahub-governance/actions/workflows/deploy-prod.yml)

---

## Overview

This repository is the **single source of truth** for all data governance metadata managed in [DataHub](https://datahubproject.io/).  
All metadata changes — datasets, domains, glossary terms, tags, ownership, policies, and data products — are version-controlled here and deployed via automated CI/CD pipelines.

> **Metadata-as-Code**: Every governance artefact is a YAML file, reviewed via Pull Request, validated by automated scripts, and deployed by GitHub Actions. No manual clicks in the DataHub UI for production metadata.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                  Developer Workstation                      │
│  git clone → edit YAML → run validate.py locally → PR      │
└──────────────────────────┬─────────────────────────────────┘
                           │ Pull Request
                           ▼
┌────────────────────────────────────────────────────────────┐
│                   GitHub Actions (CI)                       │
│  validate-metadata.yml                                      │
│  ├── yamllint                                               │
│  ├── scripts/validate.py        (schema + required fields)  │
│  ├── scripts/enforce_naming.py  (naming conventions)        │
│  └── scripts/check_owners.py   (ownership completeness)     │
└──────────────────────────┬─────────────────────────────────┘
                           │ ✅ All checks pass → Merge allowed
                           ▼
┌────────────────────────────────────────────────────────────┐
│              Branch → Environment Mapping                   │
│                                                            │
│  feature/*  ──PR──▶  develop  ──▶  DEV DataHub             │
│  develop    ──PR──▶  staging  ──▶  STAGING DataHub         │
│  staging    ──tag──▶ main     ──▶  PROD DataHub             │
└────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python ≥ 3.10
- `git`
- DataHub CLI: `pip install acryl-datahub`

### 1. Clone the repository

```bash
git clone https://github.com/your-org/datahub-governance.git
cd datahub-governance
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Validate locally before committing

```bash
python scripts/validate.py --metadata-dir metadata/
python scripts/enforce_naming.py --metadata-dir metadata/
python scripts/check_owners.py --metadata-dir metadata/ --owners-registry metadata/ownership/owners.yaml
```

### 4. Create a feature branch and make changes

```bash
git checkout -b feature/add-finance-orders-dataset
# Edit or add YAML files under metadata/
git add .
git commit -m "feat(finance): add orders silver dataset"
git push origin feature/add-finance-orders-dataset
```

### 5. Open a Pull Request

- Target branch: `develop`
- Governance team is auto-requested as reviewers (see `CODEOWNERS`)
- All CI checks must pass before merge

---

## Repository Structure

```
datahub-governance/
├── .github/
│   ├── workflows/
│   │   ├── validate-metadata.yml   # Runs on every PR
│   │   ├── deploy-dev.yml          # Auto-deploy on merge to develop
│   │   ├── deploy-staging.yml      # Deploy on merge to staging
│   │   └── deploy-prod.yml         # Deploy on release tag → main
│   └── CODEOWNERS                  # Required reviewers per path
│
├── environments/
│   ├── dev/config.env              # Dev GMS URL + environment vars
│   ├── staging/config.env          # Staging GMS URL + environment vars
│   └── prod/config.env             # Prod GMS URL + environment vars
│
├── metadata/                       # ★ All governance artefacts live here
│   ├── domains/                    # Domain definitions
│   ├── datasets/
│   │   ├── raw/                    # Layer 1: source-aligned raw datasets
│   │   ├── bronze/                 # Layer 2: cleaned/typed datasets
│   │   ├── silver/                 # Layer 3: business-conformed datasets
│   │   └── gold/                   # Layer 4: certified analytics-ready datasets
│   ├── glossary/                   # Business, Technical, Regulatory terms
│   ├── tags/                       # Tag catalogue
│   ├── ownership/                  # Owner registry & YAML mapping
│   ├── policies/                   # DataHub metadata & data policies
│   └── data-products/              # Data product definitions
│
├── ingestion/
│   ├── sources/                    # DataHub ingestion recipe YAMLs
│   └── README.md
│
├── scripts/
│   ├── validate.py                 # Schema & required field validation
│   ├── enforce_naming.py           # Naming convention enforcement
│   └── check_owners.py            # Ownership completeness checks
│
├── docs/
│   ├── governance-model.md         # Governance philosophy & roles
│   ├── naming-convention.md        # Full naming rules & examples
│   ├── ownership-model.md          # Ownership types & responsibilities
│   ├── certification-process.md    # Dataset certification workflow
│   └── glossary-structure.md      # Glossary hierarchy & governance
│
├── requirements.txt
├── .gitignore
├── CODEOWNERS
├── CONTRIBUTING.md
└── README.md                       # ← You are here
```

---

## Naming Conventions

Datasets follow the pattern:

```
<domain>.<subdomain>.<source>.<entity>.<layer>
```

**Examples:**
| URN Component | Example |
|---|---|
| domain | `finance` |
| subdomain | `accounts_payable` |
| source | `erp_sap` |
| entity | `invoice` |
| layer | `silver` |
| Full name | `finance.accounts_payable.erp_sap.invoice.silver` |

Data Products follow:
```
dp_<domain>_<business_purpose>
```

See [`docs/naming-convention.md`](docs/naming-convention.md) for the full specification.

---

## Governance Rules Enforced

| Rule | Enforcement |
|---|---|
| Every dataset must have an owner | `check_owners.py` → blocks PR |
| Every dataset must have a description | `validate.py` → blocks PR |
| Every dataset must be assigned a domain | `validate.py` → blocks PR |
| PII data must carry a sensitivity tag | `validate.py` → blocks PR |
| Gold datasets must have certification metadata | `validate.py` → blocks PR |
| All metadata changes via Pull Request | Branch protection rules |
| Governance team must approve every change | `CODEOWNERS` |

---

## Environments

| Environment | Branch | Trigger | Approval Required |
|---|---|---|---|
| **dev** | `develop` | Auto on merge | No |
| **staging** | `staging` | Auto on merge | No |
| **prod** | `main` | Release tag `v*.*.*` | Yes — 2 approvers |

---

## Documentation

| Document | Description |
|---|---|
| [Governance Model](docs/governance-model.md) | Philosophy, roles, responsibilities |
| [Naming Convention](docs/naming-convention.md) | Full naming rules |
| [Ownership Model](docs/ownership-model.md) | Owner types and responsibilities |
| [Certification Process](docs/certification-process.md) | How to certify a dataset |
| [Glossary Structure](docs/glossary-structure.md) | Glossary hierarchy and governance |
| [Contributing Guide](CONTRIBUTING.md) | How to contribute changes |

---

## Support

- **Governance questions**: Open a GitHub Discussion or contact `#data-governance` Slack channel
- **Pipeline issues**: Contact `@data-platform/platform-engineering`
- **DataHub access**: Contact `#datahub-support` Slack channel

