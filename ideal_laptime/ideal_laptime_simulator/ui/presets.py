# ui/presets.py

import json
import os

PRESETS_FILE = "data/presets.json"

def save_preset(name, data):
    if not os.path.exists(PRESETS_FILE):
        with open(PRESETS_FILE, "w") as f:
            json.dump({}, f)

    with open(PRESETS_FILE, "r") as f:
        presets = json.load(f)

    presets[name] = data

    with open(PRESETS_FILE, "w") as f:
        json.dump(presets, f, indent=4)

def load_preset(name):
    with open(PRESETS_FILE, "r") as f:
        presets = json.load(f)
    return presets.get(name)

def list_presets():
    with open(PRESETS_FILE, "r") as f:
        presets = json.load(f)
    return list(presets.keys())
