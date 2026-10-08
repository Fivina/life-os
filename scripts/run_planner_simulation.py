import sys
from pathlib import Path
from pprint import pprint

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.planning.simulator import run_simulation


if __name__ == "__main__":
    pprint(run_simulation())
