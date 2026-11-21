# Synthetic document corpus

All material here is fictional and was written for DocGraph; it contains no customer data or scraped private content. The corpus has 16 documents: 14 Markdown files plus one DOCX and one PDF. It intentionally includes aliases, overloaded terms, differences between API and table names, ownership boundaries, and negative statements so extraction can be evaluated against realistic ambiguity.

| File | Document ID | Main subject |
|---|---|---|
| `01_northstar_payments.md` | DOC-PAY-001 | Payment orchestration and settlement export |
| `02_customer_master.md` | DOC-CUST-002 | CIM/PartyHub and party identifiers |
| `03_clearrail_gateway.md` | DOC-PAY-003 | ClearRail adapter and rail responses |
| `04_risk_lake.md` | DOC-RISK-004 | Landing and curated payment data |
| `05_liquidity_report.md` | DOC-REPORT-005 | Treasury liquidity report |
| `06_aml_monitoring.md` | DOC-AML-006 | AML activity feed |
| `07_ledger_close.md` | DOC-GL-007 | General ledger posting |
| `08_cash_snapshot.md` | DOC-TREAS-008 | Cash balance snapshot |
| `09_mobile_channel.md` | DOC-MOB-009 | Mobile transfer submission |
| `10_branch_portal.md` | DOC-BRANCH-010 | Branch transfer workflow |
| `11_data_dictionary_aliases.md` | DOC-GLOSS-011 | Shared terms and naming caveats |
| `12_regulatory_returns.md` | DOC-REG-012 | Monthly regulatory return |
| `13_cardless_transfer_spec.md` | DOC-OPS-013 | Settlement operations notes |
| `14_fraud_features.md` | DOC-FRAUD-014 | Payment velocity features |
| `15_risk_ownership.docx` | DOC-RISK-015 | Curated data ownership and key aliases |
| `16_payment_controls.pdf` | DOC-OPS-016 | Payment reconciliation controls |

The hand-labeled set is [gold_v1.json](../gold/gold_v1.json), covering all 16 documents. Its evidence values are source excerpts. Review the labels before using them to characterize extraction quality.
