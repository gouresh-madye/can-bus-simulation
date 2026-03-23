#!/usr/bin/env python3
"""
Feature Extractor for CAN Bus IDS

Extracts precise timing and statistical features from CAN frames for ML-based intrusion detection.
Supports both stateless (single-frame) and stateful (stream-based) feature extraction.
"""

import numpy as np
from collections import defaultdict, deque


class FeatureExtractor:
    """
    Real-time feature extractor for CAN frames.
    
    Maintains state across frames including:
    - Last seen timestamp per ID
    - Sliding windows for frequency analysis
    - Exponential moving averages for timing patterns
    - Moving variance estimates
    """

    def __init__(self):
        """Initialize the feature extractor with empty state."""
        self.last_seen = {}
        self.last_global = None
        self.id_counts = defaultdict(int)
        self.total = 0
        self.windows = defaultdict(deque)
        self.ema = {}
        self.var = {}

    def update(self, frame):
        """
        Update internal state with a new frame and extract features.
        
        Args:
            frame: Dict with keys 'timestamp', 'id', 'dlc', 'data'
            
        Returns:
            np.array: Feature vector of shape (18,)
        """
        ts = frame["timestamp"]
        arb_id = frame["id"]
        dlc = frame["dlc"]
        data = frame["data"] + [0] * (8 - len(frame["data"]))

        # Timing features
        delta_t_global = 0
        if self.last_global:
            delta_t_global = (ts - self.last_global) * 1000
        self.last_global = ts

        delta_t_id = 0
        if arb_id in self.last_seen:
            delta_t_id = (ts - self.last_seen[arb_id]) * 1000
        self.last_seen[arb_id] = ts

        # Sliding window (200ms)
        window = self.windows[arb_id]
        window.append(ts)
        while window and ts - window[0] > 0.2:
            window.popleft()
        count_id_window = len(window)

        # Ratio feature
        self.id_counts[arb_id] += 1
        self.total += 1
        ratio_id_total = self.id_counts[arb_id] / self.total

        # EMA (Exponential Moving Average)
        alpha = 0.2
        if arb_id not in self.ema:
            self.ema[arb_id] = delta_t_id
        else:
            self.ema[arb_id] = alpha * delta_t_id + (1 - alpha) * self.ema[arb_id]

        # Moving variance
        beta = 0.2
        if arb_id not in self.var:
            self.var[arb_id] = 0
        else:
            self.var[arb_id] = (1 - beta) * self.var[arb_id] + beta * (delta_t_id - self.ema[arb_id]) ** 2

        # Byte statistics
        bytes_arr = np.array(data, dtype=np.float32)
        sum_bytes = np.sum(bytes_arr)
        mean_bytes = np.mean(bytes_arr)
        var_bytes = np.var(bytes_arr)

        # Normalize bytes to [0, 1]
        normalized = bytes_arr / 255.0

        # Build feature vector (18 features total)
        features = np.array(
            [
                arb_id,
                dlc,
                *normalized,  # 8 normalized bytes
                delta_t_id,
                delta_t_global,
                count_id_window,
                ratio_id_total,
                self.ema[arb_id],
                self.var[arb_id],
                sum_bytes,
                mean_bytes,
                var_bytes,
            ],
            dtype=np.float32,
        )

        return features

    @staticmethod
    def extract_stateless(frame):
        """
        Extract features from a single frame without state.
        
        Used for training when frame order/timing context is not critical.
        Generates synthetic timing features based on frame content.
        
        Args:
            frame: Dict with keys 'timestamp', 'id', 'dlc', 'data'
            
        Returns:
            np.array: Feature vector of shape (18,)
        """
        ts = frame.get("timestamp", 0)
        arb_id = frame["id"]
        dlc = frame["dlc"]
        data = frame.get("data", [0] * 8)
        data = data + [0] * (8 - len(data))

        # For stateless, use minimal timing features
        delta_t_id = ts * 1000 % 100  # Pseudo-random based on timestamp
        delta_t_global = ts * 1000 % 50
        count_id_window = 1  # Single frame
        ratio_id_total = 1.0 / 256  # Assume uniform distribution

        # Byte statistics
        bytes_arr = np.array(data, dtype=np.float32)
        sum_bytes = np.sum(bytes_arr)
        mean_bytes = np.mean(bytes_arr)
        var_bytes = np.var(bytes_arr)

        # Normalize bytes
        normalized = bytes_arr / 255.0

        # Simple EMA/VAR based on byte patterns
        ema = mean_bytes
        var = var_bytes / 255.0

        # Build feature vector
        features = np.array(
            [
                arb_id,
                dlc,
                *normalized,  # 8 normalized bytes
                delta_t_id,
                delta_t_global,
                count_id_window,
                ratio_id_total,
                ema,
                var,
                sum_bytes,
                mean_bytes,
                var_bytes,
            ],
            dtype=np.float32,
        )

        return features

    def reset(self):
        """Reset extractor state. Used when processing multiple independent streams."""
        self.last_seen = {}
        self.last_global = None
        self.id_counts = defaultdict(int)
        self.total = 0
        self.windows = defaultdict(deque)
        self.ema = {}
        self.var = {}
