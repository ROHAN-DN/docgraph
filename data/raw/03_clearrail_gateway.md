# ClearRail Gateway Adapter — Interface Notes

Document ID: DOC-PAY-003  
Owner: Payments Engineering

The ClearRail Gateway Adapter (CRG) receives normalized requests from Northstar and sends them to the external domestic rail. It reads `PAYMENT_CORE.PAYMENT_ORDER` by `payment_id` when retrying timed-out requests and writes rail responses to `PAYMENT_CORE.RAIL_RESPONSE`. The response table has `payment_id`, `rail_reference`, `response_code`, and `settled_at`.

The gateway adapter depends on the `RAIL_PARTICIPANT_CONFIG` service for destination routing. That service is maintained by Treasury Operations. A response code of `ACCEPTED` is an acknowledgement, not proof of final settlement; only a later final code with `settled_at` populates the settlement state.

Some older diagrams call the adapter “ClearRail Connector.” That is an alias for CRG, not a separate system.
