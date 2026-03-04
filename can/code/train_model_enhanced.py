#!/usr/bin/env python3
"""
Enhanced Model Training for Live CAN Bus IDS Simulation

This training script:
1. Loads attack data from the original dataset
2. Adds synthetic normal data matching ECU simulator patterns
3. Creates synthetic attack data matching our attack scripts
4. Trains a balanced model for optimal live detection

Usage:
    python3 train_model_enhanced.py
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
from feature_extractor import FeatureExtractor
from data_parser import load_dataset


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


def generate_synthetic_ecu_frames(num_frames, ecu_config):
    """
    Generate synthetic normal ECU frames matching the live IDS server ECU patterns.
    This ensures the model recognizes our simulated ECU traffic as normal.
    """
    frames = []
    
    for _ in range(num_frames):
        # Pick a random ECU
        ecu = random.choice(ecu_config)
        can_id = ecu["can_id"]
        pattern = ecu["data_pattern"]
        
        # Generate realistic payload for each ECU type
        data = generate_ecu_payload(pattern)
        
        frame = {
            "timestamp": random.random(),  # Not used in stateless features
            "id": can_id,
            "dlc": 8,
            "data": data
        }
        frames.append((frame, "normal"))
    
    return frames


def generate_ecu_payload(pattern):
    """Generate realistic payload data based on ECU type."""
    data = [0] * 8
    
    if pattern == "engine":
        rpm = random.randint(800, 6000)
        rpm_high = (rpm >> 8) & 0xFF
        rpm_low = rpm & 0xFF
        throttle = random.randint(0, 100)
        data = [throttle, rpm_high, rpm_low, 
                random.randint(85, 95), random.randint(20, 40),
                0, 0, random.randint(0, 255)]
                
    elif pattern == "transmission":
        gear = random.randint(0, 6)
        data = [gear, random.randint(30, 100), random.randint(20, 80),
                0, random.randint(0, 255), 0, 0, random.randint(0, 255)]
                
    elif pattern == "speed":
        speed = random.randint(0, 180)
        data = [speed, (speed * 3) & 0xFF, random.randint(0, 100),
                0, 0, 0, random.randint(0, 255), random.randint(0, 255)]
                
    elif pattern == "dashboard":
        data = [random.randint(0, 1), random.randint(0, 1), random.randint(0, 1),
                random.randint(0, 255), 0, 0, 0, 0]
                
    elif pattern == "brake":
        brake = random.randint(0, 100)
        data = [brake, (brake * 2) & 0xFF, random.randint(0, 20),
                0, 0, 0, 0, random.randint(0, 255)]
                
    elif pattern == "steering":
        angle = random.randint(0, 180)
        data = [angle >> 8, angle & 0xFF, random.randint(0, 50),
                0, 0, 0, 0, random.randint(0, 255)]
                
    elif pattern == "rpm":
        # RPM Gauge - ID 0x316
        rpm = random.randint(800, 6000)
        data = [5, (rpm >> 8) & 0xFF, rpm & 0xFF, 
                random.randint(0, 100), (rpm >> 8) & 0xFF, (rpm >> 8) & 0xFF, 
                0, random.randint(0, 255)]
                
    elif pattern == "gear":
        # Gear Indicator - ID 0x43F
        gear = random.randint(0, 6)
        data = [0, gear * 0x10, 0x60, 0xFF,
                random.randint(0, 255), random.randint(0, 255),
                0x08, 0]
    
    return data


def generate_synthetic_attacks(num_per_type):
    """
    Generate synthetic attack frames matching our attack scripts.
    This improves model accuracy for live attack detection.
    """
    attacks = []
    
    # DoS Attack: ID 0x000 with all zeros or minimal data
    for _ in range(num_per_type):
        data = [0] * 8  # DoS typically uses all zeros
        frame = {"timestamp": 0, "id": 0x000, "dlc": 8, "data": data}
        attacks.append((frame, "DoS"))
    
    # Fuzzy Attack: Random IDs and random data (high entropy)
    for _ in range(num_per_type):
        can_id = random.randint(0x000, 0x7FF)
        data = [random.randint(0, 255) for _ in range(8)]
        frame = {"timestamp": 0, "id": can_id, "dlc": 8, "data": data}
        attacks.append((frame, "fuzzing"))
    
    # RPM Spoofing: ID 0x316 with abnormal RPM values
    for _ in range(num_per_type):
        mode = random.choice(["spike", "redline", "oscillate"])
        if mode == "spike":
            rpm = random.choice([0, 9000, 10000])  # Extreme values
        elif mode == "redline":
            rpm = random.randint(7000, 9500)  # Dangerous range
        else:
            rpm = random.randint(0, 9000)  # Oscillating
        
        data = [random.randint(0, 255), (rpm >> 8) & 0xFF, rpm & 0xFF,
                random.randint(0, 255), random.randint(0, 255),
                random.randint(0, 255), 0, random.randint(0, 255)]
        frame = {"timestamp": 0, "id": 0x316, "dlc": 8, "data": data}
        attacks.append((frame, "rpm_spoofing"))
    
    # Gear Spoofing: ID 0x43F with abnormal gear values
    for _ in range(num_per_type):
        mode = random.choice(["random", "reverse", "rapid"])
        if mode == "random":
            gear = random.randint(0, 10)  # Invalid gears
        elif mode == "reverse":
            gear = 0xFF  # Invalid reverse indicator
        else:
            gear = random.choice([0, 6, 7, 8, 9, 10])  # Rapid shifts
        
        data = [random.randint(0, 255), gear, random.randint(0, 255),
                random.randint(0, 255), random.randint(0, 255),
                random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]
        frame = {"timestamp": 0, "id": 0x43F, "dlc": 8, "data": data}
        attacks.append((frame, "gear_spoofing"))
    
    return attacks


def train_enhanced_model():
    """Train model with enhanced dataset including synthetic data."""
    
    print("=" * 60)
    print("Enhanced CAN Bus IDS Model Training")
    print("=" * 60)
    
    # Label mapping
    label_map = {'normal': 0, 'DoS': 1, 'fuzzing': 2, 'rpm_spoofing': 3, 'gear_spoofing': 4}
    
    # ECU configuration (matches ids_server_live.py)
    ecu_config = [
        {"name": "Engine", "can_id": 0x100, "data_pattern": "engine"},
        {"name": "Transmission", "can_id": 0x200, "data_pattern": "transmission"},
        {"name": "SpeedSensor", "can_id": 0x300, "data_pattern": "speed"},
        {"name": "Dashboard", "can_id": 0x400, "data_pattern": "dashboard"},
        {"name": "BrakeSensor", "can_id": 0x350, "data_pattern": "brake"},
        {"name": "SteeringSensor", "can_id": 0x450, "data_pattern": "steering"},
        {"name": "RPMGauge", "can_id": 0x316, "data_pattern": "rpm"},
        {"name": "GearIndicator", "can_id": 0x43f, "data_pattern": "gear"},
    ]
    
    all_data = []
    
    # Step 1: Load original dataset
    print("\n[1/4] Loading original dataset...")
    dataset_dir = 'dataset'
    if os.path.exists(dataset_dir):
        try:
            original_data = load_dataset(dataset_dir, samples_per_class=10000)
            all_data.extend(original_data)
            print(f"      Loaded {len(original_data)} samples from original dataset")
        except Exception as e:
            print(f"      Warning: Could not load dataset: {e}")
    
    # Step 2: Generate synthetic ECU normal traffic
    print("\n[2/4] Generating synthetic ECU normal traffic...")
    synthetic_normal = generate_synthetic_ecu_frames(20000, ecu_config)
    all_data.extend(synthetic_normal)
    print(f"      Generated {len(synthetic_normal)} synthetic normal frames")
    
    # Step 3: Generate synthetic attack patterns
    print("\n[3/4] Generating synthetic attack patterns...")
    synthetic_attacks = generate_synthetic_attacks(5000)
    all_data.extend(synthetic_attacks)
    print(f"      Generated {len(synthetic_attacks)} synthetic attack frames")
    
    # Shuffle data
    random.shuffle(all_data)
    
    # Step 4: Extract features
    print("\n[4/4] Extracting features...")
    X_list = []
    y_list = []
    
    for frame, label in all_data:
        features = FeatureExtractor.extract_stateless(frame)
        X_list.append(features)
        y_list.append(label_map[label])
    
    X = np.array(X_list)
    y = np.array(y_list)
    
    print(f"      Total samples: {len(X)}")
    print(f"      Feature dimensions: {X.shape[1]}")
    
    # Class distribution
    print("\n      Class distribution:")
    for label_name, label_idx in label_map.items():
        count = np.sum(y == label_idx)
        print(f"        {label_name}: {count} samples")
    
    # Save features
    os.makedirs('outputs', exist_ok=True)
    np.save('outputs/X.npy', X)
    np.save('outputs/y.npy', y)
    
    # Split data
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
    weights = torch.tensor([class_weights[i] for i in range(num_classes)], dtype=torch.float32)
    
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
    pickle.dump({'input_size': input_size, 'num_classes': num_classes}, 
                open('outputs/model_config.pkl', 'wb'))
    
    # Training loop
    print("\n" + "=" * 60)
    print("Training Model...")
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
    print("\n" + "=" * 60)
    print("Final Model Evaluation")
    print("=" * 60)
    
    model.load_state_dict(torch.load('models/best_model.pt', weights_only=True))
    model.eval()
    
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for inputs, labels in val_loader:
            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
    
    class_names = ['normal', 'DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing']
    print("\nClassification Report:")
    print(classification_report(all_labels, all_preds, target_names=class_names, digits=4))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(all_labels, all_preds)
    print("             ", "  ".join(f"{n:>8}" for n in class_names))
    for i, row in enumerate(cm):
        print(f"{class_names[i]:>12}", "  ".join(f"{v:>8}" for v in row))
    
    print("\n[✓] Model saved to: models/best_model.pt")
    print("[✓] Scaler saved to: outputs/scaler.pkl")
    print("[✓] Config saved to: outputs/model_config.pkl")
    
    return model


if __name__ == "__main__":
    train_enhanced_model()
