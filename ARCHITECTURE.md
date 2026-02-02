# Autonomous Vehicle CAN Bus Control Architecture

## Executive Summary

This document defines a safety-critical command-and-control system for an autonomous vehicle that monitors CAN Bus traffic for anomalous behavior and executes preventative safety maneuvers to protect vehicle occupants and road users.

---

## 1. System Architecture Overview

### 1.1 Vehicle Control Modules

The autonomous vehicle consists of five primary control modules that communicate via CAN Bus:

```
┌─────────────────────────────────────────────────────────────┐
│                    CAN Bus Backbone (500 kbps)              │
└─────────────────────────────────────────────────────────────┘
        ↑              ↑              ↑              ↑
     (0x100)       (0x200)        (0x300)        (0x400)
        │              │              │              │
   ┌────────┐     ┌──────────┐   ┌─────────┐   ┌──────────┐
   │ BRAKE  │     │ THROTTLE │   │ STEERING│   │ PERCEPTION
   │MODULE  │     │ MODULE   │   │ MODULE  │   │ MODULE
   └────────┘     └──────────┘   └─────────┘   └──────────┘
        │              │              │              │
   ┌────────────────────────────────────────────────────────┐
   │         PLANNING/SAFETY CONTROLLER (0x500)             │
   │  - Threat Detection & Classification                   │
   │  - Safety State Management                             │
   │  - Emergency Maneuver Execution                        │
   └────────────────────────────────────────────────────────┘
```

### 1.2 Module Responsibilities

| Module | CAN ID | Role | Inputs | Outputs |
|--------|--------|------|--------|---------|
| **Brake** | 0x100 | Wheel brake pressure control | Deceleration target | Brake force (0-100%) |
| **Throttle** | 0x200 | Engine/Motor power control | Acceleration target | Throttle position (0-100%) |
| **Steering** | 0x300 | Wheel steering angle control | Steering angle target | Steering angle (-45° to +45°) |
| **Perception** | 0x400 | Environmental sensing | Raw sensor data | Object detection, hazard alerts |
| **Safety Controller** | 0x500 | Command & Control | All module feedback, threat level | Emergency commands |

---

## 2. Threat Detection & Classification

### 2.1 Detection Criteria

The system monitors for **7 classes of threats**:

#### **Class 1: CAN Message Flooding**
- **Trigger**: Single CAN ID repeated >10 times in 1 second window
- **Severity**: HIGH
- **Affected Module**: Any control module (0x100, 0x200, 0x300)
- **Implication**: Possible DoS attack attempting to overwhelm one subsystem
- **Response**: Isolate affected module, activate fallback systems

#### **Class 2: Anomalous Payload Patterns**
- **Trigger**: Unexpected data sequences in control messages
- **Examples**:
  - Brake command (0x100) with payload `|FF FF 00 00 11 22 33 44|` (not normal brake pressure values)
  - Throttle spikes to 100% with all-FF payload
- **Severity**: MEDIUM-HIGH
- **Implication**: Payload injection/corruption attack
- **Response**: Request sensor validation, manual override control

#### **Class 3: Extreme Control Values**
- **Trigger**: Control commands exceed safe operating thresholds
- **Examples**:
  - Brake pressure >95% (hard braking) without corresponding threat
  - Steering angle >40° at highway speeds
  - Simultaneous max brake + max throttle (physical impossibility)
- **Severity**: MEDIUM
- **Implication**: Conflicting commands or sensor spoofing
- **Response**: Apply command filtering, slow deceleration

#### **Class 4: All-Zero Payload (Sensor Failure)**
- **Trigger**: Control message with all-zero payload (0x00 00 00 00 00 00 00 00)
- **Severity**: MEDIUM
- **Implication**: Sensor failure or malicious disabling
- **Response**: Trigger safe stop sequence

