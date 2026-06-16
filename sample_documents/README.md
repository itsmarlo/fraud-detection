# Sample Claim Documents

Synthetic PDFs for claim `CLM-DEMO-10001`. All names, identifiers, addresses,
bank details, and events are fictional.

| File | Upload as | Purpose |
| --- | --- | --- |
| `01_repair_invoice.pdf` | `REPAIR_INVOICE` | Consistent invoice dated after the accident for EUR 7,800.00 |
| `02_police_report.pdf` | `POLICE_REPORT` | Police report matching the accident date |
| `03_accident_report.pdf` | `ACCIDENT_REPORT` | Claimant accident description |
| `04_witness_statement.pdf` | `WITNESS_STATEMENT` | Independent witness account |
| `05_suspicious_repair_invoice.pdf` | `REPAIR_INVOICE` | Deliberately inconsistent invoice dated before the accident for EUR 12,600.00 |

Upload each document separately because the demo UI applies one document category
to all files selected in the same upload field.

For the suspicious invoice demo, open **Show advanced fields** and set **Invoice
date** to `2026-05-08`. The extracted EUR 12,600.00 amount is evaluated
automatically; setting the form date also demonstrates the invoice-before-accident
rule.

Regenerate the PDFs with:

```bash
/Users/marla.alschweiki/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/generate_sample_documents.py
```
