# Northstar Payments Platform — Functional Overview

Document ID: DOC-PAY-001  
Owner: Payments Engineering  
Reviewed: 2025-02-14

Northstar is the bank's domestic payment orchestration service. The service accepts instructions from the Branch Portal and Mobile Banking, validates the customer and funding account, and routes eligible payments to the ClearRail gateway. Operations calls the gateway-facing service CRG in runbooks. The platform records each accepted instruction in `PAYMENT_CORE.PAYMENT_ORDER`; the order's `customer_ref` points to the bank party key, while `debit_acct` is the account identifier supplied by the channel.

The hourly `PAYMENT_SETTLEMENT_EXPORT` process reads `PAYMENT_CORE.PAYMENT_ORDER` and writes settlement rows to `PAYMENT_STAGE.SETTLEMENT_EVENT`. It does not send payment instructions; those are sent synchronously by the gateway adapter. Payments Engineering owns the orchestration service and its schedules. Treasury Operations owns the settlement cut-off calendar, not the payment tables.

Business term: a *settled payment* is an accepted instruction for which the rail has returned a final settlement code. A successful API response alone does not mean the payment settled.
