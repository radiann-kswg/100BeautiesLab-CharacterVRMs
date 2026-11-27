"""実データ・元VRM不変・重み更新・生成結果をまとめて検証する。"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path)
    args = ap.parse_args()
    refs = json.loads((HERE / "db-references.json").read_text(encoding="utf-8"))
    assert set(refs) == {"4", "16", "20", "22", "25", "93"}
    for key, reference in refs.items():
        folder = HERE / "dataset-v1" / f"Corefolder-{key}"
        meta = json.loads((folder / "provenance.json").read_text(encoding="utf-8"))
        assert hashlib.sha256((ROOT / meta["source"]).read_bytes()).hexdigest() == meta["sha256"]
        points = np.load(folder / "surface.npz")
        assert points["coords"].shape == points["rgb"].shape == (32768, 3)
        assert np.isfinite(points["coords"]).all() and np.isfinite(points["rgb"]).all()
        assert np.abs(points["coords"]).max() <= .50001
        assert points["rgb"].min() >= 0 and points["rgb"].max() <= 1
        assert len(list(folder.glob("view-*.png"))) == 8
        for entry in reference["files"]:
            assert hashlib.sha256((HERE / entry["file"]).read_bytes()).hexdigest() == entry["sha256"]
        assert reference["ai_training"]["allowed"] is True
    # 実際に見つかったsRGB二重変換の退行を検出する。
    p = np.load(HERE / "dataset-v1/Corefolder-4/surface.npz")
    rgb, counts = np.unique(np.rint(p["rgb"] * 255), axis=0, return_counts=True)
    dominant = rgb[counts.argmax()]
    assert np.max(np.abs(dominant - [0, 183, 217])) <= 2, dominant
    print("PASS: six source hashes, six point clouds, 48 renders, 24 DB images, sRGB")
    if args.run:
        import torch
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        run = args.run.resolve()
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["steps"] > 0 and all(v > 0 for v in metrics["visits"].values())
        assert not metrics["holdout"] or metrics["holdout"] not in metrics["train_ids"]
        saved = torch.load(run / "checkpoint.pt", map_location="cpu", weights_only=True)["state_dict"]
        original = torch.load(ROOT / ".cache/point-e-models/base_40m.pt", map_location="cpu", weights_only=True)
        delta = sum(float((saved[k].float() - original[k].float()).square().sum()) for k in original)
        assert np.isfinite(delta) and delta > 0, "Pretrained weights were not updated"
        probe = metrics["holdout"] or 93
        reference = np.load(HERE / f"dataset-v1/Corefolder-{probe}/surface.npz")
        xyz = reference["coords"][::16]
        items = [("Reference VRM", xyz, reference["rgb"][::16])]
        summary = {"weight_delta_l2": delta**.5}
        for name in ("before", "after"):
            cloud = np.load(run / (name + ".npz"))
            points = cloud["coords"]
            assert points.shape == (1024, 3) and np.isfinite(points).all()
            summary[name + "_chamfer_l1"] = float((cKDTree(xyz).query(points)[0].mean()
                                                      + cKDTree(points).query(xyz)[0].mean()) / 2)
            items.append((name, points, np.stack([cloud[c] for c in "RGB"], axis=1)))
        fig = plt.figure(figsize=(12, 4))
        for i, (label, points, colors) in enumerate(items):
            ax = fig.add_subplot(1, 3, i + 1, projection="3d")
            ax.scatter(*points.T, c=np.clip(colors, 0, 1), s=5, depthshade=False)
            ax.set(xlim=(-.55,.55), ylim=(-.55,.55), zlim=(-.55,.55), title=label)
            ax.set_box_aspect((1,1,1)); ax.view_init(elev=12, azim=-90); ax.set_axis_off()
        fig.tight_layout(); fig.savefig(run / "comparison.png", dpi=120); plt.close(fig)
        (run / "check.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary))


if __name__ == "__main__":
    main()

