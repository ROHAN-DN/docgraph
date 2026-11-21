# Customer Master (CIM) — Data Dictionary

Document ID: DOC-CUST-002  
Owner: Customer Platforms

Customer Identity Management (CIM), also called PartyHub by the integration team, maintains the mastered party record. The `CIM.PARTY` table contains `party_id`, `legal_name`, `birth_date`, and `party_status`. Downstream systems should use `party_id`; legacy interfaces may call the same value `cust_key`.

The `CIM.ACCOUNT_PARTY` table links `account_id` to `party_id` and includes `relationship_role`. A party can have several accounts and an account can have more than one party. Customer Platforms owns CIM. The nightly `CIM_PARTY_PUBLISH` job reads `CIM.PARTY` and writes the active party extract to `LANDING.CUSTOMER_PARTY`.

The label “customer number” in branch procedures is ambiguous: it can mean the external-facing `customer_number` or the internal `party_id`. Confirm the interface before mapping it.