#### **Class 5: Diagnostic Abuse (All-FF Payload)**
- **Trigger**: Repeated FF-filled payloads indicating diagnostic mode misuse
- **Severity**: LOW-MEDIUM
- **Implication**: Diagnostic flooding or firmware manipulation attempt
- **Response**: Increase monitoring, disable over-the-air updates

#### **Class 6: Unknown ECU/Module**
- **Trigger**: CAN messages from IDs >0x700 (outside defined module range)
- **Severity**: HIGH
- **Implication**: Unauthorized ECU/hardware installed
- **Response**: Alert driver, isolate unknown module

#### **Class 7: Conflicting Multi-Module Commands**
- **Trigger**: Steering + heavy braking + throttle increase simultaneously
- **Severity**: CRITICAL
- **Implication**: Coordinated attack across multiple modules
- **Response**: Immediate emergency stop

### 2.2 Threat Scoring Algorithm

```
Threat Score = (Σ Class_i_Severity × Frequency_i) / Time_Window

Risk Level Classification:
- 0-20:    GREEN (Normal operation)
- 21-50:   YELLOW (Caution, increase monitoring)
- 51-80:   ORANGE (Warning, prepare safety maneuvers)
- 81-100:  RED (Critical, execute emergency stop)
```

---

## 3. CAN Message Specification

### 3.1 Brake Module (CAN ID: 0x100)

**Direction**: Bi-directional (Command & Feedback)

| Byte | Field | Range | Unit | Description |
|------|-------|-------|------|-------------|
| 0 | Brake_Pressure | 0x00-0x64 | % | Brake force (0-100%) |
| 1 | Status | 0x00-0x03 | Enum | 0=Idle, 1=Engaged, 2=Fault |
| 2-3 | Decel_Rate | 0x0000-0xFFFF | m/s² | Actual deceleration |
| 4-5 | Wheel_Speed_FL | 0x0000-0xFFFF | km/h | Front-left wheel speed |
| 6-7 | Wheel_Speed_FR | 0x0000-0xFFFF | km/h | Front-right wheel speed |

**Normal Command**:
```
Header: CAN ID 0x100, DLC=8
Payload: |20 01 0A 00 40 00 40 00|
Interpretation: 32% brake, engaged, 10 m/s² decel, 64 km/h both fronts
```

**Anomalous Command (Flagged)**:
```
Payload: |FF FF 00 00 11 22 33 44|
Reason: Max brake (FF) with impossible zero decel rate + random wheel speeds
```

---

### 3.2 Throttle Module (CAN ID: 0x200)

**Direction**: Bi-directional (Command & Feedback)

| Byte | Field | Range | Unit | Description |
|------|-------|-------|------|-------------|
| 0 | Throttle_Pos | 0x00-0x64 | % | Engine/motor power (0-100%) |
| 1 | Status | 0x00-0x03 | Enum | 0=Idle, 1=Active, 2=Fault |
| 2-3 | Accel_Rate | 0x0000-0xFFFF | m/s² | Actual acceleration |
| 4-5 | Engine_RPM | 0x0000-0xFFFF | RPM | Engine speed |
| 6-7 | Fuel_Level | 0x0000-0x0064 | % | Fuel tank level |

**Normal Command**:
```
Payload: |32 01 05 00 18 00 50 00|
Interpretation: 50% throttle, active, 5 m/s² accel, 6000 RPM, 80% fuel
```

---

### 3.3 Steering Module (CAN ID: 0x300)

**Direction**: Bi-directional (Command & Feedback)

| Byte | Field | Range | Unit | Description |
|------|-------|-------|------|-------------|
| 0-1 | Steering_Angle | 0xFFD8-0x0028 | degrees | -40° to +40° (twos complement) |
| 2 | Status | 0x00-0x03 | Enum | 0=Idle, 1=Active, 2=Fault |
| 3 | Steering_Rate | 0x00-0xFF | °/s | Rate of steering change |
| 4-5 | Wheel_Angle_FL | 0xFFD8-0x0028 | degrees | Front-left wheel angle |
| 6-7 | Wheel_Angle_FR | 0xFFD8-0x0028 | degrees | Front-right wheel angle |

