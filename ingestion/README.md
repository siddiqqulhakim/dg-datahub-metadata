# Ingestion Sources

This directory contains DataHub ingestion recipe YAML files for all data sources.

---

## Directory Structure

```
ingestion/
└── sources/
    ├── snowflake-dev.yaml      # Snowflake DEV environment
    ├── snowflake-prod.yaml     # Snowflake PROD environment
    ├── dbt-prod.yaml           # dbt PROD project
    └── ...                     # Add new sources here
```

---

## File Naming Convention

```
<source-type>-<environment>.yaml
```

Examples:
- `snowflake-dev.yaml`
- `snowflake-prod.yaml`
- `bigquery-prod.yaml`
- `kafka-dev.yaml`
- `dbt-prod.yaml`

---

## Adding a New Source

1. Copy the closest existing recipe as a template
2. Update all source-specific configuration
3. Test locally: `datahub ingest -c ingestion/sources/<source>-dev.yaml`
4. Add required environment variables to the GitHub Actions secrets
5. Open a PR — `@data-platform/platform-engineering` will review

---

## Environment Variables

All recipes use environment variables for credentials. Never hardcode credentials.

| Variable | Used By | GitHub Secret |
|---|---|---|
| `SNOWFLAKE_ACCOUNT_DEV` | snowflake-dev.yaml | `SNOWFLAKE_ACCOUNT_DEV` |
| `SNOWFLAKE_ACCOUNT_PROD` | snowflake-prod.yaml | `SNOWFLAKE_ACCOUNT_PROD` |
| `SNOWFLAKE_USER_DEV` | snowflake-dev.yaml | `SNOWFLAKE_USER_DEV` |
| `SNOWFLAKE_PASSWORD_DEV` | snowflake-dev.yaml | `SNOWFLAKE_PASSWORD_DEV` |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | snowflake-prod.yaml | `SNOWFLAKE_PRIVATE_KEY_PATH` |
| `DATAHUB_GMS_URL` | all | Loaded from `environments/<env>/config.env` |
| `DATAHUB_GMS_TOKEN` | all | `DATAHUB_TOKEN_DEV` / `DATAHUB_TOKEN_PROD` |
| `DBT_MANIFEST_PATH` | dbt-prod.yaml | `DBT_MANIFEST_PATH` |
| `DBT_CATALOG_PATH` | dbt-prod.yaml | `DBT_CATALOG_PATH` |

---

## Supported Source Types

| Source | Recipe File | Notes |
|---|---|---|
| Snowflake | `snowflake-*.yaml` | Key-pair auth in prod |
| dbt | `dbt-prod.yaml` | Reads manifest/catalog from S3 |
| BigQuery | `bigquery-prod.yaml` | *(add when needed)* |
| Kafka | `kafka-dev.yaml` | *(add when needed)* |
| PostgreSQL | `postgres-dev.yaml` | *(add when needed)* |

