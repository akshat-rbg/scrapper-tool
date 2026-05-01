#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from pathlib import Path

for p in Path(".").rglob("*.py"):
    if ".venv" in p.parts or "venv" in p.parts:
        continue
    s = p.read_text()
    p.write_text("\n".join([ln[2:] if ln.startswith("  ") else ln for ln in s.splitlines()]) + "\n")
PY

black .
