#!/usr/bin/env python3
"""Fine-tune TimesFM 2.5 on NSE stock data.

Adapts PFN's methodology (log-transform, MSE loss, gradient clipping)
for the TimesFM 2.5 PyTorch API. Designed to run on a rented GPU
(vast.ai A100, RunPod, etc.) with the training data parquet file.

Architecture notes:
  - TimesFM 2.5 forward() expects patched inputs: (B, num_patches, 32)
  - Output: output_ts shape (B, num_patches, 1280) = (B, patches, 128*10)
  - Reshape to (B, patches, 128, 10) — 128 horizon steps, 10 quantiles
  - Index 5 = median (point forecast), indices 0-4,6-9 = quantiles
  - forward() does NOT apply RevIN — we pre-normalize with log-transform

Usage:
  # Quick test (tiny subset, CPU)
  python scripts/finetune_timesfm.py --data data/nse_nifty500_daily_30min.parquet \\
    --epochs 2 --batch-size 4 --device cpu --max-symbols 10

  # Full training (GPU)
  python scripts/finetune_timesfm.py --data data/nse_nifty500_daily_30min.parquet \\
    --epochs 100 --batch-size 64 --lr 1e-4 --device cuda

  # Resume from checkpoint
  python scripts/finetune_timesfm.py --data data/nse_nifty500_daily_30min.parquet \\
    --resume checkpoints/epoch_50.pt
"""

import argparse
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

try:
    import pandas as pd
except ImportError:
    print("pandas required: pip install pandas pyarrow", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Dataset ──────────────────────────────────────────────────────────────


class TimeSeriesDataset(Dataset):
    """Sliding window dataset over stock price series.

    For each symbol's price history, creates overlapping windows of
    (context, target) pairs. Applies log1p transform for scale normalization.

    Following PFN's approach:
    - Log transform: log(price + 1) to handle scale differences
    - Random window sampling within each series for data augmentation
    - Context and target are contiguous segments
    """

    def __init__(
        self,
        df: pd.DataFrame,
        context_len: int = 512,
        horizon_len: int = 128,
        stride: int = 64,
        min_series_len: int = 640,
    ):
        """
        Args:
            df: DataFrame with columns [symbol, timestamp, close, interval]
            context_len: Number of input time steps (must be multiple of 32)
            horizon_len: Number of target time steps to predict
            stride: Step size between windows (smaller = more overlap = more data)
            min_series_len: Minimum series length to include
        """
        assert context_len % 32 == 0, f"context_len must be multiple of 32, got {context_len}"

        self.context_len = context_len
        self.horizon_len = horizon_len
        self.windows: list[tuple[np.ndarray, np.ndarray]] = []

        # Group by (symbol, interval) to keep daily and intraday separate
        group_cols = ["symbol", "interval"] if "interval" in df.columns else ["symbol"]

        for group_key, group_df in df.groupby(group_cols):
            closes = group_df["close"].values.astype(np.float32)

            if len(closes) < min_series_len:
                continue

            # Log transform (PFN methodology)
            log_closes = np.log1p(closes)

            # Create sliding windows
            total_len = context_len + horizon_len
            for start in range(0, len(log_closes) - total_len + 1, stride):
                context = log_closes[start : start + context_len]
                target = log_closes[start + context_len : start + total_len]
                self.windows.append((context, target))

        logger.info(
            f"Dataset: {len(self.windows):,} windows from "
            f"{df['symbol'].nunique()} symbols "
            f"(context={context_len}, horizon={horizon_len}, stride={stride})"
        )

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        context, target = self.windows[idx]
        return torch.from_numpy(context), torch.from_numpy(target)


# ── Training utilities ───────────────────────────────────────────────────


def create_lr_schedule(
    optimizer: torch.optim.Optimizer,
    warmup_epochs: int,
    total_epochs: int,
    steps_per_epoch: int,
) -> torch.optim.lr_scheduler.LambdaLR:
    """Linear warmup + cosine decay schedule (PFN's approach)."""
    warmup_steps = warmup_epochs * steps_per_epoch
    total_steps = total_epochs * steps_per_epoch

    def lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return step / max(warmup_steps, 1)
        progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def quantile_loss(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    quantiles: list[float],
) -> torch.Tensor:
    """Pinball / quantile loss across all quantile levels.

    Args:
        predictions: (B, horizon, num_quantiles)
        targets: (B, horizon)
    """
    targets = targets.unsqueeze(-1)  # (B, horizon, 1)
    errors = targets - predictions   # (B, horizon, num_quantiles)

    q = torch.tensor(quantiles, device=predictions.device, dtype=predictions.dtype)
    losses = torch.max(q * errors, (q - 1) * errors)
    return losses.mean()


def compute_loss(
    output_ts: torch.Tensor,
    targets: torch.Tensor,
    horizon: int,
    loss_type: str = "mse+quantile",
) -> torch.Tensor:
    """Compute training loss from model output.

    Args:
        output_ts: Raw model output (B, num_patches, 1280)
        targets: Ground truth (B, horizon)
        horizon: Number of steps to evaluate
        loss_type: "mse", "quantile", or "mse+quantile"
    """
    B = output_ts.shape[0]
    num_patches = output_ts.shape[1]

    # Reshape: (B, patches, 1280) → (B, patches, 128, 10)
    output_reshaped = output_ts.reshape(B, num_patches, 128, 10)

    # Last patch predictions: (B, 128, 10)
    last_patch = output_reshaped[:, -1, :horizon, :]

    # Point forecast = median (index 5)
    point_forecast = last_patch[:, :, 5]  # (B, horizon)

    loss = torch.tensor(0.0, device=output_ts.device)

    if "mse" in loss_type:
        mse = nn.functional.mse_loss(point_forecast, targets[:, :horizon])
        loss = loss + mse

    if "quantile" in loss_type:
        quantiles = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.5]
        qloss = quantile_loss(last_patch, targets[:, :horizon], quantiles)
        loss = loss + qloss

    return loss


