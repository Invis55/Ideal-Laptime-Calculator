# engine/track_loader.py

import json
import os

def load_track(track_name):
    path = f"data/tracks/{track_name.lower().replace(' ', '_')}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"Track file not found: {path}")
    with open(path, 'r') as f:
        return json.load(f)
