# Naming Convention Reference

All metadata artefacts must follow naming conventions enforced by `scripts/enforce_naming.py`.

---

## 1. Dataset Naming Convention

### Pattern

```
<domain>__<subdomain>__<source>__<entity>__<layer>
```

Segments are separated by `__` (double underscore). Words within a segment use `_` (single underscore).
**Dots and hyphens are forbidden** — they are reserved for DNS, IP, and infrastructure naming.

### Rules

| Component | Format | Example | Notes |
|---|---|---|---|
| `domain` | snake_case | `finance` | Must match a defined domain URN |
| `subdomain` | snake_case | `accounts_payable` | Sub-area within the domain |
| `source` | snake_case | `erp_sap` | Source system identifier |
| `entity` | snake_case | `invoice` | Business entity name |
| `layer` | one of: `raw`, `bronze`, `silver`, `gold` | `silver` | Medallion layer |

### File Naming Rule

> **The YAML filename (without `.yaml`) must exactly match the `name` field inside the file.**

```
# File:  finance__accounts_payable__erp_sap__invoice__silver.yaml
name: "finance__accounts_payable__erp_sap__invoice__silver"
```

`enforce_naming.py` enforces this with a hard error — mismatches block the PR.

### Valid Examples

| Name / Filename (stem) | Domain | Layer | Notes |
|---|---|---|---|
| `finance__accounts_payable__erp_sap__invoice__raw` | finance | raw | ✅ |
| `finance__accounts_payable__erp_sap__invoice__silver` | finance | silver | ✅ |
| `marketing__campaigns__salesforce_mc__campaign_event__bronze` | marketing | bronze | ✅ |
| `operations__orders__oracle_wms__shipment__gold` | operations | gold | ✅ |
| `engineering__product_telemetry__kafka__page_view__silver` | engineering | silver | ✅ |

### Invalid Examples

| Name | Problem |
|---|---|
| `Finance__AP__SAP__Invoice__RAW` | Uppercase not allowed |
| `finance__ap__sap__invoice` | Missing layer component |
| `finance-ap-sap-invoice-raw` | Hyphens not allowed; use `__` as separator |
| `finance.accounts_payable.erp_sap.invoice.raw` | Dots not allowed; use `__` as separator |
| `finance__accounts payable__erp_sap__invoice__raw` | Spaces not allowed |
| `finance__accounts_payable__erp_sap__invoice__platinum` | `platinum` is not a valid layer |

---

## 2. Dataset URN Convention

### Pattern (Snowflake)

```
urn:li:dataset:(urn:li:dataPlatform:snowflake,<database>.<schema>.<table>,<ENV>)
```

### ENV values

| Value | Usage |
|---|---|
| `PROD` | Production DataHub instance |
| `DEV` | Development DataHub instance |
| `STAGING` | Staging DataHub instance |
| `TEST` | Test environments |

### Database/Schema mapping to Medallion layers

| Layer | Snowflake Database Prefix | Schema Prefix | Example |
|---|---|---|---|
| raw | `PROD_RAW_` | `RAW_<DOMAIN>` | `prod.raw_finance.ap_invoice` |
| bronze | `PROD_BRONZE_` | `BRONZE_<DOMAIN>` | `prod.bronze_finance.ap_invoice` |
| silver | `PROD_SILVER_` | `SILVER_<DOMAIN>` | `prod.silver_finance.ap_invoice` |
| gold | `PROD_GOLD_` | `GOLD_<DOMAIN>` | `prod.gold_finance.ap_invoice_summary` |

### Valid URN Examples

```yaml
# Snowflake Gold — Production
urn: "urn:li:dataset:(urn:li:dataPlatform:snowflake,prod.gold_finance.ap_invoice_summary,PROD)"

# Snowflake Silver — Dev
urn: "urn:li:dataset:(urn:li:dataPlatform:snowflake,dev.silver_marketing.campaign_events,DEV)"

# BigQuery
urn: "urn:li:dataset:(urn:li:dataPlatform:bigquery,project_id.dataset_id.table_name,PROD)"
```

---

## 3. Domain URN Convention

### Pattern

```
urn:li:domain:<domain_name>
```

**Rules:**
- `<domain_name>` must be lowercase
- Sub-domains use double underscore (`__`) notation: `urn:li:domain:finance__accounts_payable`
- Dots are **not allowed** — they conflict with DNS and infrastructure naming

### Examples

```yaml
urn: "urn:li:domain:finance"
urn: "urn:li:domain:finance__accounts_payable"
urn: "urn:li:domain:marketing__campaigns"
```

---

## 4. Data Product Naming Convention

