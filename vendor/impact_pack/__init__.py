import sys
from pathlib import Path

_modules = Path(__file__).resolve().parent / 'modules'
if str(_modules) not in sys.path:
    sys.path.insert(0, str(_modules))
