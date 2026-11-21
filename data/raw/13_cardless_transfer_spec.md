# Cardless Transfer Processing — Operations Extract

Document ID: DOC-OPS-013  
Owner: Payments Operations

Cardless transfers arrive through Northstar with `instrument_type = ACCOUNT`. The `PAYMENT_SETTLEMENT_EXPORT` job reads `PAYMENT_CORE.PAYMENT_ORDER` and writes `PAYMENT_STAGE.SETTLEMENT_EVENT` every hour. A rejected rail response is retained for investigation but must not be counted as settled value.

Payments Operations monitors the schedule and failure queue. Payments Engineering owns the job implementation. During a rail outage, retry records can refer to an earlier `payment_id`; they are not new payment orders.
