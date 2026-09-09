"""Point-E base40M の実際の追加訓練。既定は5体学習・93を完全除外評価。"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
from PIL import Image
import torch
from point_e.models.configs import MODEL_CONFIGS, model_from_config
from point_e.models.download import load_checkpoint
from point_e.diffusion.configs import DIFFUSION_CONFIGS, diffusion_from_config
from point_e.diffusion.sampler import PointCloudSampler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IDS = (4, 16, 20, 22, 25, 93)


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_data(folder, db):
    arrays = np.load(folder / "surface.npz")
    xyz, rgb = arrays["coords"], arrays["rgb"]
    if xyz.shape != rgb.shape or xyz.ndim != 2 or xyz.shape[1] != 3:
        raise ValueError("Invalid XYZ/RGB shapes")
    if not np.isfinite(xyz).all() or not np.isfinite(rgb).all():
        raise ValueError("Nonfinite point data")
    if np.abs(xyz).max() > .501 or rgb.min() < 0 or rgb.max() > 1:
        raise ValueError("Invalid point/color normalization")
    paths = list(sorted(folder.glob("view-*.png")))
    paths += [HERE / p for p in db.get("training_images", [])]
    if not paths:
        raise ValueError("No conditioning images")
    images = []
    for path in paths:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            images.append(Image.alpha_composite(background, rgba).convert("RGB"))
    return torch.from_numpy(np.concatenate((xyz, rgb * 255), axis=1).T).float(), images, paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--holdout", type=int, choices=(0,) + IDS, default=93)
    parser.add_argument("--run", required=True)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--sample-image", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args()
    if args.steps < 0 or not 0 < args.lr <= .001 or Path(args.run).name != args.run:
        parser.error("Invalid steps, learning rate or run name")
    out = HERE / "runs" / args.run
    out.mkdir(parents=True, exist_ok=False)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    torch.manual_seed(42)
    rng = np.random.default_rng(42)
    random.seed(42)
    torch.set_num_threads(4)
    device = torch.device("cuda")
    config = dict(MODEL_CONFIGS["base40M"], cache_dir=str(ROOT / ".cache/point-e-models"))
    model = model_from_config(config, device)
    original = load_checkpoint("base40M", device, cache_dir=config["cache_dir"])
    model.load_state_dict(original)
    del original
    if args.checkpoint:
        saved = torch.load(args.checkpoint, map_location=device, weights_only=True)
        model.load_state_dict(saved["state_dict"])
    diffusion = diffusion_from_config(DIFFUSION_CONFIGS["base40M"])
    sampler = PointCloudSampler(device=device, models=[model], diffusions=[diffusion],
                                num_points=[1024], aux_channels=["R", "G", "B"],
                                guidance_scale=[3.0], use_karras=[True], karras_steps=[64],
                                sigma_min=[.001], sigma_max=[120], s_churn=[0])

    def sample(image, name):
        model.eval()
        torch.manual_seed(2026)
        with torch.no_grad():
            result = sampler.sample_batch(1, {"images": [image]})
            pc = sampler.output_to_point_clouds(result)[0]
        if not np.isfinite(pc.coords).all():
            raise ValueError("Nonfinite generated point cloud")
        pc.save(str(out / (name + ".npz")))
        with (out / (name + ".ply")).open("wb") as f:
            pc.write_ply(f)
        return pc

    if args.sample_image:
        with Image.open(args.sample_image) as image:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            sample(Image.alpha_composite(background, rgba).convert("RGB"), "sample")
        dump(out / "sample-info.json", {"image": str(args.sample_image), "checkpoint": str(args.checkpoint)})
        return
    references = json.loads((HERE / "db-references.json").read_text(encoding="utf-8"))
    data, provenance = {}, []
    for number in IDS:
        folder = HERE / "dataset-v1" / f"Corefolder-{number}"
        cloud, images, paths = get_data(folder, references[str(number)])
        with torch.no_grad():
            embedding = torch.cat([model.cached_model_kwargs(1, {"images": [im]})["embeddings"]
                                   for im in images]).detach()
        data[number] = (cloud, images, embedding)
        provenance.append({"id": number, "role": "validation" if number == args.holdout else "train",
                           "images": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                      for p in paths]})
    train_ids = [n for n in IDS if n != args.holdout]
    probe_id = args.holdout or IDS[-1]
    cloud, images, embedding = data[probe_id]
    fixed_indices = np.random.default_rng(7).choice(cloud.shape[1], 1024, replace=False)
    fixed = cloud[:, fixed_indices].unsqueeze(0).to(device)
    generator = torch.Generator(device=device).manual_seed(123)
    noise = torch.randn(fixed.shape, device=device, generator=generator)

    def evaluate():
        model.eval()
        with torch.no_grad():
            losses = [diffusion.training_losses(model, fixed, torch.tensor([t], device=device),
                       {"embeddings": embedding[:1]}, noise=noise)["loss"].mean().item()
                      for t in (32, 128, 512, 900)]
        return float(np.mean(losses))

    before = evaluate()
    sample(images[0], "before")
    torch.manual_seed(42)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr)
    losses, visits = [], {str(n): 0 for n in train_ids}
    start = time.monotonic()
    for step in range(args.steps):
        # 小標本なので均等巡回。画像を増やしても独立した3D形状は6体のまま。
        number = train_ids[step % len(train_ids)]
        cloud, _, embeddings = data[number]
        indices = rng.choice(cloud.shape[1], 1024, replace=False)
        x = cloud[:, indices].unsqueeze(0).to(device)
        cond = embeddings[int(rng.integers(len(embeddings)))].unsqueeze(0)
        t = torch.randint(0, diffusion.num_timesteps, (1,), device=device)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss = diffusion.training_losses(model, x, t, {"embeddings": cond})["loss"].mean()
        if not torch.isfinite(loss):
            raise RuntimeError("Nonfinite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        losses.append(float(loss.detach()))
        visits[str(number)] += 1
        if (step + 1) % 20 == 0:
            print(json.dumps({"step": step + 1, "loss": float(np.mean(losses[-20:])),
                             "seconds": round(time.monotonic() - start, 1)}), flush=True)
    after = evaluate()
    model.eval()
    torch.save({"state_dict": model.state_dict(), "model": "base40M", "steps": args.steps,
                "train_ids": train_ids, "holdout": args.holdout}, out / "checkpoint.pt")
    sample(images[0], "after")
    dump(out / "metrics.json", {"steps": args.steps, "train_ids": train_ids, "visits": visits,
         "holdout": args.holdout, "evaluation": "fixed noise denoising; not a quality guarantee",
         "probe_loss_before": before, "probe_loss_after": after, "losses": losses,
         "gpu": torch.cuda.get_device_name(), "peak_gpu_gib": torch.cuda.max_memory_allocated() / 2**30,
         "training_seconds": time.monotonic() - start, "lr": args.lr, "sources": provenance})
    print(json.dumps({"before": before, "after": after, "checkpoint": str(out / "checkpoint.pt")}), flush=True)


if __name__ == "__main__":
    main()

