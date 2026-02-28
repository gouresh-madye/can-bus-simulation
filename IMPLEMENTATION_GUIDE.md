# Safety Controller Implementation Guide & Test Scenarios

## Overview

This guide demonstrates how to use the autonomous vehicle safety controller system with the existing Suricata IDS to detect and respond to CAN Bus attacks.

---

## Table of Contents

1. [System Components](#system-components)
2. [Implementation Steps](#implementation-steps)
3. [Test Scenarios](#test-scenarios)
4. [Expected Outputs](#expected-outputs)
5. [Customization Guide](#customization-guide)
6. [Troubleshooting](#troubleshooting)

---

## System Components

### Core Modules

```
vehicle_control.py
├── VehicleControlModule
│   ├── CAN message parsing (brake, throttle, steering, perception)
│   ├── Threat detection (flooding, anomalies, extreme values)
│   ├── Threat scoring algorithm
│   ├── Safety state management
│   └── Maneuver execution (slow down, stop, pull over, evasive, full stop)
│
└── CANMessage, SafetyState, ManeuverType enums

safety_controller.py
├── SuricataIDS
│   ├── EVE JSON parsing
│   ├── Rule ID mapping (1000001-1000007)
│   └── Threat classification
│
└── SafetyController
    ├── IDS alert processing
    ├── Threat aggregation
    ├── Maneuver decision logic
    └── Incident reporting
```

### Integration Points

```
Suricata IDS (eve.json)
    ↓
    └→ SafetyController.process_ids_alert()
       ├── Parse JSON
       ├── Classify threat (7 classes)
       ├── Calculate severity
       └→ Decide maneuver
          ├── SLOW DOWN: 30-40 km/h (2 m/s² decel)
          ├── STOP: 0 km/h (8 m/s² decel)
          ├── PULL OVER: 15 km/h (4 m/s² decel)
          ├── EVASIVE: Steer + brake
          └── FULL STOP: Disable vehicle
             ↓
          Generate CAN commands (0x100-0x500)
          ├── Brake module (0x100): Pressure %
          ├── Throttle module (0x200): Throttle %
          ├── Steering module (0x300): Angle degrees
          └── Safety Controller (0x500): State + maneuver
             ↓
          VehicleControlModule executes commands
          └→ Vehicle performs safety maneuver
```

---

## Implementation Steps

### Step 1: Environment Setup

```bash
# Navigate to project directory
cd c:\Users\gmady\OneDrive\Desktop\can-bus-simulation

# Install dependencies (if not already installed)
pip install pandas matplotlib seaborn scapy
```

### Step 2: Generate Test Data (if needed)

```bash
# Generate CAN PCAP from CSV
cd code
python generate_pcap.py
```

### Step 3: Run Suricata Analysis (if needed)

```bash
# Run Suricata on PCAP
suricata -c suricata.yaml -r packets/can_sim.pcap -l suricata_logs/ -s rules/can.rules

# Verify eve.json was generated
ls suricata_logs/eve.json
```

### Step 4: Test Safety Controller

```python
# In Python interactive shell or script

from code.vehicle_control import VehicleControlModule, CANMessage, ModuleID
from code.safety_controller import SafetyController, SuricataIDS

# Initialize modules
vehicle = VehicleControlModule("AV_001")
safety_controller = SafetyController(vehicle)

# Process eve.json
results = safety_controller.process_eve_log_file(
    'suricata_logs/eve.json',
    max_entries=179  # Process all alerts
)

# Print report
print(safety_controller.generate_incident_report())

# Export detailed logs
logs = vehicle.export_logs()
```

---

## Test Scenarios

### Scenario 1: CAN Flood Detection → SLOW DOWN

**Threat**: Attacker floods brake module (0x100) with identical messages

**Expected Sequence**:

```
Time  Event                              CAN ID  Severity  Action
─────────────────────────────────────────────────────────────────
T+0   Suricata detects Rule 1000001      0x100   +15       Queue alert
      (CAN Flood - ID 0x100 pattern)

T+0.1 SafetyController receives alert
      Threat class: CAN_FLOOD
      Severity: 15 + baseline = 35 total

T+0.2 Score = 35 → YELLOW (CAUTION)

T+0.5 Decision: SLOW_DOWN maneuver
      Execute:
      - Safety state → CAUTION
      - Throttle → 0%
      - Brake → 20% (2 m/s² decel)
      - Target speed: 50 km/h

T+2   Vehicle gradually decelerates
      Flooding attack continues but suppressed

T+30  Vehicle reaches safe speed (50 km/h)
      Waiting for threat to clear
      OR threat escalates → switch to STOP
```

**Test Code**:

```python
from code.vehicle_control import CANMessage, ModuleID
import struct

vehicle = VehicleControlModule("TEST_FLOOD")
safety_controller = SafetyController(vehicle)

# Simulate repeated flood of CAN messages
for i in range(15):
    payload = bytes([0x20, 0x01, 0x0A, 0x00, 0x40, 0x00, 0x40, 0x00])
    msg = CANMessage(
        can_id=ModuleID.BRAKE.value,
        dlc=8,
        payload=payload,
        timestamp=time.time() + i*0.01
    )

    result = vehicle.process_can_message(msg)
    print(f"Iteration {i}: Threat score = {result['current_threat_score']}, "
          f"State = {result['current_safety_state']}")

# Expected output:
# Iteration 10: Threat score = 15, State = CAUTION
# Iteration 15: Threat score = 35, State = WARNING → SLOW DOWN executed
```

---

### Scenario 2: Unknown ECU Detection → FULL STOP

**Threat**: Message from unknown ECU ID (0x750, outside normal range 0x100-0x500)

**Expected Sequence**:

```
Time  Event                              CAN ID  Severity  Action
─────────────────────────────────────────────────────────────────
T+0   Attacker sends message from        0x750   +30       Queue alert
      unknown ECU (>0x700)

T+0.1 SafetyController receives alert
      Threat class: UNKNOWN_ECU
      Severity: 30 (critical)

T+0.2 Score = 30 → ORANGE (WARNING) → RED if >50

T+0.5 Decision: FULL_STOP maneuver (immediate)
      Execute:
      - Safety state → CRITICAL
      - Throttle → 0% (disable)
      - Brake → MAX (disable vehicle)
      - Steering → 0° (center)
      - Override disabled (driver cannot override)

T+1   Vehicle comes to complete stop
      Hazard lights activated
      Emergency alert sent
      Logs forensic data
```

**Test Code**:

```python
vehicle = VehicleControlModule("TEST_UNKNOWN_ECU")
safety_controller = SafetyController(vehicle)

# Create alert for unknown ECU
alert = {
    'timestamp': '2025-10-16T13:04:21.289475+0530',
    'rule_id': 1000007,  # Unknown ECU rule
    'signature': 'CAN Unknown ECU ID (>0x700) Detected',
    'src_ip': '192.168.0.5',
    'dest_ip': '192.168.0.7',
    'src_port': 5003,
    'dest_port': 6000,
    'proto': 'UDP'
}

response = safety_controller.process_ids_alert(alert)

print(f"Alert processed: {response}")
print(f"Maneuver executed: {response['maneuver_executed']}")
print(f"Current vehicle state: {vehicle.safety_state.name}")
print(f"Expected: CRITICAL + FULL_STOP")

# Verify FULL_STOP executed
assert vehicle.current_maneuver.name == "FULL_STOP", "FULL_STOP not executed!"
assert vehicle.safety_state.name == "EMERGENCY", "Vehicle not in EMERGENCY state!"
print("✓ Test passed!")
```

---

### Scenario 3: Multi-Module Conflict → EMERGENCY STOP

**Threat**: Simultaneous max brake + max throttle + hard steering (physically impossible)

**Expected Sequence**:

```
Time  Event                              CAN ID  Severity  Action
─────────────────────────────────────────────────────────────────
T+0   Attacker sends:
      - Max brake (0xFF) to 0x100       0x100   +25
      - Max throttle (0xFF) to 0x200    0x200   +25
      - Hard steer (-40°) to 0x300      0x300   +20
      All within 50ms window

T+0.05 SafetyController detects multi-module conflict
      Threat class: ANOMALY_PATTERN x3
      Severity: 25 + 25 + 20 = 70

T+0.1 Score = 70 → ORANGE (WARNING) → RED if multiple conflicts

T+0.2 Decision: EMERGENCY STOP (immediate)
      Execute:
      - Safety state → EMERGENCY
      - Throttle → 0% (override attacker)
      - Brake → 80% (not max to prevent lockup)
      - Steering → 0° (straighten immediately)
      - Monitor wheel sensor feedback

T+1-8 Emergency stop sequence executes
      Vehicle safely halts
      Conflicting commands suppressed
```

**Test Code**:

```python
from code.vehicle_control import CANMessage, ModuleID
import struct

vehicle = VehicleControlModule("TEST_CONFLICT")

# Simulate conflicting commands arriving simultaneously

# Brake: Max pressure
brake_msg = CANMessage(
    can_id=ModuleID.BRAKE.value,
    dlc=8,
    payload=bytes([0xFF, 0x01, 0x0A, 0x00, 0x40, 0x00, 0x40, 0x00]),
    timestamp=time.time()
)

# Throttle: Max position
throttle_msg = CANMessage(
    can_id=ModuleID.THROTTLE.value,
    dlc=8,
    payload=bytes([0xFF, 0x01, 0x10, 0x00, 0x18, 0x00, 0x50, 0x00]),
    timestamp=time.time() + 0.01
)

# Steering: Hard left
steering_angle = int(-40 * 256)  # -40 degrees in fixed-point
steering_msg = CANMessage(
    can_id=ModuleID.STEERING.value,
    dlc=8,
    payload=bytes([
        (steering_angle >> 8) & 0xFF,
        steering_angle & 0xFF,
        0x01, 0x3C,
        0xFF, 0xD8, 0xFF, 0xD8
    ]),
    timestamp=time.time() + 0.02
)

# Process messages
vehicle.process_can_message(brake_msg)
vehicle.process_can_message(throttle_msg)
vehicle.process_can_message(steering_msg)

# Check for conflict
conflict, reason = vehicle.detect_conflicting_commands()

print(f"Conflict detected: {conflict}")
print(f"Reason: {reason}")
print(f"Threat score: {vehicle.threat_score}")
print(f"Expected: Conflict=True, Score>50, State=EMERGENCY")

# Verify threat detected
assert conflict, "Conflict not detected!"
assert vehicle.threat_score > 50, "Threat score too low!"
print("✓ Test passed!")
```

---

### Scenario 4: Sensor Spoofing → Increased Monitoring

**Threat**: Perception module reports imminent collision, but radar/LIDAR disagree (sensor fusion mismatch)

**Expected Sequence**:

```
Time  Event                              CAN ID  Severity  Action
─────────────────────────────────────────────────────────────────
T+0   Spoofed message: closest_distance  0x400   +20
      = 0 meters (collision imminent)

T+0.1 Vehicle perception receives alert
      But sensor fusion checks:
      - Radar: No obstacles
      - LIDAR: No obstacles
      - Sensor health: 40% (ANOMALY)

T+0.2 Score = 20 (anomaly) → YELLOW (CAUTION)

T+0.5 Decision: INCREASE MONITORING, no immediate maneuver
      Continue operation but alert driver

T+1-10 Waits for sensor agreement:
      - If spoofed signal continues → Score rises → SLOWDOWN
      - If spoofed signal stops → Confidence recovers → NORMAL
      - If real collision detected → EVASIVE maneuver

T+10  After 10 seconds of monitoring:
      - Sensors agree: Clear → NORMAL
      - OR continued spoofing → escalate to SLOWDOWN
```

**Test Code**:

```python
from code.vehicle_control import CANMessage, ModuleID

vehicle = VehicleControlModule("TEST_SPOOFING")

# Simulate spoofed perception message
spoofed_perception = CANMessage(
    can_id=ModuleID.PERCEPTION.value,
    dlc=8,
    payload=bytes([
        0x01,           # 1 object detected
        0x00,           # 0 meters (collision!)
        0x50,           # 80 km/h relative speed
        0x03,           # Critical threat level
        0x00,           # Lane center
        0x00,           # Dry road
        0x00,           # Clear weather
        0x28            # 40% sensor health (anomaly)
    ]),
    timestamp=time.time()
)

result = vehicle.process_can_message(spoofed_perception)

print(f"Threats detected: {result['threats_detected']}")
print(f"Threat score: {result['current_threat_score']}")
print(f"Safety state: {result['current_safety_state']}")
print(f"Perception module valid: {vehicle.perception_state.is_valid}")

# Expected: Anomaly detected, score ~20, CAUTION state
assert len(result['threats_detected']) > 0, "Anomaly not detected!"
assert result['current_threat_score'] <= 50, "Too aggressive (should be monitoring only)"
print("✓ Test passed! (Spoofing detected but not over-reacting)")
```

---

## Expected Outputs

### Console Output Example

```
[+] Vehicle Safety Controller Initialized
Vehicle: AV_Tesla_001

Processing: suricata_logs/eve.json
├─ Total entries read: 179
├─ Total alerts parsed: 179
└─ Alert processing:
   T+0.0: Rule 1000001 (CAN Flood) - Severity 15 - Threat Score: 15 (CAUTION)
   T+0.1: Rule 1000002 (Anomaly) - Severity 20 - Threat Score: 35 (CAUTION)
   T+0.2: Rule 1000003 (DoS) - Severity 25 - Threat Score: 60 (ORANGE)
          → Executing STOP maneuver
   T+0.5: Rule 1000001 (Flood) - Severity 15 - Threat Score: 75 (ORANGE)
          → Maneuver cooldown (2s)
   ...

═══════════════════════════════════════════════════════════════════════════════
                    VEHICLE STATUS AFTER PROCESSING
───────────────────────────────────────────────────────────────────────────────
Safety State:                  EMERGENCY
Current Maneuver:              STOP
Threat Score:                  85/100

Brake Module:     Pressure 80%, Status: Engaged, Decel 8.0 m/s²
Throttle Module:  Position 0%, Status: Fault, Accel 0.0 m/s²
Steering Module:  Angle 0.0°, Status: Active, Rate 0.0°/s
Perception:       3 objects, 5m closest, Threat: WARNING, Health: 100%

═══════════════════════════════════════════════════════════════════════════════
```

### Generated Incident Report

```
════════════════════════════════════════════════════════════════════════════════
                   AUTONOMOUS VEHICLE SAFETY INCIDENT REPORT
════════════════════════════════════════════════════════════════════════════════
Vehicle: AV_Tesla_001
Generated: 2025-10-16T13:05:30.123456

INCIDENT SUMMARY
────────────────────────────────────────────────────────────────────────────────
Total Threats Detected: 45
Final Vehicle Status: EMERGENCY
Final Threat Score: 85

THREAT CLASSES DETECTED
────────────────────────────────────────────────────────────────────────────────
  CAN_FLOOD: 12 occurrences
  ANOMALY_PATTERN: 18 occurrences
  DOS_ZERO_PAYLOAD: 3 occurrences
  DIAGNOSTIC_FLOOD: 6 occurrences
  UNAUTHORIZED_COMMAND: 4 occurrences
  OBD_ABUSE: 2 occurrences

VEHICLE STATUS AT END OF INCIDENT
────────────────────────────────────────────────────────────────────────────────
  Safety State: EMERGENCY
  Current Maneuver: STOP
  Threat Score: 85/100

  Subsystem Status:
    Brake: 80% pressure, Engaged
    Throttle: 0% position, Fault
    Steering: 0.0° angle, Active
    Perception: 3 objects, Critical threat

SESSION STATISTICS
────────────────────────────────────────────────────────────────────────────────
  Session Duration: 23.45 seconds
  Total CAN Messages Processed: 179
  Total Security Alerts: 45

════════════════════════════════════════════════════════════════════════════════
                              END OF REPORT
════════════════════════════════════════════════════════════════════════════════
```

---

## Customization Guide

### 1. Adjust Threat Severity Scores

Edit `safety_controller.py`:

```python
class SuricataIDS:
    @staticmethod
    def get_threat_severity(threat_class: ThreatClass) -> int:
        """Get base severity score (0-100) for a threat class"""
        severity_map = {
            ThreatClass.CAN_FLOOD: 20,           # ← Increase from 15
            ThreatClass.ANOMALY_PATTERN: 25,    # ← Increase from 20
            ThreatClass.DOS_ZERO_PAYLOAD: 30,   # ← Increase from 25
            # ... rest of mappings
        }
        return severity_map.get(threat_class, 10)
```

### 2. Modify Maneuver Decision Logic

Edit `safety_controller.py`:

```python
def _decide_maneuver(self, severity, threat_classes):
    # Change thresholds
    if severity >= 60:  # ← Changed from 50
        return ManeuverType.STOP
    elif severity >= 35:  # ← Changed from 30
        return ManeuverType.SLOW_DOWN
```

### 3. Adjust Vehicle Physics Constraints

Edit `vehicle_control.py`:

```python
class VehicleControlModule:
    def __init__(self):
        self.max_decel_normal = 3.0        # ← Increased from 2.0 m/s²
        self.max_decel_stop = 10.0         # ← Increased from 8.0 m/s²
        self.max_steering_angle = 45.0     # ← Increased from 40.0 degrees
```

### 4. Add Custom Threat Detection Rule

Edit `vehicle_control.py`:

```python
def detect_custom_threat(self, can_id: int, payload: bytes) -> Tuple[bool, str]:
    """Custom threat detection logic"""
    # Example: Detect rapid power changes
    if can_id == ModuleID.THROTTLE.value:
        throttle_now = payload[0]
        throttle_prev = self.throttle_state.throttle_pos

        delta = abs(throttle_now - throttle_prev)
        if delta > 200:  # >78% change in one message
            return True, "Rapid throttle change detected"

    return False, ""
```

---

## Troubleshooting

### Issue 1: "File not found: suricata_logs/eve.json"

**Solution**:

1. Ensure Suricata has been run: `suricata -c suricata.yaml -r packets/can_sim.pcap -l suricata_logs/`
2. Verify eve.json exists: `ls suricata_logs/eve.json`
3. Check file permissions

### Issue 2: No alerts being processed

**Solution**:

1. Verify eve.json is not empty: `wc -l suricata_logs/eve.json`
2. Check eve.json format (should be valid JSON lines)
3. Ensure Suricata rules file (rules/can.rules) is referenced in suricata.yaml

### Issue 3: Maneuvers not executing

**Solution**:

1. Check threat score: `print(vehicle.threat_score)`
2. Verify safety state: `print(vehicle.safety_state.name)`
3. Check maneuver cooldown: `time.time() - safety_controller.last_maneuver_time < 2.0`

### Issue 4: Inconsistent threat scores

**Solution**:

1. Review threat history: `vehicle.threat_history[-10:]`
2. Check time decay in `calculate_threat_score()`
3. Verify alert queue processing: `print(safety_controller.alert_queue)`

---

## Next Steps

1. **Deploy to Vehicle Simulator**: Connect to CARLA or LGSVL simulator
2. **Real-Time Monitoring**: Implement live Suricata alert streaming
3. **Machine Learning**: Add anomaly detection using neural networks
4. **Hardware Integration**: Interface with actual CAN Bus hardware (CAN-USB adapters)
5. **Redundancy**: Add secondary controller for fail-safe operation
