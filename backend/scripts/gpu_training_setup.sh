#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# TimesFM Fine-Tuning: GPU Instance Setup Script
# ──────────────────────────────────────────────────────────────────────
#
# Run this on a rented GPU instance (vast.ai, RunPod, Lambda Labs).
# It installs all dependencies, downloads the base model, and starts
# training. Designed to be fully self-contained.
#
# Prerequisites:
#   - GPU instance with CUDA (A100 80GB recommended, A10 24GB minimum)
#   - Training data + finetune script uploaded to ~/nifty/
#
# Usage:
#   # 1. Upload files to the instance:
#   scp data/nse_nifty500_daily_30min.parquet <instance>:~/nifty/data.parquet
#   scp scripts/finetune_timesfm.py <instance>:~/nifty/finetune_timesfm.py
#   scp scripts/gpu_training_setup.sh <instance>:~/nifty/setup.sh
#
#   # 2. SSH in and run:
#   ssh <instance>
#   cd ~/nifty && bash setup.sh
#
#   # 3. When done, download results:
#   scp -r <instance>:~/nifty/checkpoints/timesfm_nse/ ./checkpoints/
#
# ──────────────────────────────────────────────────────────────────────

set -e

WORKDIR=~/nifty
cd "$WORKDIR"

echo "========================================"
echo "TimesFM Fine-Tuning Setup"
echo "========================================"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'none detected')"
echo "VRAM: $(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "CUDA: $(nvcc --version 2>/dev/null | grep release | awk '{print $6}' || echo 'N/A')"
echo ""

# ── Step 1: Install dependencies ─────────────────────────────────────
echo ">>> Installing Python dependencies..."

pip install --quiet --upgrade pip

# PyTorch (should come pre-installed on GPU instances, but just in case)
python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}')" 2>/dev/null || {
    echo "Installing PyTorch..."
    pip install --quiet torch
}

# TimesFM from source (PyTorch backend)
python3 -c "import timesfm" 2>/dev/null || {
    echo "Installing TimesFM..."
    pip install --quiet "timesfm[torch] @ git+https://github.com/google-research/timesfm.git"
}

# Data deps
pip install --quiet pandas pyarrow

echo "Dependencies installed."
python3 -c "
import torch
import timesfm
print(f'  PyTorch: {torch.__version__}')
print(f'  CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    print(f'  VRAM: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB')
print(f'  TimesFM: loaded')
"

# ── Step 2: Pre-download base model ──────────────────────────────────
echo ""
echo ">>> Pre-downloading TimesFM 2.5 base model..."
python3 -c "
import timesfm, torch
torch.set_float32_matmul_precision('high')
tfm = timesfm.TimesFM_2p5_200M_torch.from_pretrained('google/timesfm-2.5-200m-pytorch')
print('Base model downloaded and loaded successfully.')
print(f'Parameters: {sum(p.numel() for p in tfm.model.parameters()):,}')
"

# ── Step 3: Verify training data ─────────────────────────────────────
echo ""
echo ">>> Verifying training data..."
if [ ! -f "$WORKDIR/data.parquet" ]; then
    echo "ERROR: Training data not found at $WORKDIR/data.parquet"
    echo "Upload it with: scp data/nse_nifty500_daily_30min.parquet <instance>:~/nifty/data.parquet"
    exit 1
fi

python3 -c "
import pandas as pd
df = pd.read_parquet('data.parquet')
print(f'  Candles: {len(df):,}')
print(f'  Symbols: {df.symbol.nunique()}')
print(f'  Date range: {df.timestamp.min()} to {df.timestamp.max()}')
if 'interval' in df.columns:
    for iv, g in df.groupby('interval'):
        print(f'  [{iv}]: {g.symbol.nunique()} symbols, {len(g):,} candles')
"

# ── Step 4: Start training ───────────────────────────────────────────
echo ""
echo "========================================"
echo "Starting fine-tuning..."
echo "========================================"
echo "Config:"
echo "  Epochs: 50 (resume with --resume checkpoints/timesfm_nse/epoch_50.pt if val still improving)"
echo "  Batch size: 64"
echo "  LR: 1e-4 (SGD, warmup 5 epochs + cosine decay)"
echo "  Context: 512, Horizon: 128"
echo "  Loss: MSE + Quantile"
echo ""
echo "Checkpoints will be saved to: $WORKDIR/checkpoints/timesfm_nse/"
echo "Training log: $WORKDIR/training.log"
echo ""

# Use nohup so training survives SSH disconnection
nohup python3 finetune_timesfm.py \
    --data data.parquet \
    --epochs 50 \
    --batch-size 64 \
    --lr 1e-4 \
    --warmup-epochs 5 \
    --grad-clip 1.0 \
    --stride 32 \
    --context-len 512 \
    --horizon-len 128 \
    --loss-type mse+quantile \
    --device cuda \
    --num-workers 4 \
    --checkpoint-dir checkpoints/timesfm_nse \
    --save-every 10 \
    --log-interval 100 \
    > training.log 2>&1 &

TRAIN_PID=$!
echo "Training started (PID: $TRAIN_PID)"
echo ""
echo "Monitor with:"
echo "  tail -f $WORKDIR/training.log"
echo ""
echo "When complete, download results:"
echo "  scp -r <instance>:~/nifty/checkpoints/timesfm_nse/ ./checkpoints/"
echo ""
echo "Key files:"
echo "  checkpoints/timesfm_nse/best_model.pt   — best validation loss weights"
echo "  checkpoints/timesfm_nse/final_model.pt   — final epoch weights"
echo "  checkpoints/timesfm_nse/epoch_*.pt       — full checkpoints (resumable)"

# Wait a few seconds and show first log lines
sleep 5
echo ""
echo ">>> First log output:"
head -20 training.log 2>/dev/null || echo "(waiting for output...)"
