# Shared Banking Data Terms and Naming Notes

Document ID: DOC-GLOSS-011  
Owner: Data Governance

“Party,” “customer,” and “client” are used inconsistently in team documents. In CIM interfaces, `party_id` is the stable mastered identifier; it can represent an individual or an organization. Do not assume every party is a natural person.

“Settlement event” usually means a rail-finalized payment event. Some operations notes use “payment event” for a raw instruction, so check whether a source is `PAYMENT_ORDER` or `SETTLEMENT_EVENT`. `CRG` and “ClearRail Connector” refer to the same adapter. “CIM” and “PartyHub” refer to the same customer master application.

Data Governance owns this glossary. Definitions here clarify terms but do not establish data flow or table ownership.
