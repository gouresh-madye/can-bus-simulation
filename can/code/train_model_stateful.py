#!/usr/bin/env python3
"""
Stateful Model Training for Live CAN Bus IDS Simulation

This training script uses STATEFUL temporal features as specified in INSTRUCTIONS.md:
- delta_t_id: Time since last frame with same ID
- delta_t_global: Time since last frame globally
- count_id_window: Count of same ID in 200ms window
- ratio_id_total: Ratio of this ID to total frames
- ema[id]: Exponential moving average of delta_t_id
- var[id]: Moving variance of delta_t_id

The model learns temporal patterns that distinguish normal ECU behavior from attacks.

Usage:
    python3 train_model_stateful.py
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import pickle
import random
import os
import time
from feature_extractor import FeatureExtractor


class SimpleNN(nn.Module):
    """Neural network model for CAN frame classification."""
    def __init__(self, input_size=19, num_classes=5):
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


# ECU Configuration (matches ids_server_live.py)
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


def generate_ecu_payload(pattern, state=None):
    """Generate realistic payload data based on ECU type."""
    if state is None:
        state = {"speed": 60, "rpm": 2500, "gear": 3, "throttle": 30}
    
    data = [0] * 8
    
    if pattern == "engine":
        rpm = state["rpm"] + random.randint(-100, 100)
        rpm = max(800, min(6000, rpm))
        rpm_high = (rpm >> 8) & 0xFF
        rpm_low = rpm & 0xFF
        data = [state["throttle"], rpm_high, rpm_low, 
                random.randint(85, 95), random.randint(20, 40),
                0, 0, random.randint(0, 255)]
                
    elif pattern == "transmission":
        data = [state["gear"], random.randint(30, 100), random.randint(20, 80),
                0, random.randint(0, 255), 0, 0, random.randint(0, 255)]
                
    elif pattern == "speed":
        speed = state["speed"] + random.randint(-5, 5)
        speed = max(0, min(180, speed))
        data = [speed, (speed * 3) & 0xFF, random.randint(0, 100),
                0, 0, 0, random.randint(0, 255), random.randint(0, 255)]
                
    elif pattern == "dashboard":
        data = [random.randint(0, 1), random.randint(0, 1), random.randint(0, 1),
                random.randint(0, 255), 0, 0, 0, 0]
                
    elif pattern == "brake":
        brake = random.randint(0, 30)
        data = [brake, (brake * 2) & 0xFF, random.randint(0, 20),
                0, 0, 0, 0, random.randint(0, 255)]
                
    elif pattern == "steering":
        angle = random.randint(80, 100)  # Near center
        data = [angle >> 8, angle & 0xFF, random.randint(0, 50),
                0, 0, 0, 0, random.randint(0, 255)]
                
    elif pattern == "rpm":
        rpm = state["rpm"] + random.randint(-50, 50)
        rpm = max(800, min(6000, rpm))
        data = [5, (rpm >> 8) & 0xFF, rpm & 0xFF, 
                random.randint(0, 100), (rpm >> 8) & 0xFF, (rpm >> 8) & 0xFF, 
                0, random.randint(0, 255)]
                
    elif pattern == "gear":
        data = [0, state["gear"] * 0x10, 0x60, 0xFF,
                random.randint(100, 200), random.randint(100, 200),
                0x08, 0]
    
    return data


def generate_normal_traffic_sequence(duration_sec=10.0):
    """
    Generate a realistic sequence of normal ECU frames with proper timing.
    Returns list of (frame, label) tuples in temporal order.
    """
    frames = []
    current_time = 0.0
    ecu_next_time = {ecu["can_id"]: 0.0 for ecu in ECU_CONFIG}
    state = {"speed": 60, "rpm": 2500, "gear": 3, "throttle": 30, "brake": 0}
    
    while current_time < duration_sec:
        # Find next ECU to fire
        next_ecu = min(ECU_CONFIG, key=lambda e: ecu_next_time[e["can_id"]])
        next_time = ecu_next_time[next_ecu["can_id"]]
        
        if next_time > duration_sec:
            break
            
        current_time = next_time
        
        # Add small jitter (±10% of period)
        jitter = next_ecu["period_ms"] * random.uniform(-0.1, 0.1) / 1000.0
        
        frame = {
            "timestamp": current_time,
            "id": next_ecu["can_id"],
            "dlc": 8,
            "data": generate_ecu_payload(next_ecu["data_pattern"], state)
        }
        frames.append((frame, "normal"))
        
        # Schedule next frame for this ECU
        ecu_next_time[next_ecu["can_id"]] = current_time + (next_ecu["period_ms"] / 1000.0) + jitter
        
        # Slowly evolve state
        if random.random() < 0.01:
            state["rpm"] = max(800, min(6000, state["rpm"] + random.randint(-200, 200)))
            state["speed"] = max(0, min(180, state["speed"] + random.randint(-10, 10)))
    
    return frames


def generate_dos_attack_sequence(duration_sec=2.0, start_time=0.0, interval_ms=0.5):
    """
    Generate DoS attack frames: ID 0x000 at very high frequency.
    """
    frames = []
    current_time = start_time
    
    while current_time < start_time + duration_sec:
        frame = {
            "timestamp": current_time,
            "id": 0x000,
            "dlc": 8,
            "data": [0, 0, 0, 0, 0, 0, 0, 0]
        }
        frames.append((frame, "DoS"))
        current_time += interval_ms / 1000.0
    
    return frames


def generate_fuzzy_attack_sequence(duration_sec=2.0, start_time=0.0):
    """
    Generate fuzzy attack frames: random IDs and random payloads.
    """
    frames = []
    current_time = start_time
    
    while current_time < start_time + duration_sec:
        frame = {
            "timestamp": current_time,
            "id": random.randint(0x000, 0x7FF),
            "dlc": 8,
            "data": [random.randint(0, 255) for _ in range(8)]
        }
        frames.append((frame, "fuzzing"))
        current_time += random.uniform(0.001, 0.05)  # Random intervals
    
    return frames


def generate_rpm_spoof_sequence(duration_sec=2.0, start_time=0.0, mode="spike"):
    """
    Generate RPM spoofing attack frames: malicious values on ID 0x316.
    """
    frames = []
    current_time = start_time
    
    while current_time < start_time + duration_sec:
        if mode == "spike":
            rpm = random.choice([0, 9000, 10000, 12000])
        elif mode == "redline":
            rpm = random.randint(8000, 12000)
        else:  # oscillate
            rpm = random.randint(0, 12000)
        
        frame = {
            "timestamp": current_time,
            "id": 0x316,
            "dlc": 8,
            "data": [random.randint(0, 255), (rpm >> 8) & 0xFF, rpm & 0xFF,
                    random.randint(0, 255), random.randint(0, 255),
                    random.randint(0, 255), 0, random.randint(0, 255)]
        }
        frames.append((frame, "rpm_spoofing"))
        current_time += 0.005  # Every 5ms (faster than normal 20ms)
    
    return frames


def generate_gear_spoof_sequence(duration_sec=2.0, start_time=0.0, mode="random"):
    """
    Generate gear spoofing attack frames: invalid values on ID 0x43F.
    """
    frames = []
    current_time = start_time
    
    while current_time < start_time + duration_sec:
        if mode == "random":
            gear = random.randint(0, 15)  # Invalid gear values
        elif mode == "reverse":
            gear = 0xFF
        else:  # rapid
            gear = random.choice([0, 1, 5, 6, 7, 8, 9, 10])
        
        frame = {
            "timestamp": current_time,
            "id": 0x43F,
            "dlc": 8,
            "data": [random.randint(0, 255), gear, random.randint(0, 255),
                    random.randint(0, 255), random.randint(0, 255),
                    random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]
        }
        frames.append((frame, "gear_spoofing"))
        current_time += 0.010  # Every 10ms (faster than normal 50ms)
    
    return frames


def generate_mixed_traffic_with_attack(attack_type, normal_duration=5.0, attack_duration=2.0):
    """
    Generate a realistic traffic sequence with normal traffic and an embedded attack.
    Returns frames sorted by timestamp.
    """
    # Generate normal traffic for the entire duration
    normal_frames = generate_normal_traffic_sequence(normal_duration + attack_duration)
    
    # Insert attack at a random point
    attack_start = random.uniform(1.0, normal_duration)
    
    if attack_type == "DoS":
        attack_frames = generate_dos_attack_sequence(attack_duration, attack_start)
    elif attack_type == "fuzzing":
        attack_frames = generate_fuzzy_attack_sequence(attack_duration, attack_start)
    elif attack_type == "rpm_spoofing":
        attack_frames = generate_rpm_spoof_sequence(attack_duration, attack_start, 
                                                    random.choice(["spike", "redline", "oscillate"]))
    elif attack_type == "gear_spoofing":
        attack_frames = generate_gear_spoof_sequence(attack_duration, attack_start,
                                                     random.choice(["random", "reverse", "rapid"]))
    else:
        attack_frames = []
    
    # Combine and sort by timestamp
    all_frames = normal_frames + attack_frames
    all_frames.sort(key=lambda x: x[0]["timestamp"])
    
    return all_frames


def extract_stateful_features(frames_with_labels):
    """
    Extract stateful features from a sequence of frames.
    The FeatureExtractor maintains state across frames.
    """
    extractor = FeatureExtractor()
    features = []
    labels = []
    
    for frame, label in frames_with_labels:
        feat = extractor.update(frame)
        features.append(feat)
        labels.append(label)
    
    return features, labels


def train_stateful_model():
    """Train model with stateful temporal features."""
    
    print("=" * 60)
    print("Stateful CAN Bus IDS Model Training")
    print("(Using temporal features from INSTRUCTIONS.md)")
    print("=" * 60)
    
    # Label mapping
    label_map = {'normal': 0, 'DoS': 1, 'fuzzing': 2, 'rpm_spoofing': 3, 'gear_spoofing': 4}
    
    all_features = []
    all_labels = []
    
    # Generate multiple training sequences
    print("\n[1/4] Generating training sequences...")
    
    # Pure normal traffic sequences
    print("      Generating normal traffic sequences...")
    for i in range(50):
        frames = generate_normal_traffic_sequence(duration_sec=10.0)
        feats, labs = extract_stateful_features(frames)
        all_features.extend(feats)
        all_labels.extend([label_map[l] for l in labs])
        if (i + 1) % 10 == 0:
            print(f"        Normal sequences: {i+1}/50")
    
    # Mixed traffic with each attack type
    print("      Generating attack traffic sequences...")
    attack_types = ["DoS", "fuzzing", "rpm_spoofing", "gear_spoofing"]
    
    for attack_type in attack_types:
        print(f"        Generating {attack_type} sequences...")
        for i in range(25):
            frames = generate_mixed_traffic_with_attack(attack_type, 
                                                        normal_duration=5.0, 
                                                        attack_duration=3.0)
            feats, labs = extract_stateful_features(frames)
            all_features.extend(feats)
            all_labels.extend([label_map[l] for l in labs])
    
    # Convert to numpy arrays
    print("\n[2/4] Processing features...")
    X = np.array(all_features)
    y = np.array(all_labels)
    
    print(f"      Total samples: {len(X)}")
    print(f"      Feature dimensions: {X.shape[1]}")
    
    # Class distribution
    print("\n      Class distribution:")
    for label_name, label_idx in label_map.items():
        count = np.sum(y == label_idx)
        print(f"        {label_name}: {count} samples")
    
    # Save features
    os.makedirs('outputs', exist_ok=True)
    np.save('outputs/X_stateful.npy', X)
    np.save('outputs/y_stateful.npy', y)
    
    # Split data
    print("\n[3/4] Training model...")
    input_size = X.shape[1]
    num_classes = len(label_map)
    
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Normalize features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    
    pickle.dump(scaler, open('outputs/scaler.pkl', 'wb'))
    
    # Convert to tensors
    X_train_t = torch.tensor(X_train, dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    X_val_t = torch.tensor(X_val, dtype=torch.float32)
    y_val_t = torch.tensor(y_val, dtype=torch.long)
    
    # Class weights for balanced training
    from collections import Counter
    class_counts = Counter(y_train)
    total = len(y_train)
    class_weights = {cls: total / count for cls, count in class_counts.items()}
    weights = torch.tensor([class_weights.get(i, 1.0) for i in range(num_classes)], dtype=torch.float32)
    
    # Dataloaders
    train_ds = TensorDataset(X_train_t, y_train_t)
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    val_ds = TensorDataset(X_val_t, y_val_t)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
    
    # Model setup
    model = SimpleNN(input_size=input_size, num_classes=num_classes)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Save model config
    pickle.dump({'input_size': input_size, 'num_classes': num_classes, 'feature_type': 'stateful'}, 
                open('outputs/model_config.pkl', 'wb'))
    
    # Training loop
    print("\n" + "=" * 60)
    print("Training...")
    print("=" * 60)
    
    epochs = 50
    best_val_loss = float('inf')
    best_val_acc = 0
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        train_correct = 0
        train_total = 0
        
        for inputs, labels in train_loader:
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, preds = torch.max(outputs, 1)
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)
        
        train_loss /= len(train_loader)
        train_acc = train_correct / train_total
        
        # Validation
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for inputs, labels in val_loader:
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                val_loss += loss.item()
                _, preds = torch.max(outputs, 1)
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)
        
        val_loss /= len(val_loader)
        val_acc = val_correct / val_total
        
        # Progress
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch {epoch+1:3d}/{epochs} | "
                  f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
                  f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}")
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_val_acc = val_acc
            os.makedirs('models', exist_ok=True)
            torch.save(model.state_dict(), 'models/best_model.pt')
    
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"Best Validation Loss: {best_val_loss:.4f}")
    print(f"Best Validation Accuracy: {best_val_acc:.4f}")
    
    # Final evaluation
    print("\n[4/4] Final Evaluation...")
    
    model.load_state_dict(torch.load('models/best_model.pt', weights_only=True))
    model.eval()
    
    all_preds = []
    all_labels_eval = []
    
    with torch.no_grad():
        for inputs, labels in val_loader:
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_labels_eval.extend(labels.cpu().numpy())
    
    class_names = ['normal', 'DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing']
    print("\nClassification Report:")
    print(classification_report(all_labels_eval, all_preds, target_names=class_names, digits=4))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(all_labels_eval, all_preds)
    print("             ", "  ".join(f"{n:>8}" for n in class_names))
    for i, row in enumerate(cm):
        print(f"{class_names[i]:>12}", "  ".join(f"{v:>8}" for v in row))
    
    print("\n" + "=" * 60)
    print("Model artifacts saved:")
    print("  [✓] models/best_model.pt - Model weights")
    print("  [✓] outputs/scaler.pkl - Feature scaler")
    print("  [✓] outputs/model_config.pkl - Model config (stateful)")
    print("=" * 60)
    
    return model


if __name__ == "__main__":
    train_stateful_model()
