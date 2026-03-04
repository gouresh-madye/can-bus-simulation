#!/usr/bin/env python3
"""
DoS (Denial of Service) Attack Injector - Software Simulation

This script simulates a DoS attack by flooding the IDS with high-frequency
frames using a dominant arbitration ID (0x000). This is the highest priority 
ID on CAN bus and simulates bus saturation.

Attack Characteristics:
- Uses CAN ID 0x000 (highest priority)
- Sends frames at very high frequency (~500μs intervals)
- Payload is all zeros
- Creates simulated bus saturation condition

NO HARDWARE REQUIRED - Connects to IDS server via TCP!

Usage:
    python3 attack_dos.py [options]
    
Options:
    --host, -H          IDS server host (default: localhost)
    --port, -p          IDS server port (default: 9999)
    --duration, -d      Attack duration in seconds (default: 10)
    --interval, -t      Time between frames in ms (default: 0.5)
"""

import socket
import json
import time
import argparse


class DoSAttacker:
    """
    DoS Attack Generator - Software Simulation.
    
    Floods the IDS with high-priority frames to simulate denial of service.
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
    
    def attack(self, duration=10.0, interval_ms=0.5):
        """
        Execute DoS attack.
        
        Args:
            duration: Attack duration in seconds
            interval_ms: Time between frames in milliseconds
        """
        print("\n" + "="*50)
        print("    DoS ATTACK INITIATED")
        print("="*50)
        print(f"  Target: {self.host}:{self.port}")
        print(f"  CAN ID: 0x000 (highest priority)")
        print(f"  Duration: {duration} seconds")
        print(f"  Interval: {interval_ms} ms")
        print("="*50 + "\n")
        
        # DoS attack payload - ID 0x000, all zeros
        dos_data = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        
        interval_sec = interval_ms / 1000.0
        start_time = time.time()
        self.frames_sent = 0
        
        try:
            while (time.time() - start_time) < duration:
                self.send_frame(0x000, dos_data)
                
                if self.frames_sent % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = self.frames_sent / elapsed
                    print(f"\r[DoS] Frames: {self.frames_sent} | Rate: {rate:.0f}/s | "
                          f"Elapsed: {elapsed:.1f}s", end='')
                
                time.sleep(interval_sec)
                
        except KeyboardInterrupt:
            print("\n[Attack interrupted by user]")
        except BrokenPipeError:
            print("\n[Connection lost to IDS server]")
        
        elapsed = time.time() - start_time
        print(f"\n\n[DoS Attack Complete]")
        print(f"  Total frames sent: {self.frames_sent}")
        print(f"  Duration: {elapsed:.2f} seconds")
        print(f"  Average rate: {self.frames_sent/elapsed:.1f} frames/sec" if elapsed > 0 else "N/A")


def main():
    parser = argparse.ArgumentParser(
        description='DoS Attack Injector (Software Simulation)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--host', '-H', type=str, default='localhost',
                        help='IDS server host')
    parser.add_argument('--port', '-p', type=int, default=9999,
                        help='IDS server port')
    parser.add_argument('--duration', '-d', type=float, default=10.0,
                        help='Attack duration in seconds')
    parser.add_argument('--interval', '-t', type=float, default=0.5,
                        help='Interval between frames in milliseconds')
    args = parser.parse_args()
    
    attacker = DoSAttacker(host=args.host, port=args.port)
    
    if attacker.connect():
        try:
            attacker.attack(duration=args.duration, interval_ms=args.interval)
        finally:
            attacker.disconnect()


if __name__ == "__main__":
    main()
