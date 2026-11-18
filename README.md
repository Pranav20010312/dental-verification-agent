# Dental insurance verification agent

A small prototype I built to work through how insurance verification could be automated for a dental office.

## What it does

Each night it reads the appointments for the next few days and checks coverage for each patient through a mock clearinghouse (standing in for an X12 270/271 eligibility check).
If that response is missing something that affects the price, like frequency limits or service history, it reads a mock payer portal page and parses the messy text into standard fields with a confidence score on each one.
It then estimates what the patient will owe, marks each appointment VERIFIED or NEEDS_REVIEW with a reason, and once claims are paid, compares the estimates against the EOBs by payer and field.

## How to run

Python 3.11 or later.

```bash
pip install -r requirements.txt
```

```bash
python run.py
```

Tests: `python -m pytest` (16 tests).

The portal text is parsed with regular expressions by default. There is also an optional parser that sends the text to a hosted language model with a JSON schema; it is used only when `ANTHROPIC_API_KEY` is set.

## Sample output

Output from an actual run, with the default regex parser:

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

It also writes `outputs/review_queue.csv` (what the front desk would work through at 7 AM) and `outputs/accuracy_report.md`.

## Results

- Auto-verified: 7 of 10 appointments (70%)
- Sent to review: 3 of 10 (30%)
- Field accuracy against the EOB answer key: 56 of 60 fields (93.3%)
- Line accuracy, all 20 procedure lines: 18 of 20 (90%)
- Line accuracy on auto-verified lines only: 13 of 14 (92.9%)

For each procedure line I compare three fields: covered, insurance paid and patient paid, with a $0.50 tolerance.

Two estimates were wrong, both for Dunmore Benefits:

P009 was sent to review because the 271 said the deductible was met while the portal said $50 was left. The EOB shows the portal was right, so the review step did its job here.

P008 was auto-verified but wrong by $42. The payer paid the composite filling at the amalgam rate (an alternate benefit downgrade), which I do not model. This is the case the feedback loop is for: the accuracy report puts Dunmore at the top of the list of payers to look at.

I want to be clear about what these numbers mean. I wrote the 10 patients myself so that every path gets exercised at least once (complete 271, portal fallback, inactive plan, frequency limit, annual max, waiting period, low confidence, conflicting sources), and I also wrote the EOB answer key. So the numbers show the routing and scoring work end to end. They do not say anything about accuracy on real claims.

## How it works

```
data/appointments.csv
  -> agent/clearinghouse.py   mock 270/271 (two payers leave out frequency limits and history)
  -> missing fields that affect cost?
       yes -> agent/portal.py (mock portal text) -> agent/parser.py
  -> agent/estimate.py        fee, deductible, coverage %, annual max, frequency, waiting period
  -> agent/pipeline.py        VERIFIED, or NEEDS_REVIEW with a reason
  -> agent/eob_check.py       compare with data/eobs.csv, mismatches by payer and field
```

An appointment goes to review if the plan is inactive, if any field that affects the cost is missing or has confidence below 0.9, or if the clearinghouse and the portal disagree. Which fields matter depends on what is booked. A crown needs the major coverage percentage and the waiting period; a cleaning needs the prophy frequency limit and history.

Confidence values: 0.99 for clearinghouse fields, 0.95 for portal fields the regex parser reads cleanly, and 0.6 when the line is hedged (a question mark, "verify", and so on). With the model-based parser the confidence comes from the model itself, which is not calibrated, so I would not treat it as a probability without measuring it first.

## Limitations

- Synthetic data only. Every patient, member ID, payer, fee and claim is made up. There is no real patient data in this repo.
- Mocked APIs. The clearinghouse, the payer portal and Open Dental are all simulated with local files. Nothing talks to a real clearinghouse, payer, browser or phone line.
- Not tested on real payers. Real 271 responses and portal pages are much messier and differ by payer. The regex parser was written against four sample pages and would not generalize.
- No HIPAA infrastructure. No encryption, access control, audit logging, BAA or PHI handling of any kind. Do not run this with real patient information.
- The model-based parser was not used for the sample run. It is covered by one unit test with a fake client; the numbers above come from the regex parser.
- Benefit rules are simplified: the office fee is treated as the allowed amount, the benefit year is the calendar year, and there are no downgrades, coordination of benefits, age limits, missing tooth clauses or in-network fee schedules.

## Layout

```
data/      appointments, fee schedule, EOB answer key, mock 271 responses, mock portal pages
agent/     models, loaders, clearinghouse, portal, parser, estimate, pipeline, eob_check
tests/     pytest tests
run.py     runs everything
```
