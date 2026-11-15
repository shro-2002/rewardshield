"""Download the released Hugging Face datasets and put every file back at its original repo path.

uv run python scripts/fetch_artifacts.py --user shro-2002          # then: uv run python scripts/repro_check.py
Uses the same file map as scripts/package_hf.py, so a fresh clone can re-derive every headline number.
"""

import argparse
import shutil
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from package_hf import DATASETS  # noqa: E402


def restore(user: str) -> list[str]:
    missing = []
    for repo, (_, groups) in DATASETS.items():
        local = Path(snapshot_download(f"{user}/{repo}", repo_type="dataset"))
        for group, paths in groups.items():
            for rel in paths:
                src, dst = local / group / Path(rel).name, ROOT / rel
                if not src.exists():
                    missing.append(f"{repo}/{group}/{Path(rel).name}")
                    continue
                if dst.exists():  # never overwrite local files (e.g. data/splits shipped in git)
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
    return missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="shro-2002")
    args = ap.parse_args()
    missing = restore(args.user)
    print("restored; missing:", missing or "none")


if __name__ == "__main__":
    main()
