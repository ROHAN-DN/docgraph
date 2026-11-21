# General Ledger Close Interface

Document ID: DOC-GL-007  
Owner: Finance Platforms

The `GL.PAYMENT_POSTING` table stores posted payment accounting entries. The `GL_PAYMENT_POST` job reads `PAYMENT_STAGE.SETTLEMENT_EVENT` and writes `GL.PAYMENT_POSTING` after applying the settlement date and currency mapping from `FINANCE.CURRENCY_RULE`. Finance Platforms owns the posting job and table.

The job posts only rail-finalized entries. The phrase “payment complete” in the close checklist means posted to the general ledger, not merely settled by the rail.
