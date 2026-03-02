# Dataset Certification Process

## Overview

The certification process is a formal quality assurance gate that validates a dataset's fitness for use as an authoritative, production-grade analytical asset. Only certified datasets may be used in executive reporting, regulatory filings, or as inputs to ML production models.

---

## 1. Certification Levels

| Level | Tag | Description |
|---|---|---|
| **Uncertified** | *(no certified tag)* | Not yet reviewed. Use with caution. |
| **Bronze Certified** | `layer.bronze` | Cleaned and deduplicated. Technical validation passed. |
| **Silver Certified** | `layer.silver` + `usage.analytics_ready` | Business-conformed. Approved for team analytics. |
| **Gold Certified** | `layer.gold` + `certified` | Full certification. Approved for executive reporting. |

---

## 2. Gold Certification Requirements

A dataset must meet ALL of the following criteria before Gold certification is granted:

### 2.1 Metadata Requirements

| Requirement | Field | Validation |
|---|---|---|
| Full description (≥ 150 chars) | `description` | `validate.py` |
| Domain assigned | `domain` | `validate.py` |
| DATAOWNER assigned (human) | `owners[].type: DATAOWNER` | `check_owners.py` |
| STEWARD assigned | `owners[].type: STEWARD` | `check_owners.py` |
| TECHNICAL_OWNER assigned | `owners[].type: TECHNICAL_OWNER` | `check_owners.py` |
| At least 1 glossary term | `glossaryTerms` | `validate.py` |
| Freshness SLA defined | `freshness.sla` | `validate.py` |
| Full lineage to source | `lineage.upstreams` | `validate.py` |
| No raw PII | No `sensitivity.pii` tag | `validate.py` |
| Retention days set | `customProperties.retention_days` | Recommended |
| Certified tag | `tags: - urn:li:tag:certified` | Manual |

### 2.2 Data Quality Requirements

| Requirement | Threshold | How evidenced |
|---|---|---|
| Overall DQ score | ≥ 95/100 | Monitored for 90 days via DQ pipeline |
| Completeness | ≥ 99% | Profiling results in DataHub |
| Uniqueness | 100% on primary key | DataHub assertion |
| Validity | ≥ 98% | Column-level DQ checks |
| No open P1 incidents | — | Checked by Certification Board |

### 2.3 Process Requirements

- Dataset has been in production (silver layer) for ≥ 30 days
- No schema-breaking changes in the last 30 days
- Downstream consumers have been identified and documented
- SLA tier defined (`sla.high` or `sla.medium`)
- `dataQuality.lastAuditDate` is within the last 90 days

---

## 3. Certification YAML Block

Add the following block to the dataset YAML file when requesting certification:

```yaml
certification:
  status: "CERTIFIED"
  certifiedBy: "urn:li:corpuser:<steward-username>"
  certifiedDate: "YYYY-MM-DD"
  certificationLevel: "GOLD"
  certificationNotes: |
    Certified by <Name> on <Date> after:
    - DQ score ≥ 98 over 90-day period (last audit: YYYY-MM-DD)
    - Lineage validated to <source system>
    - Domain lead sign-off from <name>
    - CFO/domain executive approved on <Date>
  nextReviewDate: "YYYY-MM-DD"   # 6 months from certifiedDate
  approvedBy:
    - "urn:li:corpuser:<domain-owner-username>"
    - "urn:li:corpuser:<steward-username>"
    - "urn:li:corpGroup:data-certification-board"
```

---

## 4. Certification Workflow

```
Step 1: Preparation (Data Steward)
   ├── Ensure silver dataset has been stable for 30+ days
   ├── Verify DQ score ≥ 95 over 90-day window
   ├── Complete all metadata fields (description, owners, lineage, etc.)
   └── Add certification block to dataset YAML

Step 2: PR Submission
   ├── Create branch: feature/certify-<dataset-name>
   ├── Add certification block and `certified` tag to the YAML
   ├── Set certification.status = "CERTIFIED"
   └── Open PR targeting `develop`

Step 3: Automated Validation
   ├── validate.py checks all required Gold fields are present
   ├── check_owners.py verifies human owners are assigned
   ├── enforce_naming.py validates naming compliance
   └── All checks must pass before human review begins

Step 4: Governance Review
   ├── @data-platform/governance-team reviews metadata completeness
   ├── Domain DATAOWNER approves dataset fitness for purpose
   └── @data-platform/data-certification-board conducts final review

Step 5: Approval & Merge
   ├── Minimum 2 approvals required (Governance + Certification Board)
   ├── PR merges to develop → deployed to Dev DataHub
   └── Promoted to staging → production via normal release cycle

Step 6: Post-Certification
   ├── Announcement in #data-governance Slack channel
   ├── nextReviewDate calendared for 6 months
   └── Consumers notified of Gold-certified status
```

---

## 5. Certification Renewal

Gold certifications expire and must be renewed every **6 months**.

The renewal process:
1. Data Steward updates `certification.certifiedDate` and `nextReviewDate`
2. Confirms DQ score remains ≥ 95
3. Verifies there have been no breaking schema changes
4. Opens a PR with the subject: `chore(certification): renew gold cert for <dataset>`
5. Governance Team approval required (1 approver sufficient for renewal)

If a dataset fails renewal, it is downgraded to Silver and the `certified` tag is removed.

---

## 6. Certification Revocation

Gold certification may be revoked if:
- DQ score drops below 85 for 7+ consecutive days
- A breaking schema change is deployed without prior notice
- An owner becomes unresponsive for 30+ days
- A security or compliance issue is discovered

**Revocation procedure:**
1. Platform Engineering opens an emergency PR: `hotfix/revoke-cert-<dataset>`
2. Sets `certification.status = "UNCERTIFIED"` and removes `certified` tag
3. Adds a `certification.revocationNote` explaining the reason
4. PR merges immediately (1 approval from Governance sufficient for hotfix)
5. Consumers notified via Slack + email

---

## 7. Certification Status in YAML

```yaml
# Certified
certification:
  status: "CERTIFIED"

# Pending review (submitted but not yet approved)
certification:
  status: "PENDING_REVIEW"

# Revoked
certification:
  status: "UNCERTIFIED"
  revocationNote: "Revoked on 2025-03-15 — DQ score dropped to 72 for 10 consecutive days."

# Expired — needs renewal
certification:
  status: "EXPIRED"
  nextReviewDate: "2025-01-20"   # Past today's date
```

---

## 8. Checklist Template

Use this checklist in the PR description when requesting Gold certification:

```markdown
## Gold Certification Checklist

### Metadata
- [ ] Description is complete (≥ 150 characters)
- [ ] Domain is assigned
- [ ] DATAOWNER is a named individual (not just a group)
- [ ] STEWARD is assigned
- [ ] TECHNICAL_OWNER is assigned
- [ ] At least 1 glossary term linked
- [ ] Freshness SLA defined
- [ ] Full lineage to source system documented
- [ ] No raw PII present
- [ ] `certified` tag added
- [ ] `usage.analytics_ready` tag added

### Data Quality
- [ ] DQ score ≥ 95 for 90+ consecutive days (evidence: link to DataHub profile)
- [ ] No open P1 data quality incidents
- [ ] Primary key uniqueness constraint passed
- [ ] No schema changes in last 30 days

### Process
- [ ] Dataset in production for ≥ 30 days
- [ ] SLA tier defined (`sla.high` or `sla.medium`)
- [ ] `dataQuality.lastAuditDate` updated
- [ ] `nextReviewDate` set to 6 months from today
- [ ] Domain Owner has reviewed and approves
```

