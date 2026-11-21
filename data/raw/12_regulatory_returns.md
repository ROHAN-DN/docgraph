# Monthly Payment Returns Pack

Document ID: DOC-REG-012  
Owner: Regulatory Reporting

The Monthly Payment Returns Pack is produced by `PAYMENT_RETURNS_MONTH_END`. It reads `RISK_CURATED.PAYMENT_FACT` and writes `REG_REPORTING.MONTHLY_PAYMENT_RETURN`. The transformation groups settled payment value by reporting entity, month, currency, and channel. It uses the party's reporting entity mapping from `RISK_CURATED.PARTY_REPORTING_MAP`.

Regulatory Reporting owns the return dataset and report. Enterprise Data Platform owns the upstream curated payment fact. A corrected return is versioned; the original output is retained for audit.
