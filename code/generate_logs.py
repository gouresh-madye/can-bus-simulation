import csv
import struct
import datetime
import os
import math

# Constants
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "inputdata/simulated_can_logs.csv")

# Module IDs
ID_BRAKE = "0x100"
ID_THROTTLE = "0x200"
ID_STEERING = "0x300"
ID_PERCEPTION = "0x400"
ID_SAFETY = "0x500"
ID_UNKNOWN = "0x750"

# IPs
IP_CONTROLLER = "192.168.0.10"
IP_BRAKE = "192.168.0.1"
IP_THROTTLE = "192.168.0.2"
IP_STEERING = "192.168.0.3"
IP_PERCEPTION = "192.168.0.4"
IP_SAFETY = "192.168.0.5"

# Helper to format bytes
def bytes_to_hex_str(data):
    return " ".join(f"{b:02X}" for b in data)

def get_timestamp(start_time, offset_seconds):
    t = start_time + datetime.timedelta(seconds=offset_seconds)
    return t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # Millisecond precision

def create_brake_payload(pressure, status, decel, wheel_fl, wheel_fr):
    # struct.pack format: B B H H H
    # > means big-endian
    return struct.pack('>BBHHH', pressure, status, int(decel * 1000), wheel_fl, wheel_fr)

def create_throttle_payload(pos, status, accel, rpm, fuel):
    # struct.pack format: B B H H B B (last B is padding to make 8)
    return struct.pack('>BBHHBB', pos, status, int(accel * 1000), rpm, fuel, 0)

def create_steering_payload(angle, status, rate, wheel_fl, wheel_fr):
    # struct.pack format: h B B h h
    angle_fixed = int(angle * 256)
    wheel_fl_fixed = int(wheel_fl * 256)
    wheel_fr_fixed = int(wheel_fr * 256)
    return struct.pack('>hBBhh', angle_fixed, status, rate, wheel_fl_fixed, wheel_fr_fixed)

def create_perception_payload(obj_count, dist, speed, threat, lane, road, weather, health):
    # struct.pack format: B B B B B B B B
    return struct.pack('>BBBBBBBB', obj_count, dist, speed, threat, lane, road, weather, health)

# Scenario Generators
def generate_logs():
    logs = []
    start_time = datetime.datetime.now()
    current_time_offset = 0.0
    
    # 1. Normal Driving (0-5s)
    print("Generating Normal Driving scenario...")
    for i in range(50): # 10Hz for 5s
        t_str = get_timestamp(start_time, current_time_offset)
        
        # Brake (Idle)
        logs.append([t_str, ID_BRAKE, bytes_to_hex_str(create_brake_payload(0, 0, 0, 60, 60)), 8, IP_BRAKE, IP_CONTROLLER])
        
        # Throttle (Steady)
        logs.append([t_str, ID_THROTTLE, bytes_to_hex_str(create_throttle_payload(30, 1, 0, 2000, 80)), 8, IP_THROTTLE, IP_CONTROLLER])
        
        # Steering (Straight)
        logs.append([t_str, ID_STEERING, bytes_to_hex_str(create_steering_payload(0, 1, 0, 0, 0)), 8, IP_STEERING, IP_CONTROLLER])
        
        current_time_offset += 0.1

    # 2. CAN Flood Attack on Brake ID (5-6s)
    print("Generating CAN Flood scenario...")
    for i in range(50): # 50 messages in 1s -> High freq
        t_str = get_timestamp(start_time, current_time_offset)
        logs.append([t_str, ID_BRAKE, bytes_to_hex_str(create_brake_payload(0, 0, 0, 60, 60)), 8, "192.168.0.99", IP_CONTROLLER])
        current_time_offset += 0.02 # Very fast intervals

    current_time_offset += 1.0

    # 3. Sensor Failure (All Zero) (7-8s)
    print("Generating Sensor Failure scenario...")
    for i in range(10):
        t_str = get_timestamp(start_time, current_time_offset)
        zero_payload = bytes([0]*8)
        logs.append([t_str, ID_PERCEPTION, bytes_to_hex_str(zero_payload), 8, IP_PERCEPTION, IP_CONTROLLER])
        current_time_offset += 0.1

    # 4. Diagnostic Flood (All FF) (8-9s)
    print("Generating Diagnostic Flood scenario...")
    for i in range(10):
        t_str = get_timestamp(start_time, current_time_offset)
        ff_payload = bytes([0xFF]*8)
        logs.append([t_str, ID_THROTTLE, bytes_to_hex_str(ff_payload), 8, IP_THROTTLE, IP_CONTROLLER])
        current_time_offset += 0.1

    # 5. Unknown ECU (9-10s)
    print("Generating Unknown ECU scenario...")
    for i in range(5):
        t_str = get_timestamp(start_time, current_time_offset)
        logs.append([t_str, ID_UNKNOWN, "DE AD BE EF 00 00 00 00", 8, "192.168.0.77", IP_CONTROLLER])
        current_time_offset += 0.2

    # 6. Extreme Values (High Brake Pressure) (10-11s)
    print("Generating Extreme Values scenario...")
    for i in range(10):
        t_str = get_timestamp(start_time, current_time_offset)
        # Pressure 250 (approx 98%)
        logs.append([t_str, ID_BRAKE, bytes_to_hex_str(create_brake_payload(250, 1, 5.0, 50, 50)), 8, IP_BRAKE, IP_CONTROLLER])
        current_time_offset += 0.1

    # 7. Conflicting Commands (Max Brake + Max Throttle) (11-12s)
    print("Generating Conflicting Commands scenario...")
    for i in range(10):
        t_str = get_timestamp(start_time, current_time_offset)
        # Max Brake
        logs.append([t_str, ID_BRAKE, bytes_to_hex_str(create_brake_payload(255, 1, 8.0, 0, 0)), 8, IP_BRAKE, IP_CONTROLLER])
        # Max Throttle
        logs.append([t_str, ID_THROTTLE, bytes_to_hex_str(create_throttle_payload(255, 1, 5.0, 7000, 70)), 8, IP_THROTTLE, IP_CONTROLLER])
        current_time_offset += 0.1

    # 8. Rapid Steering / Evasive (12-14s)
    print("Generating Rapid Steering scenario...")
    for i in range(20):
        t_str = get_timestamp(start_time, current_time_offset)
        angle = 35 * math.sin(i) # Swing between -35 and 35
        logs.append([t_str, ID_STEERING, bytes_to_hex_str(create_steering_payload(angle, 1, 30, 0, 0)), 8, IP_STEERING, IP_CONTROLLER])
        current_time_offset += 0.1
        
    # Write to CSV
    print(f"Writing {len(logs)} entries to {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "CAN_ID", "DATA", "DLC", "SRC_IP", "DST_IP"])
        writer.writerows(logs)

if __name__ == "__main__":
    generate_logs()