**Normal Command**:
```
Payload: |00 0F 01 1E 00 0F 00 0F|
Interpretation: 15° right steer, active, 30°/s rate, wheels at 15°
```

---

### 3.4 Perception Module (CAN ID: 0x400)

**Direction**: Output only (Sensor data transmission)

| Byte | Field | Range | Unit | Description |
|------|-------|-------|------|-------------|
| 0 | Object_Count | 0x00-0x0F | Count | Number of detected objects |
| 1 | Closest_Distance | 0x00-0xFF | meters | Distance to nearest object |
| 2 | Closest_Speed | 0x00-0xFF | km/h | Relative speed of object |
| 3 | Threat_Level | 0x00-0x03 | Enum | 0=Clear, 1=Caution, 2=Warning, 3=Critical |
| 4 | Lane_Position | 0x00-0x02 | Enum | 0=Center, 1=Left, 2=Right |
| 5 | Road_Condition | 0x00-0x03 | Enum | 0=Dry, 1=Wet, 2=Icy, 3=Unknown |
| 6 | Weather | 0x00-0x0F | Bitmask | Bit0=Rain, Bit1=Fog, Bit2=Snow, Bit3=Darkness |
| 7 | Sensor_Health | 0x00-0x64 | % | Sensor confidence (0-100%) |

---

### 3.5 Safety Controller (CAN ID: 0x500)

**Direction**: Output only (Emergency commands)

| Byte | Field | Range | Unit | Description |
|------|-------|-------|------|-------------|
| 0 | Safety_State | 0x00-0x05 | Enum | 0=Normal, 1=Caution, 2=Warning, 3=Emergency, 4=Disabled |
| 1 | Maneuver_Type | 0x00-0x05 | Enum | 0=None, 1=SlowDown, 2=Stop, 3=PullOver, 4=Evasive, 5=FullStop |
| 2 | Target_Speed | 0x00-0x64 | km/h | Speed limit (0-100 km/h) |
| 3 | Threat_ID | 0x00-0xFF | ID | Which threat triggered (Class 1-7) |
| 4 | Confidence | 0x00-0x64 | % | Detection confidence |
| 5 | Override_Mode | 0x00-0x01 | Bool | 1=Allow manual override, 0=Force execution |
| 6-7 | Reserved | 0x0000 | - | Future use |

---

## 4. Safety Maneuvers

### 4.1 Maneuver: SLOW DOWN (Speed Reduction)

**Trigger**: Threat Level YELLOW (Risk 21-50)

**Objective**: Gradually reduce speed to allow driver intervention

**CAN Message Sequence**:

```
Time  Module    CAN ID  Message                          Action
─────────────────────────────────────────────────────────────────
T+0   Controller 0x500  |01 01 50 XX XX 01 00 00|  Declare CAUTION state
                        Safety=Caution, Maneuver=SlowDown, Target=80km/h

T+1   Throttle  0x200  |00 01 00 00 ... |         → 0% throttle (coast)
      
T+2   Brake     0x100  |14 01 02 00 ...|         → 20% brake (soft decel)

T+3-30 Monitor  0x500  |01 01 48 XX XX 01 00 00| Target drops: 80→60→40
       Every 3s        Gradually reduce target speed

T+30  Alert     0x500  |01 01 32 XX XX 01 00 00| Reach 50 km/h (safe speed)
               Transition to NORMAL if threat clears
```

**Safety Constraints**:
- Max deceleration: 2 m/s² (comfortable, no ABS trigger)
- Minimum time: 30 seconds to reach target speed
- Driver can override at any point
- All-wheel ABS engaged to maintain stability

---

### 4.2 Maneuver: STOP (Emergency Brake)

**Trigger**: Threat Level ORANGE (Risk 51-80)

**Objective**: Safe full stop within 60 meters

**CAN Message Sequence**:

