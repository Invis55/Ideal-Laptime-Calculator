# ui/cli.py

import json
from engine.simulator import simulate_lap
from engine.track_loader import load_track_data
from engine.weather_model import get_weather_effects
from engine.tyre_model import get_tyre_data

def ask_input(prompt, options):
    print(f"\n{prompt}")
    for i, option in enumerate(options):
        print(f"{i + 1}. {option}")
    while True:
        try:
            choice = int(input("Choose an option: "))
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except ValueError:
            pass
        print("Invalid choice. Try again.")

def run_cli():
    with open("data/track_list.json", "r") as f:
        tracks = json.load(f)

    with open("data/tyres.json", "r") as f:
        tyre_data = json.load(f)

    track_name = ask_input("Which track do you want to simulate?", list(tracks.keys()))
    tyre_choice = ask_input("Which tyre compound?", list(tyre_data.keys()))
    weather_choice = ask_input("Select weather conditions:", ["Dry", "Light Rain", "Heavy Rain"])

    print("\n⏳ Simulating...")

    track_data = load_track_data(track_name)
    tyre_info = get_tyre_data(tyre_choice)
    weather = get_weather_effects(weather_choice)

    lap_time, section_times = simulate_lap(track_data, tyre_info, weather)

    print(f"\n🏁 Ideal Lap Time at {track_name} with {tyre_choice} in {weather_choice} conditions: {lap_time:.3f} s")
    print("\n🧩 Section Breakdown:")
    for i, section in enumerate(section_times):
        print(f"  - Section {i+1}: {section:.3f} s")

if __name__ == "__main__":
    run_cli()
