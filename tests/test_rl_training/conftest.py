"""Puts the repo root on sys.path; local to this folder (no shared config file to conflict on).
NOTE: optional-dependency skips live at the top of each test module, never here."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
