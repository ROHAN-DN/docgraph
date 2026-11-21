# Branch Portal Transfer Workflow

Document ID: DOC-BRANCH-010  
Owner: Branch Technology

The Branch Portal allows staff to submit customer transfers to Northstar. It reads `CIM.ACCOUNT_PARTY` to verify account relationships and sends the selected `party_id` as `customer_ref`. A screen label still says “customer number,” but the API payload is the internal party key.

The portal does not create settlement records. Northstar owns payment instruction persistence and Payments Engineering owns the API integration. Branch Technology owns the portal.
