# Meridian Risk Lake — Landing and Curated Zones

Document ID: DOC-RISK-004  
Owner: Enterprise Data Platform

Meridian Risk Lake runs on the enterprise data platform. The `RISK_LANDING.PAYMENT_EVENT` dataset receives rows from `PAYMENT_STAGE.SETTLEMENT_EVENT`; the hourly `PAYMENT_EVENT_INGEST` process reads the staging table and writes the landing dataset. The same process filters out test payments where `environment_code` equals `TEST`.

The daily `RISK_PAYMENT_ENRICH` process joins `RISK_LANDING.PAYMENT_EVENT` to `LANDING.CUSTOMER_PARTY` on `customer_ref = party_id`, and writes `RISK_CURATED.PAYMENT_FACT`. Its `party_key` field is copied from `LANDING.CUSTOMER_PARTY.party_id`. The process runs after both upstream loads complete. Enterprise Data Platform owns the lake jobs and curated datasets.

Risk analysts sometimes say “payment mart” when they mean `RISK_CURATED.PAYMENT_FACT`; there is no separate object named PAYMENT_MART in this platform.
