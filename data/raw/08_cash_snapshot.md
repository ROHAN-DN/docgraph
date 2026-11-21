# Treasury Cash Snapshot Feed

Document ID: DOC-TREAS-008  
Owner: Treasury Operations

The `CASH_SNAPSHOT_LOAD` process reads balances from `CORE.CASH_ACCOUNT_BALANCE` and writes `TREASURY.CASH_BALANCE_SNAPSHOT` at 06:45 each business day. It depends on the core banking end-of-day close marker. The snapshot is denominated by account currency and is used by the Daily Liquidity Position report.

Treasury Operations owns the process and snapshot. `CORE.CASH_ACCOUNT_BALANCE` is owned by Core Banking; this note does not transfer ownership of that source.
