# Ingestion Sources

This directory contains DataHub ingestion recipe YAML files for all data sources.

---

## Directory Structure

```
ingestion/
└── sources/
    ├── snowflake_dev.yaml      # Snowflake DEV environment
    ├── snowflake_prod.yaml     # Snowflake PROD environment
    ├── dbt_prod.yaml           # dbt PROD project
    └── ...                     # Add new sources here
```

---

## File Naming Convention

```
<source_type>_<environment>.yaml
```

Use underscores as word separators — hyphens and dots are not allowed (reserved for DNS/IP/infra naming).

Examples:
- `snowflake_dev.yaml`
- `snowflake_prod.yaml`
- `bigquery_prod.yaml`
- `kafka_dev.yaml`
- `dbt_prod.yaml`

---

## Adding a New Source

1. Copy the closest existing recipe as a template
2. Update all source-specific configuration
3. Test locally: `datahub ingest -c ingestion/sources/<source>_dev.yaml`
4. Add required environment variables to the GitHub Actions secrets
5. Open a PR — `@data-platform/platform-engineering` will review

---

## Environment Variables

All recipes use environment variables for credentials. Never hardcode credentials.

| Variable | Used By | GitHub Secret |
|---|---|---|
| `SNOWFLAKE_ACCOUNT_DEV` | snowflake_dev.yaml | `SNOWFLAKE_ACCOUNT_DEV` |
| `SNOWFLAKE_ACCOUNT_PROD` | snowflake_prod.yaml | `SNOWFLAKE_ACCOUNT_PROD` |
| `SNOWFLAKE_USER_DEV` | snowflake_dev.yaml | `SNOWFLAKE_USER_DEV` |
| `SNOWFLAKE_PASSWORD_DEV` | snowflake_dev.yaml | `SNOWFLAKE_PASSWORD_DEV` |
| `SNOWFLAKE_PRIVATE_KEY_PATH` | snowflake_prod.yaml | `SNOWFLAKE_PRIVATE_KEY_PATH` |
| `DATAHUB_GMS_URL` | all | Loaded from `environments/<env>/config.env` |
| `DATAHUB_GMS_TOKEN` | all | `DATAHUB_TOKEN_DEV` / `DATAHUB_TOKEN_PROD` |
| `DBT_MANIFEST_PATH` | dbt_prod.yaml | `DBT_MANIFEST_PATH` |
| `DBT_CATALOG_PATH` | dbt_prod.yaml | `DBT_CATALOG_PATH` |

---

## Supported Source Types

| Source | Recipe File | Notes |
|---|---|---|
| Snowflake | `snowflake_*.yaml` | Key-pair auth in prod |
| dbt | `dbt_prod.yaml` | Reads manifest/catalog from S3 |
| BigQuery | `bigquery_prod.yaml` | *(add when needed)* |
| Kafka | `kafka_dev.yaml` | *(add when needed)* |
| PostgreSQL | `postgres_dev.yaml` | *(add when needed)* |