### Pattern

```
dp_<domain>_<business_purpose>
```

**Rules:**
- Must start with `dp_`
- All components snake_case
- `business_purpose` should describe the value delivered, not the source system

### Valid Examples

| Name | Notes |
|---|---|
| `dp_finance_accounts_payable_insights` | ✅ |
| `dp_marketing_campaign_performance` | ✅ |
| `dp_operations_supply_chain_visibility` | ✅ |
| `dp_engineering_platform_health` | ✅ |

### Invalid Examples

| Name | Problem |
|---|---|
| `DataProduct_Finance` | Must start with `dp_`, no uppercase |
| `dp-finance-ap` | Hyphens not allowed |
| `dp_finance` | Missing business purpose component |

### URN Pattern

```
urn:li:dataProduct:dp_<domain>_<business_purpose>
```

---

## 5. Glossary Term Naming Convention

### Pattern

```
PascalCase
```

**Rules:**
- First letter of each word capitalised
- No spaces, hyphens, or underscores between words
- Abbreviations in ALL_CAPS are acceptable (e.g., `DaysPayableOutstanding`, `PII`, `GDPR_DataSubject`)

### Valid Examples

```
Invoice
AccountsPayable
DaysPayableOutstanding
CustomerAcquisitionCost
GDPR_DataSubject
SOX_InternalControl
```

### Glossary Term URN Pattern

```
urn:li:glossaryTerm:<domain>__<TermName>
```

**Examples:**
```
urn:li:glossaryTerm:finance__Invoice
urn:li:glossaryTerm:finance__DaysPayableOutstanding
urn:li:glossaryTerm:regulatory__PII
urn:li:glossaryTerm:technical__MedallionArchitecture
```

---

## 6. Tag Naming Convention

### Pattern

```
<category>.<subcategory>
```

All lowercase with dot separator.

### Categories

| Category | Purpose | Examples |
|---|---|---|
| `sensitivity` | Data classification | `sensitivity.pii`, `sensitivity.financial` |
| `layer` | Medallion layer | `layer.raw`, `layer.gold` |
| `source` | Source system | `source.sap_erp`, `source.kafka` |
| `usage` | Approved use | `usage.analytics_ready`, `usage.restricted` |
| `pii` | PII field type | `pii.email`, `pii.phone_number` |
| `compliance` | Regulatory scope | `compliance.sox`, `compliance.gdpr` |
| `sla` | SLA tier | `sla.high`, `sla.medium` |
| `ingestion` | Ingestion method | `ingestion.full_load`, `ingestion.streaming` |
| `field` | Field structure | `field.primary_key`, `field.partition_key` |
| `certified` | Certification status | `certified` |

---

## 7. File Naming Convention

| Directory | File Name Pattern | Example |
|---|---|---|
| `metadata/domains/` | `<domain>.yaml` | `finance.yaml` |
| `metadata/datasets/raw/` | `<domain>_<entity>_raw.yaml` | `finance_ap_erp_sap_invoice_raw.yaml` |
| `metadata/datasets/bronze/` | `<domain>_<entity>_bronze.yaml` | `finance_ap_erp_sap_invoice_bronze.yaml` |
| `metadata/datasets/silver/` | `<domain>_<entity>_silver.yaml` | `finance_ap_erp_sap_invoice_silver.yaml` |
| `metadata/datasets/gold/` | `<domain>_<entity>_gold.yaml` | `finance_ap_erp_sap_invoice_summary_gold.yaml` |
| `metadata/glossary/` | `<type>-terms.yaml` | `business-terms.yaml` |
| `metadata/data-products/` | `<product_name>.yaml` | `dp_finance_accounts_payable_insights.yaml` |

---

## 8. Source System Codes

Use consistent source system identifiers across all datasets:

| Source System | Code | Examples |
|---|---|---|
| SAP ERP (S/4HANA / ECC) | `erp_sap` | `finance.ap.erp_sap.invoice.raw` |
| Salesforce CRM | `salesforce_crm` | `marketing.leads.salesforce_crm.contact.silver` |
| Salesforce Marketing Cloud | `salesforce_mc` | `marketing.campaigns.salesforce_mc.send.raw` |
| Google Analytics 4 | `ga4` | `marketing.web.ga4.session.bronze` |
| Kafka (event streams) | `kafka` | `engineering.telemetry.kafka.page_view.raw` |
| Oracle WMS | `oracle_wms` | `operations.inventory.oracle_wms.stock_level.bronze` |
| dbt (transformation) | `dbt` | Used in lineage, not in source component |
| Snowflake (internal) | `snowflake` | For internally generated datasets |

