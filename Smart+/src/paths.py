import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT = _ROOT / "data"

def data_dir() -> Path:
    custom = os.getenv("DATA_DIR")
    if custom:
        p = Path(custom)
        return p if p.is_absolute() else (_ROOT / p)
    return _DEFAULT

def data_path(name: str) -> Path:
    return data_dir() / name
