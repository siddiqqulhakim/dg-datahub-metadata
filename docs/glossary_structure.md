# Glossary Structure

## Overview

The DataHub glossary provides a shared vocabulary that bridges business language and technical data assets. This document describes the glossary hierarchy, governance rules, and how to add or update terms.

---

## 1. Three-Tier Classification

All glossary terms are classified into one of three categories:

| Category | File | Purpose |
|---|---|---|
| **Business Terms** | `metadata/glossary/business-terms.yaml` | Domain-specific business concepts, KPIs, processes |
| **Technical Terms** | `metadata/glossary/technical-terms.yaml` | Engineering, platform, and architecture concepts |
| **Regulatory Terms** | `metadata/glossary/regulatory-terms.yaml` | Compliance, privacy, and regulatory definitions |

---

## 2. Hierarchy: Nodes and Terms

The glossary is organised as a two-level hierarchy:

```
GlossaryNode (parent category)
    └── GlossaryTerm (leaf: the actual definition)
```

### Example hierarchy

```
Finance                              (GlossaryNode)
├── Finance.AccountsPayable          (GlossaryNode)
│   ├── Invoice                      (GlossaryTerm)
│   ├── AccountsPayable              (GlossaryTerm)
│   ├── DaysPayableOutstanding       (GlossaryTerm)
│   └── PaymentTerms                 (GlossaryTerm)
└── Finance.Revenue                  (GlossaryNode)
    └── CashFlow                     (GlossaryTerm)

Technical                            (GlossaryNode)
├── Technical.Architecture           (GlossaryNode)
│   ├── MedallionArchitecture        (GlossaryTerm)
│   └── SlowlyChangingDimension      (GlossaryTerm)
└── Technical.DataQuality            (GlossaryNode)
    └── DataQualityScore             (GlossaryTerm)

Regulatory                           (GlossaryNode)
├── Regulatory.Privacy               (GlossaryNode)
│   ├── PII                          (GlossaryTerm)
│   └── GDPR_DataSubject             (GlossaryTerm)
└── Regulatory.Financial             (GlossaryNode)
    └── SOX_InternalControl          (GlossaryTerm)
```

---

## 3. Term YAML Structure

### Full term template

```yaml
- urn: "urn:li:glossaryTerm:<domain>__<TermName>"
  name: "<TermName>"                          # PascalCase, must be unique
  definition: |
    Clear, unambiguous definition of the term.
    Must be ≥ 50 characters. Should cover:
    - What the term means in business context
    - How it is calculated (if a metric)
    - Any regulatory or policy source
    - Valid values (if an enumeration)
  parentNode: "urn:li:glossaryNode:<NodeName>"
  domain: "urn:li:domain:<domain>"            # Links term to a data domain
  owners:
    - type: STEWARD
      id: "urn:li:corpuser:<steward-username>"
  relatedTerms:                               # Optional — links to related terms
    - urn: "urn:li:glossaryTerm:<domain>__<RelatedTerm>"
  customProperties:
    source: "<source of definition>"          # e.g., "IFRS IAS 37", "Internal Policy FIN-001"
    approved_by: "<approver name or team>"
    review_date: "YYYY-MM-DD"                 # Next scheduled review date
    formula: "<calculation formula>"          # For metrics/KPIs
    valid_values: "<comma-separated>"         # For enumerations
```

---

## 4. Naming Rules for Terms

| Rule | Detail |
|---|---|
| **PascalCase** | `AccountsPayable`, `DaysPayableOutstanding` |
| **No duplicates** | `validate.py` blocks duplicate names within and across files |
| **No spaces** | Use CamelCase boundary, not spaces or underscores |
| **Abbreviations** | Acronyms in caps: `PII`, `GDPR_DataSubject`, `SOX_InternalControl` |
| **Domain prefix in URN** | `urn:li:glossaryTerm:finance__Invoice` — use `__` (double underscore) as namespace separator; dots are reserved for DNS/IP/infra |

---

## 5. Node Naming Rules

| Rule | Detail |
|---|---|
| Top-level nodes | Single PascalCase word: `Finance`, `Technical`, `Regulatory` |
| Sub-nodes | Double-underscore-separated PascalCase: `Finance__AccountsPayable` |
| No deep nesting | Maximum 2 levels (node + sub-node) for discoverability |

---

## 6. Proposing a New Term

### Step 1: Choose the right file

- Business concept → `business-terms.yaml`
- Engineering/platform → `technical-terms.yaml`
- Compliance/regulatory → `regulatory-terms.yaml`

### Step 2: Find or create the parent node

Check if a suitable `GlossaryNode` already exists. If not, add one to the `nodes:` section first.

### Step 3: Write the definition

A good glossary definition:
- Answers "What is this?" without jargon
- Is self-contained (no assumed knowledge)
- Cites the authoritative source (policy doc, regulation, standard)
- Includes calculation formula if it's a metric
- Lists valid values if it's an enumeration

### Step 4: Open a PR

```bash
git checkout -b feature/glossary-add-<TermName>
# Add term to the appropriate file
python scripts/validate.py --metadata-dir metadata/
git add metadata/glossary/
git commit -m "feat(glossary): add business term <TermName>"
git push origin feature/glossary-add-<TermName>
```

PR title: `feat(glossary): add <Category> term — <TermName>`

### Step 5: Review process

| Term type | Required reviewers |
|---|---|
| Business term | Domain Steward + Governance Team |
| Technical term | Platform Engineering + Governance Team |
| Regulatory term | Compliance Lead + Governance Team + Legal (if new regulation) |

---

## 7. Updating an Existing Term

When updating a definition:
- Do NOT change the `urn` or `name` — these are immutable identifiers
- Update the `definition` text
- Update `customProperties.review_date`
- Add a note explaining the reason for the change in the PR description
- Same reviewers as proposing a new term

---

## 8. Deprecating a Term

When a term is no longer in use:

```yaml
- urn: "urn:li:glossaryTerm:finance__OldTerm"
  name: "OldTerm"
  definition: |
    DEPRECATED: This term has been superseded by 'NewTerm'.
    Please update any references to use urn:li:glossaryTerm:finance__NewTerm.
    Original definition: ...
  deprecated: true
  deprecationNote: "Superseded by finance__NewTerm as of 2025-03-01"
  replacedBy: "urn:li:glossaryTerm:finance__NewTerm"
```

Do not delete the YAML entry — retain it for historical reference.

---

## 9. Linking Datasets to Glossary Terms

In dataset YAML files, link terms at both dataset and field level:

```yaml
# Dataset-level glossary links
glossaryTerms:
  - urn: "urn:li:glossaryTerm:finance__Invoice"
  - urn: "urn:li:glossaryTerm:finance__AccountsPayable"

# Field-level glossary links
schema:
  fields:
    - name: "days_payable_outstanding"
      glossaryTerms:
        - urn: "urn:li:glossaryTerm:finance__DaysPayableOutstanding"
```

**Rules:**
- Gold datasets must have ≥ 1 dataset-level glossary term
- Field-level links are encouraged for key business metrics
- All referenced term URNs must exist in the glossary files

---

## 10. Governance Calendar

| Activity | Frequency | Owner |
|---|---|---|
| New term proposals reviewed | Within 5 business days of PR | Domain Steward + Governance |
| Full glossary review | Quarterly | All Domain Stewards |
| Regulatory terms review | Annually (or on regulation change) | Compliance Lead |
| Deprecation cleanup | Semi-annually | Governance Lead |

