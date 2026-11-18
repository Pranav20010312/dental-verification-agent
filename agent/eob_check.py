"""Compare estimates with paid claims (EOBs) and log mismatches by payer.

data/eobs.csv is a synthetic answer key: what the payer actually paid.
Fields compared per procedure line: covered, insurance_paid, patient_paid.
"""
import csv
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from .data import DATA_DIR
from .models import VerificationResult

TOLERANCE = 0.50  # dollars
FIELDS = ("covered", "insurance_paid", "patient_paid")


class EobLine(BaseModel):
    patient_id: str
    payer: str
    line: int
    cdt_code: str
    covered: bool
    insurance_paid: float
    patient_paid: float


class Mismatch(BaseModel):
    patient_id: str
    payer: str
    cdt_code: str
    field: str
    estimated: str
    actual: str
    agent_status: str


class AccuracyReport(BaseModel):
    fields_checked: int = 0
    fields_correct: int = 0
    lines_checked: int = 0
    lines_correct: int = 0
    verified_lines: int = 0
    verified_lines_correct: int = 0
    mismatches: list[Mismatch] = []

    def by_payer(self) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for m in self.mismatches:
            counts[m.payer][m.field] += 1
        return {p: dict(f) for p, f in sorted(counts.items(), key=lambda x: -sum(x[1].values()))}


def load_eobs(path: Path = DATA_DIR / "eobs.csv") -> dict[tuple[str, int], EobLine]:
    with open(path, newline="") as f:
        rows = [EobLine(**r) for r in csv.DictReader(f)]
    return {(r.patient_id, r.line): r for r in rows}


def _equal(field: str, est, act) -> bool:
    return est == act if field == "covered" else abs(est - act) <= TOLERANCE


def compare(results: list[VerificationResult],
            eobs: dict[tuple[str, int], EobLine]) -> AccuracyReport:
    rep = AccuracyReport()
    for res in results:
        pid = res.appointment.patient_id
        for i, line in enumerate(res.estimate.lines, start=1):
            eob = eobs.get((pid, i))
            if eob is None or eob.cdt_code != line.cdt_code:
                continue  # claim not paid yet or line mismatch: nothing to compare
            est = {"covered": line.covered, "insurance_paid": line.insurance,
                   "patient_paid": line.patient}
            line_ok = True
            for field in FIELDS:
                rep.fields_checked += 1
                if _equal(field, est[field], getattr(eob, field)):
                    rep.fields_correct += 1
                else:
                    line_ok = False
                    rep.mismatches.append(Mismatch(
                        patient_id=pid, payer=eob.payer, cdt_code=line.cdt_code, field=field,
                        estimated=str(est[field]), actual=str(getattr(eob, field)),
                        agent_status=res.status))
            rep.lines_checked += 1
            rep.lines_correct += line_ok
            if res.status == "VERIFIED":
                rep.verified_lines += 1
                rep.verified_lines_correct += line_ok
    return rep


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def to_markdown(rep: AccuracyReport) -> str:
    out = ["# Accuracy report: estimates vs. paid claims (synthetic EOB key)", "",
           f"- Field accuracy: {rep.fields_correct}/{rep.fields_checked} "
           f"({pct(rep.fields_correct, rep.fields_checked)})",
           f"- Line accuracy (all 3 fields right): {rep.lines_correct}/{rep.lines_checked} "
           f"({pct(rep.lines_correct, rep.lines_checked)})",
           f"- Line accuracy, auto-verified only: {rep.verified_lines_correct}/"
           f"{rep.verified_lines} ({pct(rep.verified_lines_correct, rep.verified_lines)})",
           "", "## Mismatches by payer and field (worst payer first)", ""]
    if not rep.mismatches:
        out.append("None.")
    for payer, fields in rep.by_payer().items():
        out.append(f"- **{payer}**: " + ", ".join(f"{f} x{n}" for f, n in fields.items()))
    out += ["", "## Mismatch log", "",
            "| Patient | Payer | Code | Field | Estimated | Actual | Agent status |",
            "|---|---|---|---|---|---|---|"]
    out += [f"| {m.patient_id} | {m.payer} | {m.cdt_code} | {m.field} | {m.estimated} "
            f"| {m.actual} | {m.agent_status} |" for m in rep.mismatches]
    return "\n".join(out) + "\n"
