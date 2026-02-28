import numpy as np
from collections import defaultdict, deque

class FeatureExtractor:
    """
    Feature extractor for CAN bus frames.
    
    Supports two modes:
    1. Stateful mode (update): Maintains state across frames for time-series features
    2. Stateless mode (extract_stateless): Per-frame features without temporal dependencies
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all internal state for a fresh extraction session."""
        self.last_seen = {}
        self.last_global = None
        self.id_counts = defaultdict(int)
        self.total = 0
        self.windows = defaultdict(deque)
        self.ema = {}
        self.var = {}
    
    @staticmethod
    def extract_stateless(frame):
        """
        Extract per-frame features without any temporal state.
        These features are independent of processing order.
        
        Features extracted:
        - arb_id: Arbitration ID (normalized)
        - dlc: Data Length Code
        - data bytes (8 bytes, normalized to 0-1)
        - sum_bytes: Sum of all data bytes
        - mean_bytes: Mean of data bytes
        - var_bytes: Variance of data bytes
        - max_byte: Maximum byte value
        - min_byte: Minimum byte value  
        - byte_entropy: Entropy of byte distribution
        - zero_byte_count: Count of zero bytes
        - unique_byte_count: Count of unique byte values
        
        Returns: numpy array of shape (19,)
        """
        arb_id = frame["id"]
        dlc = frame["dlc"]
        data = frame["data"] + [0]*(8-len(frame["data"]))
        
        bytes_arr = np.array(data, dtype=np.float32)
        normalized = bytes_arr / 255.0
        
        # Basic byte statistics
        sum_bytes = np.sum(bytes_arr)
        mean_bytes = np.mean(bytes_arr)
        var_bytes = np.var(bytes_arr)
        max_byte = np.max(bytes_arr)
        min_byte = np.min(bytes_arr)
        
        # Additional features for better discrimination
        zero_byte_count = np.sum(bytes_arr == 0)
        unique_byte_count = len(np.unique(bytes_arr))
        
        # Byte entropy (measure of randomness - helps detect fuzzing)
        byte_counts = np.bincount(data, minlength=256)
        byte_probs = byte_counts[byte_counts > 0] / 8.0
        byte_entropy = -np.sum(byte_probs * np.log2(byte_probs + 1e-10))
        
        # Normalize arb_id to 0-1 range (CAN IDs are 11-bit: 0-2047)
        arb_id_normalized = arb_id / 2047.0
        
        return np.array([
            arb_id_normalized,
            dlc / 8.0,  # Normalize DLC
            *normalized,
            sum_bytes / 2040.0,  # Normalize (max = 255*8)
            mean_bytes / 255.0,
            var_bytes / 16256.25,  # Normalize (max variance for 0-255)
            max_byte / 255.0,
            min_byte / 255.0,
            byte_entropy / 3.0,  # Normalize (max entropy for 8 bytes)
            zero_byte_count / 8.0,
            unique_byte_count / 8.0
        ], dtype=np.float32)

    def update(self, frame):
        """
        Extract features with stateful temporal tracking.
        Use this for real-time streaming where order matters.
        """
        ts = frame["timestamp"]
        arb_id = frame["id"]
        dlc = frame["dlc"]
        data = frame["data"] + [0]*(8-len(frame["data"]))

        # Timing
        delta_t_global = 0
        if self.last_global:
            delta_t_global = (ts - self.last_global)*1000
        self.last_global = ts

        delta_t_id = 0
        if arb_id in self.last_seen:
            delta_t_id = (ts - self.last_seen[arb_id])*1000
        self.last_seen[arb_id] = ts

        # Window
        window = self.windows[arb_id]
        window.append(ts)
        while window and ts - window[0] > 0.2:
            window.popleft()

        count_id_window = len(window)

        # Ratio
        self.id_counts[arb_id] += 1
        self.total += 1
        ratio_id_total = self.id_counts[arb_id] / self.total

        # EMA
        alpha = 0.2
        if arb_id not in self.ema:
            self.ema[arb_id] = delta_t_id
        else:
            self.ema[arb_id] = alpha*delta_t_id + (1-alpha)*self.ema[arb_id]

        # Variance
        beta = 0.2
        if arb_id not in self.var:
            self.var[arb_id] = 0
        else:
            self.var[arb_id] = (1-beta)*self.var[arb_id] + beta*(delta_t_id - self.ema[arb_id])**2

        # Byte stats
        bytes_arr = np.array(data)
        sum_bytes = np.sum(bytes_arr)
        mean_bytes = np.mean(bytes_arr)
        var_bytes = np.var(bytes_arr)

        normalized = bytes_arr / 255.0

        return np.array([
            arb_id,
            dlc,
            *normalized,
            delta_t_id,
            delta_t_global,
            count_id_window,
            ratio_id_total,
            self.ema[arb_id],
            self.var[arb_id],
            sum_bytes,
            mean_bytes,
            var_bytes
        ], dtype=np.float32)
