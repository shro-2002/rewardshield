# Kaggle bootstrap: install pinned toolkits before torch is imported, locate the attached model.
import glob, json, os, subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "agenttune==1.1.5", "auditkit==1.1.11", "sqlglot"], check=True)
_cfg = [p for p in glob.glob("/kaggle/input/**/config.json", recursive=True) if "global" in p]
MODEL_DIR = os.path.dirname(_cfg[0]) if _cfg else ""
print("python", sys.version.split()[0], "model_dir", MODEL_DIR, flush=True)
