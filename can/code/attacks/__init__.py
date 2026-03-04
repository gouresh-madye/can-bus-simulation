"""
CAN Bus Attack Injection Modules (Software Simulation)

This package contains attack generators for testing the CAN Bus IDS:

- attack_dos.py      : DoS (Denial of Service) attack
- attack_fuzzy.py    : Fuzzing attack with random data
- attack_rpm_spoof.py: RPM value spoofing
- attack_gear_spoof.py: Gear indicator spoofing

Each attack script connects to the IDS server via TCP and sends
simulated malicious CAN frames. NO HARDWARE REQUIRED!
"""

__all__ = [
    'attack_dos',
    'attack_fuzzy', 
    'attack_rpm_spoof',
    'attack_gear_spoof'
]
