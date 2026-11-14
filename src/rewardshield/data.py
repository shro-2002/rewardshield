"""Split loading with database paths re-rooted for the current machine (Mac or Kaggle)."""

from __future__ import annotations

import json
from pathlib import Path


def load_split(path: str, spider_root: str | None = None) -> list[dict]:
    rows = [json.loads(line) for line in open(path)]
    if spider_root:
        for r in rows:
            r["db_path"] = str(Path(spider_root) / "database" / r["db_id"] / f"{r['db_id']}.sqlite")
    return rows
