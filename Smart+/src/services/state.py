import os, json
from ..config import CFG

STATE_PATH = os.path.join(CFG.csv_dir, ".state.json")

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    return {"last_ts": None}

def save_state(state: dict):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)