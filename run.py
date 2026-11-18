"""One command demo: python run.py

Runs the verification agent over the synthetic appointments, prints a table,
then writes outputs/review_queue.csv and outputs/accuracy_report.md.
"""
import csv
from pathlib import Path

from agent.eob_check import compare, load_eobs, pct, to_markdown
from agent.parser import MODEL, model_enabled
from agent.pipeline import run_all

OUT = Path(__file__).resolve().parent / "outputs"


def money(x: float) -> str:
    return f"${x:,.2f}"


def main() -> None:
    mode = f"language model ({MODEL})" if model_enabled() else "regex fallback (ANTHROPIC_API_KEY not set)"
    print("Dental insurance verification agent (synthetic data, mocked APIs)")
    print(f"Portal parser: {mode}\n")

    results = run_all()
    header = f"{'ID':<5} {'Payer':<20} {'Path':<13} {'Status':<13} {'Pt cost':>9}  Review reason"
    print(header)
    print("-" * len(header))
    for r in results:
        a = r.appointment
        path = "271+portal" if "portal" in r.sources else "271"
        reason = "; ".join(r.reasons) or "-"
        print(f"{a.patient_id:<5} {a.payer:<20} {path:<13} {r.status:<13} "
              f"{money(r.estimate.patient_total):>9}  {reason}")

    OUT.mkdir(exist_ok=True)
    review = [r for r in results if r.status == "NEEDS_REVIEW"]
    with open(OUT / "review_queue.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["patient_id", "name", "payer", "member_id", "appt_date",
                    "cdt_codes", "est_patient_cost", "reason"])
        for r in review:
            a = r.appointment
            w.writerow([a.patient_id, a.name, a.payer, a.member_id, a.appt_date,
                        ";".join(a.cdt_codes), f"{r.estimate.patient_total:.2f}",
                        "; ".join(r.reasons)])

    report = compare(results, load_eobs())
    (OUT / "accuracy_report.md").write_text(to_markdown(report))

    n = len(results)
    print(f"\nAuto-verified: {n - len(review)}/{n} ({pct(n - len(review), n)})   "
          f"Sent to review: {len(review)}/{n} ({pct(len(review), n)})")
    print(f"Field accuracy vs EOB key: {report.fields_correct}/{report.fields_checked} "
          f"({pct(report.fields_correct, report.fields_checked)})   "
          f"Auto-verified line accuracy: {report.verified_lines_correct}/"
          f"{report.verified_lines} ({pct(report.verified_lines_correct, report.verified_lines)})")
    for m in report.mismatches:
        print(f"  EOB mismatch: {m.patient_id} {m.payer} {m.cdt_code} {m.field}: "
              f"estimated {m.estimated}, paid {m.actual} (agent said {m.agent_status})")
    print("\nWrote outputs/review_queue.csv and outputs/accuracy_report.md")


if __name__ == "__main__":
    main()
