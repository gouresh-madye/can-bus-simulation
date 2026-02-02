"""
Autonomous Vehicle Control Module
Manages communication with vehicle subsystems and executes safety maneuvers

This module provides:
- Vehicle module abstractions (Brake, Throttle, Steering, Perception)
- CAN message parsing and validation
- Command execution and logging
"""

import time
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import struct
from collections import defaultdict


class SafetyState(Enum):
    """Vehicle safety states"""
    NORMAL = 0
    CAUTION = 1
    WARNING = 2
    EMERGENCY = 3
    DISABLED = 4


class ManeuverType(Enum):
    """Available safety maneuvers"""
    NONE = 0
    SLOW_DOWN = 1
    STOP = 2
    PULL_OVER = 3
    EVASIVE = 4
    FULL_STOP = 5


class ModuleID(Enum):
    """CAN module identifiers"""
    BRAKE = 0x100
    THROTTLE = 0x200
    STEERING = 0x300
    PERCEPTION = 0x400
    SAFETY_CONTROLLER = 0x500


@dataclass
class CANMessage:
    """Represents a CAN bus message"""
    can_id: int
    dlc: int  # Data Length Code (0-8)
    payload: bytes  # 0-8 bytes
    timestamp: float
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None


@dataclass
class BrakeState:
    """Current brake system state"""
    pressure_percent: int = 0  # 0-100%
    status: int = 0  # 0=Idle, 1=Engaged, 2=Fault
    decel_rate: float = 0.0  # m/s²
    wheel_speed_fl: int = 0  # km/h
    wheel_speed_fr: int = 0  # km/h
    is_valid: bool = True


@dataclass
class ThrottleState:
    """Current throttle system state"""
    throttle_pos: int = 0  # 0-100%
    status: int = 0  # 0=Idle, 1=Active, 2=Fault
    accel_rate: float = 0.0  # m/s²
    engine_rpm: int = 0
    fuel_level: int = 100  # 0-100%
    is_valid: bool = True


@dataclass
class SteeringState:
    """Current steering system state"""
    steering_angle: float = 0.0  # -40 to +40 degrees
    status: int = 0  # 0=Idle, 1=Active, 2=Fault
    steering_rate: float = 0.0  # degrees/second
    wheel_angle_fl: float = 0.0
    wheel_angle_fr: float = 0.0
    is_valid: bool = True


@dataclass
class PerceptionState:
    """Current perception/sensor state"""
    object_count: int = 0
    closest_distance: int = 255  # meters
    closest_speed: int = 0  # km/h
    threat_level: int = 0  # 0=Clear, 1=Caution, 2=Warning, 3=Critical
    lane_position: int = 0  # 0=Center, 1=Left, 2=Right
    road_condition: int = 0  # 0=Dry, 1=Wet, 2=Icy, 3=Unknown
    weather: int = 0  # Bitmask
    sensor_health: int = 100  # 0-100%
    is_valid: bool = True


