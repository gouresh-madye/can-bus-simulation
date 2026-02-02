"""
Safety Controller - Integrates IDS Alerts with Vehicle Control

This module bridges Suricata IDS threat detection with the vehicle control system,
translating detected attacks into appropriate safety maneuvers.
"""

import json
import time
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime

from vehicle_control import (
    VehicleControlModule, CANMessage, ManeuverType, SafetyState,
    ModuleID
)


class ThreatClass(Enum):
    """Threat classifications from Suricata IDS"""
    CAN_FLOOD = 1                    # Rule 1000001
    ANOMALY_PATTERN = 2              # Rule 1000002
    DOS_ZERO_PAYLOAD = 3             # Rule 1000003
    DIAGNOSTIC_FLOOD = 4             # Rule 1000004
    UNAUTHORIZED_COMMAND = 5         # Rule 1000005
    OBD_ABUSE = 6                    # Rule 1000006
    UNKNOWN_ECU = 7                  # Rule 1000007


class SuricataIDS:
    """Interface to Suricata IDS alert parsing"""
    
    # Map Suricata rule IDs to threat classes
    RULE_ID_MAP = {
        1000001: ThreatClass.CAN_FLOOD,
        1000002: ThreatClass.ANOMALY_PATTERN,
        1000003: ThreatClass.DOS_ZERO_PAYLOAD,
        1000004: ThreatClass.DIAGNOSTIC_FLOOD,
        1000005: ThreatClass.UNAUTHORIZED_COMMAND,
        1000006: ThreatClass.OBD_ABUSE,
        1000007: ThreatClass.UNKNOWN_ECU
    }
    
    @staticmethod
    def parse_eve_log_entry(json_line: str) -> Optional[Dict]:
        """
        Parse a single line from Suricata eve.json
        
        Expected format:
        {"timestamp":"...", "alert":{"signature_id":1000001, ...}, ...}
        """
        try:
            entry = json.loads(json_line)
            if entry.get('event_type') != 'alert':
                return None
            
            return {
                'timestamp': entry.get('timestamp'),
                'rule_id': entry.get('alert', {}).get('signature_id'),
                'signature': entry.get('alert', {}).get('signature'),
                'src_ip': entry.get('src_ip'),
                'dest_ip': entry.get('dest_ip'),
                'src_port': entry.get('src_port'),
                'dest_port': entry.get('dest_port'),
                'proto': entry.get('proto')
            }
        except (json.JSONDecodeError, ValueError):
            return None
    
    @staticmethod
    def rule_id_to_threat_class(rule_id: int) -> Optional[ThreatClass]:
        """Convert Suricata rule ID to threat class"""
        return SuricataIDS.RULE_ID_MAP.get(rule_id)
    
    @staticmethod
    def get_threat_severity(threat_class: ThreatClass) -> int:
        """Get base severity score (0-100) for a threat class"""
        severity_map = {
            ThreatClass.CAN_FLOOD: 15,
            ThreatClass.ANOMALY_PATTERN: 20,
            ThreatClass.DOS_ZERO_PAYLOAD: 25,
            ThreatClass.DIAGNOSTIC_FLOOD: 10,
            ThreatClass.UNAUTHORIZED_COMMAND: 20,
            ThreatClass.OBD_ABUSE: 15,
            ThreatClass.UNKNOWN_ECU: 30
        }
        return severity_map.get(threat_class, 10)


