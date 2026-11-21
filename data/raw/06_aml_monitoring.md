# Sentinel AML Monitoring Feed

Document ID: DOC-AML-006  
Owner: Financial Crime Data

Sentinel is the bank's anti-money-laundering monitoring application. Its `AML.PAYMENT_ACTIVITY` dataset is populated by `AML_PAYMENT_FEED`, which reads `RISK_CURATED.PAYMENT_FACT` and writes one activity row per settled payment. The feed maps `party_key` to `subject_party_id` and excludes transactions reversed before end of day.

Financial Crime Data owns the feed and Sentinel dataset. Financial Crime Operations owns alert disposition. In older control documents, Sentinel is shortened to “SNTL.”