class VehicleControlModule:
    """
    Central vehicle control module for autonomous vehicles.
    
    Monitors CAN Bus traffic, detects threats, manages vehicle state,
    and executes safety maneuvers.
    """

    def __init__(self, vehicle_name: str = "AV_001"):
        """Initialize the vehicle control module"""
        self.vehicle_name = vehicle_name
        self.start_time = time.time()
        
        # Vehicle state
        self.safety_state = SafetyState.NORMAL
        self.current_maneuver = ManeuverType.NONE
        self.threat_score = 0
        self.threat_history: List[Tuple[float, int, str]] = []
        
        # Module states
        self.brake_state = BrakeState()
        self.throttle_state = ThrottleState()
        self.steering_state = SteeringState()
        self.perception_state = PerceptionState()
        
        # Threat detection
        self.message_frequency: Dict[int, List[float]] = defaultdict(list)
        self.anomaly_count: Dict[int, int] = defaultdict(int)
        self.last_command: Dict[int, CANMessage] = {}
        
        # CAN message log
        self.message_log: List[CANMessage] = []
        self.alert_log: List[Dict] = []
        
        # Constraints
        self.max_decel_normal = 2.0  # m/s²
        self.max_decel_stop = 8.0    # m/s²
        self.max_decel_emergency = 10.0
        self.max_steering_angle = 40.0  # degrees
        self.max_steering_rate = 60.0  # degrees/second
        
    # ========== MESSAGE PARSING ==========
    
    def parse_brake_message(self, payload: bytes) -> BrakeState:
        """Parse brake module CAN message (ID: 0x100)"""
        if len(payload) < 8:
            return BrakeState(is_valid=False)
        
        try:
            brake_pressure = payload[0]
            status = payload[1]
            decel_rate = struct.unpack('>H', payload[2:4])[0]
            wheel_speed_fl = struct.unpack('>H', payload[4:6])[0]
            wheel_speed_fr = struct.unpack('>H', payload[6:8])[0]
            
            state = BrakeState(
                pressure_percent=brake_pressure,
                status=status,
                decel_rate=decel_rate / 1000.0,  # Convert to m/s²
                wheel_speed_fl=wheel_speed_fl,
                wheel_speed_fr=wheel_speed_fr,
                is_valid=True
            )
            
            # Validate ranges
            if not (0 <= brake_pressure <= 255):
                state.is_valid = False
            if not (0 <= status <= 2):
                state.is_valid = False
                
            return state
        except Exception as e:
            print(f"Error parsing brake message: {e}")
            return BrakeState(is_valid=False)
    
    def parse_throttle_message(self, payload: bytes) -> ThrottleState:
        """Parse throttle module CAN message (ID: 0x200)"""
        if len(payload) < 8:
            return ThrottleState(is_valid=False)
        
        try:
            throttle_pos = payload[0]
            status = payload[1]
            accel_rate = struct.unpack('>H', payload[2:4])[0]
            engine_rpm = struct.unpack('>H', payload[4:6])[0]
            fuel_level = payload[6]
            
            state = ThrottleState(
                throttle_pos=throttle_pos,
                status=status,
                accel_rate=accel_rate / 1000.0,
                engine_rpm=engine_rpm,
                fuel_level=fuel_level,
                is_valid=True
            )
            
            # Validate ranges
            if not (0 <= throttle_pos <= 255):
                state.is_valid = False
            if not (0 <= fuel_level <= 100):
                state.is_valid = False
                
            return state
        except Exception as e:
            print(f"Error parsing throttle message: {e}")
            return ThrottleState(is_valid=False)
    
    def parse_steering_message(self, payload: bytes) -> SteeringState:
        """Parse steering module CAN message (ID: 0x300)"""
        if len(payload) < 8:
            return SteeringState(is_valid=False)
        
        try:
            # Steering angle as signed 16-bit (two's complement)
            steering_angle_raw = struct.unpack('>h', payload[0:2])[0]
            steering_angle = steering_angle_raw / 256.0  # Convert to degrees
            
            status = payload[2]
            steering_rate = payload[3]
            wheel_angle_fl = struct.unpack('>h', payload[4:6])[0] / 256.0
            wheel_angle_fr = struct.unpack('>h', payload[6:8])[0] / 256.0
            
            state = SteeringState(
                steering_angle=steering_angle,
                status=status,
                steering_rate=steering_rate,
                wheel_angle_fl=wheel_angle_fl,
                wheel_angle_fr=wheel_angle_fr,
                is_valid=True
            )
            
            # Validate ranges
            if not (-40 <= steering_angle <= 40):
                state.is_valid = False
            if not (0 <= status <= 2):
                state.is_valid = False
                
            return state
        except Exception as e:
            print(f"Error parsing steering message: {e}")
            return SteeringState(is_valid=False)
    
    def parse_perception_message(self, payload: bytes) -> PerceptionState:
        """Parse perception module CAN message (ID: 0x400)"""
        if len(payload) < 8:
            return PerceptionState(is_valid=False)
        
        try:
            object_count = payload[0] & 0x0F
            closest_distance = payload[1]
            closest_speed = payload[2]
            threat_level = payload[3] & 0x03
            lane_position = payload[4] & 0x03
            road_condition = payload[5] & 0x03
            weather = payload[6] & 0x0F
            sensor_health = payload[7]
            
            state = PerceptionState(
                object_count=object_count,
                closest_distance=closest_distance,
                closest_speed=closest_speed,
                threat_level=threat_level,
                lane_position=lane_position,
                road_condition=road_condition,
                weather=weather,
                sensor_health=sensor_health,
                is_valid=True
            )
            
            # Validate ranges
            if not (0 <= sensor_health <= 100):
                state.is_valid = False
                
            return state
        except Exception as e:
            print(f"Error parsing perception message: {e}")
            return PerceptionState(is_valid=False)
    
    # ========== THREAT DETECTION ==========
    
    def detect_can_flood(self, can_id: int, current_time: float, 
                        window_seconds: float = 1.0) -> bool:
        """
        Detect CAN message flooding (multiple messages in short time window).
        
        Returns True if flooding detected (>10 messages in 1 second).
        """
        # Clean old timestamps outside window
        cutoff_time = current_time - window_seconds
        self.message_frequency[can_id] = [
            ts for ts in self.message_frequency[can_id] 
            if ts > cutoff_time
        ]
        
        # Add current message
        self.message_frequency[can_id].append(current_time)
        
        # Check threshold
        if len(self.message_frequency[can_id]) > 10:
            return True
        return False
    
    def detect_payload_anomaly(self, can_id: int, payload: bytes) -> Tuple[bool, str]:
        """
        Detect anomalous payload patterns.
        
        Returns (is_anomalous, reason)
        """
        if len(payload) != 8:
            return False, "Invalid payload length"
        
        # Check for all-zero payload (sensor failure)
        if all(b == 0x00 for b in payload):
            return True, "All-zero payload (sensor failure)"
        
        # Check for all-FF payload (diagnostic abuse)
        if all(b == 0xFF for b in payload):
            return True, "All-FF payload (diagnostic flood)"
        
        # Module-specific anomalies
        if can_id == ModuleID.BRAKE.value:
            brake_pressure = payload[0]
            decel_rate = struct.unpack('>H', payload[2:4])[0] / 1000.0
            
            # Impossible: max brake (FF) with zero deceleration
            if brake_pressure == 0xFF and decel_rate == 0:
                return True, "Max brake with zero decel rate (physically impossible)"
            
            # Conflicting pattern: low pressure but high decel
            if brake_pressure < 50 and decel_rate > 5:
                return True, "Low brake pressure with high decel (impossible)"
        
        elif can_id == ModuleID.THROTTLE.value:
            throttle_pos = payload[0]
            accel_rate = struct.unpack('>H', payload[2:4])[0] / 1000.0
            
            # Impossible: zero throttle with positive acceleration
            if throttle_pos == 0 and accel_rate > 1:
                return True, "Zero throttle with positive acceleration"
        
        elif can_id == ModuleID.STEERING.value:
            steering_angle = struct.unpack('>h', payload[0:2])[0] / 256.0
            
            # Extreme steering angles
            if abs(steering_angle) > 40:
                return True, f"Steering angle out of range: {steering_angle}°"
        
        return False, ""
    
    def detect_extreme_values(self, can_id: int, payload: bytes) -> Tuple[bool, str]:
        """
        Detect control values exceeding safe operating thresholds.
        
        Returns (is_extreme, reason)
        """
        if can_id == ModuleID.BRAKE.value:
            brake_pressure = payload[0]
            if brake_pressure > 242:  # >95%
                return True, f"Excessive brake pressure: {brake_pressure}"
        
        elif can_id == ModuleID.THROTTLE.value:
            throttle_pos = payload[0]
            # Sustained max throttle might indicate stuck accelerator
            if throttle_pos > 250:  # >98%
                return True, f"Excessive throttle position: {throttle_pos}"
        
        elif can_id == ModuleID.STEERING.value:
            steering_angle = struct.unpack('>h', payload[0:2])[0] / 256.0
            if abs(steering_angle) > 38:
                return True, f"Extreme steering angle: {steering_angle}°"
        
        return False, ""
    
    def detect_unknown_ecu(self, can_id: int) -> bool:
        """Detect messages from unknown ECU IDs (>0x700)"""
        return can_id > 0x700
    
    def detect_conflicting_commands(self) -> Tuple[bool, str]:
        """
        Detect physically impossible simultaneous commands.
        
        Returns (conflict_detected, conflict_description)
        """
        # Both max brake and max throttle
        if (self.brake_state.pressure_percent > 200 and 
            self.throttle_state.throttle_pos > 200 and
            self.brake_state.is_valid and self.throttle_state.is_valid):
            return True, "Simultaneous max brake and max throttle"
        
        # Hard steering while hard braking
        if (abs(self.steering_state.steering_angle) > 30 and 
            self.brake_state.pressure_percent > 200 and
            self.steering_state.is_valid and self.brake_state.is_valid):
            return True, "Hard steering with hard braking (rollover risk)"
        
        return False, ""
    
    # ========== THREAT SCORING ==========
    
    def calculate_threat_score(self) -> int:
        """
        Calculate overall threat score based on detected anomalies.
        
        Score ranges:
        - 0-20: GREEN (Normal)
        - 21-50: YELLOW (Caution)
        - 51-80: ORANGE (Warning)
        - 81-100: RED (Critical)
        """
        score = 0
        
        # Recent anomalies (decay over time)
        current_time = time.time()
        for ts, anomaly_score, reason in self.threat_history[-10:]:
            time_delta = current_time - ts
            if time_delta < 5:  # Consider anomalies in last 5 seconds
                decay = max(0.5, 1.0 - (time_delta / 10.0))
                score += int(anomaly_score * decay)
        
        # Cap at 100
        return min(100, score)
    
    def update_threat_level(self, score: int) -> SafetyState:
        """Update safety state based on threat score"""
        if score <= 20:
            return SafetyState.NORMAL
        elif score <= 50:
            return SafetyState.CAUTION
        elif score <= 80:
            return SafetyState.WARNING
        else:
            return SafetyState.EMERGENCY
    
    # ========== MESSAGE PROCESSING ==========
    
    def process_can_message(self, msg: CANMessage) -> Dict:
        """
        Process an incoming CAN message and detect threats.
        
        Returns dictionary with threat information.
        """
        self.message_log.append(msg)
        result = {
            'timestamp': msg.timestamp,
            'can_id': msg.can_id,
            'threats_detected': [],
            'threat_score_delta': 0
        }
        
        # Check for unknown ECU
        if self.detect_unknown_ecu(msg.can_id):
            result['threats_detected'].append({
                'class': 6,
                'severity': 30,
                'reason': f'Unknown ECU ID: 0x{msg.can_id:X}'
            })
        
        # Check for flooding
        if self.detect_can_flood(msg.can_id, msg.timestamp):
            result['threats_detected'].append({
                'class': 1,
                'severity': 15,
                'reason': f'CAN message flooding detected on 0x{msg.can_id:X}'
            })
        
        # Check for payload anomalies
        is_anomalous, reason = self.detect_payload_anomaly(msg.can_id, msg.payload)
        if is_anomalous:
            result['threats_detected'].append({
                'class': 2,
                'severity': 20,
                'reason': reason
            })
        
        # Check for extreme values
        is_extreme, reason = self.detect_extreme_values(msg.can_id, msg.payload)
        if is_extreme:
            result['threats_detected'].append({
                'class': 3,
                'severity': 15,
                'reason': reason
            })
        
        # Update module states
        if msg.can_id == ModuleID.BRAKE.value:
            self.brake_state = self.parse_brake_message(msg.payload)
        elif msg.can_id == ModuleID.THROTTLE.value:
            self.throttle_state = self.parse_throttle_message(msg.payload)
        elif msg.can_id == ModuleID.STEERING.value:
            self.steering_state = self.parse_steering_message(msg.payload)
        elif msg.can_id == ModuleID.PERCEPTION.value:
            self.perception_state = self.parse_perception_message(msg.payload)
        
        # Check for multi-module conflicts
        conflict_detected, conflict_reason = self.detect_conflicting_commands()
        if conflict_detected:
            result['threats_detected'].append({
                'class': 7,
                'severity': 30,
                'reason': conflict_reason
            })
        
        # Update threat history
        total_severity = sum(t['severity'] for t in result['threats_detected'])
        if total_severity > 0:
            reason = '; '.join(t['reason'] for t in result['threats_detected'])
            self.threat_history.append((msg.timestamp, total_severity, reason))
            result['threat_score_delta'] = total_severity
        
        # Calculate new threat score
        self.threat_score = self.calculate_threat_score()
        self.safety_state = self.update_threat_level(self.threat_score)
        
        result['current_threat_score'] = self.threat_score
        result['current_safety_state'] = self.safety_state.name
        
        # Log alert if threats detected
        if result['threats_detected']:
            self.alert_log.append(result)
        
        return result
    
    # ========== COMMAND GENERATION ==========
    
    def generate_safety_command(self, maneuver: ManeuverType) -> CANMessage:
        """
        Generate safety controller CAN message (ID: 0x500).
        
        Byte layout:
        0: Safety state (0-5)
        1: Maneuver type (0-5)
        2: Target speed (km/h)
        3: Threat ID
        4: Confidence (0-100%)
        5: Override mode (0-1)
        6-7: Reserved
        """
        safety_state_value = self.safety_state.value
        maneuver_value = maneuver.value
        target_speed = self._get_target_speed_for_maneuver(maneuver)
        threat_id = len(self.threat_history) % 256
        confidence = min(100, self.threat_score)
        override_mode = 1 if maneuver == ManeuverType.FULL_STOP else 0
        
        payload = bytes([
            safety_state_value,
            maneuver_value,
            target_speed,
            threat_id,
            confidence,
            override_mode,
            0x00,
            0x00
        ])
        
        return CANMessage(
            can_id=ModuleID.SAFETY_CONTROLLER.value,
            dlc=8,
            payload=payload,
            timestamp=time.time()
        )
    
    def generate_brake_command(self, target_pressure: int, 
                              target_decel: float) -> CANMessage:
        """Generate brake control command"""
        # Clamp values
        pressure = min(255, max(0, target_pressure))
        decel_ms2 = min(int(target_decel * 1000), 65535)
        
        payload = bytes([
            pressure,
            0x01,  # Status: Engaged
            (decel_ms2 >> 8) & 0xFF,
            decel_ms2 & 0xFF,
            0x00, 0x00, 0x00, 0x00
        ])
        
        return CANMessage(
            can_id=ModuleID.BRAKE.value,
            dlc=8,
            payload=payload,
            timestamp=time.time()
        )
    
    def generate_throttle_command(self, target_position: int) -> CANMessage:
        """Generate throttle control command"""
        position = min(255, max(0, target_position))
        
        payload = bytes([
            position,
            0x01,  # Status: Active
            0x00, 0x00,
            0x00, 0x00, 0x00, 0x00
        ])
        
        return CANMessage(
            can_id=ModuleID.THROTTLE.value,
            dlc=8,
            payload=payload,
            timestamp=time.time()
        )
    
    def generate_steering_command(self, target_angle: float) -> CANMessage:
        """Generate steering control command"""
        # Clamp and convert to fixed-point
        angle = max(-40, min(40, target_angle))
        angle_fixed = int(angle * 256)
        
        payload = bytes([
            (angle_fixed >> 8) & 0xFF,
            angle_fixed & 0xFF,
            0x01,  # Status: Active
            0x00,  # Steering rate
            0x00, 0x00, 0x00, 0x00
        ])
        
        return CANMessage(
            can_id=ModuleID.STEERING.value,
            dlc=8,
            payload=payload,
            timestamp=time.time()
        )
    
    # ========== SAFETY MANEUVERS ==========
    
    def _get_target_speed_for_maneuver(self, maneuver: ManeuverType) -> int:
        """Get target speed (km/h) for a given maneuver"""
        mapping = {
            ManeuverType.NONE: 100,
            ManeuverType.SLOW_DOWN: 50,
            ManeuverType.STOP: 0,
            ManeuverType.PULL_OVER: 15,
            ManeuverType.EVASIVE: 30,
            ManeuverType.FULL_STOP: 0
        }
        return mapping.get(maneuver, 100)
    
    def execute_slow_down(self) -> List[CANMessage]:
        """Execute SLOW DOWN maneuver (30s to reach 50 km/h)"""
        commands = []
        
        # 1. Issue safety state command
        commands.append(self.generate_safety_command(ManeuverType.SLOW_DOWN))
        
        # 2. Remove throttle
        commands.append(self.generate_throttle_command(0))
        
        # 3. Apply gentle braking (20%)
        commands.append(self.generate_brake_command(51, self.max_decel_normal))
        
        self.current_maneuver = ManeuverType.SLOW_DOWN
        return commands
    
    def execute_stop(self) -> List[CANMessage]:
        """Execute STOP maneuver (emergency brake)"""
        commands = []
        
        # 1. Issue safety state command
        commands.append(self.generate_safety_command(ManeuverType.STOP))
        
        # 2. Remove throttle immediately
        commands.append(self.generate_throttle_command(0))
        
        # 3. Apply strong braking (80%)
        commands.append(self.generate_brake_command(204, self.max_decel_stop))
        
        self.current_maneuver = ManeuverType.STOP
        return commands
    
    def execute_pull_over(self) -> List[CANMessage]:
        """Execute PULL OVER maneuver"""
        commands = []
        
        # 1. Issue safety state command
        commands.append(self.generate_safety_command(ManeuverType.PULL_OVER))
        
        # 2. Begin steering to exit lane (left)
        commands.append(self.generate_steering_command(-40))
        
        # 3. Remove throttle
        commands.append(self.generate_throttle_command(0))
        
        # 4. Apply moderate braking (40%)
        commands.append(self.generate_brake_command(102, 4.0))
        
        self.current_maneuver = ManeuverType.PULL_OVER
        return commands
    
    def execute_evasive(self, direction: str = 'left') -> List[CANMessage]:
        """Execute EVASIVE maneuver (collision avoidance)"""
        commands = []
        
        # 1. Issue safety state command
        commands.append(self.generate_safety_command(ManeuverType.EVASIVE))
        
        # 2. Remove throttle
        commands.append(self.generate_throttle_command(0))
        
        # 3. Apply braking (moderate)
        commands.append(self.generate_brake_command(102, 6.0))
        
        # 4. Steer aggressively in evasion direction
        angle = -25 if direction == 'left' else 25
        commands.append(self.generate_steering_command(angle))
        
        self.current_maneuver = ManeuverType.EVASIVE
        return commands
    
    def execute_full_stop(self) -> List[CANMessage]:
        """Execute FULL STOP maneuver (disable vehicle)"""
        commands = []
        
        # 1. Issue safety state command (no override)
        commands.append(self.generate_safety_command(ManeuverType.FULL_STOP))
        
        # 2. Remove all power
        commands.append(self.generate_throttle_command(0))
        
        # 3. Apply maximum braking
        commands.append(self.generate_brake_command(255, self.max_decel_emergency))
        
        # 4. Center steering
        commands.append(self.generate_steering_command(0))
        
        self.current_maneuver = ManeuverType.FULL_STOP
        return commands
    
    # ========== DECISION LOGIC ==========
    
    def decide_safety_action(self) -> Tuple[ManeuverType, List[CANMessage]]:
        """
        Decide which safety maneuver to execute based on threat score.
        
        Returns (maneuver_type, list_of_can_commands)
        """
        score = self.threat_score
        state = self.safety_state
        
        if state == SafetyState.NORMAL:
            return ManeuverType.NONE, []
        
        elif state == SafetyState.CAUTION:
            # Increase monitoring, no action yet
            return ManeuverType.NONE, []
        
        elif state == SafetyState.WARNING:
            # SLOW DOWN maneuver
            if self.current_maneuver != ManeuverType.SLOW_DOWN:
                return ManeuverType.SLOW_DOWN, self.execute_slow_down()
            return self.current_maneuver, []
        
        elif state == SafetyState.EMERGENCY:
            # Check for conflicting commands (critical threat)
            conflict, reason = self.detect_conflicting_commands()
            if conflict:
                return ManeuverType.FULL_STOP, self.execute_full_stop()
            
            # Check for unknown ECU (high risk)
            unknown_ecu = any(t['class'] == 6 for t in 
                             self.alert_log[-10:] if 'class' in t)
            if unknown_ecu:
                return ManeuverType.FULL_STOP, self.execute_full_stop()
            
            # Default emergency: STOP
            return ManeuverType.STOP, self.execute_stop()
        
        return ManeuverType.NONE, []
    
    # ========== REPORTING ==========
    
    def get_status(self) -> Dict:
        """Get current vehicle status"""
        return {
            'vehicle_name': self.vehicle_name,
            'safety_state': self.safety_state.name,
            'threat_score': self.threat_score,
            'current_maneuver': self.current_maneuver.name,
            'brake': {
                'pressure': f"{self.brake_state.pressure_percent}%",
                'status': ['Idle', 'Engaged', 'Fault'][self.brake_state.status],
                'decel': f"{self.brake_state.decel_rate:.2f} m/s²",
                'valid': self.brake_state.is_valid
            },
            'throttle': {
                'position': f"{self.throttle_state.throttle_pos}%",
                'status': ['Idle', 'Active', 'Fault'][self.throttle_state.status],
                'accel': f"{self.throttle_state.accel_rate:.2f} m/s²",
                'valid': self.throttle_state.is_valid
            },
            'steering': {
                'angle': f"{self.steering_state.steering_angle:.1f}°",
                'status': ['Idle', 'Active', 'Fault'][self.steering_state.status],
                'valid': self.steering_state.is_valid
            },
            'perception': {
                'objects': self.perception_state.object_count,
                'closest_distance': f"{self.perception_state.closest_distance}m",
                'threat_level': ['Clear', 'Caution', 'Warning', 'Critical']
                                 [self.perception_state.threat_level],
                'sensor_health': f"{self.perception_state.sensor_health}%",
                'valid': self.perception_state.is_valid
            }
        }
    
    def export_logs(self) -> Dict:
        """Export all logs for analysis"""
        return {
            'vehicle_name': self.vehicle_name,
            'session_duration': time.time() - self.start_time,
            'total_messages': len(self.message_log),
            'total_alerts': len(self.alert_log),
            'final_threat_score': self.threat_score,
            'threat_history': self.threat_history,
            'alerts': self.alert_log
        }
