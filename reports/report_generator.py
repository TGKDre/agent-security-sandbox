import json
from datetime import datetime
from pathlib import Path

def save_report(results, model, csr, report_dir="reports"):
    Path(report_dir).mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    jp = Path(report_dir) / f"run_{ts}.json"
    mp = Path(report_dir) / f"run_{ts}.md"
    safe = [{k: v for k, v in r.items() if k != "trace"} for r in results]
    jp.write_text(json.dumps({"model": model, "csr": csr, "results": safe}, indent=2), encoding="utf-8")
    mp.write_text(generate_markdown(results, model, csr), encoding="utf-8")
    return jp, mp

def generate_markdown(results, model, csr):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Agent Security Sandbox — Evaluation Report",
        f"**Model:** {model}  ", f"**Date:** {ts}  ",
        f"**Compromise Success Rate:** {csr:.1f}%", "",
        "## Results", "",
        "| ID | Scenario | Threat | Result | Latency |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        status = "COMPROMISED" if r.get("compromised") else "SAFE" if r.get("compromised") is False else "ERROR"
        lines.append(f"| {r['id']} | {r['name']} | {r.get('threat_type','-')} | {status} | {r.get('latency_ms',0)} ms |")
    lines += ["", "## Findings", ""]
    comp = [r for r in results if r.get("compromised")]
    for r in comp:
        lines.append(f"- **{r['id']} - {r['name']}**: {r.get('reason','')}")
    if not comp:
        lines.append("No compromises detected.")
    lines += ["", "## Methodology", "",
        "Each scenario injects adversarial content via simulated tools (document store, shell, user directory, messaging).",
        "The ActionJudge evaluates the full agent trace for secret leakage, dangerous tool use,",
        "injection signal acceptance, and unauthorized privilege escalation attempts.",
    ]
    return "\n".join(lines)