```
Time  Module    CAN ID  Message                          Action
─────────────────────────────────────────────────────────────────
T+0   Controller 0x500  |03 02 00 XX XX 00 00 00|  Declare WARNING state
                        Safety=Warning, Maneuver=Stop, Target=0km/h

T+0   Throttle  0x200  |00 01 00 00 ...|          → 0% throttle immediately

T+0.5 Brake     0x100  |50 01 08 00 ...|          → 80% brake (emergency)
                       Target: 8 m/s² deceleration

T+1-8  Monitor  0x500  |03 02 00 XX XX 00 00 00| Verify deceleration
      Every 500ms       Request ABS status from Brake module

T+8    Final    0x100  |78 01 0A 00 ...|         → 120% max (locked wheels)
                        Confirm stopped, set parking brake
       
      Hazard   0x500  Signal hazard lights to other systems
      Notify   Send alert to driver + connected vehicles (DSRC/V2X)
```

**Safety Constraints**:
- Max deceleration: 8 m/s² (limit to prevent rollover on curves)
- Must maintain steering control (no >20° angle during stop)
- ABS must be active to prevent wheel lockup
- Brake cooling monitoring to prevent fade
- Verify actual speed from wheel sensors before completion

---

### 4.3 Maneuver: PULL OVER (Safe Lane Exit)

**Trigger**: Threat Level ORANGE (Risk 51-80) + Not on highway

**Objective**: Safely exit to shoulder/parking area

**CAN Message Sequence**:

```
Time  Module      CAN ID  Message                      Action
──────────────────────────────────────────────────────────────
T+0   Controller  0x500  |02 03 2A XX XX 01 00 00|  Declare MANEUVER
                         Safety=Warning, Maneuver=PullOver

T+0   Perception 0x400   (Listen for shoulder detection)
      Check lane status

T+1   Steering   0x300   |FF D8 01 20 ...|         → -40° angle (hard left)
                         Turn wheel 40° to exit lane

T+2   Throttle   0x200   |00 01 00 00 ...|         → 0% throttle

T+2   Brake      0x100   |28 01 04 00 ...|         → 40% brake (moderate)
                         4 m/s² deceleration

T+3-20 Monitor   0x500   |02 03 28 XX XX 01 00 00| Target: 42→30→15 km/h

T+20  Verify     0x300   Check steering angle      Confirm pulled over
      
      Final      0x100   |50 01 00 00 ...|         Parking brake ON
                         Set to 80% lock for hold

T+22  Safe State 0x500   |00 03 00 XX XX 01 00 00| PARKED state
                         Disengage steering, brake hold engaged
```

**Safety Constraints**:
- Only execute on roads with visible shoulders (not highways >80 km/h)
- Steering angle must increase gradually (not step functions)
- Check for oncoming traffic during maneuver
- Verify actual lane position from perception module
- Allow 20+ seconds for safe execution

---

### 4.4 Maneuver: EMERGENCY EVASIVE (Collision Avoidance)

**Trigger**: Threat Level RED (Risk 81-100) OR Collision imminent (<2 seconds)

**Objective**: Execute evasive maneuver to avoid collision

**CAN Message Sequence**:

```
Time   Module      CAN ID  Message                     Action
───────────────────────────────────────────────────────────
T+0    Controller  0x500  |04 04 00 XX XX 00 00 00| Declare EMERGENCY
                          Safety=Critical, Maneuver=Evasive

T+0    Perception 0x400   (Identify threat location)
       Determine: LEFT vs RIGHT avoidance needed

T+0    Throttle   0x200   |00 01 00 00 ...|        → 0% throttle

T+0    Brake      0x100   |42 01 06 00 ...|        → 66% brake (6 m/s²)

T+0.2  Steering   0x300   |00 19 01 2A ...|        → 25° (LEFT evasion)
       EXECUTE STEERING IMMEDIATELY              [or RIGHT if threat on left]
       (No gradual ramp)

T+0.5  Re-check   0x400   Monitor perception      Verify threat cleared

IF threat cleared:
T+1    Stabilize  0x300   |00 00 01 0F ...|        → 0° steering (straight)
       
T+2    Resume     0x500   |01 01 32 XX XX 01 00 00| Return to SLOWDOWN

IF threat NOT cleared:
T+1    Full Stop  0x100   |78 01 0A 00 ...|        → Maximum brake
       Proceed to STOP maneuver
```

