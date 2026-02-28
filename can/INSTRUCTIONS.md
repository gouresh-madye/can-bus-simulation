# Real-Time CAN IDS/IPS Laptop Simulation (Feature-Accurate Version)

---

# 1️⃣ Objective

Build a **real-time streaming CAN IDS/IPS simulation system** that:

* Receives CAN-like frames via TCP socket
* Extracts precise timing + statistical features
* Performs per-frame inference using `best_model.pt`
* Detects attacks (DoS, Fuzzing, Spoofing, Replay)
* Issues IPS vehicle safety commands
* Logs predictions in real-time

This simulates real CAN traffic like your provided example frames.

---

# 2️⃣ System Architecture

```text
Normal Traffic Generator  ─┐
                           ├──>  TCP Server (IDS)
Attack Injector ───────────┘

IDS Server:
    → Feature Extractor
    → PyTorch Model (CPU)
    → IDS Decision
    → IPS Command Engine
    → Vehicle Simulation Handler
```

Runs fully on laptop (no Raspberry Pi).

---

# 3️⃣ Frame Format (Strict CAN Representation)

Each frame:

```json
{
  "timestamp": 1479121434.850202,
  "id": 0x350,
  "dlc": 8,
  "data": [5, 40, 132, 102, 109, 0, 0, 162]
}
```

Constraints:

* ID: 11-bit (0–2047)
* DLC: 0–8
* Payload padded with zeros if < 8
* Timestamp precision: milliseconds

---

# 4️⃣ Feature Vector (Final Specification)

For each frame compute:

### 🔹 Core Features

| Feature         | Type                    |
| --------------- | ----------------------- |
| id              | int                     |
| dlc             | int                     |
| byte_0..byte_7  | float (0–1 normalized)  |
| delta_t_id      | float (ms)              |
| delta_t_global  | float (ms)              |
| count_id_window | int (200ms window)      |
| ratio_id_total  | float                   |
| mean_delta_t_id | float (EMA)             |
| var_delta_t_id  | float (moving variance) |
| sum_bytes       | int                     |
| mean_bytes      | float                   |
| var_bytes       | float                   |

---

# 5️⃣ Real-Time Feature Extraction Logic

## 5.1 Timing (Milliseconds)

```python
delta_t_id = (current_ts - last_seen[id]) * 1000
delta_t_global = (current_ts - last_global_ts) * 1000
```

---

## 5.2 Sliding Window (200ms)

Maintain per-ID deque:

```python
while window and current_ts - window[0] > 0.2:
    window.popleft()
count_id_window = len(window)
```

---

## 5.3 Ratio Feature

```python
ratio_id_total = id_count[id] / total_frames
```

---

## 5.4 Exponential Moving Average

```python
ema[id] = alpha * delta_t_id + (1-alpha) * ema[id]
```

Alpha = 0.2

---

## 5.5 Moving Variance (Welford-like approximation)

```python
var[id] = (1-beta)*var[id] + beta*(delta_t_id - ema[id])**2
```

Beta = 0.2

---

## 5.6 Byte-Level Statistics

For padded 8 bytes:

```python
sum_bytes = sum(bytes)
mean_bytes = sum_bytes / 8
var_bytes = np.var(bytes)
```

Normalize bytes:

```python
normalized_byte = byte / 255.0
```

---

# 6️⃣ Normal Traffic Behavior (Based on Your Example)

Your example shows:

* Repeating IDs (e.g., 0x350, 0x02c0)
* Periodic timing (~5–10 ms gaps)
* Stable payload patterns
* Low variance in delta_t_id
* Stable byte distributions

The IDS must learn:

* Consistent delta_t_id
* Low variance
* Stable sum/mean bytes
* Regular ID frequencies

---

# 7️⃣ Attack Simulation Logic

---

## 1️⃣ DoS Attack

Behavior:

* Same ID spammed
* delta_t_id ≈ 0–1ms
* count_id_window spikes
* ratio_id_total becomes large
* variance very low but frequency extreme

IPS Action:

```
STOP_VEHICLE
```

---

## 2️⃣ Fuzzing Attack

Behavior:

* Random bytes
* High var_bytes
* High entropy payload
* Irregular byte statistics

IPS Action:

```
SLOW_DOWN
```

---

## 3️⃣ Spoofing Attack

Behavior:

* Legitimate ID
* Abnormal payload values
* Byte mean shifts
* sum_bytes anomaly

IPS Action:

```
PULL_OVER
```

---

## 4️⃣ Replay Attack

Behavior:

* Old frames replayed
* delta_t_id inconsistent
* Window timing mismatch

IPS Action:

```
SLOW_DOWN
```

---

# 8️⃣ IPS Command Engine

Mapping:

| Prediction | IPS Command  |
| ---------- | ------------ |
| normal     | NO_ACTION    |
| DoS        | STOP_VEHICLE |
| fuzzing    | SLOW_DOWN    |
| spoofing   | PULL_OVER    |
| replay     | SLOW_DOWN    |

Example output:

```
[1479121434.861332] ID=0x0153 → Spoofing (0.94)
[VEHICLE CONTROL] PULL_OVER
```

---

# 9️⃣ Complete Updated Feature Extractor (Accurate Version)

```python
import numpy as np
from collections import defaultdict, deque

class FeatureExtractor:
    def __init__(self):
        self.last_seen = {}
        self.last_global = None
        self.id_counts = defaultdict(int)
        self.total = 0
        self.windows = defaultdict(deque)
        self.ema = {}
        self.var = {}

    def update(self, frame):
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
```

---

# 🔟 Expected Behavior During Demo

### Normal Run

Console:

```
ID=0x350 → normal (0.99) → NO_ACTION
ID=0x02c0 → normal (0.98) → NO_ACTION
```

---

### During DoS Injection

```
ID=0x100 → DoS (0.97)
[VEHICLE CONTROL] STOP_VEHICLE
```

---

# 1️⃣1️⃣ Performance Targets (Laptop)

| Metric             | Target  |
| ------------------ | ------- |
| Inference time     | < 5ms   |
| End-to-end latency | < 15ms  |
| CPU usage          | < 40%   |
| Memory             | < 300MB |

---

# 1️⃣2️⃣ Deliverables

✔ Real-time TCP streaming
✔ Accurate millisecond feature extraction
✔ Byte statistical features
✔ Model inference
✔ IDS decision
✔ IPS command simulation
✔ CSV logging
✔ Multi-terminal attack injection

