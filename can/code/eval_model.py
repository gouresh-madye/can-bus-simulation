import torch
import torch.nn as nn
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, precision_recall_curve, auc, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import label_binarize
import matplotlib.pyplot as plt
import time
import pickle

class SimpleNN(nn.Module):
    def __init__(self, input_size=18, num_classes=5):
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

def evaluate_model():
    # Load data
    X = np.load('outputs/X.npy')
    y = np.load('outputs/y.npy')
    
    # Load model config
    model_config = pickle.load(open('outputs/model_config.pkl', 'rb'))
    input_size = model_config['input_size']
    num_classes = model_config['num_classes']

    # Split into train+val and test (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # Load scaler and transform test
    scaler = pickle.load(open('outputs/scaler.pkl', 'rb'))
    X_test = scaler.transform(X_test)

    # Load model
    model = SimpleNN(input_size=input_size, num_classes=num_classes)
    model.load_state_dict(torch.load('models/best_model.pt'))
    model.eval()

    # Test data to tensor
    X_test_tensor = torch.tensor(X_test, dtype=torch.float32)
    y_test_tensor = torch.tensor(y_test, dtype=torch.long)

    # Measure latency
    start_time = time.time()
    with torch.no_grad():
        outputs = model(X_test_tensor)
        probs = torch.softmax(outputs, dim=1)
        preds = torch.argmax(probs, dim=1).numpy()
    end_time = time.time()
    total_time = end_time - start_time
    latency_per_frame = (total_time / len(X_test)) * 1000  # ms
    throughput = len(X_test) / total_time  # frames/sec

    # Metrics
    print("Classification Report:")
    report = classification_report(y_test, preds, target_names=['normal', 'DoS', 'fuzzing', 'rpm_spoofing', 'gear_spoofing'])
    print(report)

    # Confusion Matrix
    cm = confusion_matrix(y_test, preds)
    print("Confusion Matrix:")
    print(cm)

    # FPR for normal (class 0 vs rest)
    # Treat as binary: normal (0) vs attack (1-4)
    y_binary = (y_test == 0).astype(int)
    pred_binary = (preds == 0).astype(int)
    tn = np.sum((y_binary == 0) & (pred_binary == 0))
    fp = np.sum((y_binary == 0) & (pred_binary == 1))
    fn = np.sum((y_binary == 1) & (pred_binary == 0))
    tp = np.sum((y_binary == 1) & (pred_binary == 1))
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    print(f"False Positive Rate on normal traffic: {fpr:.4f}")

    # ROC and PR for attack vs normal
    y_binary_test = (y_test != 0).astype(int)  # 1 for attack, 0 for normal
    probs_binary = 1 - probs[:, 0].numpy()  # prob of attack

    # ROC
    fpr_roc, tpr_roc, _ = roc_curve(y_binary_test, probs_binary)
    roc_auc = auc(fpr_roc, tpr_roc)

    # PR
    precision, recall, _ = precision_recall_curve(y_binary_test, probs_binary)
    pr_auc = auc(recall, precision)

    print(f"ROC-AUC (attack vs normal): {roc_auc:.4f}")
    print(f"PR-AUC (attack vs normal): {pr_auc:.4f}")
    print(f"Average inference latency per frame: {latency_per_frame:.2f} ms")
    print(f"Throughput: {throughput:.2f} frames/sec")

    # Plots
    plt.figure(figsize=(12, 10))

    # Confusion Matrix
    plt.subplot(2, 2, 1)
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion Matrix')
    plt.colorbar()
    classes = ['normal', 'DoS', 'fuzzing', 'spoofing', 'replay']
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, format(cm[i, j], 'd'), ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")

    # ROC Curve
    plt.subplot(2, 2, 2)
    plt.plot(fpr_roc, tpr_roc, label=f'ROC curve (AUC = {roc_auc:.2f})')
    plt.plot([0, 1], [0, 1], 'k--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve (Attack vs Normal)')
    plt.legend(loc="lower right")

    # PR Curve
    plt.subplot(2, 2, 3)
    plt.plot(recall, precision, label=f'PR curve (AUC = {pr_auc:.2f})')
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curve (Attack vs Normal)')
    plt.legend(loc="lower left")

    # Bar plot for per-class F1
    from sklearn.metrics import f1_score
    f1_scores = f1_score(y_test, preds, average=None)
    plt.subplot(2, 2, 4)
    plt.bar(classes, f1_scores, color='skyblue')
    plt.title('Per-Class F1 Scores')
    plt.ylabel('F1 Score')
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig('outputs/evaluation_plots.png', dpi=300)
    plt.show()

if __name__ == "__main__":
    evaluate_model()
