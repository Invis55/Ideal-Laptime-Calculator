# engine/tyre_model.py

import json
import os

with open("data/tyres.json", "r") as f:
    TYRES = json.load(f)

def get_tyre_data(name):
    return TYRES.get(name, TYRES["Soft"])

def get_tyre_performance(tyre):
    base = tyre["grip"]
    wear_penalty = tyre["wear"] * tyre["degradation_rate"]
    return base - wear_penalty
