"""
CAN Bus IDS Model Evaluation Script

Evaluates the trained model with comprehensive metrics as specified in INSTRUCTIONS.md:
- Inference time (target: < 5ms)
- End-to-end latency (target: < 15ms)
- Detection accuracy per attack type
- False Positive Rate on normal traffic
- ROC-AUC and PR-AUC curves
- Per-class precision, recall, F1 scores
"""

import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, 
    precision_recall_curve, auc, roc_curve, f1_score,
    precision_score, recall_score, accuracy_score
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import label_binarize
import matplotlib.pyplot as plt
import seaborn as sns
import time
import pickle
import os

# Class names matching the training labels
CLASS_NAMES = ['normal', 'DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing']

# Performance targets from INSTRUCTIONS.md
TARGETS = {
    'inference_time_ms': 5.0,
    'end_to_end_latency_ms': 15.0,
    'cpu_usage_percent': 40.0,
    'memory_mb': 300.0
}

class SimpleNN(nn.Module):
    def __init__(self, input_size=19, num_classes=5):
        super(SimpleNN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, num_classes)
        )

    def forward(self, x):
        return self.net(x)


def measure_single_frame_latency(model, sample, n_iterations=1000):
    """Measure inference latency for single frames (realistic scenario)"""
    latencies = []
    sample_tensor = torch.tensor(sample.reshape(1, -1), dtype=torch.float32)
    
    # Warm up
    for _ in range(100):
        with torch.no_grad():
            _ = model(sample_tensor)
    
    # Measure
    for _ in range(n_iterations):
        start = time.perf_counter()
        with torch.no_grad():
            _ = model(sample_tensor)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # ms
    
    return np.array(latencies)


