import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "agent-runtime"))


def rejects(handler, payload):
    try:
        handler(payload)
    except ValueError:
        return
    raise AssertionError(f"{handler.__name__} accepted invalid input")