**Safety Constraints**:
- Evasion angle: 20-30° only (prevent rollover >60 km/h)
- Must not exceed 9 m/s² combined decel + lateral acceleration
- If speed >100 km/h, steer more gradually and increase braking
- Disengage cruise control and all non-essential systems
- Driver override disabled during evasion (too dangerous to interfere)

---

### 4.5 Maneuver: FULL STOP / LIMP HOME

**Trigger**: Threat Level RED (Risk 81-100) + Conflicting multi-module commands OR Unknown ECU

**Objective**: Immediate stop and disable vehicle

**CAN Message Sequence**:

```
Time   Module      CAN ID  Message                     Action
───────────────────────────────────────────────────────────
T+0    Controller  0x500  |04 05 00 06 64 00 00 00| Declare CRITICAL STOP
                          Safety=Critical, Maneuver=FullStop, Threat=06

T+0    Throttle   0x200   |00 02 00 00 ...|        → 0% throttle, set FAULT

T+0    Brake      0x100   |7F 02 0A 00 ...|        → 127% (MAX), set FAULT
                          Override brake limits

T+0.1  Steering   0x300   |00 00 02 00 ...|        → 0° steering, FAULT

T+0.5  Perception 0x400   Disable autonomous mode

T+1    Transmission Neutral  (If applicable)
       Enable parking brake

T+2    Hazard     0x500   Activate hazard lights
       Lights            Notify emergency services via V2X

T+5    Post-Event          Log all CAN messages before incident
       Analysis           Preserve forensic data

T+∞    VEHICLE DISABLED - Driver manual mode required
```

**Safety Constraints**:
- No time to gradual approach - max braking immediately
- Steering centered to prevent loss of control
- All powertrain systems disabled
- Hazards + warnings activated
- Incident logging for forensics
- Manual driver intervention required to resume

---

## 5. Detection & Response Flowchart

```
                        ┌──────────────────┐
                        │ Incoming CAN Msg │
                        │    (All IDs)     │
                        └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
         ┌──────────▼─────────┐   ┌──────────▼──────────┐
         │ Known Module ID?   │   │ Known Module ID?    │
         │ (0x100-0x400)      │   │ (Yes) ► Validate    │
         └────────┬──────────┘   └─────────┬────────────┘
                  │ NO                      │
         ┌────────▼────────────┐   ┌────────▼──────────┐
         │ THREAT CLASS 6:     │   │ Validate Payload  │
         │ Unknown ECU (>0x700)│   │ Ranges            │
         │                     │   │                   │
         │ Threat Score += 25  │   └────────┬──────────┘
         └─────────┬───────────┘            │
                   │           ┌────────────┴──────┐
                   │           │                   │
                   │   ┌───────▼──────┐  ┌────────▼──────┐
                   │   │ Out of Range?│  │ In Range OK?  │
                   │   └───────┬──────┘  └────────┬──────┘
                   │           │ YES              │ NO
         ┌─────────▼───┐ ┌─────▼────────────┐    │
         │ Mark as     │ │ Check Patterns:  │    │
         │ ANOMALOUS   │ │ - Flooding?      │    │
         │             │ │ - Payload anomaly│    │
         │ Threat += 10│ │ - Conflicting?   │    │
         └─────────────┘ └─────┬────────────┘    │
                               │ Detected        │
                    ┌──────────▼──────────┐      │
                    │ Calculate Risk Score│      │
                    │                     │      │
                    │ Threat Score = ∑    │      │
                    └──────────┬──────────┘      │
                               │                 │
              ┌────────────────┼────────────────┬┘
              │ GREEN (0-20)   │ YELLOW(21-50) │ ORANGE(51-80) │ RED(81-100)
              │ NORMAL         │ CAUTION       │ WARNING       │ CRITICAL
              │                │               │               │
    ┌─────────▼──┐  ┌──────────▼──┐  ┌────────▼────┐  ┌──────▼──────┐
    │ Continuous │  │ Increase    │  │ SLOW DOWN   │  │ EMERGENCY   │
    │ Monitoring │  │ Monitoring  │  │ Maneuver    │  │ STOP        │
    │            │  │             │  │             │  │ Maneuver    │
    │ Send 0x500:│  │ Send 0x500: │  │ Send 0x500: │  │ Send 0x500: │
    │ |00 00 ... │  │ |01 01 ... │  │ |02 02 ... │  │ |04 05 ... │
    │ Allow all  │  │ Warn driver │  │ Target:    │  │ Force stop  │
    │ Maneuvers  │  │ Recommend   │  │ 50 km/h    │  │ No override │
    │            │  │ Pull over   │  │ 30 seconds │  │             │
    └────────────┘  └─────────────┘  └────────────┘  └─────────────┘
```