def evaluate_model():
    """Main evaluation function with comprehensive metrics and visualizations"""
    
    print("=" * 60)
    print("CAN Bus IDS Model Evaluation")
    print("=" * 60)
    
    # Load data
    X = np.load('outputs/X.npy')
    y = np.load('outputs/y.npy')
    
    print(f"\nDataset: {len(X)} samples")
    print(f"Class distribution:")
    for i, name in enumerate(CLASS_NAMES):
        count = np.sum(y == i)
        print(f"  {name}: {count} ({100*count/len(y):.1f}%)")
    
    # Load model config
    model_config = pickle.load(open('outputs/model_config.pkl', 'rb'))
    input_size = model_config['input_size']
    num_classes = model_config['num_classes']
    feature_type = model_config.get('feature_type', 'unknown')
    
    print(f"\nModel Configuration:")
    print(f"  Input size: {input_size}")
    print(f"  Num classes: {num_classes}")
    print(f"  Feature type: {feature_type}")

    # Split into train and test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\nTest set: {len(X_test)} samples")

    # Load scaler and transform test
    scaler = pickle.load(open('outputs/scaler.pkl', 'rb'))
    X_test_scaled = scaler.transform(X_test)

    # Load model
    model = SimpleNN(input_size=input_size, num_classes=num_classes)
    model.load_state_dict(torch.load('models/best_model.pt', weights_only=True))
    model.eval()

    # Convert to tensors
    X_test_tensor = torch.tensor(X_test_scaled, dtype=torch.float32)
    y_test_tensor = torch.tensor(y_test, dtype=torch.long)

    # ============== BATCH INFERENCE ==============
    print("\n" + "=" * 60)
    print("BATCH INFERENCE METRICS")
    print("=" * 60)
    
    start_time = time.time()
    with torch.no_grad():
        outputs = model(X_test_tensor)
        probs = torch.softmax(outputs, dim=1)
        preds = torch.argmax(probs, dim=1).numpy()
    end_time = time.time()
    
    total_time = end_time - start_time
    batch_latency_per_frame = (total_time / len(X_test)) * 1000
    batch_throughput = len(X_test) / total_time
    
    print(f"Batch inference time: {total_time*1000:.2f} ms for {len(X_test)} frames")
    print(f"Average latency per frame: {batch_latency_per_frame:.4f} ms")
    print(f"Throughput: {batch_throughput:.0f} frames/sec")

    # ============== SINGLE FRAME LATENCY ==============
    print("\n" + "=" * 60)
    print("SINGLE FRAME LATENCY (Realistic Scenario)")
    print("=" * 60)
    
    latencies = measure_single_frame_latency(model, X_test_scaled[0])
    
    print(f"Single frame inference latency:")
    print(f"  Mean: {np.mean(latencies):.4f} ms")
    print(f"  Median: {np.median(latencies):.4f} ms")
    print(f"  Std: {np.std(latencies):.4f} ms")
    print(f"  Min: {np.min(latencies):.4f} ms")
    print(f"  Max: {np.max(latencies):.4f} ms")
    print(f"  95th percentile: {np.percentile(latencies, 95):.4f} ms")
    print(f"  99th percentile: {np.percentile(latencies, 99):.4f} ms")
    
    # Check against target
    target_met = np.mean(latencies) < TARGETS['inference_time_ms']
    status = "PASS" if target_met else "FAIL"
    print(f"\n  Target (< {TARGETS['inference_time_ms']} ms): {status}")

    # ============== CLASSIFICATION METRICS ==============
    print("\n" + "=" * 60)
    print("CLASSIFICATION METRICS")
    print("=" * 60)
    
    # Overall accuracy
    accuracy = accuracy_score(y_test, preds)
    print(f"\nOverall Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Detailed classification report
    print("\nClassification Report:")
    print("-" * 60)
    report = classification_report(y_test, preds, target_names=CLASS_NAMES, digits=4)
    print(report)

    # Per-class metrics
    precision_per_class = precision_score(y_test, preds, average=None)
    recall_per_class = recall_score(y_test, preds, average=None)
    f1_per_class = f1_score(y_test, preds, average=None)
    
    print("\nPer-Class Detection Rates:")
    print("-" * 60)
    print(f"{'Class':<15} {'Precision':>10} {'Recall':>10} {'F1':>10}")
    print("-" * 60)
    for i, name in enumerate(CLASS_NAMES):
        print(f"{name:<15} {precision_per_class[i]:>10.4f} {recall_per_class[i]:>10.4f} {f1_per_class[i]:>10.4f}")

    # ============== FALSE POSITIVE ANALYSIS ==============
    print("\n" + "=" * 60)
    print("FALSE POSITIVE ANALYSIS")
    print("=" * 60)
    
    # FPR for normal traffic (misclassified as attack)
    normal_mask = y_test == 0
    normal_preds = preds[normal_mask]
    normal_correct = np.sum(normal_preds == 0)
    normal_false_positive = np.sum(normal_preds != 0)
    fpr_normal = normal_false_positive / len(normal_preds) if len(normal_preds) > 0 else 0
    
    print(f"\nNormal Traffic Analysis:")
    print(f"  Total normal samples: {np.sum(normal_mask)}")
    print(f"  Correctly classified: {normal_correct}")
    print(f"  False positives (normal->attack): {normal_false_positive}")
    print(f"  False Positive Rate: {fpr_normal:.4f} ({fpr_normal*100:.2f}%)")
    
    # Per-attack false negative rate (attacks missed)
    print("\nAttack Detection Analysis:")
    for i, name in enumerate(CLASS_NAMES[1:], 1):  # Skip normal
        attack_mask = y_test == i
        attack_preds = preds[attack_mask]
        if len(attack_preds) > 0:
            detected = np.sum(attack_preds == i)
            missed = np.sum(attack_preds != i)
            detection_rate = detected / len(attack_preds)
            print(f"  {name}: {detected}/{len(attack_preds)} detected ({detection_rate*100:.2f}%)")

    # ============== CONFUSION MATRIX ==============
    print("\n" + "=" * 60)
    print("CONFUSION MATRIX")
    print("=" * 60)
    
    cm = confusion_matrix(y_test, preds)
    print("\nRaw counts:")
    print(cm)
    
    # Normalized confusion matrix
    cm_normalized = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    print("\nNormalized (row-wise %):")
    for i, row in enumerate(cm_normalized):
        print(f"  {CLASS_NAMES[i]:<15}: {' '.join([f'{v*100:6.2f}%' for v in row])}")

    # ============== ROC / PR CURVES ==============
    print("\n" + "=" * 60)
    print("ROC-AUC AND PR-AUC METRICS")
    print("=" * 60)
    
    # Binary: attack vs normal
    y_binary = (y_test != 0).astype(int)  # 1 for attack, 0 for normal
    probs_attack = 1 - probs[:, 0].numpy()  # P(attack) = 1 - P(normal)
    
    fpr_roc, tpr_roc, thresholds_roc = roc_curve(y_binary, probs_attack)
    roc_auc = auc(fpr_roc, tpr_roc)
    
    precision_curve, recall_curve, thresholds_pr = precision_recall_curve(y_binary, probs_attack)
    pr_auc = auc(recall_curve, precision_curve)
    
    print(f"\nBinary (Attack vs Normal):")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    print(f"  PR-AUC: {pr_auc:.4f}")
    
    # Multi-class ROC-AUC (One-vs-Rest)
    probs_np = probs.numpy()
    y_onehot = label_binarize(y_test, classes=range(num_classes))
    
    roc_auc_per_class = {}
    for i, name in enumerate(CLASS_NAMES):
        if len(np.unique(y_onehot[:, i])) > 1:
            roc_auc_per_class[name] = roc_auc_score(y_onehot[:, i], probs_np[:, i])
        else:
            roc_auc_per_class[name] = float('nan')
    
    print(f"\nPer-Class ROC-AUC (One-vs-Rest):")
    for name, auc_val in roc_auc_per_class.items():
        print(f"  {name}: {auc_val:.4f}")
    
    # Macro and weighted average
    valid_aucs = [v for v in roc_auc_per_class.values() if not np.isnan(v)]
    macro_auc = np.mean(valid_aucs)
    print(f"\n  Macro-average ROC-AUC: {macro_auc:.4f}")

    # ============== VISUALIZATIONS ==============
    print("\n" + "=" * 60)
    print("GENERATING VISUALIZATIONS")
    print("=" * 60)
    
    # Create output directory if needed
    os.makedirs('outputs', exist_ok=True)
    
    # Use a clean style
    plt.style.use('default')
    fig = plt.figure(figsize=(18, 14))
    
    # 1. Confusion Matrix Heatmap
    ax1 = fig.add_subplot(2, 3, 1)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, ax=ax1)
    ax1.set_title('Confusion Matrix (Counts)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('True Label')
    ax1.set_xlabel('Predicted Label')
    plt.setp(ax1.get_xticklabels(), rotation=45, ha='right')
    plt.setp(ax1.get_yticklabels(), rotation=0)
    
    # 2. Normalized Confusion Matrix
    ax2 = fig.add_subplot(2, 3, 2)
    sns.heatmap(cm_normalized, annot=True, fmt='.2%', cmap='RdYlGn', 
                xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES, ax=ax2,
                vmin=0, vmax=1)
    ax2.set_title('Confusion Matrix (Normalized %)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('True Label')
    ax2.set_xlabel('Predicted Label')
    plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')
    plt.setp(ax2.get_yticklabels(), rotation=0)
    
    # 3. ROC Curve
    ax3 = fig.add_subplot(2, 3, 3)
    ax3.plot(fpr_roc, tpr_roc, 'b-', linewidth=2, label=f'ROC (AUC = {roc_auc:.4f})')
    ax3.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
    ax3.fill_between(fpr_roc, tpr_roc, alpha=0.2)
    ax3.set_xlim([0.0, 1.0])
    ax3.set_ylim([0.0, 1.05])
    ax3.set_xlabel('False Positive Rate')
    ax3.set_ylabel('True Positive Rate')
    ax3.set_title('ROC Curve (Attack vs Normal)', fontsize=12, fontweight='bold')
    ax3.legend(loc='lower right')
    ax3.grid(True, alpha=0.3)
    
    # 4. Precision-Recall Curve
    ax4 = fig.add_subplot(2, 3, 4)
    ax4.plot(recall_curve, precision_curve, 'g-', linewidth=2, label=f'PR (AUC = {pr_auc:.4f})')
    ax4.fill_between(recall_curve, precision_curve, alpha=0.2, color='green')
    ax4.set_xlim([0.0, 1.0])
    ax4.set_ylim([0.0, 1.05])
    ax4.set_xlabel('Recall')
    ax4.set_ylabel('Precision')
    ax4.set_title('Precision-Recall Curve (Attack vs Normal)', fontsize=12, fontweight='bold')
    ax4.legend(loc='lower left')
    ax4.grid(True, alpha=0.3)
    
    # 5. Per-Class Metrics Bar Chart
    ax5 = fig.add_subplot(2, 3, 5)
    x = np.arange(len(CLASS_NAMES))
    width = 0.25
    
    bars1 = ax5.bar(x - width, precision_per_class, width, label='Precision', color='steelblue')
    bars2 = ax5.bar(x, recall_per_class, width, label='Recall', color='forestgreen')
    bars3 = ax5.bar(x + width, f1_per_class, width, label='F1', color='coral')
    
    ax5.set_ylabel('Score')
    ax5.set_title('Per-Class Metrics', fontsize=12, fontweight='bold')
    ax5.set_xticks(x)
    ax5.set_xticklabels(CLASS_NAMES, rotation=45, ha='right')
    ax5.legend(loc='lower right')
    ax5.set_ylim([0, 1.1])
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax5.annotate(f'{height:.2f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=7)
    
    # 6. Latency Distribution
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.hist(latencies, bins=50, color='purple', alpha=0.7, edgecolor='black')
    ax6.axvline(np.mean(latencies), color='red', linestyle='--', linewidth=2, 
                label=f'Mean: {np.mean(latencies):.3f} ms')
    ax6.axvline(TARGETS['inference_time_ms'], color='green', linestyle='-', linewidth=2,
                label=f'Target: {TARGETS["inference_time_ms"]} ms')
    ax6.set_xlabel('Inference Time (ms)')
    ax6.set_ylabel('Frequency')
    ax6.set_title('Single Frame Inference Latency Distribution', fontsize=12, fontweight='bold')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('outputs/evaluation_plots.png', dpi=300, bbox_inches='tight')
    print("  Saved: outputs/evaluation_plots.png")
    
    # ============== ADDITIONAL VISUALIZATIONS ==============
    
    # Figure 2: Detection Performance Summary
    fig2 = plt.figure(figsize=(14, 10))
    
    # 1. Detection Rate by Attack Type
    ax7 = fig2.add_subplot(2, 2, 1)
    detection_rates = []
    for i, name in enumerate(CLASS_NAMES):
        mask = y_test == i
        if np.sum(mask) > 0:
            rate = np.sum(preds[mask] == i) / np.sum(mask)
            detection_rates.append(rate)
        else:
            detection_rates.append(0)
    
    colors = ['green' if r > 0.95 else 'orange' if r > 0.9 else 'red' for r in detection_rates]
    bars = ax7.bar(CLASS_NAMES, detection_rates, color=colors, edgecolor='black')
    ax7.axhline(y=0.95, color='green', linestyle='--', label='Excellent (95%)')
    ax7.axhline(y=0.90, color='orange', linestyle='--', label='Good (90%)')
    ax7.set_ylabel('Detection Rate')
    ax7.set_title('Detection Rate by Class', fontsize=12, fontweight='bold')
    ax7.set_ylim([0, 1.1])
    ax7.legend()
    plt.setp(ax7.get_xticklabels(), rotation=45, ha='right')
    
    for bar, rate in zip(bars, detection_rates):
        ax7.annotate(f'{rate*100:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, rate),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 2. Per-Class ROC-AUC
    ax8 = fig2.add_subplot(2, 2, 2)
    auc_values = [roc_auc_per_class[name] for name in CLASS_NAMES]
    colors = ['green' if v > 0.95 else 'orange' if v > 0.9 else 'red' for v in auc_values]
    bars = ax8.bar(CLASS_NAMES, auc_values, color=colors, edgecolor='black')
    ax8.axhline(y=0.95, color='green', linestyle='--', label='Excellent')
    ax8.axhline(y=0.90, color='orange', linestyle='--', label='Good')
    ax8.set_ylabel('ROC-AUC')
    ax8.set_title('Per-Class ROC-AUC (One-vs-Rest)', fontsize=12, fontweight='bold')
    ax8.set_ylim([0, 1.1])
    ax8.legend()
    plt.setp(ax8.get_xticklabels(), rotation=45, ha='right')
    
    for bar, val in zip(bars, auc_values):
        if not np.isnan(val):
            ax8.annotate(f'{val:.3f}',
                        xy=(bar.get_x() + bar.get_width() / 2, val),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 3. Confidence Distribution for Correct Predictions
    ax9 = fig2.add_subplot(2, 2, 3)
    correct_mask = preds == y_test
    correct_confidences = probs_np[np.arange(len(preds)), preds][correct_mask]
    incorrect_confidences = probs_np[np.arange(len(preds)), preds][~correct_mask]
    
    ax9.hist(correct_confidences, bins=50, alpha=0.7, label=f'Correct ({len(correct_confidences)})', 
             color='green', edgecolor='black')
    if len(incorrect_confidences) > 0:
        ax9.hist(incorrect_confidences, bins=50, alpha=0.7, label=f'Incorrect ({len(incorrect_confidences)})', 
                 color='red', edgecolor='black')
    ax9.set_xlabel('Prediction Confidence')
    ax9.set_ylabel('Frequency')
    ax9.set_title('Confidence Distribution', fontsize=12, fontweight='bold')
    ax9.legend()
    ax9.grid(True, alpha=0.3)
    
    # 4. Performance Summary Table
    ax10 = fig2.add_subplot(2, 2, 4)
    ax10.axis('off')
    
    summary_data = [
        ['Metric', 'Value', 'Target', 'Status'],
        ['Accuracy', f'{accuracy*100:.2f}%', '>95%', 'PASS' if accuracy > 0.95 else 'FAIL'],
        ['Inference Time', f'{np.mean(latencies):.3f} ms', f'<{TARGETS["inference_time_ms"]} ms', 
         'PASS' if np.mean(latencies) < TARGETS['inference_time_ms'] else 'FAIL'],
        ['ROC-AUC', f'{roc_auc:.4f}', '>0.95', 'PASS' if roc_auc > 0.95 else 'FAIL'],
        ['PR-AUC', f'{pr_auc:.4f}', '>0.95', 'PASS' if pr_auc > 0.95 else 'FAIL'],
        ['FPR (Normal)', f'{fpr_normal*100:.2f}%', '<5%', 'PASS' if fpr_normal < 0.05 else 'FAIL'],
        ['Throughput', f'{batch_throughput:.0f} fps', '-', '-'],
    ]
    
    table = ax10.table(cellText=summary_data[1:], colLabels=summary_data[0],
                       cellLoc='center', loc='center',
                       colColours=['lightblue']*4)
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Color the status column
    for i in range(1, len(summary_data)):
        status = summary_data[i][3]
        if status == 'PASS':
            table[(i, 3)].set_facecolor('lightgreen')
        elif status == 'FAIL':
            table[(i, 3)].set_facecolor('lightcoral')
    
    ax10.set_title('Performance Summary', fontsize=12, fontweight='bold', y=0.95)
    
    plt.tight_layout()
    plt.savefig('outputs/evaluation_summary.png', dpi=300, bbox_inches='tight')
    print("  Saved: outputs/evaluation_summary.png")
    
    # ============== MULTI-CLASS ROC CURVES ==============
    fig3 = plt.figure(figsize=(10, 8))
    ax11 = fig3.add_subplot(1, 1, 1)
    
    colors = plt.cm.Set1(np.linspace(0, 1, num_classes))
    for i, (name, color) in enumerate(zip(CLASS_NAMES, colors)):
        if len(np.unique(y_onehot[:, i])) > 1:
            fpr_i, tpr_i, _ = roc_curve(y_onehot[:, i], probs_np[:, i])
            auc_i = roc_auc_per_class[name]
            ax11.plot(fpr_i, tpr_i, color=color, linewidth=2, 
                     label=f'{name} (AUC = {auc_i:.4f})')
    
    ax11.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random')
    ax11.set_xlim([0.0, 1.0])
    ax11.set_ylim([0.0, 1.05])
    ax11.set_xlabel('False Positive Rate', fontsize=12)
    ax11.set_ylabel('True Positive Rate', fontsize=12)
    ax11.set_title('Multi-Class ROC Curves (One-vs-Rest)', fontsize=14, fontweight='bold')
    ax11.legend(loc='lower right')
    ax11.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('outputs/multiclass_roc.png', dpi=300, bbox_inches='tight')
    print("  Saved: outputs/multiclass_roc.png")
    
    # ============== FINAL SUMMARY ==============
    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    
    print("\nResults Summary:")
    print(f"  - Accuracy: {accuracy*100:.2f}%")
    print(f"  - ROC-AUC: {roc_auc:.4f}")
    print(f"  - PR-AUC: {pr_auc:.4f}")
    print(f"  - Inference Time: {np.mean(latencies):.3f} ms (target: <{TARGETS['inference_time_ms']} ms)")
    print(f"  - FPR (Normal): {fpr_normal*100:.2f}%")
    print(f"  - Throughput: {batch_throughput:.0f} frames/sec")
    
    print("\nVisualization files saved:")
    print("  - outputs/evaluation_plots.png")
    print("  - outputs/evaluation_summary.png")
    print("  - outputs/multiclass_roc.png")
    
    # Return metrics for programmatic use
    return {
        'accuracy': accuracy,
        'roc_auc': roc_auc,
        'pr_auc': pr_auc,
        'inference_time_ms': np.mean(latencies),
        'fpr_normal': fpr_normal,
        'throughput': batch_throughput,
        'per_class_f1': dict(zip(CLASS_NAMES, f1_per_class)),
        'per_class_auc': roc_auc_per_class
    }


if __name__ == "__main__":
    metrics = evaluate_model()
