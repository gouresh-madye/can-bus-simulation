import numpy as np
from collections import Counter
from feature_extractor import FeatureExtractor
from data_parser import load_dataset

def build_features_and_labels(dataset_dir, samples_per_class=50000, use_stateless=True):
    """
    Build feature matrix and labels from the dataset.
    
    Args:
        dataset_dir: Path to dataset directory
        samples_per_class: Number of samples per class for balanced dataset
        use_stateless: If True, use stateless per-frame features (recommended for training)
                       If False, use stateful temporal features
    
    Returns:
        X: Feature matrix (n_samples, n_features)
        y: Label vector (n_samples,)
    """
    # Load balanced and shuffled dataset
    data = load_dataset(dataset_dir, samples_per_class=samples_per_class)
    
    # Updated label map with correct attack types
    label_map = {
        'normal': 0, 
        'DoS': 1, 
        'fuzzing': 2, 
        'rpm_spoofing': 3,   # Previously 'spoofing'
        'gear_spoofing': 4   # Previously 'replay'
    }
    
    X = []
    y = []
    
    if use_stateless:
        # Use stateless per-frame features (no temporal dependencies)
        # This is recommended for training to avoid order-dependent features
        for frame, label in data:
            features = FeatureExtractor.extract_stateless(frame)
            X.append(features)
            y.append(label_map[label])
    else:
        # Use stateful features with a fresh extractor
        # Reset state for each processing to ensure consistency
        extractor = FeatureExtractor()
        for frame, label in data:
            features = extractor.update(frame)
            X.append(features)
            y.append(label_map[label])
    
    X = np.array(X)
    y = np.array(y)
    
    return X, y

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Build features from CAN bus dataset')
    parser.add_argument('--samples', type=int, default=50000, 
                        help='Number of samples per class (default: 50000)')
    parser.add_argument('--stateful', action='store_true',
                        help='Use stateful temporal features instead of stateless')
    args = parser.parse_args()
    
    print(f"Building features with {args.samples} samples per class...")
    print(f"Feature mode: {'stateful' if args.stateful else 'stateless'}")
    
    X, y = build_features_and_labels(
        'dataset', 
        samples_per_class=args.samples,
        use_stateless=not args.stateful
    )
    
    np.save('outputs/X.npy', X)
    np.save('outputs/y.npy', y)
    
    print(f"\nFeatures shape: {X.shape}, Labels shape: {y.shape}")
    print(f"\nClass distribution:")
    label_names = ['normal', 'DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing']
    counts = Counter(y)
    for i, name in enumerate(label_names):
        print(f"  {name}: {counts[i]} samples")
