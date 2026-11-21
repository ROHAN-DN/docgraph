# Daily Liquidity Position Report

Document ID: DOC-REPORT-005  
Owner: Treasury Analytics

The Daily Liquidity Position report is published to the Treasury workspace at 07:30 on business days. It reads `RISK_CURATED.PAYMENT_FACT` and `TREASURY.CASH_BALANCE_SNAPSHOT`. The `net_outflow` measure sums settled debit amounts less returned credits by currency and value date. Pending or merely accepted payments are excluded.

The report is produced by the `LIQUIDITY_DAILY_REFRESH` process, which depends on completion of `RISK_PAYMENT_ENRICH` and `CASH_SNAPSHOT_LOAD`. Treasury Analytics owns the report definition; Treasury Operations owns the cash snapshot feed.
