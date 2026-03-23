#!/usr/bin/env python3
"""
Data Parser for CAN Bus Dataset

Loads and parses CAN frame data from text files in the dataset directory.
Supports various formats and returns structured frame-label pairs for training.
"""

import os
import json
import re
from typing import List, Tuple, Dict


def load_dataset(dataset_dir: str, samples_per_class: int = 10000) -> List[Tuple[Dict, str]]:
    """
    Load CAN frame dataset from directory.
    
    Supports:
    - JSON lines format (one frame per line)
    - CSV format with standard CAN fields
    - Text format with frame definitions
    
    Args:
        dataset_dir: Path to dataset directory
        samples_per_class: Maximum samples per class to load
        
    Returns:
        List of (frame, label) tuples where frame is a dict with keys:
        'timestamp', 'id', 'dlc', 'data'
    """
    data = []
    
    if not os.path.exists(dataset_dir):
        print(f"Warning: Dataset directory {dataset_dir} not found")
        return data
    
    # Look for all data files
    for filename in os.listdir(dataset_dir):
        filepath = os.path.join(dataset_dir, filename)
        
        if not os.path.isfile(filepath):
            continue
        
        # Parse based on file extension/name
        if filename.endswith('.txt'):
            data.extend(_parse_text_file(filepath, samples_per_class))
        elif filename.endswith('.jsonl') or filename.endswith('.json'):
            data.extend(_parse_jsonl_file(filepath, samples_per_class))
        elif filename.endswith('.csv'):
            data.extend(_parse_csv_file(filepath, samples_per_class))
    
    return data


def _parse_text_file(filepath: str, samples_per_class: int) -> List[Tuple[Dict, str]]:
    """Parse text file containing CAN frames."""
    data = []
    
    try:
        with open(filepath, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                frame, label = _parse_frame_line(line)
                if frame:
                    data.append((frame, label))
                
                # Limit samples
                if samples_per_class and len(data) >= samples_per_class:
                    break
    except Exception as e:
        print(f"Warning: Error parsing {filepath}: {e}")
    
    return data


def _parse_jsonl_file(filepath: str, samples_per_class: int) -> List[Tuple[Dict, str]]:
    """Parse JSONL file containing CAN frames."""
    data = []
    
    try:
        with open(filepath, 'r') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    obj = json.loads(line)
                    
                    # Extract frame fields
                    frame = {
                        'timestamp': obj.get('timestamp', i * 0.01),
                        'id': obj.get('id', 0x000),
                        'dlc': obj.get('dlc', 8),
                        'data': obj.get('data', [0] * 8)
                    }
                    
                    # Extract label
                    label = obj.get('label', obj.get('attack', 'normal'))
                    
                    data.append((frame, label))
                    
                    if samples_per_class and len(data) >= samples_per_class:
                        break
                        
                except json.JSONDecodeError:
                    continue
                    
    except Exception as e:
        print(f"Warning: Error parsing {filepath}: {e}")
    
    return data


def _parse_csv_file(filepath: str, samples_per_class: int) -> List[Tuple[Dict, str]]:
    """Parse CSV file containing CAN frames."""
    data = []
    
    try:
        with open(filepath, 'r') as f:
            # Try to detect header
            first_line = f.readline().strip()
            has_header = any(x in first_line.lower() for x in ['timestamp', 'id', 'dlc', 'label'])
            
            # Reset if header found
            if not has_header:
                lines = [first_line] + f.readlines()
            else:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Parse CSV
                parts = [x.strip() for x in line.split(',')]
                
                if len(parts) < 4:
                    continue
                
                try:
                    timestamp = float(parts[0]) if parts[0] else 0
                    can_id = int(parts[1], 16 if parts[1].startswith('0x') else 10)
                    dlc = int(parts[2]) if len(parts) > 2 else 8
                    
                    # Parse data bytes
                    data_str = parts[3] if len(parts) > 3 else ""
                    data_bytes = _parse_data_bytes(data_str)
                    
                    # Parse label
                    label = parts[4] if len(parts) > 4 else 'normal'
                    
                    frame = {
                        'timestamp': timestamp,
                        'id': can_id,
                        'dlc': dlc,
                        'data': data_bytes
                    }
                    
                    data.append((frame, label))
                    
                    if samples_per_class and len(data) >= samples_per_class:
                        break
                        
                except (ValueError, IndexError):
                    continue
                    
    except Exception as e:
        print(f"Warning: Error parsing {filepath}: {e}")
    
    return data


def _parse_frame_line(line: str) -> Tuple[Dict, str]:
    """
    Parse a single frame line.
    
    Supports formats like:
    - "ID=0x123 DLC=8 DATA=11 22 33 44 55 66 77 88 LABEL=normal"
    - "0x123,8,11223344556677888,normal"
    - "[timestamp] ID dlc byte1 byte2 ... label"
    """
    frame = None
    label = "normal"
    
    try:
        # Try key=value format
        if '=' in line:
            parts = {}
            for segment in re.split(r'\s+', line):
                if '=' in segment:
                    k, v = segment.split('=', 1)
                    parts[k.lower()] = v
            
            if 'id' in parts:
                can_id = int(parts['id'], 16 if parts['id'].startswith('0x') else 10)
                dlc = int(parts.get('dlc', 8))
                data_str = parts.get('data', '')
                data_bytes = _parse_data_bytes(data_str)
                timestamp = float(parts.get('timestamp', 0))
                label = parts.get('label', parts.get('attack', 'normal'))
                
                frame = {
                    'timestamp': timestamp,
                    'id': can_id,
                    'dlc': dlc,
                    'data': data_bytes
                }
        
        # Try comma-separated format
        elif ',' in line:
            parts = [x.strip() for x in line.split(',')]
            if len(parts) >= 3:
                can_id = int(parts[0], 16 if parts[0].startswith('0x') else 10)
                dlc = int(parts[1])
                data_bytes = _parse_data_bytes(parts[2])
                label = parts[3] if len(parts) > 3 else 'normal'
                
                frame = {
                    'timestamp': 0,
                    'id': can_id,
                    'dlc': dlc,
                    'data': data_bytes
                }
    
    except (ValueError, IndexError):
        pass
    
    return frame, label


def _parse_data_bytes(data_str: str) -> List[int]:
    """
    Parse data bytes from string.
    
    Supports:
    - "11 22 33 44 55 66 77 88" (space-separated hex)
    - "1122334455667788" (continuous hex)
    - "17,34,51,68,85,102,119,136" (comma-separated decimal)
    """
    data = []
    
    if not data_str:
        return [0] * 8
    
    # Remove common delimiters and split
    data_str = data_str.replace('-', ' ').replace(',', ' ')
    parts = data_str.split()
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        try:
            # Try hex
            if part.startswith('0x'):
                data.append(int(part, 16))
            elif all(c in '0123456789ABCDEFabcdef' for c in part):
                # Could be hex without 0x
                if len(part) == 2:
                    data.append(int(part, 16))
                else:
                    # Parse pairs of hex digits
                    for i in range(0, len(part), 2):
                        data.append(int(part[i:i+2], 16))
            else:
                # Try decimal
                data.append(int(part))
        except ValueError:
            continue
    
    # Pad or truncate to 8 bytes
    data = data[:8]
    data.extend([0] * (8 - len(data)))
    
    return data
