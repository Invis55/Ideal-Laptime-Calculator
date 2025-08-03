import math

# --- Track Data: Spa-Francorchamps ---
track_sections = [
    # (type, length in m, corner_speed in km/h if corner else None)
    ("straight", 700, None),  # Start-Finish to La Source
    ("corner", 100, 90),      # La Source
    ("straight", 400, None),  # Downhill to Eau Rouge
    ("corner", 200, 270),     # Eau Rouge & Raidillon
    ("straight", 800, None),  # Kemmel
    ("corner", 180, 160),     # Les Combes
    ("corner", 100, 130),     # Malmedy
    ("straight", 200, None),
    ("corner", 170, 80),      # Bruxelles
    ("straight", 300, None),
    ("corner", 120, 110),     # No Name
    ("straight", 250, None),
    ("corner", 170, 180),     # Pouhon
    ("straight", 300, None),
    ("corner", 80, 100),      # Fagnes
    ("corner", 100, 130),     # Campus
    ("straight", 400, None),
    ("corner", 160, 140),     # Blanchimont
    ("straight", 500, None),
    ("corner", 100, 90),      # Bus Stop
    ("straight", 150, None),  # Finish
]

# --- Physics Parameters ---
CAR_MASS = 800  # kg
AIR_DENSITY = 1.225  # kg/m^3
FRONTAL_AREA = 1.5  # m^2
DRAG_COEFF = 0.9
GRAVITY = 9.81  # m/s²
DOWNFORCE_COEFF = 3.0
TIRE_GRIP_COEFF = 1.8
THROTTLE_BLIP_TIME = 0.05  # seconds lost per gearshift

# --- Gear Ratios and Engine ---
gear_ratios = [12.0, 8.5, 6.5, 5.0, 4.0, 3.2, 2.8]
final_drive_ratio = 3.5
wheel_radius = 0.33  # meters
engine_redline_rpm = 15000
engine_torque = 400  # Nm (flat simplified torque curve)

def rpm_to_speed(rpm, gear_ratio):
    speed_mps = (rpm * math.pi * wheel_radius) / (30 * gear_ratio * final_drive_ratio)
    return speed_mps

def get_speed_for_gear(gear):
    if 1 <= gear <= len(gear_ratios):
        return rpm_to_speed(engine_redline_rpm, gear_ratios[gear - 1])
    return 0

def acceleration_force(speed):
    drag_force = 0.5 * AIR_DENSITY * DRAG_COEFF * FRONTAL_AREA * speed ** 2
    downforce = 0.5 * AIR_DENSITY * DOWNFORCE_COEFF * FRONTAL_AREA * speed ** 2
    max_traction = (CAR_MASS * GRAVITY + downforce) * TIRE_GRIP_COEFF
    engine_force = min(engine_torque / wheel_radius, max_traction)
    return max(0, engine_force - drag_force)

def braking_deceleration(speed):
    downforce = 0.5 * AIR_DENSITY * DOWNFORCE_COEFF * FRONTAL_AREA * speed**2
    grip = (CAR_MASS * GRAVITY + downforce) * TIRE_GRIP_COEFF
    max_braking_force = grip
    return max_braking_force / CAR_MASS  # a = F/m

def simulate_braking(entry_speed, corner_speed):
    speed_diff = entry_speed - corner_speed
    if speed_diff <= 0:
        return 0.0, 0.0

    decel = braking_deceleration(entry_speed)
    time = speed_diff / decel
    distance = (entry_speed * time) - (0.5 * decel * time**2)
    return time, distance

def simulate_acceleration(start_speed, end_speed, distance):
    speed = start_speed
    time = 0
    step = 0.5  # meters
    gear = 1
    blips = 0

    while distance > 0 and speed < end_speed:
        accel = acceleration_force(speed) / CAR_MASS
        dt = 0.05
        speed += accel * dt
        distance -= speed * dt
        time += dt

        # Gear shifting
        new_gear = gear
        for g in range(1, len(gear_ratios)):
            if speed <= get_speed_for_gear(g + 1):
                new_gear = g
                break
        if new_gear != gear:
            gear = new_gear
            blips += 1
            time += THROTTLE_BLIP_TIME  # simulate throttle blip during gear change

    return time

def corner_loss(speed, corner_speed):
    braking_time, _ = simulate_braking(speed, corner_speed)
    return braking_time + 0.15  # entry/exit loss combined

def simulate_lap(track):
    total_time = 0.0
    current_speed = 0.0  # Starting from zero

    for section in track:
        section_type, length, corner_speed = section

        if section_type == "straight":
            target_speed = get_speed_for_gear(7)
            accel_time = simulate_acceleration(current_speed, target_speed, length)
            total_time += accel_time
            current_speed = target_speed
        elif section_type == "corner":
            corner_speed_mps = corner_speed / 3.6
            loss_time = corner_loss(current_speed, corner_speed_mps)
            total_time += loss_time
            current_speed = corner_speed_mps

    return total_time

# --- Run Simulation ---
lap_time = simulate_lap(track_sections)
print(f"Ideal lap time at Spa: {lap_time:.2f} seconds")
