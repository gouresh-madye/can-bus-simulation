import csv
import os
import random

def parse_txt(file_path):
    """Parse normal traffic from .txt files."""
    frames = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 14:
                continue
            ts = float(parts[1])
            id_hex = parts[3]
            dlc = int(parts[6])
            data_hex = parts[7:15]
            id_int = int(id_hex, 16)
            data = [int(x, 16) for x in data_hex]
            frames.append({"timestamp": ts, "id": id_int, "dlc": dlc, "data": data, "label": "normal"})
    return frames

def parse_csv(file_path, attack_type):
    """
    Parse CSV files and correctly label frames based on column 12.
    'R' = Regular/Normal traffic
    'T' = Attack traffic (True positive)
    """
    normal_frames = []
    attack_frames = []
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 12:
                continue
            try:
                ts = float(row[0])
                id_int = int(row[1], 16)
                dlc = int(row[2])
                data = [int(x, 16) for x in row[3:11]]
                # Column 11 (index 11) contains 'R' for normal, 'T' for attack
                label_marker = row[11].strip() if len(row) > 11 else 'R'
                
                frame = {"timestamp": ts, "id": id_int, "dlc": dlc, "data": data}
                
                if label_marker == 'T':
                    frame["label"] = attack_type
                    attack_frames.append(frame)
                else:
                    frame["label"] = "normal"
                    normal_frames.append(frame)
            except (ValueError, IndexError):
                continue
    return normal_frames, attack_frames

def load_dataset(dataset_dir, samples_per_class=50000, seed=42):
    """
    Load dataset with proper label parsing and balanced sampling.
    
    Args:
        dataset_dir: Path to dataset directory
        samples_per_class: Number of samples per class for balanced dataset
        seed: Random seed for reproducibility
    
    Returns:
        List of (frame, label) tuples, shuffled
    """
    random.seed(seed)
    
    # Attack type mapping based on actual dataset semantics
    # DoS = Denial of Service attack (flooding)
    # Fuzzy = Fuzzing attack (random data injection)
    # RPM = RPM spoofing attack (manipulating RPM values)
    # gear = Gear spoofing attack (manipulating gear values)
    attack_type_map = {
        'DoS': 'DoS',
        'Fuzzy': 'fuzzing',
        'RPM': 'rpm_spoofing',    # More specific label
        'gear': 'gear_spoofing'   # More specific label
    }
    
    all_normal_frames = []
    attack_frames_by_type = {}
    
    for file in os.listdir(dataset_dir):
        file_path = os.path.join(dataset_dir, file)
        
        if file.endswith('.txt'):
            # Normal traffic from .txt file
            frames = parse_txt(file_path)
            all_normal_frames.extend(frames)
            
        elif file.endswith('.csv'):
            # Determine attack type from filename
            attack_type = None
            for key, label in attack_type_map.items():
                if key in file:
                    attack_type = label
                    break
            
            if attack_type is None:
                continue
            
            # Parse CSV and separate normal vs attack frames
            normal_from_csv, attack_from_csv = parse_csv(file_path, attack_type)
            
            # Add normal frames from CSV to pool
            all_normal_frames.extend(normal_from_csv)
            
            # Store attack frames by type
            if attack_type not in attack_frames_by_type:
                attack_frames_by_type[attack_type] = []
            attack_frames_by_type[attack_type].extend(attack_from_csv)
    
    # Balance the dataset by sampling equally from each class
    balanced_data = []
    
    # Sample normal frames
    if len(all_normal_frames) >= samples_per_class:
        sampled_normal = random.sample(all_normal_frames, samples_per_class)
    else:
        sampled_normal = all_normal_frames
        print(f"Warning: Only {len(all_normal_frames)} normal frames available")
    
    for frame in sampled_normal:
        balanced_data.append((frame, 'normal'))
    
    # Sample from each attack type
    for attack_type, frames in attack_frames_by_type.items():
        if len(frames) >= samples_per_class:
            sampled_attack = random.sample(frames, samples_per_class)
        else:
            sampled_attack = frames
            print(f"Warning: Only {len(frames)} {attack_type} attack frames available")
        
        for frame in sampled_attack:
            balanced_data.append((frame, attack_type))
    
    # Shuffle all data to prevent temporal patterns
    random.shuffle(balanced_data)
    
    print(f"Dataset loaded: {len(balanced_data)} total samples")
    for label in ['normal'] + list(attack_frames_by_type.keys()):
        count = sum(1 for _, l in balanced_data if l == label)
        print(f"  {label}: {count} samples")
    
    return balanced_data
