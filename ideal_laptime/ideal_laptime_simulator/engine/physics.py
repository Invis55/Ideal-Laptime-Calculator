# engine/physics.py

def calculate_drag(aero_efficiency, speed):
    return 0.5 * 1.225 * (speed**2) * aero_efficiency

def calculate_braking_distance(speed, braking_efficiency):
    return (speed**2) / (2 * braking_efficiency)

def calculate_traction(grip_level, tyre_temp):
    return grip_level * (1 - abs(tyre_temp - 90) / 100)

def calculate_corner_speed(max_cornering_force, radius):
    return (max_cornering_force * radius) ** 0.5
