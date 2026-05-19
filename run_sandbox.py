#!/usr/bin/env python3
import argparse, time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from agents.tool_agent import ToolAgent
from scenarios.loader import load_all_scenarios
from judges.action_judge import ActionJudge
from reports.report_generator import save_report

console = Console()

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", default="scenarios/")
    p.add_argument("--model", default="gpt-3.5-turbo")
    p.add_argument("--report-dir", default="reports")
    return p.parse_args()

def main():
    cfg = parse_args()
    scenarios = load_all_scenarios(cfg.scenario)
    provider = "openai" if "gpt" in cfg.model else "anthropic"
    console.print(Panel.fit(
        f"[bold]Agent Security Sandbox[/bold]\nModel: {cfg.model} ({provider})\nScenarios: {len(scenarios)} loaded",
        title="Config"))
    agent = ToolAgent(model=cfg.model, provider=provider)
    judge = ActionJudge()
    results = []
    for sc in scenarios:
        start = time.time()
        try:
            trace = agent.run(sc)
            verdict = judge.evaluate(sc, trace)
            latency = int((time.time() - start) * 1000)
            icon = "✘" if verdict["compromised"] else "✔"
            console.print(f"  {icon} {sc['id']}: {verdict['reason']}")
            results.append({**sc, **verdict, "latency_ms": latency, "trace": trace})
            time.sleep(3)  # respect rate limits between scenarios
        except Exception as e:
            console.print(f"  ⚠ {sc['id']}: {e}")
            results.append({**sc, "compromised": None, "reason": str(e), "latency_ms": 0, "trace": []})
    table = Table(title="Security Evaluation Results", show_lines=True)
    table.add_column("ID", style="cyan"); table.add_column("Scenario")
    table.add_column("Threat", justify="center"); table.add_column("Result", justify="center")
    table.add_column("Latency", justify="right")
    for r in results:
        if r.get("compromised") is True: rs = "[red]✘ COMPROMISED[/red]"
        elif r.get("compromised") is False: rs = "[green]✔ SAFE[/green]"
        else: rs = "[yellow]⚠ ERROR[/yellow]"
        table.add_row(r["id"], r["name"], r.get("threat_type","–"), rs, f"{r.get('latency_ms',0)} ms")
    console.print(table)
    total = [r for r in results if r.get("compromised") is not None]
    comp = [r for r in total if r.get("compromised")]
    csr = (len(comp)/len(total)*100) if total else 0
    console.print(Panel.fit(f"Batch complete\nCompromise Success Rate: {csr:.1f}%\nScenarios: {len(total)}", title="Results"))
    jp, mp = save_report(results, cfg.model, csr, cfg.report_dir)
    console.print(f"  JSON: {jp}\n  Markdown: {mp}")

if __name__ == "__main__":
    main()
