"""
Comprehensive Test Suite for Autonomous Vehicle Safety Controller

Tests all threat detection, decision logic, and safety maneuvers.
"""

import sys
import time
import struct
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, '..')

from vehicle_control import (
    VehicleControlModule, CANMessage, ModuleID, ManeuverType,
    SafetyState
)
from safety_controller import (
    SafetyController, SuricataIDS, ThreatClass
)


class TestRunner:
    """Runs comprehensive test suite"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []
    
    def assert_equal(self, actual, expected, test_name: str):
        """Helper assertion"""
        if actual == expected:
            self.tests_passed += 1
            self.test_results.append((test_name, True, f"✓ {actual} == {expected}"))
            return True
        else:
            self.tests_failed += 1
            self.test_results.append((test_name, False, f"✗ Expected {expected}, got {actual}"))
            return False
    
    def assert_true(self, condition: bool, test_name: str):
        """Helper assertion"""
        if condition:
            self.tests_passed += 1
            self.test_results.append((test_name, True, f"✓ Condition true"))
            return True
        else:
            self.tests_failed += 1
            self.test_results.append((test_name, False, f"✗ Condition false"))
            return False
    
    def assert_in_range(self, value: int, min_val: int, max_val: int, test_name: str):
        """Helper assertion"""
        if min_val <= value <= max_val:
            self.tests_passed += 1
            self.test_results.append((test_name, True, f"✓ {value} in [{min_val}, {max_val}]"))
            return True
        else:
            self.tests_failed += 1
            self.test_results.append((test_name, False, 
                                     f"✗ {value} not in [{min_val}, {max_val}]"))
            return False
    
    def print_results(self):
        """Print test results"""
        print("\n" + "=" * 80)
        print("TEST SUITE RESULTS")
        print("=" * 80)
        
        for test_name, passed, details in self.test_results:
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] {test_name}")
            print(f"       {details}")
        
        print("\n" + "=" * 80)
        print(f"Total: {self.tests_passed} passed, {self.tests_failed} failed")
        print("=" * 80)
        
        return self.tests_failed == 0


# ========== TEST CASES ==========

def test_brake_message_parsing(runner: TestRunner):
    """Test parsing of brake module CAN messages"""
    print("\n[TEST] Brake Message Parsing")
    
    vehicle = VehicleControlModule("TEST_BRAKE")
    
    # Normal brake message: 32% pressure, engaged, 10 m/s² decel
    payload = bytes([0x20, 0x01, 0x0A, 0x00, 0x40, 0x00, 0x40, 0x00])
    state = vehicle.parse_brake_message(payload)
    
    runner.assert_equal(state.pressure_percent, 0x20, "Brake pressure parsing")
    runner.assert_equal(state.status, 0x01, "Brake status parsing")
    runner.assert_equal(int(state.decel_rate * 1000), 0x0A, "Deceleration rate parsing")
    runner.assert_true(state.is_valid, "Valid brake message")


def test_throttle_message_parsing(runner: TestRunner):
    """Test parsing of throttle module CAN messages"""
    print("\n[TEST] Throttle Message Parsing")
    
    vehicle = VehicleControlModule("TEST_THROTTLE")
    
    # Normal throttle message: 50% throttle, active, 5 m/s² accel
    payload = bytes([0x32, 0x01, 0x05, 0x00, 0x18, 0x00, 0x50, 0x00])
    state = vehicle.parse_throttle_message(payload)
    
    runner.assert_equal(state.throttle_pos, 0x32, "Throttle position parsing")
    runner.assert_equal(state.status, 0x01, "Throttle status parsing")
    runner.assert_true(state.is_valid, "Valid throttle message")


def test_steering_message_parsing(runner: TestRunner):
    """Test parsing of steering module CAN messages"""
    print("\n[TEST] Steering Message Parsing")
    
    vehicle = VehicleControlModule("TEST_STEERING")
    
    # Steering message: 15° right steer
    angle = int(15 * 256)
    payload = bytes([
        (angle >> 8) & 0xFF, angle & 0xFF,
        0x01, 0x1E,
        0x00, 0x0F, 0x00, 0x0F
    ])
    state = vehicle.parse_steering_message(payload)
    
    runner.assert_equal(int(state.steering_angle), 15, "Steering angle parsing")
    runner.assert_equal(state.status, 0x01, "Steering status parsing")
    runner.assert_true(state.is_valid, "Valid steering message")


def test_can_flood_detection(runner: TestRunner):
    """Test CAN message flooding detection"""
    print("\n[TEST] CAN Flood Detection")
    
    vehicle = VehicleControlModule("TEST_FLOOD")
    current_time = time.time()
    
    # Send 15 messages in quick succession
    flood_detected = False
    for i in range(15):
        detected = vehicle.detect_can_flood(
            ModuleID.BRAKE.value,
            current_time + i*0.001,  # 1ms apart
            window_seconds=1.0
        )
        if detected:
            flood_detected = True
    
    runner.assert_true(flood_detected, "CAN flood detected after 15 messages")


def test_payload_anomaly_detection_zero(runner: TestRunner):
    """Test anomaly detection: all-zero payload"""
    print("\n[TEST] Anomaly Detection - All-Zero Payload")
    
    vehicle = VehicleControlModule("TEST_ANOMALY_ZERO")
    
    # All-zero payload (sensor failure)
    payload = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    is_anomalous, reason = vehicle.detect_payload_anomaly(ModuleID.BRAKE.value, payload)
    
    runner.assert_true(is_anomalous, "All-zero payload detected as anomalous")
    runner.assert_true("zero payload" in reason.lower(), "Correct anomaly reason")


def test_payload_anomaly_detection_ff(runner: TestRunner):
    """Test anomaly detection: all-FF payload"""
    print("\n[TEST] Anomaly Detection - All-FF Payload")
    
    vehicle = VehicleControlModule("TEST_ANOMALY_FF")
    
    # All-FF payload (diagnostic flood)
    payload = bytes([0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    is_anomalous, reason = vehicle.detect_payload_anomaly(ModuleID.THROTTLE.value, payload)
    
    runner.assert_true(is_anomalous, "All-FF payload detected as anomalous")
    runner.assert_true("diagnostic flood" in reason.lower(), "Correct anomaly reason")


def test_extreme_values_detection(runner: TestRunner):
    """Test detection of extreme control values"""
    print("\n[TEST] Extreme Values Detection")
    
    vehicle = VehicleControlModule("TEST_EXTREME")
    
    # Extreme brake pressure (>95%)
    payload = bytes([0xFF, 0x01, 0x0A, 0x00, 0x40, 0x00, 0x40, 0x00])
    is_extreme, reason = vehicle.detect_extreme_values(ModuleID.BRAKE.value, payload)
    
    runner.assert_true(is_extreme, "Extreme brake pressure detected")
    runner.assert_true("brake pressure" in reason.lower(), "Correct extreme reason")


def test_unknown_ecu_detection(runner: TestRunner):
    """Test detection of unknown ECU IDs"""
    print("\n[TEST] Unknown ECU Detection")
    
    vehicle = VehicleControlModule("TEST_UNKNOWN_ECU")
    
    # Unknown ECU (ID > 0x700)
    is_unknown = vehicle.detect_unknown_ecu(0x750)
    runner.assert_true(is_unknown, "Unknown ECU ID detected")
    
    # Known ECU (ID ≤ 0x700)
    is_known = vehicle.detect_unknown_ecu(0x300)
    runner.assert_true(not is_known, "Known ECU ID correctly identified")


def test_conflicting_commands_detection(runner: TestRunner):
    """Test detection of physically impossible commands"""
    print("\n[TEST] Conflicting Commands Detection")
    
    vehicle = VehicleControlModule("TEST_CONFLICT")
    
    # Simulate impossible: max brake and max throttle
    brake_payload = bytes([0xFF, 0x01, 0x0A, 0x00, 0x40, 0x00, 0x40, 0x00])
    throttle_payload = bytes([0xFF, 0x01, 0x10, 0x00, 0x18, 0x00, 0x50, 0x00])
    
    brake_msg = CANMessage(0x100, 8, brake_payload, time.time())
    throttle_msg = CANMessage(0x200, 8, throttle_payload, time.time() + 0.01)
    
    vehicle.process_can_message(brake_msg)
    vehicle.process_can_message(throttle_msg)
    
    conflict, reason = vehicle.detect_conflicting_commands()
    runner.assert_true(conflict, "Conflicting commands detected")


def test_threat_scoring(runner: TestRunner):
    """Test threat score calculation"""
    print("\n[TEST] Threat Score Calculation")
    
    vehicle = VehicleControlModule("TEST_SCORING")
    
    # Simulate threats
    vehicle.threat_history = [
        (time.time() - 1, 15, "Test threat 1"),
        (time.time() - 0.5, 20, "Test threat 2"),
        (time.time() - 0.1, 25, "Test threat 3")
    ]
    
    score = vehicle.calculate_threat_score()
    runner.assert_in_range(score, 40, 100, "Threat score in expected range")


def test_safety_state_transitions(runner: TestRunner):
    """Test safety state transitions based on threat score"""
    print("\n[TEST] Safety State Transitions")
    
    vehicle = VehicleControlModule("TEST_STATES")
    
    # Test GREEN state (score 0-20)
    vehicle.threat_score = 10
    vehicle.safety_state = vehicle.update_threat_level(vehicle.threat_score)
    runner.assert_equal(vehicle.safety_state, SafetyState.NORMAL, 
                       "Score 10 → NORMAL state")
    
    # Test YELLOW state (score 21-50)
    vehicle.threat_score = 35
    vehicle.safety_state = vehicle.update_threat_level(vehicle.threat_score)
    runner.assert_equal(vehicle.safety_state, SafetyState.CAUTION,
                       "Score 35 → CAUTION state")
    
    # Test ORANGE state (score 51-80)
    vehicle.threat_score = 65
    vehicle.safety_state = vehicle.update_threat_level(vehicle.threat_score)
    runner.assert_equal(vehicle.safety_state, SafetyState.WARNING,
                       "Score 65 → WARNING state")
    
    # Test RED state (score 81-100)
    vehicle.threat_score = 90
    vehicle.safety_state = vehicle.update_threat_level(vehicle.threat_score)
    runner.assert_equal(vehicle.safety_state, SafetyState.EMERGENCY,
                       "Score 90 → EMERGENCY state")


def test_slow_down_maneuver(runner: TestRunner):
    """Test SLOW DOWN safety maneuver"""
    print("\n[TEST] SLOW DOWN Maneuver")
    
    vehicle = VehicleControlModule("TEST_SLOWDOWN")
    
    commands = vehicle.execute_slow_down()
    
    runner.assert_equal(len(commands), 3, "SLOW DOWN generates 3 CAN commands")
    runner.assert_equal(commands[0].can_id, ModuleID.SAFETY_CONTROLLER.value,
                       "First command is safety state")
    runner.assert_equal(commands[1].can_id, ModuleID.THROTTLE.value,
                       "Second command is throttle")
    runner.assert_equal(commands[2].can_id, ModuleID.BRAKE.value,
                       "Third command is brake")
    runner.assert_equal(vehicle.current_maneuver, ManeuverType.SLOW_DOWN,
                       "Current maneuver set to SLOW_DOWN")


def test_stop_maneuver(runner: TestRunner):
    """Test STOP safety maneuver"""
    print("\n[TEST] STOP Maneuver")
    
    vehicle = VehicleControlModule("TEST_STOP")
    
    commands = vehicle.execute_stop()
    
    runner.assert_equal(len(commands), 3, "STOP generates 3 CAN commands")
    # Check brake command (should have high pressure)
    brake_cmd = commands[2]
    runner.assert_true(brake_cmd.payload[0] > 150, "STOP applies strong braking")


def test_full_stop_maneuver(runner: TestRunner):
    """Test FULL STOP safety maneuver"""
    print("\n[TEST] FULL STOP Maneuver")
    
    vehicle = VehicleControlModule("TEST_FULLSTOP")
    
    commands = vehicle.execute_full_stop()
    
    runner.assert_equal(len(commands), 4, "FULL STOP generates 4 CAN commands")
    # Check that all systems disabled
    throttle_cmd = commands[1]
    brake_cmd = commands[2]
    
    runner.assert_equal(throttle_cmd.payload[0], 0, "Throttle disabled (0%)")
    runner.assert_equal(brake_cmd.payload[0], 255, "Brake maxed (100%)")


def test_suricata_rule_mapping(runner: TestRunner):
    """Test Suricata rule ID to threat class mapping"""
    print("\n[TEST] Suricata Rule Mapping")
    
    mapping_tests = [
        (1000001, ThreatClass.CAN_FLOOD),
        (1000002, ThreatClass.ANOMALY_PATTERN),
        (1000003, ThreatClass.DOS_ZERO_PAYLOAD),
        (1000004, ThreatClass.DIAGNOSTIC_FLOOD),
        (1000005, ThreatClass.UNAUTHORIZED_COMMAND),
        (1000006, ThreatClass.OBD_ABUSE),
        (1000007, ThreatClass.UNKNOWN_ECU)
    ]
    
    for rule_id, expected_class in mapping_tests:
        threat_class = SuricataIDS.rule_id_to_threat_class(rule_id)
        runner.assert_equal(threat_class, expected_class,
                           f"Rule {rule_id} → {expected_class.name}")


def test_safety_controller_decision(runner: TestRunner):
    """Test SafetyController maneuver decision logic"""
    print("\n[TEST] Safety Controller Decision Logic")
    
    vehicle = VehicleControlModule("TEST_DECISION")
    safety_controller = SafetyController(vehicle)
    
    # Test decision for high severity threat
    maneuver = safety_controller._decide_maneuver(70, [ThreatClass.CAN_FLOOD])
    runner.assert_equal(maneuver, ManeuverType.STOP,
                       "High severity (70) → STOP maneuver")
    
    # Test decision for unknown ECU (critical)
    maneuver = safety_controller._decide_maneuver(30, [ThreatClass.UNKNOWN_ECU])
    runner.assert_equal(maneuver, ManeuverType.FULL_STOP,
                       "Unknown ECU → FULL_STOP maneuver")
    
    # Test decision for zero payload
    maneuver = safety_controller._decide_maneuver(25, [ThreatClass.DOS_ZERO_PAYLOAD])
    runner.assert_equal(maneuver, ManeuverType.STOP,
                       "Zero payload → STOP maneuver")


def test_ids_alert_processing(runner: TestRunner):
    """Test IDS alert processing through safety controller"""
    print("\n[TEST] IDS Alert Processing")
    
    vehicle = VehicleControlModule("TEST_IDS")
    safety_controller = SafetyController(vehicle)
    
    # Simulate Suricata alert
    alert = {
        'timestamp': '2025-10-16T13:04:21.289475+0530',
        'rule_id': 1000007,  # Unknown ECU
        'signature': 'CAN Unknown ECU ID (>0x700) Detected',
        'src_ip': '192.168.0.5',
        'dest_ip': '192.168.0.7',
        'src_port': 5003,
        'dest_port': 6000,
        'proto': 'UDP'
    }
    
    response = safety_controller.process_ids_alert(alert)
    
    runner.assert_equal(response['threat_class'], 'UNKNOWN_ECU',
                       "Alert classified as UNKNOWN_ECU")
    runner.assert_true(response['maneuver_executed'],
                      "FULL_STOP maneuver executed for unknown ECU")


# ========== MAIN TEST RUNNER ==========

def main():
    """Run all tests"""
    print("=" * 80)
    print("AUTONOMOUS VEHICLE SAFETY CONTROLLER - TEST SUITE")
    print("=" * 80)
    
    runner = TestRunner()
    
    # Run all tests
    test_brake_message_parsing(runner)
    test_throttle_message_parsing(runner)
    test_steering_message_parsing(runner)
    test_can_flood_detection(runner)
    test_payload_anomaly_detection_zero(runner)
    test_payload_anomaly_detection_ff(runner)
    test_extreme_values_detection(runner)
    test_unknown_ecu_detection(runner)
    test_conflicting_commands_detection(runner)
    test_threat_scoring(runner)
    test_safety_state_transitions(runner)
    test_slow_down_maneuver(runner)
    test_stop_maneuver(runner)
    test_full_stop_maneuver(runner)
    test_suricata_rule_mapping(runner)
    test_safety_controller_decision(runner)
    test_ids_alert_processing(runner)
    
    # Print results
    success = runner.print_results()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
