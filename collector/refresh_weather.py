"""Refresh the forecast line in every upcoming draft (runs each morning Sun–Thu).

Drafts mark the line with <!-- weather --> ... <!-- /weather -->.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import weather  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    today = date.today()
    for draft in sorted((ROOT / "drafts").glob("????-??-??.md")):
        friday = date.fromisoformat(draft.stem)
        if friday < today:
            continue
        wx = weather.forecast(friday)
        text = draft.read_text()
        new = weather.replace_block(text, wx["line"])
        run = ROOT / "runs" / friday.isoformat()
        if run.exists():
            (run / "weather.json").write_text(json.dumps(wx, indent=1))
        if new != text:
            draft.write_text(new)
            print(f"{draft.name}: {wx['line']}")
        else:
            print(f"{draft.name}: unchanged")


if __name__ == "__main__":
    main()
