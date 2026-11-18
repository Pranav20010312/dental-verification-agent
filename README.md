# Dental Insurance Verification Agent (prototype)

## What it does

Every night, the agent reads the next few days of appointments and checks the dental coverage of each patient through a mock clearinghouse (a stand-in for an X12 270/271 eligibility check).
When the eligibility response is missing fields that drive the price, such as frequency limits or service history, it reads a mock payer portal page and parses the messy text into standard fields, each with a confidence score.
It then estimates what the patient will owe, routes each appointment to VERIFIED or NEEDS_REVIEW with a stated reason, and later scores its own estimates against paid claims (EOBs) by payer and field.

## How to run

Requires Python 3.11 or later.

```bash
pip install -r requirements.txt
```

```bash
python run.py
```

Run the tests with `python -m pytest`. To try the optional LLM parsing step, set `ANTHROPIC_API_KEY` before `python run.py`; without it, the agent uses a regex parser.

## Sample output

From a real run of `python run.py` (no API key set, so the regex parser was used):

```
Dental insurance verification agent (synthetic data, mocked APIs)
Portal parser: regex fallback (ANTHROPIC_API_KEY not set)

ID    Payer                Path          Status          Pt cost  Review reason
-------------------------------------------------------------------------------
P001  Acme Dental PPO      271           VERIFIED          $0.00  -
P002  Acme Dental PPO      271           VERIFIED        $625.00  -
P003  Bluebird Dental      271           NEEDS_REVIEW    $175.00  plan inactive per 271
P004  Bluebird Dental      271           VERIFIED        $300.00  -
P005  Bluebird Dental      271           VERIFIED        $175.00  -
P006  Cedar Mutual Dental  271+portal    VERIFIED          $0.00  -
P007  Cedar Mutual Dental  271+portal    NEEDS_REVIEW      $0.00  low confidence on freq.prophy (0.60); low confidence on hist.prophy (0.60)
P008  Dunmore Benefits     271+portal    VERIFIED         $89.00  -
P009  Dunmore Benefits     271+portal    NEEDS_REVIEW     $54.00  source conflict on deductible_remaining: 271=0, portal=50.0
P010  Acme Dental PPO      271           VERIFIED      $1,200.00  -

Auto-verified: 7/10 (70.0%)   Sent to review: 3/10 (30.0%)
Field accuracy vs EOB key: 56/60 (93.3%)   Auto-verified line accuracy: 13/14 (92.9%)
  EOB mismatch: P008 Dunmore Benefits D2391 insurance_paid: estimated 91.0, paid 49.0 (agent said VERIFIED)
  EOB mismatch: P008 Dunmore Benefits D2391 patient_paid: estimated 89.0, paid 131.0 (agent said VERIFIED)
  EOB mismatch: P009 Dunmore Benefits D2391 insurance_paid: estimated 126.0, paid 91.0 (agent said NEEDS_REVIEW)
  EOB mismatch: P009 Dunmore Benefits D2391 patient_paid: estimated 54.0, paid 89.0 (agent said NEEDS_REVIEW)

Wrote outputs/review_queue.csv and outputs/accuracy_report.md
```

The run also writes `outputs/review_queue.csv` (the 7 AM front desk queue, with reasons) and `outputs/accuracy_report.md`.

## Results

| Metric | Result |
|---|---|
| Auto-verified | 7 of 10 appointments (70%) |
| Sent to review | 3 of 10 appointments (30%) |
| Field accuracy vs. EOB key | 56 of 60 fields (93.3%) |
| Line accuracy, all lines | 18 of 20 procedure lines (90.0%) |
| Line accuracy, auto-verified lines only | 13 of 14 procedure lines (92.9%) |

Fields compared per procedure line: covered, insurance paid, patient paid ($0.50 tolerance).

What the mismatches show:

- **P009 (sent to review, correctly).** The 271 said the deductible was met; the portal said $50 remained. The agent flagged the conflict instead of guessing. The EOB shows the portal was right. A human would have caught this before the visit.
- **P008 (auto-verified, wrong).** The payer paid the posterior composite filling at the cheaper amalgam rate (an alternate benefit downgrade). The agent does not model downgrades, so it overestimated what insurance would pay by $42. This is the kind of error the feedback loop exists for: the accuracy report puts Dunmore Benefits at the top of the list to fix.

These numbers are not a performance claim. The 10 patients were written by hand so that each path (complete 271, portal fallback, inactive plan, frequency limit, annual maximum, waiting period, low confidence, source conflict) is exercised at least once, and the EOB answer key was written by the same person. The numbers show that the routing and scoring work end to end, not how the agent would perform on real claims.

## How it works

```
data/appointments.csv
   -> agent/clearinghouse.py   mock 270/271 (two payers omit frequency limits and history)
   -> missing cost-driving fields?
        yes -> agent/portal.py (mock portal text) -> agent/parser.py (Claude Haiku or regex)
   -> agent/estimate.py        fee, deductible, coverage %, annual max, frequency, waiting period
   -> agent/pipeline.py        VERIFIED, or NEEDS_REVIEW with a reason
   -> agent/eob_check.py       compare with data/eobs.csv, mismatches by payer and field
```

Routing rule: NEEDS_REVIEW if the plan is inactive, if any cost-driving field is missing or has confidence below 0.9, or if the clearinghouse and the portal disagree on a field. Cost-driving fields depend on the procedures booked (for example, a crown needs the major coverage percentage and the waiting period; a cleaning needs the prophy frequency limit and history).

Confidence: clearinghouse fields get 0.99. Regex fields get 0.95, or 0.6 when the source line contains hedging such as a question mark or the word "verify". With the LLM parser, confidence is reported by the model itself through a JSON schema; it is not calibrated and should not be trusted as a probability without measuring it.

## Limitations

- **Synthetic data only.** All patients, members, payers, fees and claims are invented. No real patient data is used.
- **Mocked APIs.** The clearinghouse, the payer portal and Open Dental are all simulated with local files. Nothing connects to a real clearinghouse, payer, browser agent or phone line.
- **Not tested on real payers.** Real 271 responses and portal pages are far messier and vary by payer. The regex parser was written for the four synthetic portal pages and would not generalize.
- **No HIPAA infrastructure.** There is no encryption, access control, audit logging, BAA coverage or PHI handling of any kind. Do not use this with real patient information.
- **LLM path not exercised in the sample run.** The Claude Haiku parsing step is covered by a unit test with a fake client, but the results above come from the regex parser.
- **Simplified benefit rules.** Office fee is treated as the allowed amount; benefit year is the calendar year; no alternate benefit downgrades, coordination of benefits, age limits, missing tooth clauses or in-network fee schedules.

## Project layout

```
data/        appointments.csv, fee_schedule.csv, eobs.csv, clearinghouse_271.json, portal_pages.json
agent/       models, data loaders, clearinghouse, portal, parser, estimate, pipeline, eob_check
tests/       16 pytest tests
run.py       one command demo
```
