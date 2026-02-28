import socket
import json
import torch
import torch.nn as nn
from feature_extractor import FeatureExtractor
import csv
import os
import pickle

class SimpleNN(nn.Module):
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

class IDSServer:
    def __init__(self):
        # Load model config
        model_config = pickle.load(open('outputs/model_config.pkl', 'rb'))
        input_size = model_config['input_size']
        num_classes = model_config['num_classes']
        self.model = SimpleNN(input_size=input_size, num_classes=num_classes)
        self.model.load_state_dict(torch.load('models/best_model.pt'))
        self.model.eval()
        self.scaler = pickle.load(open('outputs/scaler.pkl', 'rb'))
        self.classes = ['normal', 'DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing']
        self.commands = {
            'normal': 'NO_ACTION', 
            'DoS': 'STOP_VEHICLE', 
            'fuzzing': 'SLOW_DOWN', 
            'rpm_spoofing': 'PULL_OVER', 
            'gear_spoofing': 'SLOW_DOWN'
        }
        self.log_file = 'logs/ids_log.csv'
        if not os.path.exists('logs'):
            os.makedirs('logs')
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'id', 'prediction', 'confidence', 'command'])

    def process_frame(self, frame):
        # Use stateless features to match training
        features = FeatureExtractor.extract_stateless(frame)
        # Apply scaler normalization
        features_scaled = self.scaler.transform(features.reshape(1, -1))
        features_tensor = torch.tensor(features_scaled, dtype=torch.float32)
        with torch.no_grad():
            outputs = self.model(features_tensor)
            probs = torch.softmax(outputs, dim=1)
            pred_idx = torch.argmax(probs, dim=1).item()
            pred_class = self.classes[pred_idx]
            confidence = probs[0][pred_idx].item()
            command = self.commands[pred_class]
        # Log
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([frame['timestamp'], frame['id'], pred_class, confidence, command])
        # Print
        print(f"[{frame['timestamp']}] ID={frame['id']:04X} → {pred_class} ({confidence:.2f})")
        print(f"[VEHICLE CONTROL] {command}")
        return command

    def run(self, host='localhost', port=9998):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((host, port))
        server_socket.listen(1)
        print(f"IDS Server listening on {host}:{port}")
        while True:
            client_socket, addr = server_socket.accept()
            print(f"Connection from {addr}")
            buffer = ""
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        frame = json.loads(line.strip())
                        self.process_frame(frame)
                    except json.JSONDecodeError:
                        pass
            client_socket.close()

if __name__ == "__main__":
    server = IDSServer()
    server.run()
