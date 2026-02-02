# 🚗 CAN Bus Autonomous Vehicle Safety System

A comprehensive autonomous vehicle safety system that detects CAN Bus attacks and executes safety maneuvers in response. This project integrates Suricata IDS for threat detection with a vehicle control module that automatically responds to threats through graduated safety actions.

## 🆕 What's New: Autonomous Vehicle Safety Control

**NEW!** This project now includes a complete safety system that:
- ✅ Detects 7 classes of CAN Bus threats (floods, anomalies, sensor failures, etc.)
- ✅ Scores threats on a 0-100 scale with intelligent aggregation
- ✅ Executes 5 graduated safety maneuvers (SLOW_DOWN, STOP, PULL_OVER, EVASIVE, FULL_STOP)
- ✅ Generates specific CAN messages for vehicle control modules
- ✅ Enforces 8 physical safety constraints
- ✅ Implements 5 fail-safe mechanisms

**👉 [Start with the Safety System Overview](README_SAFETY_SYSTEM.md)** | **[Quick Start (5 minutes)](QUICKSTART.md)** | **[Full Architecture](ARCHITECTURE.md)**

## 📋 Table of Contents

- [What This System Does](#what-this-system-does)
- [Features](#features)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Safety System (NEW)](#safety-system-new)
  - [IDS Detection](#ids-detection)
  - [Visualization](#visualization)
- [Threat Detection](#threat-detection)
- [Safety Maneuvers](#safety-maneuvers)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## 🎯 What This System Does

### Autonomous Vehicle Protection Pipeline

```
CAN Bus Traffic
    ↓
Suricata IDS (10 Detection Rules)
    ↓
eve.json Alerts
    ↓
Safety Controller (7 Threat Classes)
    ↓
Threat Scoring Algorithm (0-100)
    ↓
Safety Decision Logic
    ↓
Vehicle Control Commands
    ↓
5 Safety Maneuvers (Graduated Response)
```

### Real-World Example

When Suricata detects a CAN flood attack (Rule 1000001):
1. Alert is parsed and classified as "CAN Flooding" threat (Class 1)
2. Threat score increases to 35/100 (YELLOW state)
3. Safety controller triggers SLOW_DOWN maneuver
4. Vehicle control module sends deceleration command to brake module (0x100)
5. Brake applies 2 m/s² deceleration while monitoring for further threats

If attack continues or escalates:
- Score increases to 65/100 (ORANGE state) → STOP maneuver
- Score reaches 85/100 (RED state) → FULL_STOP with emergency braking

## ✨ Features

### Safety System (NEW!) 🆕

- **Threat Detection**: 7-class threat detection system integrated with Suricata
- **Intelligent Scoring**: Threat scoring algorithm (0-100 scale) with time decay
- **Graduated Response**: 5 safety maneuvers triggered by threat level
- **CAN Control**: Specific CAN messages for 5 vehicle modules (Brake, Throttle, Steering, Perception, Safety)
- **Safety Constraints**: 8 physical safety limits (max deceleration, steering range, etc.)
- **Fail-Safe Mechanisms**: 5 redundant safety checks to prevent unintended behavior
- **Incident Reporting**: Detailed incident logs with threat timeline

### IDS Detection Features

- **Real-Time Detection**: Suricata IDS integration with eve.json output
- **10 Detection Rules**: Comprehensive rules for CAN-specific threats
- **CAN Traffic Generation**: Simulate CAN bus traffic with various attack patterns
- **Log Analysis**: Parse and analyze Suricata logs
- **Visualization**: Interactive visualizations of detected alerts and threat timelines

### Detected Threats

1. **CAN Flood Detection** - High-frequency repeated CAN ID patterns (Rule 1000001)
2. **Anomaly Detection** - Abnormal message sequences (Rule 1000002)
3. **DoS Attacks** - Zero payload suspicious patterns (Rule 1000003)
4. **Diagnostic Floods** - FF payload flooding (Rule 1000004)
5. **Unauthorized Commands** - Control frame anomalies (Rule 1000005)
6. **OBD Abuse** - Malicious OBD-II access attempts (Rule 1000006)
7. **Unknown ECU IDs** - Detection of unregistered ECU identifiers (Rule 1000007)
8. **Rapid Steering** - Dangerous steering angle changes (Rule 1000008)
9. **Conflicting Controls** - Simultaneous conflicting commands (Rule 1000009)
10. **Excessive Brake Pressure** - Abnormal brake pressure values (Rule 1000010)

## 📁 Project Structure

```
can-bus-simulation/
├── code/
│   ├── vehicle_control.py          # Core threat detection & control (600+ lines)
│   ├── safety_controller.py        # Suricata integration & decisions (300+ lines)
│   ├── test_safety_controller.py   # 17 comprehensive unit tests (400+ lines)
│   ├── generate_pcap.py            # PCAP generator for CAN traffic
│   └── visualize.ipynb             # Jupyter notebook for visualization
├── packets/
│   └── can_sim.pcap                # Generated CAN traffic capture
├── inputdata/
│   └── simulated_can_logs.csv       # Sample CAN log data
├── rules/
│   └── can.rules                   # 10 Suricata detection rules (enhanced)
├── suricata_logs/
│   ├── fast.log                    # Alert summary
│   └── eve.json                    # Detailed JSON logs
├── suricata.yaml                   # Suricata IDS configuration
├── requirements.txt                # Python dependencies
├── screenshots/                    # Documentation screenshots
│
├── Documentation Files:
├── README_SAFETY_SYSTEM.md         # Safety system overview
├── QUICKSTART.md                   # 5-minute quick start guide
├── ARCHITECTURE.md                 # Complete system design (400 lines)
├── IMPLEMENTATION_GUIDE.md         # Step-by-step implementation (300 lines)
├── COMPLETE_IMPLEMENTATION.md      # Full technical specification (500 lines)
├── DELIVERY_SUMMARY.md             # Project completion status
└── DOCUMENTATION_INDEX.md          # Navigation guide for all docs
```

## 🔧 Prerequisites

### System Requirements

- **Operating System**: macOS, Linux, or Windows (WSL)
- **Python**: 3.10 or higher
- **Suricata IDS**: 7.0.0 or higher
- **Sudo Access**: Required for Suricata execution

### macOS Installation

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Suricata
brew install suricata

# Verify installation
suricata --version
```

### Linux (Ubuntu/Debian) Installation

```bash
# Add Suricata PPA
sudo add-apt-repository ppa:oisf/suricata-stable
sudo apt-get update

# Install Suricata
sudo apt-get install suricata

# Verify installation
suricata --version
```

## 📦 Installation

### 1. Clone or Download the Project

```bash
cd ~/Documents/MajorProject
```

### 2. Install Python Dependencies

#### Option A: Using Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# OR
.venv\Scripts\activate     # On Windows

# Upgrade pip and install dependencies
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

#### Option B: Using Conda/Miniforge

```bash
# Create conda environment
conda create -n can-ids python=3.11 -y

# Activate environment
conda activate can-ids

# Install dependencies from conda-forge
conda install -c conda-forge pandas matplotlib seaborn jupyter -y
```

#### Option C: System-wide Installation

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## 🚀 Usage

### Safety System (NEW) 🆕

#### Quick Start (5 minutes)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Run the safety controller with test alerts
python3 -c "
from code.safety_controller import SafetyController

# Create controller
controller = SafetyController()

# Process sample threats
alerts = [
    {'alert': {'category': 'CAN Flood Detected'}, 'threat_score': 30},
    {'alert': {'category': 'Anomaly Detection'}, 'threat_score': 25},
]

for alert in alerts:
    controller.process_ids_alert(alert)
    
# View incident report
print(controller.generate_incident_report())
"

# 3. Run full test suite (17 tests)
python3 code/test_safety_controller.py
```

For detailed setup, see **[QUICKSTART.md](QUICKSTART.md)** or **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)**.

#### Understanding the Safety System

**Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- System design with 5 vehicle modules
- 7 threat detection classes
- 5 safety maneuver sequences
- CAN message specifications

**Implementation**: [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
- Component integration
- 4 test scenarios with code examples
- Customization guide
- Incident reporting

**Complete Specification**: [COMPLETE_IMPLEMENTATION.md](COMPLETE_IMPLEMENTATION.md)
- Detailed threat criteria
- CAN message byte-level specs
- Safety constraints
- Real-world attack scenarios

### IDS Detection

### IDS Detection

#### Step 1: Generate CAN Traffic

```bash
python3 generate_pcap.py
```

**Output**: Creates `packets/can_sim.pcap` with simulated CAN traffic including various attack vectors.

#### Step 2: Run Suricata IDS

Execute Suricata to analyze the generated PCAP file:

```bash
# Clean previous logs and create fresh output directory
sudo rm -rf ~/Documents/MajorProject/suricata_logs && \
mkdir ~/Documents/MajorProject/suricata_logs

# Run Suricata analysis
sudo suricata -r ~/Documents/MajorProject/packets/can_sim.pcap \
  -c ~/Documents/MajorProject/suricata.yaml \
  -S ~/Documents/MajorProject/rules/can.rules \
  -l ~/Documents/MajorProject/suricata_logs \
  --runmode=single -vv
```

**Parameters Explained:**

- `-r`: Read from PCAP file
- `-c`: Suricata configuration file
- `-S`: Custom rules file
- `-l`: Log output directory
- `--runmode=single`: Single-threaded mode for consistent results
- `-vv`: Verbose output for debugging

**Expected Output:**

- `suricata_logs/fast.log` - Human-readable alert summary
- `suricata_logs/eve.json` - JSON format detailed logs
- Console output showing detected alerts

![Suricata Implementation](screenshots/suricata_application.png)

#### Suricata Logs

After running Suricata, check the generated logs:

```bash
# View fast.log (alert summary)
cat ~/Documents/MajorProject/suricata_logs/fast.log

# Count alerts by type
grep -o '\[.*\]' ~/Documents/MajorProject/suricata_logs/fast.log | sort | uniq -c
```

![Suricata Logs Output](screenshots/logs.png)

#### Step 3: Visualize Results

#### Using Jupyter Notebook

1. **Start Jupyter Notebook**:

   ```bash
   # If using virtual environment, make sure it's activated
   jupyter notebook
   ```

2. **Open the notebook**:

   - Navigate to `visualize_fastlog.ipynb`
   - Run all cells sequentially (Cell → Run All)

3. **Interactive Analysis**:
   The notebook provides:
   - Alert frequency bar charts
   - Timeline visualization of attacks
   - Source vs Destination IP heatmaps
   - Statistical summaries

#### Using Python Script (Alternative)

If you prefer to run analysis without Jupyter:

```bash
python3 -c "
import pandas as pd
import re
from datetime import datetime

# Read and parse fast.log
with open('suricata_logs/fast.log', 'r') as f:
    lines = [l.strip() for l in f if l.strip()]

pattern = re.compile(
    r'(?P<timestamp>\d{2}/\d{2}/\d{4}-\d{2}:\d{2}:\d{2}\.\d+).*\[(?P<gid>\d+):(?P<sid>\d+):(?P<rev>\d+)\]\s+(?P<alert>.*?)\s+\[\*\*\]'
)

records = []
for line in lines:
    match = pattern.search(line)
    if match:
        records.append(match.groupdict())

df = pd.DataFrame(records)
print('\n📊 Alert Summary:')
print(df['alert'].value_counts())
print(f'\n🔢 Total Alerts: {len(df)}')
print(f'📡 Unique Source IPs: {df[\"alert\"].nunique()}')
"
```

## 📊 Visualization

The `visualize_fastlog.ipynb` notebook provides comprehensive visualizations:

### 1. Alert Frequency Analysis

- Bar chart showing count of each alert type
- Identifies most common attack vectors

### 2. Timeline Visualization

- Chronological view of all detected alerts
- Helps identify attack patterns and timing

### 3. Network Heatmap

- Source IP vs Destination IP matrix
- Visualizes communication patterns
- Highlights suspicious connections

### Sample Output

```
Parsed 78 alerts, skipped 0 lines.

📈 Summary of Alerts:
CAN Anomaly - ID 0x200 abnormal sequence          22
CAN Flood Detected - ID 0x100 pattern             21
CAN Diagnostic Flood - FF Payload                 15
CAN Unknown ECU ID (>0x700) Detected              13
CAN Unauthorized Command - Control Frame          10
CAN DoS Suspicious - Zero Payload                  4

Unique Source IPs: 5
Unique Destination IPs: 5
```

## 🛡️ Threat Detection

The safety system detects and responds to **7 threat classes**:

| Class | Name | Examples | Threat Score | Response |
|-------|------|----------|---------------|----------|
| 1 | CAN Flooding | Repeated ID patterns, high frequency | 15-40 | SLOW_DOWN |
| 2 | Anomalies | Abnormal sequences, unexpected data | 20-45 | SLOW_DOWN |
| 3 | Sensor Failure | Extreme values, missing data | 25-50 | STOP |
| 4 | Diagnostic Abuse | OBD-II floods, malicious probes | 30-55 | STOP |
| 5 | Unauthorized Cmd | Unknown ECUs, control anomalies | 35-60 | PULL_OVER |
| 6 | OBD Abuse | ECU parameter changes, memory access | 40-70 | EVASIVE |
| 7 | Unknown ECU | Unregistered IDs, spoofing | 45-75 | FULL_STOP |

### Threat Scoring

Threats are scored 0-100 with intelligent aggregation:
- **GREEN** (0-25): No action, monitoring only
- **YELLOW** (26-50): SLOW_DOWN maneuver, reduce speed
- **ORANGE** (51-75): STOP maneuver, controlled stop
- **RED** (76-100): FULL_STOP maneuver, emergency stop

Scores decay over time as threats resolve (half-life: 30 seconds).

## 🚗 Safety Maneuvers

The system executes **5 graduated safety actions** in response to threats:

| Maneuver | Trigger | Action | CAN Commands | Duration |
|----------|---------|--------|--------------|----------|
| SLOW_DOWN | Threat 26-50 | Reduce to 25 mph | Throttle -30%, Brake +20% | Until threat clears |
| STOP | Threat 51-75 | Controlled deceleration | Throttle OFF, Brake 2 m/s² | Until stopped |
| PULL_OVER | Threat 76-85 | Pull to roadside | Steer ±20°, Brake 3 m/s² | Until stopped |
| EVASIVE | Threat 86-95 | Dodge obstacle | Steer ±40°, Throttle +50% | 2-3 seconds |
| FULL_STOP | Threat 96-100 | Emergency stop | Brake 10 m/s², Hazards ON | Until stopped |

Each maneuver includes:
- ✅ CAN message generation for each vehicle module
- ✅ Real-time feedback verification
- ✅ Physical constraint enforcement
- ✅ Watchdog timers for safety
- ✅ Automated incident logging

## 📊 Testing

Run the comprehensive test suite:

```bash
# Run all 17 tests
python3 code/test_safety_controller.py

# Run specific test class
python3 code/test_safety_controller.py TestVehicleControlModule

# Run with verbose output
python3 -v code/test_safety_controller.py
```

**Test Coverage** (17 tests):
- ✅ Message parsing (3 tests)
- ✅ Threat detection (6 tests)
- ✅ Threat scoring (1 test)
- ✅ State transitions (4 tests)
- ✅ Maneuver execution (3 tests)
- ✅ Suricata integration (2 tests)

## 📊 Detection Rules

### Rule Format

Each CAN detection rule in `rules/can.rules` follows this structure:

```
alert udp any any -> any any (msg:"Alert Message";
content:"pattern"; sid:XXXXXX; rev:X; priority:3;)
```

### Current Rule Set

| SID     | Alert Type               | Threat Class | Description                 |
| ------- | ------------------------ | ------------ | --------------------------- |
| 1000001 | CAN Flood Detected       | 1            | Repeated ID patterns        |
| 1000002 | CAN Anomaly              | 2            | Abnormal sequences          |
| 1000003 | CAN DoS Suspicious       | 3            | Zero payload attacks        |
| 1000004 | CAN Diagnostic Flood     | 4            | FF payload flooding         |
| 1000005 | CAN Unauthorized Command | 5            | Control frame anomalies     |
| 1000006 | CAN OBD Abuse            | 6            | OBD-II parameter abuse      |
| 1000007 | CAN Unknown ECU ID       | 7            | ECU IDs greater than 0x700  |
| 1000008 | CAN Rapid Steering       | 2            | Dangerous steering changes  |
| 1000009 | CAN Conflicting Controls | 5            | Simultaneous conflicts      |
| 1000010 | CAN Excessive Brake      | 3            | Abnormal pressure values    |

### Adding Custom Rules

Edit `rules/can.rules` to add new detection patterns:

```bash
# Example: Detect specific CAN ID
alert udp any any -> any any (msg:"CAN Custom ID 0x300 Detected";
content:"|03 00|"; sid:1000010; rev:1; priority:2;)
```

## 🖼️ Screenshots

### Suricata Implementation

![Suricata Running](screenshots/suricata_application.png)

### Generated Logs

![Alert Logs](screenshots/logs.png)

## 🔍 Troubleshooting

### Common Issues

#### 1. Suricata Permission Denied

**Error**: `Permission denied when accessing PCAP`

**Solution**:

```bash
# Run with sudo
sudo suricata -r ...

# OR change file permissions
chmod 644 ~/Documents/MajorProject/packets/can_sim.pcap
```

#### 2. Python Package Installation Fails

**Error**: `Failed building wheel for matplotlib`

**Solution for macOS**:

```bash
# Install system dependencies
xcode-select --install
brew install pkg-config freetype libpng

# Retry installation
python3 -m pip install -r requirements.txt
```

**Alternative**: Use conda/miniforge (see Installation section)

#### 3. Suricata Not Found

**Error**: `suricata: command not found`

**Solution**:

```bash
# macOS
brew install suricata

# Linux
sudo apt-get install suricata

# Verify
which suricata
```

#### 4. Empty Log Files

**Problem**: `suricata_logs/fast.log` is empty

**Solutions**:

1. Check if PCAP file exists and has content
2. Verify rules file path is correct
3. Run Suricata with `-vv` flag for verbose output
4. Check Suricata version compatibility

#### 5. Jupyter Notebook Kernel Issues

**Error**: Kernel errors or import failures

**Solution**:

```bash
# Reinstall kernel
python3 -m ipykernel install --user --name=can-ids

# Start Jupyter with specific kernel
jupyter notebook --kernel=can-ids
```

### Debug Mode

Run Suricata with maximum verbosity for troubleshooting:

```bash
sudo suricata -r ~/Documents/MajorProject/packets/can_sim.pcap \
  -c ~/Documents/MajorProject/suricata.yaml \
  -S ~/Documents/MajorProject/rules/can.rules \
  -l ~/Documents/MajorProject/suricata_logs \
  --runmode=single -vvv --log-level=debug
```

## 📚 Documentation Guide

This project includes comprehensive documentation for different audiences:

| Document | Purpose | Time | Best For |
|----------|---------|------|----------|
| [README_SAFETY_SYSTEM.md](README_SAFETY_SYSTEM.md) | High-level overview | 5-10 min | Understanding the system |
| [QUICKSTART.md](QUICKSTART.md) | Quick setup & reference | 5-15 min | Getting running fast |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Complete system design | 20-30 min | Understanding design |
| [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) | Step-by-step implementation | 20-30 min | Hands-on learning |
| [COMPLETE_IMPLEMENTATION.md](COMPLETE_IMPLEMENTATION.md) | Full technical spec | 45-60 min | Deep technical understanding |
| [DELIVERY_SUMMARY.md](DELIVERY_SUMMARY.md) | Project status & metrics | 15-20 min | Project overview |
| [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) | Navigation guide | 5-10 min | Finding what you need |

**👉 Start with**: [README_SAFETY_SYSTEM.md](README_SAFETY_SYSTEM.md) or [QUICKSTART.md](QUICKSTART.md)

**Full documentation navigation**: See [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)

## 🎯 Expected Results

After completing all steps successfully, you should have:

✅ Autonomous vehicle safety system protecting against 7 threat classes  
✅ Real-time threat detection with intelligent scoring (0-100)  
✅ Automated execution of 5 safety maneuvers via CAN commands  
✅ Incident reports with threat timelines  
✅ 17 unit tests validating all safety mechanisms  
✅ Statistical analysis of attack patterns

## 📚 Additional Resources

- **Safety System**: [README_SAFETY_SYSTEM.md](README_SAFETY_SYSTEM.md) - Overview of the autonomous vehicle protection system
- **Quick Start**: [QUICKSTART.md](QUICKSTART.md) - 5-minute setup and common tasks
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) - Complete system design with 9 sections
- **Implementation**: [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) - Step-by-step integration guide
- **Full Spec**: [COMPLETE_IMPLEMENTATION.md](COMPLETE_IMPLEMENTATION.md) - Comprehensive technical specification
- **Suricata Documentation**: [Suricata Official Docs](https://suricata.readthedocs.io/)
- **CAN Bus Protocol Overview**: [CAN Bus Wikipedia](https://en.wikipedia.org/wiki/CAN_bus)
- **Writing Suricata Rules**: [Suricata Rules Guide](https://suricata.readthedocs.io/en/latest/rules/)

## 🤝 Contributing

Feel free to enhance this project by:

- Adding new threat detection patterns
- Creating additional safety maneuvers
- Enhancing the threat scoring algorithm
- Expanding the test suite
- Improving visualization techniques
- Adding simulator integration (CARLA, LGSVL)
- Implementing machine learning anomaly detection

## 📄 License

This project is for educational and research purposes.

---

## 🎯 Key Statistics

| Metric | Value |
|--------|-------|
| Threat Classes | 7 |
| Safety Maneuvers | 5 |
| Detection Rules | 10 |
| Safety Constraints | 8 |
| Fail-Safe Mechanisms | 5 |
| Vehicle Control Modules | 5 |
| Threat Scoring Range | 0-100 |
| Unit Tests | 17 |
| Code Lines | 1,400+ |
| Documentation Lines | 1,950+ |

---

## 🚀 Quick Start Summary

### For Safety System Users:
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run test suite
python3 code/test_safety_controller.py

# 3. Try a quick example (see QUICKSTART.md)
```

### For IDS Users:
```bash
# 1. Generate traffic
python3 code/generate_pcap.py

# 2. Run Suricata
sudo suricata -r packets/can_sim.pcap \
  -c suricata.yaml \
  -S rules/can.rules \
  -l suricata_logs \
  --runmode=single -vv

# 3. Visualize
jupyter notebook code/visualize.ipynb
```

---

## 📖 Learning Paths

**Path 1: Executive Summary (15 minutes)**
1. [README_SAFETY_SYSTEM.md](README_SAFETY_SYSTEM.md) (5 min)
2. [QUICKSTART.md](QUICKSTART.md) overview (5 min)  
3. [DELIVERY_SUMMARY.md](DELIVERY_SUMMARY.md) (5 min)

**Path 2: Technical Overview (1 hour)**
1. [README_SAFETY_SYSTEM.md](README_SAFETY_SYSTEM.md) (5 min)
2. [QUICKSTART.md](QUICKSTART.md) (10 min)
3. [ARCHITECTURE.md](ARCHITECTURE.md) (30 min)
4. [COMPLETE_IMPLEMENTATION.md](COMPLETE_IMPLEMENTATION.md) sections 1-2 (15 min)

**Path 3: Full Implementation (2 hours)**
1. [QUICKSTART.md](QUICKSTART.md) (15 min)
2. [ARCHITECTURE.md](ARCHITECTURE.md) (30 min)
3. [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) (30 min)
4. Code review (30 min)
5. Run tests (15 min)

---

**🎉 Welcome to the CAN Bus Autonomous Vehicle Safety System!**

For detailed guidance, start with [README_SAFETY_SYSTEM.md](README_SAFETY_SYSTEM.md) or [QUICKSTART.md](QUICKSTART.md).

For documentation navigation, see [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md).
