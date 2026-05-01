#!/usr/bin/env bash
set -euo pipefail

python -c "from pathlib import Path; p=Path('naukri_scraper.py'); s=p.read_text(); p.write_text('\n'.join([ln[2:] if ln.startswith('  ') else ln for ln in s.splitlines()]) + '\n')"
black naukri_scraper.py
