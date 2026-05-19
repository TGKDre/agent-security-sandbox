#!/usr/bin/env python3
"""
compare_models.py

Runs the same scenario suite against multiple models and prints a
side-by-side comparison table. Writes a combined Markdown report.

Usage:
    python compare_models.py
    python compare_models.py --scenarios scenarios/ --report-dir reports

Models compared by default:
    openai/gpt-4o-mini
    anthropic/claude-haiku-3-5  (requires ANTHROPIC_API_KEY)
"""
import argparse, time, json
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from agents.tool_agent import ToolAgent
from scenarios.loader import load_all_scenarios
from judges.action_judge import ActionJudge

console = Console()

DEFAULT_MODELS = [
    {"model": "gpt-4o-mini",          "provider": "openai"},
    {"model": "claude-haiku-3-5",      "provider": "anthropic"},
]

def run_model(model, provider, scenarios, judge):
    agent = ToolAgent(model=model, provider=provider)
    results = {}
    for sc in scenarios:
        start = time.time()
        try:
            trace = agent.run(sc)
            verdict = judge.evaluate(sc, trace)
            latency = int((time.time() - start) * 1000)
            results[sc["id"]] = {
                "compromised": verdict["compromised"],
                "reason": verdict["reason"],
                "latency_ms": latency
            }
            icon = "\u2718" if verdict["compromised"] else "\u2714"
            console.print(f"    {icon} {sc['id']}: {verdict['reason']}")
        except Exception as e:
            console.print(f"    \u26a0 {sc['id']}: {e}")
            results[sc["id"]] = {"compromised": None, "reason": str(e), "latency_ms": 0}
        time.sleep(3)
    return results

def csr(results):
    valid = [r for r in results.values() if r["compromised"] is not None]
    comp  = [r for r in valid if r["compromised"]]
    return (len(comp) / len(valid) * 100) if valid else 0.0

def build_comparison_table(scenarios, all_results, model_configs):
    table = Table(title="Cross-Model Security Comparison", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Scenario")
    table.add_column("Threat")
    for cfg in model_configs:
        table.add_column(cfg["model"], justify="center")
    for sc in scenarios:
        row = [sc["id"], sc["name"], sc.get("threat_type", "-")]
        for cfg in model_configs:
            r = all_results[cfg["model"]].get(sc["id"], {})
            if r.get("compromised") is True:  row.append("[red]\u2718 COMP[/red]")
            elif r.get("compromised") is False: row.append("[green]\u2714 SAFE[/green]")
            else: row.append("[yellow]\u26a0 ERR[/yellow]")
        table.add_row(*row)
    return table

def save_comparison_report(scenarios, all_results, model_configs, report_dir):
    Path(report_dir).mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = [
        "# Agent Security Sandbox \u2014 Cross-Model Comparison",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Models:** {', '.join(c['model'] for c in model_configs)}",
        "",
        "## Compromise Success Rate",
        "",
    ]
    for cfg in model_configs:
        c = csr(all_results[cfg["model"]])
        lines.append(f"- **{cfg['model']}**: {c:.1f}% CSR")
    lines += ["", "## Scenario Results", ""]
    header = "| ID | Scenario | Threat | " + " | ".join(c["model"] for c in model_configs) + " |"
    sep    = "|---|---|---| " + " | ".join(["---"] * len(model_configs)) + " |"
    lines += [header, sep]
    for sc in scenarios:
        row = f"| {sc['id']} | {sc['name']} | {sc.get('threat_type','-')} |"
        for cfg in model_configs:
            r = all_results[cfg["model"]].get(sc["id"], {})
            if r.get("compromised") is True:   row += " COMPROMISED |"
            elif r.get("compromised") is False: row += " SAFE |"
            else:                               row += " ERROR |"
        lines.append(row)
    lines += [
        "",
        "## Observations",
        "",
        "*(Fill in after reviewing results)*",
        "",
        "## Methodology",
        "",
        "Same 8 scenarios run sequentially against each model. "
        "Scenario definitions, tool registry, and judge logic are identical across all runs. "
        "Rate limit handling via tenacity exponential backoff.",
    ]
    mp = Path(report_dir) / f"comparison_{ts}.md"
    jp = Path(report_dir) / f"comparison_{ts}.json"
    mp.write_text("\n".join(lines), encoding="utf-8")
    safe = {m: dict(v) for m, v in all_results.items()}
    jp.write_text(json.dumps({"models": [c["model"] for c in model_configs], "results": safe}, indent=2), encoding="utf-8")
    return mp, jp

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--scenarios", default="scenarios/")
    p.add_argument("--report-dir", default="reports")
    p.add_argument("--models", nargs="+", help="provider/model pairs e.g. openai/gpt-4o anthropic/claude-haiku-3-5")
    return p.parse_args()

def main():
    cfg = parse_args()
    model_configs = DEFAULT_MODELS
    if cfg.models:
        model_configs = []
        for m in cfg.models:
            provider, model = m.split("/", 1)
            model_configs.append({"provider": provider, "model": model})
    scenarios = load_all_scenarios(cfg.scenarios)
    judge = ActionJudge()
    all_results = {}
    for mc in model_configs:
        console.print(Panel.fit(
            f"[bold]{mc['model']}[/bold] ({mc['provider']})",
            title="Running model"))
        all_results[mc["model"]] = run_model(mc["model"], mc["provider"], scenarios, judge)
        c = csr(all_results[mc["model"]])
        console.print(f"  CSR: [bold]{c:.1f}%[/bold]\n")
    console.print(build_comparison_table(scenarios, all_results, model_configs))
    for mc in model_configs:
        c = csr(all_results[mc["model"]])
        console.print(f"  {mc['model']}: {c:.1f}% CSR")
    mp, jp = save_comparison_report(scenarios, all_results, model_configs, cfg.report_dir)
    console.print(f"\n  Markdown: {mp}\n  JSON:     {jp}")

if __name__ == "__main__":
    main()
