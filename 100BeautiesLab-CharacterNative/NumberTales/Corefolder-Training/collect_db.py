"""学習許可済みマニフェストと現行創作DBを照合し、6体の画像・設定資料を関連付ける。"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
IDS = {4, 16, 20, 22, 25, 93}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()
    root = args.db.resolve()
    records = json.loads((root / "data/Works_NumberTales/DataBases/db_Primary.json").read_text(encoding="utf-8-sig"))
    current = {str(r["Num"]): r for r in records if r.get("Num") in IDS}
    allowed = {}
    for line in args.manifest.read_text(encoding="utf-8-sig").splitlines():
        r = json.loads(line)
        if r.get("_type") == "character" and r.get("work_key") == "#Works_NumberTales" and r.get("db_source", "").endswith("/db_Primary.json"):
            if r.get("ai_training", {}).get("allowed") is True and r.get("id") in current:
                allowed[r["id"]] = r
    if set(allowed) != set(current) or len(allowed) != 6:
        raise ValueError("All six IDs must have explicit training permission")
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    output = {}
    for key in sorted(current, key=int):
        record, permission = current[key], allowed[key]
        if any(record.get(k) for k in ("AI_Optout", "isPrivate", "DB_Hidden", "Works_Hidden")):
            raise ValueError(f"Current DB excludes {key}")
        if record.get("Progress") != "released":
            raise ValueError(f"Review readiness of {key}")
        dest = HERE / "db-assets" / f"Corefolder-{key}"
        dest.mkdir(parents=True, exist_ok=True)
        images = record.get("Images", {})
        base = Path("data/Works_NumberTales/Images/DB_Primary")
        candidates = [("train", base / "corefolder" / (x + ".png"))
                      for x in images.get("corefolder_PNGPath", [])]
        for kind in ("concept", "catalog"):
            if images.get(kind + "_PNGName"):
                candidates.append(("reference", base / kind / (images[kind + "_PNGName"] + ".png")))
        # 複数キャラ入りのartsや人型画像は誤った画像・形状対応を作らないため学習ペアにしない。
        listed = {p for kind in ("corefolder", "concept", "catalog")
                  for p in permission.get("images", {}).get(kind, []) if isinstance(p, str)}
        files, train = [], []
        for role, relative in candidates:
            if relative.as_posix() not in listed:
                raise ValueError(f"Image absent from allowed manifest: {relative}")
            source = (root / relative).resolve()
            if not source.is_relative_to(root):
                raise ValueError("Path escaped DB root")
            target = dest / source.name
            shutil.copyfile(source, target)
            local = target.relative_to(HERE).as_posix()
            files.append({"role": role, "file": local, "source": relative.as_posix(), "sha256": sha(source)})
            if role == "train":
                train.append(local)
        fields = ("Num", "Name_JP", "Name_EN", "Progress", "ColorPalette", "TailsUnit", "AppearanceDetail")
        output[key] = {"db_commit": commit, "db_source": permission["db_source"],
                       "record_sha256": hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest(),
                       "manifest_sha256": sha(args.manifest), "ai_training": permission["ai_training"],
                       "settings": {k: record[k] for k in fields if k in record},
                       "ai_hints": permission.get("ai_hints", {}),
                       "settings_use": "Reference and evaluation constraints; not language-model weight training",
                       "training_images": train, "files": files}
    (HERE / "db-references.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"characters": len(output), "training_images": sum(len(r["training_images"]) for r in output.values()),
                      "reference_images": sum(len(r["files"])-len(r["training_images"]) for r in output.values())}))


if __name__ == "__main__":
    main()

