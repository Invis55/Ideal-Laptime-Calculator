# engine/simulator.py

from .physics import calculate_drag, calculate_braking_distance, calculate_traction, calculate_corner_speed
from .tyre_model import get_tyre_performance
from .weather_model import adjust_grip_for_weather

def simulate_section(section, tyre, weather, car, driver_skill):
    length = section['length']
    type_ = section['type']

    if type_ == 'straight':
        speed = car['top_speed']
        drag = calculate_drag(car['aero_efficiency'], speed)
        adjusted_speed = speed - drag * 0.01
        time = length / adjusted_speed
    elif type_ == 'corner':
        base_grip = car['base_grip'] * get_tyre_performance(tyre)
        grip = adjust_grip_for_weather(base_grip, weather)
        traction = calculate_traction(grip, tyre['temp'])
        speed = min(section['corner_speed'], traction * 300)
        time = length / speed
    else:
        time = 0

    time /= driver_skill
    return time
