from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json


@dataclass(frozen=True)
class ResearchStep:
    stage: str
    status: str
    message: str


def append_research_log(path: str | Path, run_type: str, payload: dict) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "run_type": run_type, **payload}
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def steps_to_dicts(steps: list[ResearchStep]) -> list[dict[str, str]]:
    return [asdict(step) for step in steps]
