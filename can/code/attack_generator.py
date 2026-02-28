import socket
import json
import time
import argparse
from data_parser import parse_csv

def attack_generator(attack_type='DoS', num_frames=1000, host='localhost', port=9998):
    """
    Generate attack CAN bus traffic from the dataset.
    
    Args:
        attack_type: Type of attack ('DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing')
        num_frames: Number of attack frames to send (default: 1000)
        host: IDS server host (default: localhost)
        port: IDS server port (default: 9998)
    """
    file_map = {
        'DoS': 'DoS_dataset.csv', 
        'fuzzing': 'Fuzzy_dataset.csv', 
        'rpm_spoofing': 'RPM_dataset.csv', 
        'gear_spoofing': 'gear_dataset.csv'
    }
    
    if attack_type not in file_map:
        print(f"Unknown attack type: {attack_type}")
        print(f"Available types: {list(file_map.keys())}")
        return
    
    # Parse only attack frames (T labels) from the CSV
    _, attack_frames = parse_csv(f'dataset/{file_map[attack_type]}', attack_type)
    attack_frames.sort(key=lambda x: x['timestamp'])
    attack_frames = attack_frames[:num_frames]
    
    if not attack_frames:
        print(f"No attack frames loaded for {attack_type}")
        return
    
    print(f"Sending {len(attack_frames)} {attack_type} attack frames to {host}:{port}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    start_time = time.time()
    last_ts = attack_frames[0]['timestamp']
    
    for i, frame in enumerate(attack_frames):
        current_time = time.time()
        sleep_time = (frame['timestamp'] - last_ts) - (current_time - start_time)
        if sleep_time > 0:
            time.sleep(sleep_time)
        start_time = time.time()
        last_ts = frame['timestamp']
        
        # Strip label before sending (don't reveal ground truth to IDS)
        frame_to_send = {
            'timestamp': frame['timestamp'],
            'id': frame['id'],
            'dlc': frame['dlc'],
            'data': frame['data']
        }
        data = json.dumps(frame_to_send) + '\n'
        sock.sendall(data.encode('utf-8'))
        
        if (i + 1) % 100 == 0:
            print(f"Sent {i + 1}/{len(attack_frames)} frames")
    
    sock.close()
    print(f"Finished sending {len(attack_frames)} {attack_type} attack frames")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate attack CAN bus traffic')
    parser.add_argument('--type', type=str, default='DoS', 
                        choices=['DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing'],
                        help='Type of attack to generate')
    parser.add_argument('--frames', type=int, default=1000, help='Number of frames to send')
    parser.add_argument('--host', type=str, default='localhost', help='IDS server host')
    parser.add_argument('--port', type=int, default=9998, help='IDS server port')
    args = parser.parse_args()
    
    attack_generator(attack_type=args.type, num_frames=args.frames, host=args.host, port=args.port)
