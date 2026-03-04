#!/usr/bin/env python3
"""
Real-Time CAN Bus IDS Server - Pure Software Simulation

This server:
1. Runs a TCP server that accepts CAN frame connections
2. Automatically generates realistic normal ECU traffic (internal)
3. Accepts attack traffic from external scripts via TCP
4. Classifies each frame using the trained ML model
5. Logs and displays detection results in real-time

NO HARDWARE REQUIRED - Fully software simulated!

Usage:
    Terminal 1: python3 ids_server_live.py
    Terminal 2: python3 attacks/attack_dos.py  (inject attacks)
"""

import socket
import json
import time
import threading
import torch
import torch.nn as nn
import numpy as np
import pickle
import csv
import os
import random
import queue
from datetime import datetime
from collections import deque
from feature_extractor import FeatureExtractor


class SimpleNN(nn.Module):
    """Neural network model for CAN frame classification."""
    def __init__(self, input_size=18, num_classes=5):
        super(SimpleNN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, num_classes)
        )

    def forward(self, x):
        return self.net(x)


class ECUSimulator:
    """
    Simulates realistic ECU (Electronic Control Unit) traffic patterns.
    
    Each ECU sends periodic CAN frames with realistic timing and payloads.
    This creates the baseline "normal" traffic that the IDS learns to recognize.
    """
    
    # ECU Configuration: Simulates real vehicle ECUs
    ECU_CONFIG = [
        {"name": "Engine", "can_id": 0x100, "period_ms": 10, "data_pattern": "engine"},
        {"name": "Transmission", "can_id": 0x200, "period_ms": 20, "data_pattern": "transmission"},
        {"name": "SpeedSensor", "can_id": 0x300, "period_ms": 50, "data_pattern": "speed"},
        {"name": "Dashboard", "can_id": 0x400, "period_ms": 100, "data_pattern": "dashboard"},
        {"name": "BrakeSensor", "can_id": 0x350, "period_ms": 25, "data_pattern": "brake"},
        {"name": "SteeringSensor", "can_id": 0x450, "period_ms": 30, "data_pattern": "steering"},
        {"name": "RPMGauge", "can_id": 0x316, "period_ms": 20, "data_pattern": "rpm"},
        {"name": "GearIndicator", "can_id": 0x43f, "period_ms": 50, "data_pattern": "gear"},
    ]
    
    def __init__(self, frame_queue):
        self.frame_queue = frame_queue
        self.running = False
        self.threads = []
        self.state = {
            "speed": 60,  # km/h
            "rpm": 2500,  # RPM
            "gear": 3,    # Current gear
            "throttle": 30,  # Throttle %
            "brake": 0,   # Brake %
            "steering": 0,  # Steering angle
        }
        
    def generate_payload(self, pattern):
        """Generate realistic payload data based on ECU type."""
        data = [0] * 8
        
        if pattern == "engine":
            rpm_high = (self.state["rpm"] >> 8) & 0xFF
            rpm_low = self.state["rpm"] & 0xFF
            data = [self.state["throttle"], rpm_high, rpm_low, 
                    random.randint(85, 95),
                    random.randint(20, 40),
                    0, 0, random.randint(0, 255)]
                    
        elif pattern == "transmission":
            data = [self.state["gear"], 0, 
                    random.randint(50, 100),
                    0, 0, 0, 0, random.randint(0, 255)]
                    
        elif pattern == "speed":
            speed_high = (self.state["speed"] >> 8) & 0xFF
            speed_low = self.state["speed"] & 0xFF
            data = [speed_high, speed_low, 
                    random.randint(0, 5),
                    0, 0, 0, 0, random.randint(0, 255)]
                    
        elif pattern == "dashboard":
            data = [self.state["gear"], 
                    (self.state["rpm"] >> 8) & 0xFF,
                    self.state["rpm"] & 0xFF,
                    self.state["speed"] & 0xFF,
                    0xFF, random.randint(0, 255), 0, 0]
                    
        elif pattern == "brake":
            data = [self.state["brake"], 0, 
                    random.randint(0, 10),
                    0, 0, 0, 0, random.randint(0, 255)]
                    
        elif pattern == "steering":
            steering_val = self.state["steering"] + 128
            data = [steering_val, 0, 0, 0, 0, 0, 0, random.randint(0, 255)]
            
        elif pattern == "rpm":
            rpm_scaled = min(255, self.state["rpm"] // 20)
            data = [0x05, rpm_scaled, random.randint(0x60, 0x70), 
                    0x09, rpm_scaled, 0x20, 0x00, random.randint(0x70, 0x80)]
                    
        elif pattern == "gear":
            gear_byte = (self.state["gear"] << 4) | 0x00
            data = [gear_byte, 0x40, 0x60, 0xFF, 
                    random.randint(0x70, 0x80), random.randint(0xA0, 0xC0), 
                    0x08, 0x00]
        
        return data
    
    def update_vehicle_state(self):
        """Simulate gradual vehicle state changes for realism."""
        self.state["speed"] = max(0, min(120, self.state["speed"] + random.randint(-2, 2)))
        self.state["rpm"] = max(800, min(6000, self.state["rpm"] + random.randint(-50, 50)))
        
        if self.state["speed"] < 20:
            self.state["gear"] = 1
        elif self.state["speed"] < 40:
            self.state["gear"] = 2
        elif self.state["speed"] < 60:
            self.state["gear"] = 3
        elif self.state["speed"] < 80:
            self.state["gear"] = 4
        else:
            self.state["gear"] = 5
            
        self.state["throttle"] = max(0, min(100, self.state["throttle"] + random.randint(-3, 3)))
        self.state["steering"] = max(-30, min(30, self.state["steering"] + random.randint(-2, 2)))
    
    def ecu_sender(self, ecu_config):
        """Thread function to generate frames for a single ECU."""
        period_sec = ecu_config["period_ms"] / 1000.0
        can_id = ecu_config["can_id"]
        pattern = ecu_config["data_pattern"]
        
        while self.running:
            data = self.generate_payload(pattern)
            frame = {
                'timestamp': time.time(),
                'id': can_id,
                'dlc': 8,
                'data': data,
                'source': 'ecu'
            }
            self.frame_queue.put(frame)
            
            jitter = period_sec * random.uniform(-0.1, 0.1)
            time.sleep(period_sec + jitter)
    
    def state_updater(self):
        """Thread to periodically update vehicle state."""
        while self.running:
            self.update_vehicle_state()
            time.sleep(0.5)
    
    def start(self):
        """Start all ECU simulation threads."""
        self.running = True
        
        state_thread = threading.Thread(target=self.state_updater, daemon=True)
        state_thread.start()
        self.threads.append(state_thread)
        
        for ecu in self.ECU_CONFIG:
            t = threading.Thread(target=self.ecu_sender, args=(ecu,), daemon=True)
            t.start()
            self.threads.append(t)
            print(f"  [✓] ECU '{ecu['name']}' started (ID=0x{ecu['can_id']:03X}, period={ecu['period_ms']}ms)")
    
    def stop(self):
        """Stop all ECU simulation threads."""
        self.running = False
        for t in self.threads:
            t.join(timeout=1.0)


class LiveIDSServer:
    """
    Real-time Intrusion Detection System - Pure Software Simulation.
    
    Features:
    - Automatic normal traffic generation via ECU simulator
    - TCP server to receive attack frames from external scripts
    - Real-time frame classification using trained ML model
    - Attack detection based on traffic patterns
    - Detailed logging and real-time display
    """
    
    def __init__(self, host='localhost', port=9999, model_path='models/best_model.pt'):
        self.host = host
        self.port = port
        self.model_path = model_path
        
        # Frame queue for processing (shared between ECU sim and attack receivers)
        self.frame_queue = queue.Queue()
        
        # ECU simulator
        self.ecu_simulator = None
        
        # Feature extractor (stateful - maintains temporal state)
        self.feature_extractor = FeatureExtractor()
        self.use_stateful_features = True  # Default to stateful
        
        # Load ML model
        self._load_model()
        
        # Attack detection classes and responses
        self.classes = ['normal', 'DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing']
        self.commands = {
            'normal': 'NO_ACTION', 
            'DoS': 'STOP_VEHICLE', 
            'fuzzing': 'SLOW_DOWN', 
            'rpm_spoofing': 'PULL_OVER', 
            'gear_spoofing': 'SLOW_DOWN'
        }
        
        # Detection statistics
        self.stats = {cls: 0 for cls in self.classes}
        self.total_frames = 0
        self.start_time = None
        
        # Server state
        self.running = False
        self.server_socket = None
        
        # Setup logging
        self._setup_logging()
    
    def _load_model(self):
        """Load the trained neural network model."""
        try:
            config_path = 'outputs/model_config.pkl'
            if os.path.exists(config_path):
                model_config = pickle.load(open(config_path, 'rb'))
                input_size = model_config['input_size']
                num_classes = model_config['num_classes']
                # Check if model uses stateful features
                feature_type = model_config.get('feature_type', 'stateless')
                self.use_stateful_features = (feature_type == 'stateful')
            else:
                input_size = 19  # Default to stateful (19 features)
                num_classes = 5
                self.use_stateful_features = True
            
            self.model = SimpleNN(input_size=input_size, num_classes=num_classes)
            self.model.load_state_dict(torch.load(self.model_path, map_location='cpu', weights_only=True))
            self.model.eval()
            
            scaler_path = 'outputs/scaler.pkl'
            if os.path.exists(scaler_path):
                self.scaler = pickle.load(open(scaler_path, 'rb'))
            else:
                self.scaler = None
                print("[Warning] Scaler not found, using raw features")
            
            feature_mode = "stateful (temporal)" if self.use_stateful_features else "stateless"
            print(f"[✓] Model loaded: {self.model_path} ({feature_mode} features)")
        except Exception as e:
            print(f"[Error] Failed to load model: {e}")
            raise
        except Exception as e:
            print(f"[Error] Failed to load model: {e}")
            raise
    
    def _setup_logging(self):
        """Initialize log file."""
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = f'{log_dir}/ids_live_{timestamp}.csv'
        
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'can_id', 'dlc', 'data', 'source', 
                           'prediction', 'confidence', 'command', 'is_attack'])
        
        print(f"[✓] Logging to: {self.log_file}")
    
    def process_frame(self, frame):
        """Process a single CAN frame and classify it."""
        # Extract features (stateful or stateless based on model config)
        if self.use_stateful_features:
            features = self.feature_extractor.update(frame)
        else:
            features = FeatureExtractor.extract_stateless(frame)
        
        # Apply scaler if available
        if self.scaler is not None:
            features_scaled = self.scaler.transform(features.reshape(1, -1))
        else:
            features_scaled = features.reshape(1, -1)
        
        features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
        
        # Classify
        with torch.no_grad():
            outputs = self.model(features_tensor)
            probs = torch.softmax(outputs, dim=1)
            pred_idx = torch.argmax(probs, dim=1).item()
            pred_class = self.classes[pred_idx]
            confidence = probs[0][pred_idx].item()
        
        command = self.commands[pred_class]
        is_attack = pred_class != 'normal'
        
        # Update statistics
        self.stats[pred_class] += 1
        self.total_frames += 1
        
        # Log
        data_hex = ' '.join(f'{b:02X}' for b in frame['data'])
        source = frame.get('source', 'unknown')
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([frame['timestamp'], f"0x{frame['id']:03X}", frame['dlc'], 
                           data_hex, source, pred_class, f"{confidence:.4f}", command, is_attack])
        
        # Display
        self._display_result(frame, pred_class, confidence, command, is_attack)
        
        return pred_class, confidence, command
    
    def _display_result(self, frame, pred_class, confidence, command, is_attack):
        """Display detection result with formatting."""
        data_hex = ' '.join(f'{b:02X}' for b in frame['data'][:8])
        source = frame.get('source', 'unknown')
        
        if is_attack:
            print(f"\n{'='*70}")
            print(f"🚨 ATTACK DETECTED: {pred_class.upper()}")
            print(f"   Source: {source} | ID=0x{frame['id']:03X} | Data={data_hex}")
            print(f"   Confidence: {confidence:.2%}")
            print(f"   Response: {command}")
            print(f"{'='*70}")
        else:
            if self.total_frames % 100 == 0:
                elapsed = time.time() - self.start_time
                fps = self.total_frames / elapsed if elapsed > 0 else 0
                attack_count = sum(v for k, v in self.stats.items() if k != 'normal')
                print(f"\r[IDS] Frames: {self.total_frames} | Rate: {fps:.1f} fps | "
                      f"Attacks: {attack_count}   ", end='', flush=True)
    
    def handle_client(self, client_socket, addr):
        """Handle incoming attack traffic from a client."""
        print(f"\n[+] Attack injector connected from {addr}")
        buffer = ""
        
        try:
            while self.running:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                    
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        frame = json.loads(line.strip())
                        frame['source'] = f'attack:{addr[1]}'
                        self.frame_queue.put(frame)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            print(f"[-] Client {addr} error: {e}")
        finally:
            client_socket.close()
            print(f"[-] Attack injector {addr} disconnected")
    
    def accept_connections(self):
        """Accept incoming TCP connections from attack scripts."""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[Error] Accept failed: {e}")
    
    def process_frames(self):
        """Main processing loop - process frames from queue."""
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.1)
                self.process_frame(frame)
            except queue.Empty:
                continue
    
    def print_stats(self):
        """Print detection statistics."""
        elapsed = time.time() - self.start_time
        print(f"\n\n{'='*60}")
        print("IDS Detection Statistics")
        print(f"{'='*60}")
        print(f"Total frames processed: {self.total_frames}")
        print(f"Runtime: {elapsed:.1f} seconds")
        print(f"Average rate: {self.total_frames/elapsed:.1f} frames/sec" if elapsed > 0 else "N/A")
        print(f"\nDetections by class:")
        for cls, count in self.stats.items():
            pct = (count / self.total_frames * 100) if self.total_frames > 0 else 0
            marker = "⚠️ " if cls != 'normal' and count > 0 else ""
            print(f"  {cls:15s}: {count:6d} ({pct:5.2f}%) {marker}")
        print(f"{'='*60}")
    
    def run(self):
        """Main loop: Start server, ECU simulation, and process frames."""
        print("\n" + "="*60)
        print("   CAN Bus IDS - Pure Software Simulation")
        print("="*60)
        print(f"[✓] No hardware required!")
        
        # Start TCP server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"[✓] Attack receiver listening on {self.host}:{self.port}")
        
        self.running = True
        
        # Start ECU simulator (normal traffic generator)
        print("\n[Starting ECU Simulators...]")
        self.ecu_simulator = ECUSimulator(self.frame_queue)
        self.ecu_simulator.start()
        
        # Start connection acceptor thread
        accept_thread = threading.Thread(target=self.accept_connections, daemon=True)
        accept_thread.start()
        
        print("\n[IDS monitoring started - Press Ctrl+C to stop]\n")
        print("To inject attacks, run in another terminal:")
        print(f"  python3 attacks/attack_dos.py")
        print(f"  python3 attacks/attack_fuzzy.py")
        print(f"  python3 attacks/attack_rpm_spoof.py")
        print(f"  python3 attacks/attack_gear_spoof.py")
        print("-" * 60 + "\n")
        
        self.start_time = time.time()
        
        try:
            self.process_frames()
        except KeyboardInterrupt:
            print("\n\n[Stopping IDS...]")
        finally:
            self.running = False
            if self.ecu_simulator:
                self.ecu_simulator.stop()
            if self.server_socket:
                self.server_socket.close()
            self.print_stats()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='CAN Bus IDS Server (Software Simulation)')
    parser.add_argument('--host', '-H', type=str, default='localhost',
                        help='Host to listen on (default: localhost)')
    parser.add_argument('--port', '-p', type=int, default=9999,
                        help='Port to listen on (default: 9999)')
    parser.add_argument('--model', '-m', type=str, default='models/best_model.pt',
                        help='Path to trained model')
    args = parser.parse_args()
    
    server = LiveIDSServer(host=args.host, port=args.port, model_path=args.model)
    server.run()
