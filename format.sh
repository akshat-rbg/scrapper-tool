  #!/usr/bin/env bash
  set -euo pipefail                                                                                                                                                                                                  
   
  if ! command -v ruff >/dev/null 2>&1; then                                                                                                                                                                         
    echo "ruff not found — installing..."                   
    pip install ruff                                                                                                                                                                                                 
  fi                                                        

  # Format code (like prettier --write)                                                                                                                                                                              
  ruff format .
                                                                                                                                                                                                                     
  # Sort imports + auto-fix lint issues                     
  ruff check --fix 