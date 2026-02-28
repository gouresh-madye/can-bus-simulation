import socket
import json
import time
import argparse
from data_parser import parse_txt

def normal_generator(num_frames=100, host='localhost', port=9998):
    """
    Generate normal CAN bus traffic from the dataset.
    
    Args:
        num_frames: Number of frames to send (default: 100)
        host: IDS server host (default: localhost)
        port: IDS server port (default: 9998)
    """
    frames = parse_txt('dataset/normal_run_data.txt')
    frames.sort(key=lambda x: x['timestamp'])
    frames = frames[:num_frames]
    
    if not frames:
        print("No frames loaded from dataset")
        return
    
    print(f"Sending {len(frames)} normal frames to {host}:{port}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    start_time = time.time()
    last_ts = frames[0]['timestamp']
    
    for i, frame in enumerate(frames):
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
            print(f"Sent {i + 1}/{len(frames)} frames")
    
    sock.close()
    print(f"Finished sending {len(frames)} normal frames")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate normal CAN bus traffic')
    parser.add_argument('--frames', type=int, default=100, help='Number of frames to send')
    parser.add_argument('--host', type=str, default='localhost', help='IDS server host')
    parser.add_argument('--port', type=int, default=9998, help='IDS server port')
    args = parser.parse_args()
    
    normal_generator(num_frames=args.frames, host=args.host, port=args.port)
