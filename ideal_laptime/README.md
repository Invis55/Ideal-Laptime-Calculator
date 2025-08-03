# Ideal LapTime Simulator

This simulator estimates ideal laptimes for different F1 circuits by modeling tyres, aerodynamics, weather, and cornering profiles.

## Features
- Detailed track data input (corners + straights)
- Tyre degradation and compound logic
- Weather & ERS/DRS modeling
- Full lap simulation with time breakdown

## Structure
- `engine/`: Physics, tyre, weather models
- `tracks/`: Track JSONs
- `ui/`: CLI and scenario presets
- `results/`: Logs of lap simulations

## Usage
```bash
python main.py
