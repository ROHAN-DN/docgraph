# Fraud Feature Daily Build

Document ID: DOC-FRAUD-014  
Owner: Fraud Analytics Engineering

The `FRAUD.PAYMENT_VELOCITY_FEATURE` dataset is written by `PAYMENT_VELOCITY_BUILD`. The job reads `RISK_CURATED.PAYMENT_FACT` and groups settled payment counts and amounts by `party_key` and rolling time window. It also reads `FRAUD.DEVICE_TRUST_SCORE`; that input changes the feature risk band but does not supply payment values.

Fraud Analytics Engineering owns the build and feature dataset. Fraud Strategy owns the thresholds documented in the model card. “Velocity mart” is an informal name for the feature dataset.
