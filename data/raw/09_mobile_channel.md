# Mobile Banking Payment Submission

Document ID: DOC-MOB-009  
Owner: Digital Channels

Mobile Banking submits domestic transfers to the Northstar payment API. It reads `CIM.PARTY` to display the verified account holder name and sends `party_id` as `customer_ref` in the payment request. The mobile app does not write directly to `PAYMENT_CORE.PAYMENT_ORDER`; Northstar validates and persists the instruction.

Digital Channels owns the application. Customer Platforms owns CIM. A cached display name can be stale for up to fifteen minutes; the value used for payment routing is revalidated by Northstar.
