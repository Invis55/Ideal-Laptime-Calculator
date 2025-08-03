# engine/weather_model.py

def adjust_grip_for_weather(base_grip, weather):
    grip_modifier = 1.0

    if weather['rain'] > 0:
        grip_modifier -= 0.4 * weather['rain']

    if weather['temp'] < 15:
        grip_modifier -= 0.1

    if weather['wind'] > 30:
        grip_modifier -= 0.05

    return max(0.1, base_grip * grip_modifier)