class SafetyController:
    """
    Central safety controller that integrates IDS alerts with vehicle control.
    
    Workflow:
    1. Receive IDS alerts (from Suricata eve.json)
    2. Parse alerts and classify threats
    3. Update threat score
    4. Decide on safety maneuver
    5. Generate CAN commands
    6. Execute maneuver
    """
    
    def __init__(self, vehicle: VehicleControlModule):
        """Initialize safety controller"""
        self.vehicle = vehicle
        self.alert_queue: List[Dict] = []
        self.processed_alerts: List[Dict] = []
        self.last_maneuver_time = 0
        self.maneuver_cooldown_seconds = 2  # Prevent rapid maneuver switching
        
    # ========== ALERT PROCESSING ==========
    
    def process_ids_alert(self, alert_dict: Dict) -> Dict:
        """
        Process a single IDS alert and update threat status.
        
        Args:
            alert_dict: Parsed alert from Suricata
            
        Returns:
            Response dict with actions taken
        """
        response = {
            'timestamp': alert_dict.get('timestamp'),
            'rule_id': alert_dict.get('rule_id'),
            'threat_class': None,
            'threat_severity': 0,
            'action_taken': None,
            'maneuver_executed': False
        }
        
        # Classify threat
        rule_id = alert_dict.get('rule_id')
        threat_class = SuricataIDS.rule_id_to_threat_class(rule_id)
        
        if not threat_class:
            return response
        
        response['threat_class'] = threat_class.name
        response['threat_severity'] = SuricataIDS.get_threat_severity(threat_class)
        
        # Add to queue
        self.alert_queue.append({
            'alert': alert_dict,
            'threat_class': threat_class,
            'severity': response['threat_severity'],
            'processed': False
        })
        
        # Process queue
        response['maneuver_executed'] = self._process_alert_queue()
        
        return response
    
    def _process_alert_queue(self) -> bool:
        """
        Process queued alerts and determine if maneuver needed.
        
        Returns True if maneuver was executed.
        """
        if not self.alert_queue:
            return False
        
        # Check maneuver cooldown
        current_time = time.time()
        if current_time - self.last_maneuver_time < self.maneuver_cooldown_seconds:
            return False
        
        # Aggregate threats
        total_severity = sum(a['severity'] for a in self.alert_queue 
                           if not a['processed'])
        threat_classes = [a['threat_class'] for a in self.alert_queue 
                         if not a['processed']]
        
        # Decide on maneuver
        maneuver = self._decide_maneuver(total_severity, threat_classes)
        
        if maneuver != ManeuverType.NONE:
            commands = self._execute_maneuver(maneuver)
            self.last_maneuver_time = current_time
            
            # Mark alerts as processed
            for alert in self.alert_queue:
                alert['processed'] = True
                self.processed_alerts.append(alert)
            
            self.alert_queue.clear()
            return True
        
        return False
    
    def _decide_maneuver(self, severity: int, 
                        threat_classes: List[ThreatClass]) -> ManeuverType:
        """
        Decide which safety maneuver to execute based on threat analysis.
        
        Decision logic:
        - Severity 25+: Check for critical threats
        - Unknown ECU or conflicting: FULL_STOP
        - Zero payload (sensor failure): STOP
        - Anomaly or unauthorized command: SLOW_DOWN
        """
        # Check for critical threats
        if ThreatClass.UNKNOWN_ECU in threat_classes:
            return ManeuverType.FULL_STOP
        
        if ThreatClass.CAN_FLOOD in threat_classes:
            if severity > 50:
                return ManeuverType.STOP
            return ManeuverType.SLOW_DOWN
        
        if ThreatClass.DOS_ZERO_PAYLOAD in threat_classes:
            return ManeuverType.STOP
        
        if ThreatClass.ANOMALY_PATTERN in threat_classes:
            if severity > 40:
                return ManeuverType.STOP
            return ManeuverType.SLOW_DOWN
        
        if ThreatClass.UNAUTHORIZED_COMMAND in threat_classes:
            return ManeuverType.SLOW_DOWN
        
        if severity >= 50:
            return ManeuverType.STOP
        elif severity >= 30:
            return ManeuverType.SLOW_DOWN
        
        return ManeuverType.NONE
    
    def _execute_maneuver(self, maneuver: ManeuverType) -> List[CANMessage]:
        """Execute the chosen maneuver through vehicle control module"""
        if maneuver == ManeuverType.SLOW_DOWN:
            return self.vehicle.execute_slow_down()
        elif maneuver == ManeuverType.STOP:
            return self.vehicle.execute_stop()
        elif maneuver == ManeuverType.PULL_OVER:
            return self.vehicle.execute_pull_over()
        elif maneuver == ManeuverType.EVASIVE:
            return self.vehicle.execute_evasive()
        elif maneuver == ManeuverType.FULL_STOP:
            return self.vehicle.execute_full_stop()
        
        return []
    
    # ========== BATCH PROCESSING ==========
    
    def process_eve_log_file(self, file_path: str, max_entries: int = None) -> Dict:
        """
        Process eve.json log file from Suricata.
        
        Args:
            file_path: Path to eve.json
            max_entries: Maximum number of entries to process (for testing)
            
        Returns:
            Summary of processing results
        """
        summary = {
            'file': file_path,
            'total_entries_read': 0,
            'total_alerts_parsed': 0,
            'threat_classes_detected': {},
            'maneuvers_executed': {},
            'final_vehicle_status': {}
        }
        
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if max_entries and line_num > max_entries:
                        break
                    
                    summary['total_entries_read'] += 1
                    
                    # Parse alert
                    alert = SuricataIDS.parse_eve_log_entry(line)
                    if not alert:
                        continue
                    
                    summary['total_alerts_parsed'] += 1
                    
                    # Process alert
                    response = self.process_ids_alert(alert)
                    
                    # Track threat classes
                    threat_class = response.get('threat_class')
                    if threat_class:
                        summary['threat_classes_detected'][threat_class] = \
                            summary['threat_classes_detected'].get(threat_class, 0) + 1
                    
                    # Track maneuvers
                    if response.get('maneuver_executed'):
                        current_maneuver = self.vehicle.current_maneuver.name
                        summary['maneuvers_executed'][current_maneuver] = \
                            summary['maneuvers_executed'].get(current_maneuver, 0) + 1
        
        except FileNotFoundError:
            print(f"Error: File not found: {file_path}")
            return summary
        
        # Final status
        summary['final_vehicle_status'] = self.vehicle.get_status()
        
        return summary
    
    # ========== REPORTING ==========
    
    def get_threat_analysis(self) -> Dict:
        """Get comprehensive threat analysis"""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_alerts_received': len(self.processed_alerts) + len(self.alert_queue),
            'alerts_processed': len(self.processed_alerts),
            'alerts_pending': len(self.alert_queue),
            'threat_classes_encountered': [
                a['threat_class'].name for a in self.processed_alerts
            ],
            'vehicle_status': self.vehicle.get_status(),
            'logs': self.vehicle.export_logs()
        }
    
    def generate_incident_report(self) -> str:
        """Generate a human-readable incident report"""
        report = []
        report.append("=" * 80)
        report.append("AUTONOMOUS VEHICLE SAFETY INCIDENT REPORT")
        report.append("=" * 80)
        report.append(f"Vehicle: {self.vehicle.vehicle_name}")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")
        
        # Summary
        analysis = self.get_threat_analysis()
        report.append("INCIDENT SUMMARY")
        report.append("-" * 80)
        report.append(f"Total Threats Detected: {analysis['total_alerts_received']}")
        report.append(f"Final Vehicle Status: {analysis['vehicle_status']['safety_state']}")
        report.append(f"Final Threat Score: {analysis['vehicle_status']['threat_score']}")
        report.append("")
        
        # Threat Classes
        if analysis['threat_classes_encountered']:
            report.append("THREAT CLASSES DETECTED")
            report.append("-" * 80)
            threat_counts = {}
            for threat in analysis['threat_classes_encountered']:
                threat_counts[threat] = threat_counts.get(threat, 0) + 1
            
            for threat, count in sorted(threat_counts.items()):
                report.append(f"  {threat}: {count} occurrences")
            report.append("")
        
        # Vehicle Status at End
        report.append("VEHICLE STATUS AT END OF INCIDENT")
        report.append("-" * 80)
        status = analysis['vehicle_status']
        report.append(f"  Safety State: {status['safety_state']}")
        report.append(f"  Current Maneuver: {status['current_maneuver']}")
        report.append(f"  Threat Score: {status['threat_score']}/100")
        report.append("")
        report.append("  Subsystem Status:")
        report.append(f"    Brake: {status['brake']['pressure']} pressure, {status['brake']['status']}")
        report.append(f"    Throttle: {status['throttle']['position']} position, {status['throttle']['status']}")
        report.append(f"    Steering: {status['steering']['angle']} angle, {status['steering']['status']}")
        report.append(f"    Perception: {status['perception']['objects']} objects, " +
                     f"{status['perception']['threat_level']} threat")
        report.append("")
        
        # Logs
        logs = analysis['logs']
        report.append("SESSION STATISTICS")
        report.append("-" * 80)
        report.append(f"  Session Duration: {logs['session_duration']:.2f} seconds")
        report.append(f"  Total CAN Messages Processed: {logs['total_messages']}")
        report.append(f"  Total Security Alerts: {logs['total_alerts']}")
        report.append("")
        
        report.append("=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)
        
        return "\n".join(report)


# ========== EXAMPLE USAGE ==========

def main():
    """
    Example usage: Process Suricata eve.json and execute safety maneuvers
    """
    print("Initializing Autonomous Vehicle Safety Controller...")
    
    # Create vehicle control module
    vehicle = VehicleControlModule(vehicle_name="AV_Tesla_001")
    
    # Create safety controller
    safety_controller = SafetyController(vehicle)
    
    print("\nProcessing Suricata IDS alerts from eve.json...")
    
    # Process log file
    results = safety_controller.process_eve_log_file(
        '../suricata_logs/eve.json',
        max_entries=50  # Process first 50 alerts for demo
    )
    
    # Print summary
    print("\n" + "=" * 80)
    print("PROCESSING SUMMARY")
    print("=" * 80)
    print(f"Total entries read: {results['total_entries_read']}")
    print(f"Total alerts parsed: {results['total_alerts_parsed']}")
    print(f"\nThreat classes detected:")
    for threat_class, count in results['threat_classes_detected'].items():
        print(f"  {threat_class}: {count}")
    print(f"\nManeuvers executed:")
    for maneuver, count in results['maneuvers_executed'].items():
        print(f"  {maneuver}: {count}")
    
    # Print incident report
    print("\n" + safety_controller.generate_incident_report())


if __name__ == "__main__":
    main()
