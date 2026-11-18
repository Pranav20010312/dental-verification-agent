# Accuracy report: estimates vs. paid claims (synthetic EOB key)

- Field accuracy: 56/60 (93.3%)
- Line accuracy (all 3 fields right): 18/20 (90.0%)
- Line accuracy, auto-verified only: 13/14 (92.9%)

## Mismatches by payer and field (worst payer first)

- **Dunmore Benefits**: insurance_paid x2, patient_paid x2

## Mismatch log

| Patient | Payer | Code | Field | Estimated | Actual | Agent status |
|---|---|---|---|---|---|---|
| P008 | Dunmore Benefits | D2391 | insurance_paid | 91.0 | 49.0 | VERIFIED |
| P008 | Dunmore Benefits | D2391 | patient_paid | 89.0 | 131.0 | VERIFIED |
| P009 | Dunmore Benefits | D2391 | insurance_paid | 126.0 | 91.0 | NEEDS_REVIEW |
| P009 | Dunmore Benefits | D2391 | patient_paid | 54.0 | 89.0 | NEEDS_REVIEW |
