#!/usr/bin/env python3
"""
AVITS Multi-Account Orchestrator Runner
Usage: python run_orchestrator.py [--run-all] [--account ID] [--list] [--add EMAIL PASSWORD LOCATION]
"""

import sys
import os

# ============================================================
# FORCE UTF-8 ENCODING FOR WINDOWS CONSOLE
# ============================================================
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from avits_login_v3.orchestrator import main

if __name__ == "__main__":
    main()