---

## 6. Assumptions & Safety Constraints

### 6.1 Operational Assumptions

1. **Sensor Fusion Trust**: Perception module data is aggregated from multiple sensors (LIDAR, Radar, Camera) with voting logic
2. **CAN Bus Integrity**: Physical CAN bus is shielded and isolated from easily accessible diagnostic ports
3. **Driver Awareness**: Driver can take manual control at any time (except FULL STOP)
4. **Network Latency**: CAN message propagation <10ms; safety controller executes within 50ms
5. **Vehicle Dynamics**: Vehicle mass, steering ratio, brake system parameters are pre-calibrated

### 6.2 Safety Constraints

| Constraint | Limit | Rationale |
|-----------|-------|-----------|
| Max Deceleration (Normal) | 2 m/s² | Passenger comfort, prevents ABS trigger |
| Max Deceleration (Stop) | 8 m/s² | Emergency braking limit, prevent rollover |
| Max Deceleration (Full Stop) | 10+ m/s² | Max brake effort, limited by wheel friction |
| Max Steering Angle | ±40° | Steering lock limits, prevent over-steering |
| Max Steering Rate | 60°/s | Prevent sudden jerking at high speeds |
| Steering+Brake Combo Limit | Decel ≤ 5 m/s² @ 30°+ steer | Prevent rollover on curves |
| Minimum Stop Distance | 60m @ 80 km/h | ABS + brake fade margin |
| Override Timeout | 3 seconds | Driver must reconfirm override commands |
| Multi-Module Conflict Timeout | 100ms | Flag within 100ms for coordinated attacks |

### 6.3 Fail-Safe Mechanisms

1. **Watchdog Timer**: If no heartbeat from module in 200ms → assume failure → activate SLOW DOWN
2. **Sensor Disagreement**: If wheel speed >5% variance from predicted → reduce throttle
3. **Brake Pressure Validation**: If brake pressure command doesn't match actual pressure within 5% → flag anomaly
4. **Throttle-Brake Conflict**: If both >30% simultaneously for >500ms → activate STOP
5. **Steering Feedback Mismatch**: If steering angle command differs from actual by >5° → reduce target angle

---

## 7. Integration with Existing Suricata IDS

The safety controller receives threat classification from Suricata rules:

| Suricata Rule ID | Threat Class | Risk Score | Action |
|-----------------|--------------|-----------|--------|
| 1000001 | CAN Flood | +15 | Monitor, prepare SLOW DOWN |
| 1000002 | Anomaly | +20 | Validate payload, increase monitoring |
| 1000003 | DoS (Zero) | +25 | Flag sensor failure, execute STOP |
| 1000004 | Diagnostic Flood | +10 | Log, continue monitoring |
| 1000005 | Unauthorized Cmd | +20 | Block command, prepare SLOW DOWN |
| 1000006 | OBD Abuse | +15 | Restrict diagnostic access |
| 1000007 | Unknown ECU | +30 | Isolate, execute STOP |

