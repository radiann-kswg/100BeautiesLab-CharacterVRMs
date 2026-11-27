#!/usr/bin/env python3
"""
tripo_cli.py — Tripo AI (https://platform.tripo3d.ai) を使った 3D モデリング CLI

公式 SDK `tripo3d` (pip) の薄いラッパー。すべてのジョブは
  outputs/<YYYYMMDD>/<HHMMSS>_<type>_<task_id[:8]>/
に task.json + モデル本体 + プレビュー画像を保存し、logs/jobs.jsonl に追記する。

サブコマンド:
  balance                       残クレジット
  doctor                        接続・環境チェック
  context  [--show]             Dropbox コンテキストフォルダの一覧 / 資料表示
  image2model  <image>          1 枚の 2D イラスト → 3D
  multiview2model --front F [--left L --back B --right R]   多視点 → 3D
  text2model   "<prompt>"       テキスト → 3D
  import       <model.glb|obj|fbx|stl>   既存 3D モデルを Tripo に取り込み (task_id を得る)
  texture      <task_id>        既存モデルへ再テクスチャ (--text/--image-prompt/--style-image)
  refine       <task_id>        draft → 高精細化
  lowpoly      <task_id>        スマートローポリ化
  segment      <task_id>        パーツ分割
  rig          <task_id>        リギング (--check で事前判定のみ)
  stylize      <task_id> --style lego|voxel|voronoi|minecraft
  convert      <task_id> --format GLTF|FBX|OBJ|STL|USDZ|3MF
  status       <task_id>        進捗確認
  download     <task_id>        完了済タスクの成果物を保存
  wait         <task_id>        完了までポーリングして保存

入力パスはローカル → Dropbox 同期先 (TRIPO_DROPBOX_ROOT/01_inputs/...) の順で解決。URL も可。
環境変数: TRIPO_API_KEY (必須), TRIPO_DEFAULT_VERSION, TRIPO_OUTPUT_DIR, TRIPO_LOG_DIR, TRIPO_DROPBOX_ROOT

---
【100BeautiesLab-CharacterVRMs 向け複製について】
原本: Dropbox `Claude Coworks Projectfile/Tripio AI x Claude UserFiles/tripo-3d-studio/scripts/tripo_cli.py`
本ファイルは原本の複製。原本からの差分は以下のみ (原本が更新されたら本ファイルへ追従し、この差分を再適用する):
  * LOG_DIR を環境変数 TRIPO_LOG_DIR で上書き可能にした (キャラクター単位の台帳を置くため)。
  * append_log の mkdir に parents=True を付けた。
  * doctor の出力に log dir を 1 行追加した。
通常は本ファイルを直接呼ばず、`Tools/Tripo/tripo.py` (ラッパー) 経由で実行する。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(os.environ.get("TRIPO_OUTPUT_DIR", ROOT / "outputs"))
LOG_DIR = Path(os.environ.get("TRIPO_LOG_DIR", ROOT / "logs"))  # [100BeautiesLab 差分] 環境変数で上書き可
CONFIG_FILE = ROOT / "config" / "tripo.yaml"

# ---------- config -----------------------------------------------------------

def load_config() -> dict:
    """config/tripo.yaml を読む (PyYAML があれば)。無ければ組込み既定。"""
    cfg = {
        "default_version": "v3.1-20260211",
        "texture_version": "v3.0-20250812",
        "rig_version": "v2.0-20250506",
        "poll_interval": 5,
        "timeout": 1800,
        "presets": {},
    }
    if CONFIG_FILE.exists():
        try:
            import yaml  # type: ignore
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(yaml.safe_load(f) or {})
        except ImportError:
            pass
    if os.environ.get("TRIPO_DEFAULT_VERSION"):
        cfg["default_version"] = os.environ["TRIPO_DEFAULT_VERSION"]
    return cfg


CFG = load_config()


def load_dotenv() -> None:
    """.env を最小実装で読む (python-dotenv 不要)。既存の環境変数は上書きしない。"""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()

# ---------- dropbox ----------------------------------------------------------

def dropbox_root() -> Path | None:
    """ローカルに同期された Dropbox コンテキストフォルダ (存在する場合のみ)。"""
    raw = (CFG.get("dropbox", {}) or {}).get("local_root") or os.environ.get("TRIPO_DROPBOX_ROOT", "")
    if not raw:
        return None
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():          # 相対指定はリポジトリルート基準 (Dropbox 内に置く場合 "..")
        p = (ROOT / p).resolve()
    return p if p.is_dir() else None


def dropbox_sub(kind: str) -> Path | None:
    root = dropbox_root()
    if not root:
        return None
    sub = (CFG.get("dropbox", {}).get("layout", {}) or {}).get(kind, "")
    return root / sub if sub else root


def resolve_input(path: str, kind: str) -> str:
    """ローカル → Dropbox/<layout[kind]> → Dropbox 直下 の順に探す。URL はそのまま。"""
    if path.startswith(("http://", "https://")) or Path(path).exists():
        return path
    for cand in (dropbox_sub(kind), dropbox_root()):
        if cand and (cand / path).exists():
            return str(cand / path)
    return path


def mirror_to_dropbox(d: Path) -> str | None:
    """job dir と台帳を Dropbox 同期先へコピー。失敗しても本処理は止めない。"""
    dbx = CFG.get("dropbox", {}) or {}
    if not dbx.get("mirror_outputs", False):
        return None
    root = dropbox_root()
    if not root:
        return None
    import shutil
    try:
        dst = root / dbx["layout"].get("outputs", "02_outputs") / d.relative_to(OUTPUT_DIR)
        shutil.copytree(d, dst, dirs_exist_ok=True)
        logs_dst = root / dbx["layout"].get("logs", "03_logs")
        logs_dst.mkdir(parents=True, exist_ok=True)
        if (LOG_DIR / "jobs.jsonl").exists():
            shutil.copy2(LOG_DIR / "jobs.jsonl", logs_dst / "jobs.jsonl")
        return str(dst)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] dropbox mirror failed: {e}")
        return None

def _relocate_dirs_if_inside_dropbox() -> None:
    """リポジトリ自体が Dropbox コンテキストフォルダ内にある場合、outputs/logs を
    02_outputs / 03_logs に直接向け、二重保存 (ミラー) を止める。"""
    global OUTPUT_DIR, LOG_DIR
    root = dropbox_root()
    if not root or os.environ.get("TRIPO_OUTPUT_DIR"):
        return
    try:
        ROOT.resolve().relative_to(root.resolve())
    except ValueError:
        return
    layout = (CFG.get("dropbox", {}).get("layout", {}) or {})
    OUTPUT_DIR = root / layout.get("outputs", "02_outputs")
    LOG_DIR = root / layout.get("logs", "03_logs")
    CFG.setdefault("dropbox", {})["mirror_outputs"] = False


_relocate_dirs_if_inside_dropbox()

# ---------- helpers ----------------------------------------------------------

def die(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(code)


def require_key() -> str:
    key = os.environ.get("TRIPO_API_KEY", "")
    if not key.startswith("tsk_"):
        die("TRIPO_API_KEY が未設定です。.env に TRIPO_API_KEY=tsk_... を書いてください "
            "(取得: https://platform.tripo3d.ai/api-keys)")
    return key


def get_client():
    try:
        from tripo3d import TripoClient
    except ImportError:
        die("tripo3d SDK が未インストールです: pip install -r requirements.txt")
    return TripoClient(api_key=require_key())


def job_dir(task_type: str, task_id: str) -> Path:
    now = datetime.now()
    d = OUTPUT_DIR / now.strftime("%Y%m%d") / f"{now.strftime('%H%M%S')}_{task_type}_{task_id[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record["logged_at"] = datetime.now().isoformat(timespec="seconds")
    with open(LOG_DIR / "jobs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def task_to_dict(task) -> dict:
    out = task.output
    return {
        "task_id": task.task_id,
        "type": task.type,
        "status": str(getattr(task.status, "value", task.status)),
        "progress": task.progress,
        "input": task.input,
        "output": {
            "model": out.model,
            "base_model": out.base_model,
            "pbr_model": out.pbr_model,
            "rendered_image": out.rendered_image,
            "riggable": out.riggable,
            "rig_type": str(out.rig_type) if out.rig_type else None,
        },
        "error_code": task.error_code,
        "error_msg": task.error_msg,
    }


async def finalize(client, task_id: str, no_wait: bool, extra: dict | None = None) -> dict:
    """task 送信後の共通処理: 待機 → 保存 → ログ。"""
    from tripo3d import TaskStatus

    print(f"[task] submitted: {task_id}")
    if no_wait:
        append_log({"task_id": task_id, "status": "submitted", **(extra or {})})
        print(json.dumps({"task_id": task_id}, ensure_ascii=False))
        return {"task_id": task_id}

    task = await client.wait_for_task(
        task_id, verbose=True,
        polling_interval=CFG.get("poll_interval", 5),
        timeout=CFG.get("timeout", 1800),
    )
    rec = task_to_dict(task)
    rec.update(extra or {})
    if task.status != TaskStatus.SUCCESS:
        append_log(rec)
        die(f"task {task_id} finished with status={rec['status']} "
            f"code={task.error_code} msg={task.error_msg}")

    d = job_dir(task.type, task_id)
    files = await client.download_task_models(task, str(d))
    preview = None
    if task.output.rendered_image:
        try:
            preview = await client.download_rendered_image(task, str(d))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] preview download failed: {e}")
    rec["files"] = {k: v for k, v in files.items() if v}
    rec["preview"] = preview
    rec["job_dir"] = str(d)
    (d / "task.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    mirrored = mirror_to_dropbox(d)
    if mirrored:
        rec["dropbox_mirror"] = mirrored
        (d / "task.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    append_log(rec)
    print(f"[done] saved to {d}")
    if mirrored:
        print(f"[dropbox] mirrored to {mirrored}")
    for k, v in rec["files"].items():
        print(f"  {k}: {v}")
    if preview:
        print(f"  preview: {preview}")
    return rec


def apply_preset(args) -> dict:
    """--preset で config/tripo.yaml の presets を展開し、明示引数で上書き。"""
    kw = {}
    if getattr(args, "preset", None):
        preset = CFG.get("presets", {}).get(args.preset)
        if preset is None:
            die(f"unknown preset: {args.preset} (available: {list(CFG.get('presets', {}))})")
        kw.update(preset)
    return kw


def gen_kwargs(args) -> dict:
    """image/multiview/text 共通の生成パラメータを組み立てる。"""
    kw = apply_preset(args)
    for name in ("model_version", "face_limit", "model_seed", "texture_seed",
                 "texture_quality", "geometry_quality", "texture_alignment",
                 "orientation"):
        v = getattr(args, name, None)
        if v is not None:
            kw[name] = v
    for flag in ("quad", "smart_low_poly", "generate_parts", "auto_size",
                 "compress", "enable_image_autofix"):
        if getattr(args, flag, False):
            kw[flag] = True
    if getattr(args, "no_texture", False):
        kw["texture"] = False
        kw["pbr"] = False
    if getattr(args, "no_pbr", False):
        kw["pbr"] = False
    if getattr(args, "no_uv", False):
        kw["export_uv"] = False
    kw.setdefault("model_version", CFG["default_version"])
    if kw.get("generate_parts"):
        kw["texture"] = False
        kw["pbr"] = False
        kw["quad"] = False
    return kw


# ---------- commands ---------------------------------------------------------

async def cmd_balance(args):
    async with get_client() as c:
        b = await c.get_balance()
        print(json.dumps({"balance": b.balance, "frozen": b.frozen}, ensure_ascii=False))


async def cmd_doctor(args):
    print("== tripo doctor ==")
    print(f"python      : {sys.version.split()[0]}")
    for mod in ("tripo3d", "aiohttp", "boto3", "yaml"):
        try:
            m = __import__(mod)
            print(f"{mod:<12}: ok ({getattr(m, '__version__', '?')})")
        except ImportError:
            print(f"{mod:<12}: MISSING")
    key = os.environ.get("TRIPO_API_KEY", "")
    print(f"TRIPO_API_KEY: {'set (' + key[:8] + '…)' if key else 'NOT SET'}")
    for host in ("api.tripo3d.ai", "s3.us-west-2.amazonaws.com", "tripo-data.rg1.data.tripo3d.ai"):
        try:
            socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            dns = "dns ok"
        except OSError:
            dns = "dns FAIL"
        print(f"host {host:<34}: {dns}")
    if key:
        try:
            async with get_client() as c:
                b = await c.get_balance()
                print(f"API           : ok (balance={b.balance})")
        except Exception as e:  # noqa: BLE001
            print(f"API           : FAIL — {e}")
            print("  ↳ サンドボックス実行時は許可ドメインに *.tripo3d.ai と s3.us-west-2.amazonaws.com を追加してください")
    dbx = CFG.get("dropbox", {}) or {}
    root = dropbox_root()
    print(f"dropbox remote: {dbx.get('remote_path', '-')}")
    print(f"dropbox local : {root if root else 'not synced locally (TRIPO_DROPBOX_ROOT unset or missing) — Claude.ai ではコネクタ経由で参照'}")
    print(f"output dir    : {OUTPUT_DIR}")
    print(f"log dir       : {LOG_DIR}")
    print(f"default ver   : {CFG['default_version']}")


async def cmd_image2model(args):
    args.image = resolve_input(args.image, "images")
    src = Path(args.image)
    if not src.exists() and not args.image.startswith("http"):
        die(f"image not found: {src}")
    kw = gen_kwargs(args)
    async with get_client() as c:
        tid = await c.image_to_model(args.image, **kw)
        await finalize(c, tid, args.no_wait, {"source": args.image, "params": kw})


async def cmd_multiview2model(args):
    for k in ("front", "left", "back", "right"):
        v = getattr(args, k)
        if v:
            setattr(args, k, resolve_input(v, "multiview"))
    views = [args.front, args.left, args.back, args.right]
    if not args.front:
        die("--front は必須です")
    if sum(1 for v in views if v) < 2:
        die("多視点生成には最低 2 枚 (front + もう 1 枚) が必要です")
    for v in views:
        if v and not Path(v).exists() and not v.startswith("http"):
            die(f"view not found: {v}")
    # SDK / API は [front, left, back, right] の固定順・4 要素。欠損視点は None → {} として送られる。
    images = [v if v else None for v in views]
    kw = gen_kwargs(args)
    kw.pop("enable_image_autofix", None)  # multiview では非対応
    async with get_client() as c:
        tid = await c.multiview_to_model(images, **kw)
        await finalize(c, tid, args.no_wait,
                       {"source": {"front": args.front, "left": args.left,
                                   "back": args.back, "right": args.right}, "params": kw})


async def cmd_text2model(args):
    kw = gen_kwargs(args)
    kw.pop("enable_image_autofix", None)
    kw.pop("texture_alignment", None)
    kw.pop("orientation", None)
    if args.negative:
        kw["negative_prompt"] = args.negative
    if args.image_seed is not None:
        kw["image_seed"] = args.image_seed
    async with get_client() as c:
        tid = await c.text_to_model(prompt=args.prompt, **kw)
        await finalize(c, tid, args.no_wait, {"source": args.prompt, "params": kw})


async def cmd_import(args):
    args.model = resolve_input(args.model, "models")
    src = Path(args.model)
    if not src.exists():
        die(f"model not found: {src}")
    if src.suffix.lower() not in (".glb", ".obj", ".fbx", ".stl"):
        die("import は glb / obj / fbx / stl のみ対応")
    if src.stat().st_size > 150 * 1024 * 1024:
        die("150MB を超えるモデルは import できません")
    async with get_client() as c:
        tid = await c.import_model(str(src))
        print("[info] import_model は元モデルをそのまま登録します。返る task_id を texture/lowpoly/rig 等に渡してください。")
        await finalize(c, tid, args.no_wait, {"source": str(src)})


async def cmd_texture(args):
    kw = apply_preset(args)
    kw["model_version"] = args.model_version or CFG["texture_version"]
    if args.text:
        kw["text_prompt"] = args.text
    if args.image_prompt:
        kw["image_prompt"] = resolve_input(args.image_prompt, "images")
    if args.style_image:
        kw["style_image"] = resolve_input(args.style_image, "images")
    if args.texture_quality:
        kw["texture_quality"] = args.texture_quality
    if args.texture_alignment:
        kw["texture_alignment"] = args.texture_alignment
    if args.texture_seed is not None:
        kw["texture_seed"] = args.texture_seed
    if args.no_pbr:
        kw["pbr"] = False
    if args.part_names:
        kw["part_names"] = args.part_names
    async with get_client() as c:
        tid = await c.texture_model(args.task_id, **kw)
        await finalize(c, tid, args.no_wait, {"source_task": args.task_id, "params": kw})


async def cmd_refine(args):
    async with get_client() as c:
        tid = await c.refine_model(args.task_id)
        await finalize(c, tid, args.no_wait, {"source_task": args.task_id})


async def cmd_lowpoly(args):
    kw = {}
    if args.face_limit:
        kw["face_limit"] = args.face_limit
    if args.quad:
        kw["quad"] = True
    if args.part_names:
        kw["part_names"] = args.part_names
    async with get_client() as c:
        tid = await c.smart_lowpoly(args.task_id, **kw)
        await finalize(c, tid, args.no_wait, {"source_task": args.task_id, "params": kw})


async def cmd_segment(args):
    async with get_client() as c:
        tid = await c.mesh_segmentation(args.task_id)
        await finalize(c, tid, args.no_wait, {"source_task": args.task_id})


async def cmd_rig(args):
    from tripo3d import RigSpec, RigType
    async with get_client() as c:
        if args.check:
            tid = await c.check_riggable(args.task_id)
            task = await c.wait_for_task(tid, verbose=True)
            rec = task_to_dict(task)
            append_log({**rec, "source_task": args.task_id})
            print(json.dumps(rec["output"], ensure_ascii=False, indent=2))
            return
        kw = {
            "model_version": args.model_version or CFG["rig_version"],
            "out_format": args.out_format,
            "rig_type": RigType(args.rig_type),
            "spec": RigSpec(args.spec),
        }
        tid = await c.rig_model(args.task_id, **kw)
        await finalize(c, tid, args.no_wait, {"source_task": args.task_id,
                                              "params": {k: str(v) for k, v in kw.items()}})


async def cmd_stylize(args):
    from tripo3d import PostStyle
    async with get_client() as c:
        tid = await c.stylize_model(args.task_id, PostStyle(args.style), block_size=args.block_size)
        await finalize(c, tid, args.no_wait, {"source_task": args.task_id, "params": {"style": args.style}})


async def cmd_convert(args):
    kw = {"format": args.format}
    if args.face_limit:
        kw["face_limit"] = args.face_limit
    if args.quad:
        kw["quad"] = True
    if args.texture_size:
        kw["texture_size"] = args.texture_size
    if args.flatten_bottom:
        kw["flatten_bottom"] = True
    async with get_client() as c:
        tid = await c.convert_model(args.task_id, **kw)
        await finalize(c, tid, args.no_wait, {"source_task": args.task_id, "params": kw})


async def cmd_status(args):
    async with get_client() as c:
        task = await c.get_task(args.task_id)
        print(json.dumps(task_to_dict(task), ensure_ascii=False, indent=2))


async def cmd_download(args):
    from tripo3d import TaskStatus
    async with get_client() as c:
        task = await c.get_task(args.task_id)
        if task.status != TaskStatus.SUCCESS:
            die(f"task is {task.status}; use `wait` instead")
        await finalize(c, args.task_id, no_wait=False)


async def cmd_wait(args):
    async with get_client() as c:
        await finalize(c, args.task_id, no_wait=False)


async def cmd_context(args):
    """Dropbox コンテキストフォルダの内容を一覧し、00_context 内のテキスト資料を表示する。"""
    dbx = CFG.get("dropbox", {}) or {}
    print(f"remote : {dbx.get('remote_path')}")
    root = dropbox_root()
    if not root:
        print("local  : (未同期) Claude.ai / Cowork では Dropbox コネクタで上記パスを list_folder してください")
        return
    print(f"local  : {root}")
    for kind, sub in (dbx.get("layout") or {}).items():
        p = root / sub
        files = sorted(x for x in p.rglob("*") if x.is_file() and not x.name.startswith(".")) if p.exists() else []
        print(f"\n[{kind}] {sub}  ({len(files)} files)")
        for f in files[:args.limit]:
            print(f"  - {f.relative_to(root)}")
    if args.show:
        ctx = root / (dbx.get("layout") or {}).get("context", "00_context")
        for f in sorted(ctx.glob("*")) if ctx.exists() else []:
            if f.suffix.lower() in (".md", ".txt", ".yaml", ".yml", ".json"):
                print(f"\n===== {f.name} =====")
                print(f.read_text(encoding="utf-8", errors="replace")[:8000])


# ---------- argparse ---------------------------------------------------------

def add_gen_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--preset", help="config/tripo.yaml の presets 名 (draft/standard/hq/game/print)")
    p.add_argument("--model-version", dest="model_version",
                   help="P1-20260311 | v3.1-20260211 | v3.0-20250812 | v2.5-20250123 | Turbo-v1.0-20250506")
    p.add_argument("--face-limit", dest="face_limit", type=int)
    p.add_argument("--model-seed", dest="model_seed", type=int)
    p.add_argument("--texture-seed", dest="texture_seed", type=int)
    p.add_argument("--texture-quality", dest="texture_quality", choices=["standard", "detailed"])
    p.add_argument("--geometry-quality", dest="geometry_quality", choices=["standard", "detailed"])
    p.add_argument("--texture-alignment", dest="texture_alignment", choices=["original_image", "geometry"])
    p.add_argument("--orientation", choices=["default", "align_image"])
    p.add_argument("--quad", action="store_true", help="四角面メッシュ (FBX 出力になる)")
    p.add_argument("--smart-low-poly", dest="smart_low_poly", action="store_true")
    p.add_argument("--generate-parts", dest="generate_parts", action="store_true",
                   help="パーツ分割 (texture/pbr/quad を自動で無効化)")
    p.add_argument("--auto-size", dest="auto_size", action="store_true")
    p.add_argument("--compress", action="store_true")
    p.add_argument("--autofix", dest="enable_image_autofix", action="store_true")
    p.add_argument("--no-texture", dest="no_texture", action="store_true")
    p.add_argument("--no-pbr", dest="no_pbr", action="store_true")
    p.add_argument("--no-uv", dest="no_uv", action="store_true")
    p.add_argument("--no-wait", dest="no_wait", action="store_true", help="送信のみ (task_id を返す)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="tripo", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("balance").set_defaults(fn=cmd_balance)
    sp.add_parser("doctor").set_defaults(fn=cmd_doctor)

    p = sp.add_parser("context", help="Dropbox コンテキストフォルダの内容を一覧")
    p.add_argument("--show", action="store_true", help="00_context のテキスト資料を表示")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(fn=cmd_context)

    p = sp.add_parser("image2model", help="2D イラスト 1 枚 → 3D")
    p.add_argument("image")
    add_gen_opts(p)
    p.set_defaults(fn=cmd_image2model)

    p = sp.add_parser("multiview2model", help="多視点 (front 必須) → 3D")
    p.add_argument("--front", required=True)
    p.add_argument("--left")
    p.add_argument("--back")
    p.add_argument("--right")
    add_gen_opts(p)
    p.set_defaults(fn=cmd_multiview2model)

    p = sp.add_parser("text2model", help="テキスト → 3D")
    p.add_argument("prompt")
    p.add_argument("--negative", help="negative prompt")
    p.add_argument("--image-seed", dest="image_seed", type=int, help="中間画像生成の seed")
    add_gen_opts(p)
    p.set_defaults(fn=cmd_text2model)

    p = sp.add_parser("import", help="既存 3D モデルを取り込み task_id を得る")
    p.add_argument("model")
    p.add_argument("--no-wait", dest="no_wait", action="store_true")
    p.set_defaults(fn=cmd_import)

    p = sp.add_parser("texture", help="既存モデルへ再テクスチャ")
    p.add_argument("task_id")
    p.add_argument("--preset")
    p.add_argument("--model-version", dest="model_version")
    p.add_argument("--text", help="テクスチャのテキスト指示")
    p.add_argument("--image-prompt", dest="image_prompt", help="参照画像 (path/URL)")
    p.add_argument("--style-image", dest="style_image", help="スタイル参照画像 (path/URL)")
    p.add_argument("--texture-quality", dest="texture_quality", choices=["standard", "detailed"])
    p.add_argument("--texture-alignment", dest="texture_alignment", choices=["original_image", "geometry"])
    p.add_argument("--texture-seed", dest="texture_seed", type=int)
    p.add_argument("--part-names", dest="part_names", nargs="+")
    p.add_argument("--no-pbr", dest="no_pbr", action="store_true")
    p.add_argument("--no-wait", dest="no_wait", action="store_true")
    p.set_defaults(fn=cmd_texture)

    for name, fn, help_ in (("refine", cmd_refine, "draft → 高精細化"),
                            ("segment", cmd_segment, "メッシュをパーツ分割"),
                            ("status", cmd_status, "進捗確認"),
                            ("download", cmd_download, "完了済タスクを保存"),
                            ("wait", cmd_wait, "完了までポーリングして保存")):
        p = sp.add_parser(name, help=help_)
        p.add_argument("task_id")
        if name in ("refine", "segment"):
            p.add_argument("--no-wait", dest="no_wait", action="store_true")
        p.set_defaults(fn=fn)

    p = sp.add_parser("lowpoly", help="スマートローポリ化")
    p.add_argument("task_id")
    p.add_argument("--face-limit", dest="face_limit", type=int)
    p.add_argument("--quad", action="store_true")
    p.add_argument("--part-names", dest="part_names", nargs="+")
    p.add_argument("--no-wait", dest="no_wait", action="store_true")
    p.set_defaults(fn=cmd_lowpoly)

    p = sp.add_parser("rig", help="リギング")
    p.add_argument("task_id")
    p.add_argument("--check", action="store_true", help="riggable 判定のみ")
    p.add_argument("--model-version", dest="model_version")
    p.add_argument("--out-format", dest="out_format", choices=["glb", "fbx"], default="glb")
    p.add_argument("--rig-type", dest="rig_type", default="biped",
                   choices=["biped", "quadruped", "hexapod", "octopod", "avian", "serpentine", "aquatic", "others"])
    p.add_argument("--spec", choices=["tripo", "mixamo"], default="tripo")
    p.add_argument("--no-wait", dest="no_wait", action="store_true")
    p.set_defaults(fn=cmd_rig)

    p = sp.add_parser("stylize", help="スタイル変換")
    p.add_argument("task_id")
    p.add_argument("--style", required=True, choices=["lego", "voxel", "voronoi", "minecraft"])
    p.add_argument("--block-size", dest="block_size", type=int, default=80)
    p.add_argument("--no-wait", dest="no_wait", action="store_true")
    p.set_defaults(fn=cmd_stylize)

    p = sp.add_parser("convert", help="形式変換")
    p.add_argument("task_id")
    p.add_argument("--format", required=True, choices=["GLTF", "FBX", "OBJ", "STL", "USDZ", "3MF"])
    p.add_argument("--face-limit", dest="face_limit", type=int)
    p.add_argument("--quad", action="store_true")
    p.add_argument("--texture-size", dest="texture_size", type=int)
    p.add_argument("--flatten-bottom", dest="flatten_bottom", action="store_true")
    p.add_argument("--no-wait", dest="no_wait", action="store_true")
    p.set_defaults(fn=cmd_convert)
    return ap


def main() -> None:
    args = build_parser().parse_args()
    t0 = time.time()
    try:
        asyncio.run(args.fn(args))
    except KeyboardInterrupt:
        die("interrupted", 130)
    finally:
        if args.cmd not in ("status", "balance", "doctor", "context"):
            print(f"[time] {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
