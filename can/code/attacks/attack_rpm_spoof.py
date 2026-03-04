#!/usr/bin/env python3
"""
RPM Spoofing Attack Injector - Software Simulation

This script simulates an RPM spoofing attack by sending frames on the RPM
CAN ID (0x316) with abnormal/manipulated RPM values. This can cause the
dashboard to display incorrect engine speeds.

Attack Characteristics:
- Uses CAN ID 0x316 (RPM gauge)
- Sends unrealistic RPM values (sudden jumps, impossible speeds)
- Higher frequency than normal ECU (flooding specific ID)
- Payload pattern mimics real RPM messages but with bad values

NO HARDWARE REQUIRED - Connects to IDS server via TCP!

Usage:
    python3 attack_rpm_spoof.py [options]
    
Options:
    --host, -H          IDS server host (default: localhost)
    --port, -p          IDS server port (default: 9999)
    --duration, -d      Attack duration in seconds (default: 10)
    --mode, -m          Attack mode: 'spike', 'redline', 'oscillate' (default: spike)
"""

import socket
import json
import time
import argparse
import random
import math


class RPMSpoofAttacker:
    """
    RPM Spoofing Attack Generator - Software Simulation.
    
    Sends manipulated RPM values to confuse vehicle systems.
    """
    
    # CAN ID for RPM gauge (from dataset analysis)
    RPM_CAN_ID = 0x316
    
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.sock = None
        self.frames_sent = 0
        
    def connect(self):
        """Connect to IDS server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            print(f"[✓] Connected to IDS server at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[Error] Failed to connect: {e}")
            print(f"[Hint] Make sure the IDS server is running:")
            print(f"       python3 ids_server_live.py")
            return False
    
    def disconnect(self):
        """Disconnect from IDS server."""
        if self.sock:
            self.sock.close()
    
    def send_frame(self, can_id, data):
        """Send a simulated CAN frame to the IDS."""
        frame = {
            'timestamp': time.time(),
            'id': can_id,
            'dlc': len(data),
            'data': data
        }
        message = json.dumps(frame) + '\n'
        self.sock.sendall(message.encode('utf-8'))
        self.frames_sent += 1
    
    def generate_rpm_payload(self, rpm_value):
        """
        Generate an RPM spoofing payload.
        
        Based on dataset analysis: RPM messages have pattern:
        [0x05/0x45, rpm_scaled, 0x68, 0x09, rpm_scaled, 0x20/0x24, 0x00, checksum]
        """
        rpm_scaled = min(255, max(0, rpm_value // 20))
        
        # Spoofed payload (mimics real format but with attack values)
        data = [
            0x45,           # Modified header byte (attack signature)
            rpm_scaled,     # RPM high byte
            0x24,           # Attack pattern
            0xFF,           # Modified byte
            rpm_scaled,     # RPM repeated
            0x24,           # Attack pattern
            0x00,
            0xFF            # Invalid checksum
        ]
        return data
    
    def attack_spike(self, duration=10.0, interval_ms=1.0):
        """Spike attack: Send sudden extreme RPM changes."""
        start_time = time.time()
        
        while (time.time() - start_time) < duration:
            rpm = random.choice([0, 500, 8000, 9000, 10000, 12000])
            data = self.generate_rpm_payload(rpm)
            self.send_frame(self.RPM_CAN_ID, data)
            
            if self.frames_sent % 100 == 0:
                self._print_progress(start_time)
            
            time.sleep(interval_ms / 1000.0)
    
    def attack_redline(self, duration=10.0, interval_ms=1.0):
        """Redline attack: Constantly report dangerous high RPM."""
        start_time = time.time()
        
        while (time.time() - start_time) < duration:
            rpm = random.randint(8000, 12000)
            data = self.generate_rpm_payload(rpm)
            self.send_frame(self.RPM_CAN_ID, data)
            
            if self.frames_sent % 100 == 0:
                self._print_progress(start_time)
            
            time.sleep(interval_ms / 1000.0)
    
    def attack_oscillate(self, duration=10.0, interval_ms=1.0):
        """Oscillate attack: Rapidly changing RPM values."""
        start_time = time.time()
        phase = 0
        
        while (time.time() - start_time) < duration:
            base_rpm = 4000 + 3000 * math.sin(phase)
            rpm = int(base_rpm + random.randint(-1000, 1000))
            rpm = max(0, min(12000, rpm))
            
            data = self.generate_rpm_payload(rpm)
            self.send_frame(self.RPM_CAN_ID, data)
            phase += 0.5
            
            if self.frames_sent % 100 == 0:
                self._print_progress(start_time)
            
            time.sleep(interval_ms / 1000.0)
    
    def _print_progress(self, start_time):
        """Print attack progress."""
        elapsed = time.time() - start_time
        rate = self.frames_sent / elapsed if elapsed > 0 else 0
        print(f"\r[RPM Spoof] Frames: {self.frames_sent} | Rate: {rate:.0f}/s | "
              f"Elapsed: {elapsed:.1f}s", end='')
    
    def attack(self, duration=10.0, interval_ms=1.0, mode='spike'):
        """
        Execute RPM spoofing attack.
        
        Args:
            duration: Attack duration in seconds
            interval_ms: Time between frames in milliseconds
            mode: Attack mode ('spike', 'redline', 'oscillate')
        """
        print("\n" + "="*50)
        print("    RPM SPOOFING ATTACK INITIATED")
        print("="*50)
        print(f"  Target: {self.host}:{self.port}")
        print(f"  CAN ID: 0x{self.RPM_CAN_ID:03X} (RPM gauge)")
        print(f"  Attack Mode: {mode}")
        print(f"  Duration: {duration} seconds")
        print(f"  Interval: {interval_ms} ms")
        print("="*50 + "\n")
        
        self.frames_sent = 0
        start_time = time.time()
        
        try:
            if mode == 'spike':
                self.attack_spike(duration, interval_ms)
            elif mode == 'redline':
                self.attack_redline(duration, interval_ms)
            elif mode == 'oscillate':
                self.attack_oscillate(duration, interval_ms)
            else:
                print(f"[Error] Unknown mode: {mode}")
                return
                
        except KeyboardInterrupt:
            print("\n[Attack interrupted by user]")
        except BrokenPipeError:
            print("\n[Connection lost to IDS server]")
        
        elapsed = time.time() - start_time
        print(f"\n\n[RPM Spoofing Attack Complete]")
        print(f"  Mode: {mode}")
        print(f"  Total frames sent: {self.frames_sent}")
        print(f"  Duration: {elapsed:.2f} seconds")
        print(f"  Average rate: {self.frames_sent/elapsed:.1f} frames/sec" if elapsed > 0 else "N/A")


def main():
    parser = argparse.ArgumentParser(
        description='RPM Spoofing Attack Injector (Software Simulation)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--host', '-H', type=str, default='localhost',
                        help='IDS server host')
    parser.add_argument('--port', '-p', type=int, default=9999,
                        help='IDS server port')
    parser.add_argument('--duration', '-d', type=float, default=10.0,
                        help='Attack duration in seconds')
    parser.add_argument('--interval', '-t', type=float, default=1.0,
                        help='Interval between frames in milliseconds')
    parser.add_argument('--mode', '-m', type=str, default='spike',
                        choices=['spike', 'redline', 'oscillate'],
                        help='Attack mode')
    args = parser.parse_args()
    
    attacker = RPMSpoofAttacker(host=args.host, port=args.port)
    
    if attacker.connect():
        try:
            attacker.attack(
                duration=args.duration,
                interval_ms=args.interval,
                mode=args.mode
            )
        finally:
            attacker.disconnect()


if __name__ == "__main__":
    main()
