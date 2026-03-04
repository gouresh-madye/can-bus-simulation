#!/usr/bin/env python3
"""
Gear Spoofing Attack Injector - Software Simulation

This script simulates a gear spoofing attack by sending frames on the gear
indicator CAN ID (0x43F) with manipulated gear values. This can cause the
dashboard to display incorrect gear positions.

Attack Characteristics:
- Uses CAN ID 0x43F (gear indicator)
- Sends unrealistic gear transitions (e.g., jumping from 1st to reverse)
- Higher frequency than normal ECU
- Payload pattern mimics real gear messages but with invalid states

NO HARDWARE REQUIRED - Connects to IDS server via TCP!

Usage:
    python3 attack_gear_spoof.py [options]
    
Options:
    --host, -H          IDS server host (default: localhost)
    --port, -p          IDS server port (default: 9999)
    --duration, -d      Attack duration in seconds (default: 10)
    --mode, -m          Attack mode: 'random', 'reverse', 'rapid' (default: random)
"""

import socket
import json
import time
import argparse
import random


class GearSpoofAttacker:
    """
    Gear Spoofing Attack Generator - Software Simulation.
    
    Sends manipulated gear values to confuse vehicle systems.
    """
    
    # CAN ID for gear indicator (from dataset analysis)
    GEAR_CAN_ID = 0x43F
    
    # Gear values (typical automatic transmission)
    GEARS = {
        'P': 0x00,  # Park
        'R': 0x10,  # Reverse
        'N': 0x20,  # Neutral
        'D': 0x30,  # Drive
        '1': 0x01,  # 1st
        '2': 0x02,  # 2nd
        '3': 0x03,  # 3rd
        '4': 0x04,  # 4th
        '5': 0x05,  # 5th
        '6': 0x06,  # 6th
    }
    
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
    
    def generate_gear_payload(self, gear_byte):
        """
        Generate a gear spoofing payload.
        
        Based on dataset analysis: Gear messages have pattern:
        [gear_byte, 0x40/0x45, 0x60, 0xFF, speed_related, timing, 0x08, 0x00]
        """
        # Spoofed payload (mimics real format but with attack values)
        data = [
            gear_byte,      # Gear position
            0x45,           # Modified byte (attack signature)
            0x60,
            0xFF,
            0x6B,           # Attack pattern
            0x00,
            0x00,
            0x00
        ]
        return data
    
    def attack_random(self, duration=10.0, interval_ms=1.0):
        """Random attack: Send random gear values including invalid ones."""
        start_time = time.time()
        possible_values = list(self.GEARS.values()) + [0xFF, 0x7F, 0xF0, 0x0F]
        
        while (time.time() - start_time) < duration:
            gear = random.choice(possible_values)
            data = self.generate_gear_payload(gear)
            self.send_frame(self.GEAR_CAN_ID, data)
            
            if self.frames_sent % 100 == 0:
                self._print_progress(start_time)
            
            time.sleep(interval_ms / 1000.0)
    
    def attack_reverse(self, duration=10.0, interval_ms=1.0):
        """Reverse attack: Constantly send reverse gear signal."""
        start_time = time.time()
        reverse_byte = self.GEARS['R']
        
        while (time.time() - start_time) < duration:
            data = self.generate_gear_payload(reverse_byte)
            self.send_frame(self.GEAR_CAN_ID, data)
            
            if self.frames_sent % 100 == 0:
                self._print_progress(start_time)
            
            time.sleep(interval_ms / 1000.0)
    
    def attack_rapid(self, duration=10.0, interval_ms=1.0):
        """Rapid shift attack: Rapidly alternate between gears."""
        start_time = time.time()
        gear_sequence = [
            self.GEARS['1'],
            self.GEARS['6'],
            self.GEARS['R'],
            self.GEARS['D'],
            self.GEARS['P'],
            self.GEARS['3'],
        ]
        idx = 0
        
        while (time.time() - start_time) < duration:
            gear = gear_sequence[idx % len(gear_sequence)]
            data = self.generate_gear_payload(gear)
            self.send_frame(self.GEAR_CAN_ID, data)
            idx += 1
            
            if self.frames_sent % 100 == 0:
                self._print_progress(start_time)
            
            time.sleep(interval_ms / 1000.0)
    
    def _print_progress(self, start_time):
        """Print attack progress."""
        elapsed = time.time() - start_time
        rate = self.frames_sent / elapsed if elapsed > 0 else 0
        print(f"\r[Gear Spoof] Frames: {self.frames_sent} | Rate: {rate:.0f}/s | "
              f"Elapsed: {elapsed:.1f}s", end='')
    
    def attack(self, duration=10.0, interval_ms=1.0, mode='random'):
        """
        Execute gear spoofing attack.
        
        Args:
            duration: Attack duration in seconds
            interval_ms: Time between frames in milliseconds
            mode: Attack mode ('random', 'reverse', 'rapid')
        """
        print("\n" + "="*50)
        print("    GEAR SPOOFING ATTACK INITIATED")
        print("="*50)
        print(f"  Target: {self.host}:{self.port}")
        print(f"  CAN ID: 0x{self.GEAR_CAN_ID:03X} (gear indicator)")
        print(f"  Attack Mode: {mode}")
        print(f"  Duration: {duration} seconds")
        print(f"  Interval: {interval_ms} ms")
        print("="*50 + "\n")
        
        self.frames_sent = 0
        start_time = time.time()
        
        try:
            if mode == 'random':
                self.attack_random(duration, interval_ms)
            elif mode == 'reverse':
                self.attack_reverse(duration, interval_ms)
            elif mode == 'rapid':
                self.attack_rapid(duration, interval_ms)
            else:
                print(f"[Error] Unknown mode: {mode}")
                return
                
        except KeyboardInterrupt:
            print("\n[Attack interrupted by user]")
        except BrokenPipeError:
            print("\n[Connection lost to IDS server]")
        
        elapsed = time.time() - start_time
        print(f"\n\n[Gear Spoofing Attack Complete]")
        print(f"  Mode: {mode}")
        print(f"  Total frames sent: {self.frames_sent}")
        print(f"  Duration: {elapsed:.2f} seconds")
        print(f"  Average rate: {self.frames_sent/elapsed:.1f} frames/sec" if elapsed > 0 else "N/A")


def main():
    parser = argparse.ArgumentParser(
        description='Gear Spoofing Attack Injector (Software Simulation)',
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
    parser.add_argument('--mode', '-m', type=str, default='random',
                        choices=['random', 'reverse', 'rapid'],
                        help='Attack mode')
    args = parser.parse_args()
    
    attacker = GearSpoofAttacker(host=args.host, port=args.port)
    
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