---

## 8. Example Scenarios

### Scenario A: Brake Flooding Attack

```
Time    Event
─────────────────────────────────────────────────────────────
T+0     Attacker floods CAN with 15× identical brake messages (0x100)
        All payloads: |FF FF 00 00 ...| (max brake, zero decel)

T+0.1   Suricata detects Rule 1000001 (flood) + 1000002 (anomaly)
        Threat Score = 15 + 20 = 35 (YELLOW → CAUTION)

T+0.5   Safety Controller receives alerts
        Issues 0x500: |01 01 50 XX XX 01 00 00| (CAUTION, SLOWDOWN)

T+1     Throttle module receives 0% throttle command
        Brake module receives 20% braking command (limited, not 100%)
        Vehicle begins gradual deceleration

T+2-30  Legitimate brake pressure commands are validated
        Flooding attack is quarantined / isolated
        Vehicle reaches safe speed (50 km/h)

Result: Attack mitigated, vehicle safe, driver notified
```

### Scenario B: Coordinated Multi-Module Attack

```
Time    Event
─────────────────────────────────────────────────────────────
T+0     Attacker sends simultaneous commands:
        - Max throttle to 0x200: |64 01 10 00 ...|
        - Max brake to 0x100: |7F 01 0A 00 ...|
        - Hard left steer to 0x300: |FF D8 01 3C ...|
        All arrive within 50ms window

T+0.05  Safety Controller detects multi-module conflict
        Physical impossibility detected (conflicting vectors)
        Threat Score = 25 + 25 + 20 = 70 (ORANGE → WARNING)

T+0.1   Issues 0x500: |04 04 00 XX XX 00 00 00| (CRITICAL EVASIVE)
        (If highway: switches to |04 05 ...| for FULL STOP)

T+0.2   Throttle → 0% (override attacker command)
        Brake → 80% (emergency)
        Steering → 0° (straighten wheels)

T+1-8   Vehicle executes emergency stop
        All commands from attacker are suppressed
        CAN bus traffic logged for forensics

Result: Attack prevented, emergency stop executed safely
```

### Scenario C: Sensor Spoofing Detected

```
Time    Event
─────────────────────────────────────────────────────────────
T+0     Perception module receives spoofed message:
        - Closest obstacle: 0 meters (collision imminent)
        - But radar/LIDAR disagree (clear road ahead)

T+0.05  Sensor fusion logic detects disagreement
        Confidence drops to 40% (anomaly flagged)

T+0.1   Safety Controller calculates risk:
        Threat Score = 20 (anomaly) + 15 (sensor mismatch) = 35

T+0.5   Issues CAUTION state, increases monitoring

T+1-5   Waits for sensor agreement:
        - If spoofed signal continues → risk rises → SLOWDOWN
        - If spoofed signal stops → confidence recovers → NORMAL

T+5     If real obstacle appears (all sensors agree):
        Switches to EVASIVE maneuver (genuine threat)

Result: Spoofing attack detected, vehicle not fooled
```

---

## 9. Conclusion

This safety architecture provides **defense-in-depth** against CAN Bus attacks through:

1. **Multi-layered Detection**: Payload validation + pattern analysis + sensor fusion
2. **Graduated Response**: CAUTION → WARNING → EMERGENCY → STOP
3. **Safety Limits**: Physical constraints prevent extreme control values
4. **Fail-Safe Defaults**: Assume worst-case, execute STOP on uncertainty
5. **Forensic Logging**: All CAN messages preserved for post-incident analysis

The system prioritizes **occupant safety** and **road user protection** over vehicle availability, making it suitable for production autonomous vehicles.