# ── Main training loop ───────────────────────────────────────────────────


def train(args):
    device = torch.device(args.device)
    logger.info(f"Device: {device}")

    # ── Load data ────────────────────────────────────────────────────
    logger.info(f"Loading data from {args.data}...")
    df = pd.read_parquet(args.data)
    logger.info(f"Loaded {len(df):,} candles, {df['symbol'].nunique()} symbols")

    if args.interval and "interval" in df.columns:
        df = df[df["interval"] == args.interval]
        logger.info(f"Filtered to interval={args.interval}: {len(df):,} candles, {df['symbol'].nunique()} symbols")

    if args.max_symbols:
        symbols = sorted(df["symbol"].unique())[:args.max_symbols]
        df = df[df["symbol"].isin(symbols)]
        logger.info(f"Filtered to {args.max_symbols} symbols: {len(df):,} candles")

    # Train/val split: reserve the last (context_len + horizon_len) points per series
    # for validation, rest for training. This ensures at least 1 val window per series.
    val_window = args.context_len + args.horizon_len
    train_dfs = []
    val_dfs = []
    group_cols = ["symbol", "interval"] if "interval" in df.columns else ["symbol"]
    for _, group_df in df.groupby(group_cols):
        n = len(group_df)
        if n < val_window * 2:
            # Series too short for both train and val — use for training only
            train_dfs.append(group_df)
            continue
        train_dfs.append(group_df.iloc[:-val_window])
        val_dfs.append(group_df.iloc[-val_window * 2:])

    train_df = pd.concat(train_dfs, ignore_index=True)
    val_df = pd.concat(val_dfs, ignore_index=True)

    train_dataset = TimeSeriesDataset(
        train_df,
        context_len=args.context_len,
        horizon_len=args.horizon_len,
        stride=args.stride,
    )
    val_dataset = TimeSeriesDataset(
        val_df,
        context_len=args.context_len,
        horizon_len=args.horizon_len,
        stride=args.horizon_len,  # No overlap for validation
        min_series_len=args.context_len + args.horizon_len,  # Lower threshold for val
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
        drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
    )

    logger.info(f"Train: {len(train_dataset):,} windows, {len(train_loader)} batches")
    logger.info(f"Val: {len(val_dataset):,} windows, {len(val_loader)} batches")

    # ── Load model ───────────────────────────────────────────────────
    logger.info("Loading TimesFM 2.5 model...")
    import timesfm

    torch.set_float32_matmul_precision("high")

    tfm = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        args.base_model, torch_compile=False,
    )
    model = tfm.model  # The actual nn.Module
    model.train()
    model.to(device)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Model: {total_params:,} params ({trainable_params:,} trainable)")

    # ── Optimizer ────────────────────────────────────────────────────
    optimizer = torch.optim.SGD(
        model.parameters(),
        lr=args.lr,
        momentum=0.9,
        weight_decay=args.weight_decay,
    )

    scheduler = create_lr_schedule(
        optimizer,
        warmup_epochs=args.warmup_epochs,
        total_epochs=args.epochs,
        steps_per_epoch=len(train_loader),
    )

    # ── Resume from checkpoint ───────────────────────────────────────
    start_epoch = 0
    best_val_loss = float("inf")

    if args.resume:
        logger.info(f"Resuming from {args.resume}")
        ckpt = torch.load(args.resume, map_location=device, weights_only=False)
        if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
            # Full checkpoint (from periodic saves)
            model.load_state_dict(ckpt["model_state_dict"])
            optimizer.load_state_dict(ckpt["optimizer_state_dict"])
            scheduler.load_state_dict(ckpt["scheduler_state_dict"])
            start_epoch = ckpt["epoch"] + 1
            best_val_loss = ckpt.get("best_val_loss", float("inf"))
            logger.info(f"Resumed at epoch {start_epoch}, best_val_loss={best_val_loss:.6f}")
        else:
            # Raw state_dict (from best_model.pt) — load weights only, restart optimizer
            state_dict = ckpt if not isinstance(ckpt, dict) or "model_state_dict" not in ckpt else ckpt["model_state_dict"]
            model.load_state_dict(state_dict)
            start_epoch = args.resume_epoch if hasattr(args, "resume_epoch") and args.resume_epoch else 0
            logger.info(f"Loaded weights from {args.resume} (optimizer reset, starting epoch {start_epoch})")

    # ── Checkpointing setup ──────────────────────────────────────────
    ckpt_dir = Path(args.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # ── Training loop ────────────────────────────────────────────────
    logger.info(f"Starting training: {args.epochs} epochs, lr={args.lr}, batch_size={args.batch_size}")
    logger.info(f"Loss: {args.loss_type}, context={args.context_len}, horizon={args.horizon_len}")

    num_patches = args.context_len // 32

    for epoch in range(start_epoch, args.epochs):
        model.train()
        epoch_loss = 0.0
        epoch_steps = 0
        t_epoch = time.time()

        for batch_idx, (context, target) in enumerate(train_loader):
            context = context.to(device)  # (B, context_len)
            target = target.to(device)    # (B, horizon_len)

            # Patch inputs: (B, context_len) → (B, num_patches, 32)
            patched_input = context.reshape(-1, num_patches, 32)
            patched_mask = torch.zeros_like(patched_input, dtype=torch.bool)

            # Forward pass
            (_, _, output_ts, _), _ = model(patched_input, patched_mask)

            # Compute loss
            loss = compute_loss(output_ts, target, args.horizon_len, args.loss_type)

            # Backward
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=args.grad_clip)
            optimizer.step()
            scheduler.step()

            epoch_loss += loss.item()
            epoch_steps += 1

            if batch_idx % args.log_interval == 0 and batch_idx > 0:
                avg = epoch_loss / epoch_steps
                lr = scheduler.get_last_lr()[0]
                logger.info(
                    f"  Epoch {epoch+1}/{args.epochs} "
                    f"[{batch_idx}/{len(train_loader)}] "
                    f"loss={avg:.6f} lr={lr:.2e}"
                )

        train_loss = epoch_loss / max(epoch_steps, 1)

        # ── Validation ───────────────────────────────────────────────
        model.eval()
        val_loss = 0.0
        val_steps = 0

        with torch.no_grad():
            for context, target in val_loader:
                context = context.to(device)
                target = target.to(device)

                patched_input = context.reshape(-1, num_patches, 32)
                patched_mask = torch.zeros_like(patched_input, dtype=torch.bool)

                (_, _, output_ts, _), _ = model(patched_input, patched_mask)
                loss = compute_loss(output_ts, target, args.horizon_len, args.loss_type)

                val_loss += loss.item()
                val_steps += 1

        val_loss = val_loss / max(val_steps, 1)
        elapsed = time.time() - t_epoch

        logger.info(
            f"Epoch {epoch+1}/{args.epochs}: "
            f"train_loss={train_loss:.6f}, val_loss={val_loss:.6f}, "
            f"time={elapsed:.1f}s, lr={scheduler.get_last_lr()[0]:.2e}"
        )

        # ── Checkpointing ────────────────────────────────────────────
        is_best = val_loss < best_val_loss
        if is_best:
            best_val_loss = val_loss

        # Save best model (state_dict only, ~883MB) on every improvement
        if is_best:
            best_path = ckpt_dir / "best_model.pt"
            torch.save(model.state_dict(), best_path)
            logger.info(f"  New best model: val_loss={val_loss:.6f}")

        # Save full resumable checkpoint only at save_every intervals and final epoch
        if (epoch + 1) % args.save_every == 0 or epoch == args.epochs - 1:
            ckpt_path = ckpt_dir / f"epoch_{epoch+1}.pt"
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "scheduler_state_dict": scheduler.state_dict(),
                "train_loss": train_loss,
                "val_loss": val_loss,
                "best_val_loss": best_val_loss,
                "args": vars(args),
            }, ckpt_path)
            logger.info(f"  Saved full checkpoint: {ckpt_path}")

    # ── Save final model ─────────────────────────────────────────────
    final_path = ckpt_dir / "final_model.pt"
    torch.save(model.state_dict(), final_path)
    logger.info(f"Training complete. Final model: {final_path}")
    logger.info(f"Best val_loss: {best_val_loss:.6f}")


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune TimesFM 2.5 on NSE stock data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Data
    parser.add_argument("--data", required=True, help="Path to training parquet file")
    parser.add_argument("--max-symbols", type=int, default=None, help="Limit to N symbols (for testing)")
    parser.add_argument("--interval", default=None, help="Filter to specific interval (e.g. 'daily', '30min')")

    # Model
    parser.add_argument("--base-model", default="google/timesfm-2.5-200m-pytorch",
                        help="Base model to fine-tune")
    parser.add_argument("--context-len", type=int, default=512, help="Context length (multiple of 32)")
    parser.add_argument("--horizon-len", type=int, default=128, help="Prediction horizon")

    # Training
    parser.add_argument("--epochs", type=int, default=100, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--weight-decay", type=float, default=0.0, help="Weight decay")
    parser.add_argument("--grad-clip", type=float, default=1.0, help="Gradient clipping norm")
    parser.add_argument("--warmup-epochs", type=int, default=5, help="LR warmup epochs")
    parser.add_argument("--stride", type=int, default=64, help="Sliding window stride")
    parser.add_argument("--loss-type", default="mse+quantile",
                        choices=["mse", "quantile", "mse+quantile"],
                        help="Loss function")

    # Infrastructure
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num-workers", type=int, default=4, help="DataLoader workers")
    parser.add_argument("--checkpoint-dir", default="checkpoints/timesfm_nse",
                        help="Checkpoint save directory")
    parser.add_argument("--save-every", type=int, default=10, help="Save checkpoint every N epochs")
    parser.add_argument("--log-interval", type=int, default=50, help="Log every N batches")
    parser.add_argument("--resume", default=None, help="Resume from checkpoint path")

    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
