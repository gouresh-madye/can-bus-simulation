#!/usr/bin/env python3
"""
Fuzzy Attack Injector - Software Simulation

This script simulates a fuzzing attack by sending frames with random CAN IDs
and random payload data at irregular intervals. This tests the IDS's ability
to detect anomalous patterns that don't match legitimate ECU behavior.

Attack Characteristics:
- Random CAN IDs (full 11-bit range: 0x000-0x7FF)
- Random 8-byte payloads
- Irregular timing (adds noise)
- High entropy data (unusual byte patterns)

NO HARDWARE REQUIRED - Connects to IDS server via TCP!

Usage:
    python3 attack_fuzzy.py [options]
    
Options:
    --host, -H          IDS server host (default: localhost)
    --port, -p          IDS server port (default: 9999)
    --duration, -d      Attack duration in seconds (default: 10)
    --min-interval      Minimum interval between frames in ms (default: 1)
    --max-interval      Maximum interval between frames in ms (default: 50)
"""

import socket
import json
import time
import argparse
import random


class FuzzyAttacker:
    """
    Fuzzy Attack Generator - Software Simulation.
    
    Sends frames with random IDs and payloads to test IDS detection.
    """
    
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
    
    def generate_fuzzy_frame(self):
        """Generate a frame with random ID and random payload."""
        can_id = random.randint(0x000, 0x7FF)
        data = [random.randint(0, 255) for _ in range(8)]
        return can_id, data
    
    def attack(self, duration=10.0, min_interval_ms=1.0, max_interval_ms=50.0):
        """
        Execute fuzzy attack.
        
        Args:
            duration: Attack duration in seconds
            min_interval_ms: Minimum time between frames in milliseconds
            max_interval_ms: Maximum time between frames in milliseconds
        """
        print("\n" + "="*50)
        print("    FUZZY ATTACK INITIATED")
        print("="*50)
        print(f"  Target: {self.host}:{self.port}")
        print(f"  CAN ID Range: 0x000-0x7FF (random)")
        print(f"  Payload: Random bytes")
        print(f"  Duration: {duration} seconds")
        print(f"  Interval: {min_interval_ms}-{max_interval_ms} ms (random)")
        print("="*50 + "\n")
        
        start_time = time.time()
        self.frames_sent = 0
        unique_ids = set()
        
        try:
            while (time.time() - start_time) < duration:
                can_id, data = self.generate_fuzzy_frame()
                self.send_frame(can_id, data)
                unique_ids.add(can_id)
                
                if self.frames_sent % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = self.frames_sent / elapsed
                    print(f"\r[Fuzzy] Frames: {self.frames_sent} | Unique IDs: {len(unique_ids)} | "
                          f"Rate: {rate:.0f}/s", end='')
                
                interval = random.uniform(min_interval_ms, max_interval_ms) / 1000.0
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n[Attack interrupted by user]")
        except BrokenPipeError:
            print("\n[Connection lost to IDS server]")
        
        elapsed = time.time() - start_time
        print(f"\n\n[Fuzzy Attack Complete]")
        print(f"  Total frames sent: {self.frames_sent}")
        print(f"  Unique CAN IDs used: {len(unique_ids)}")
        print(f"  Duration: {elapsed:.2f} seconds")
        print(f"  Average rate: {self.frames_sent/elapsed:.1f} frames/sec" if elapsed > 0 else "N/A")


def main():
    parser = argparse.ArgumentParser(
        description='Fuzzy Attack Injector (Software Simulation)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--host', '-H', type=str, default='localhost',
                        help='IDS server host')
    parser.add_argument('--port', '-p', type=int, default=9999,
                        help='IDS server port')
    parser.add_argument('--duration', '-d', type=float, default=10.0,
                        help='Attack duration in seconds')
    parser.add_argument('--min-interval', type=float, default=1.0,
                        help='Minimum interval between frames in milliseconds')
    parser.add_argument('--max-interval', type=float, default=50.0,
                        help='Maximum interval between frames in milliseconds')
    args = parser.parse_args()
    
    attacker = FuzzyAttacker(host=args.host, port=args.port)
    
    if attacker.connect():
        try:
            attacker.attack(
                duration=args.duration,
                min_interval_ms=args.min_interval,
                max_interval_ms=args.max_interval
            )
        finally:
            attacker.disconnect()


if __name__ == "__main__":
    main()
