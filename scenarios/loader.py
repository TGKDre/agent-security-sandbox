import yaml
from pathlib import Path

def load_scenario_file(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("scenarios", [])

def load_all_scenarios(path: str) -> list:
    p = Path(path)
    if p.is_file():
        return load_scenario_file(str(p))
    return [sc for f in sorted(p.glob("*.yaml")) for sc in load_scenario_file(str(f))]
