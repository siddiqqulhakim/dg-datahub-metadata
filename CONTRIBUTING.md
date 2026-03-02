# Contributing to DataHub Governance

Thank you for contributing to our Metadata-as-Code governance repository.  
This guide explains how to propose, review, and deploy changes safely.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Prerequisites](#prerequisites)
3. [Branching Strategy](#branching-strategy)
4. [How to Add a New Domain](#how-to-add-a-new-domain)
5. [How to Add a New Dataset](#how-to-add-a-new-dataset)
6. [How to Add a Glossary Term](#how-to-add-a-glossary-term)
7. [How to Certify a Dataset](#how-to-certify-a-dataset)
8. [Pull Request Checklist](#pull-request-checklist)
9. [Running Validation Locally](#running-validation-locally)
10. [Commit Message Convention](#commit-message-convention)
11. [Roles and Review Process](#roles-and-review-process)

---

## Code of Conduct

All contributors must follow the company data governance policies.  
Sensitive data (credentials, PII samples) must **never** be committed to this repository.

---

## Prerequisites

```bash
# Python 3.10+
python --version

# Install all dependencies
pip install -r requirements.txt

# Verify DataHub CLI
datahub version
```

---

## Branching Strategy

```
main          ←── production deployments (release tags only)
  ↑
staging       ←── pre-production validation
  ↑
develop       ←── integration branch (auto-deploys to dev)
  ↑
feature/*     ←── your working branch
fix/*         ←── bug fixes on metadata
hotfix/*      ←── urgent production corrections
```

### Branch naming rules

| Type | Pattern | Example |
|---|---|---|
| New feature | `feature/<domain>-<description>` | `feature/finance-add-invoice-dataset` |
| Bug fix | `fix/<description>` | `fix/ownership-missing-steward` |
| Hotfix | `hotfix/<description>` | `hotfix/prod-pii-tag-missing` |
| Documentation | `docs/<description>` | `docs/update-naming-conventions` |

---

## How to Add a New Domain

1. Create a new YAML file under `metadata/domains/`:

```bash
touch metadata/domains/<domain-name>.yaml
```

2. Use the domain template:

```yaml
# metadata/domains/<domain-name>.yaml
---
version: "1"
kind: domain
urn: "urn:li:domain:<domain-name>"
name: "<Human-Readable Domain Name>"
description: |
  Comprehensive description of the domain, its scope, the business unit it serves,
  and the types of data it owns.
owners:
  - type: DATAOWNER
    id: "urn:li:corpuser:<github-username>"
  - type: STEWARD
    id: "urn:li:corpuser:<steward-github-username>"
customProperties:
  domain_lead: "<github-username>"
  business_unit: "<business-unit-name>"
  cost_center: "<cost-center-code>"
  created_date: "<YYYY-MM-DD>"
  review_cycle: "quarterly"
```

3. Run validation locally:

```bash
python scripts/validate.py --metadata-dir metadata/domains/
```

4. Open a PR targeting `develop`.

---

## How to Add a New Dataset

1. Determine the layer: `raw`, `bronze`, `silver`, or `gold`
2. Determine the naming: `<domain>.<subdomain>.<source>.<entity>.<layer>`
3. Create the file:

```bash
touch metadata/datasets/<layer>/<domain>_<subdomain>_<source>_<entity>_<layer>.yaml
```

4. Use the dataset template for your layer (see `metadata/datasets/` for examples)
5. Required fields:

| Field | Required | Gold Required |
|---|---|---|
| `urn` | ✅ | ✅ |
| `name` | ✅ | ✅ |
| `description` | ✅ | ✅ |
| `domain` | ✅ | ✅ |
| `owners` | ✅ (min 1 DATAOWNER + 1 STEWARD) | ✅ |
| `tags` | If PII: `sensitivity.pii` mandatory | ✅ |
| `certification` | ❌ | ✅ (status: CERTIFIED) |
| `glossaryTerms` | Recommended | ✅ (min 1) |

5. Run all scripts:

```bash
python scripts/validate.py --metadata-dir metadata/
python scripts/enforce_naming.py --metadata-dir metadata/
python scripts/check_owners.py --metadata-dir metadata/ --owners-registry metadata/ownership/owners.yaml
```

6. Open a PR targeting `develop`.

---

## How to Add a Glossary Term

1. Choose the correct glossary file:
   - Business concepts → `metadata/glossary/business-terms.yaml`
   - Technical/engineering → `metadata/glossary/technical-terms.yaml`
   - Regulatory/compliance → `metadata/glossary/regulatory-terms.yaml`

2. Add a new term entry (no duplicate `name` values allowed — enforced by `validate.py`):

```yaml
- urn: "urn:li:glossaryTerm:<domain>.<TermName>"
  name: "<TermName>"
  definition: |
    Clear, unambiguous definition of the term.
  parentNode: "urn:li:glossaryNode:<NodeName>"
  domain: "urn:li:domain:<domain>"
  owners:
    - type: STEWARD
      id: "urn:li:corpuser:<steward-username>"
  customProperties:
    source: "<source-of-definition>"
    review_date: "<YYYY-MM-DD>"
    approved_by: "<governance-lead>"
```

3. Open a PR targeting `develop`.

---

## How to Certify a Dataset

See [`docs/certification-process.md`](docs/certification-process.md) for the full workflow.

**Summary:**
1. Ensure all required fields for certification are present
2. Set `certification.status` to `CERTIFIED`
3. Add `certification.certifiedBy` and `certification.certifiedDate`
4. Add at least one `glossaryTerm`
5. Ensure `lineage` section is populated
6. Open a PR — the Data Certification Board (`@data-platform/data-certification-board`) will be auto-requested as a reviewer

---

## Pull Request Checklist

Before opening a PR, ensure:

- [ ] I have run `validate.py` and it passes with zero errors
- [ ] I have run `enforce_naming.py` and it passes
- [ ] I have run `check_owners.py` and every dataset has valid owners
- [ ] All new YAML files follow the naming convention
- [ ] Descriptions are meaningful (not placeholder text)
- [ ] PII datasets carry `sensitivity.pii` tag
- [ ] Gold datasets include full `certification` block
- [ ] No credentials, tokens, or sensitive data in any file
- [ ] Commit messages follow the convention below
- [ ] PR title follows: `<type>(<domain>): <short description>`

---

## Running Validation Locally

```bash
# Full validation suite
python scripts/validate.py --metadata-dir metadata/ --verbose

# Only naming convention check
python scripts/enforce_naming.py --metadata-dir metadata/

# Only ownership check
python scripts/check_owners.py \
  --metadata-dir metadata/ \
  --owners-registry metadata/ownership/owners.yaml

# Run all at once (exit code is the sum of all script exit codes)
python scripts/validate.py --metadata-dir metadata/ && \
python scripts/enforce_naming.py --metadata-dir metadata/ && \
python scripts/check_owners.py --metadata-dir metadata/ \
  --owners-registry metadata/ownership/owners.yaml && \
echo "✅ All checks passed"
```

---

## Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <short description>

[optional body]
[optional footer]
```

| Type | Use For |
|---|---|
| `feat` | New metadata artefact |
| `fix` | Correcting existing metadata |
| `docs` | Documentation only |
| `refactor` | Restructuring without behaviour change |
| `chore` | Build/tooling changes |
| `hotfix` | Urgent production correction |

**Examples:**
```
feat(finance): add silver invoice dataset with PII tagging
fix(marketing): correct ownership for campaign_events dataset
docs(glossary): add regulatory term GDPR_DataSubject
hotfix(prod): add missing sensitivity.pii tag to hr.employees.gold
```

---

## Roles and Review Process

| Role | GitHub Team | Responsibilities |
|---|---|---|
| **Data Steward** | `@<domain>/data-stewards` | Proposes and maintains domain metadata |
| **Governance Lead** | `@data-platform/governance-team` | Reviews & approves all PRs |
| **Platform Engineer** | `@data-platform/platform-engineering` | Maintains pipelines, ingestion configs |
| **Certification Board** | `@data-platform/data-certification-board` | Signs off on Gold dataset certification |
| **Security Reviewer** | `@security/data-security-team` | Reviews policy and PII tag changes |

### Review SLA

| Environment Target | Expected Review Time |
|---|---|
| dev | 1 business day |
| staging | 2 business days |
| prod | 3 business days |

### Merge rules

- **develop**: 1 approval from `@data-platform/governance-team`
- **staging**: 1 approval from `@data-platform/governance-team` + all CI checks
- **main**: 2 approvals from `@data-platform/governance-team` + 1 from `@data-platform/platform-engineering` + release tag

