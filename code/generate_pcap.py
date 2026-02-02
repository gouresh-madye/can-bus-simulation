import csv
from scapy.all import *
import binascii

import os

# Determine script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Input CSV file (relative to script location)
csv_file = os.path.join(BASE_DIR, "../inputdata/simulated_can_logs.csv")

# Output PCAP file (relative to script location)
pcap_file = os.path.join(BASE_DIR, "../packets/can_sim.pcap")

packets = []

print(f"[+] Reading CAN log data from {csv_file}")

with open(csv_file, "r") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        try:
            # Parse each field
            can_id = int(row["CAN_ID"], 16)
            src_ip = row.get("SRC_IP", "192.168.0.1")
            dst_ip = row.get("DST_IP", "192.168.0.2")
            
            # Convert DATA hex string into bytes
            data_hex = row["DATA"].replace(" ", "").replace("0x", "")
            data_bytes = binascii.unhexlify(data_hex)
            
            # Build UDP packet (CAN-like)
            pkt = IP(src=src_ip, dst=dst_ip) / UDP(sport=5000 + i, dport=6000) / data_bytes
            packets.append(pkt)
        except Exception as e:
            print(f"[!] Skipping row {i+1} due to error: {e}")

# Write to PCAP
if packets:
    wrpcap(pcap_file, packets)
    print(f"[+] Generated PCAP: {pcap_file}")
    print(f"[+] Total packets written: {len(packets)}")
else:
    print("[-] No packets created. Please check your CSV format and data.")
