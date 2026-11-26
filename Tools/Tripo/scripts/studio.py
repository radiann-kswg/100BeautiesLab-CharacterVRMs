"""Use the Japanese Tripo Studio UI and archive its GLB exports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
from datetime import date
from pathlib import Path
from uuid import UUID

WORKSPACE = "https://studio.tripo3d.ai/ja/workspace/generate"
EXPORT = "エクスポート"
GENERATE = re.compile(r"^生成\s+(\d[\d,]*)(?:\s+\d[\d,]*)?$")


def validate_glb(path):
    size = path.stat().st_size
    with path.open("rb") as src:
        magic, version, length, json_size, kind = struct.unpack("<4s4I", src.read(20))
        if (magic, version, length, kind) != (b"glTF", 2, size, 0x4E4F534A):
            raise ValueError("GLB 2.0 のヘッダーまたはファイル長が不正")
        if json_size > size - 28:
            raise ValueError("JSONチャンクがファイル長を超えています")
        model = json.loads(src.read(json_size))
        bin_size, bin_kind = struct.unpack("<II", src.read(8))
        if bin_kind != 0x004E4942 or src.tell() + bin_size != size:
            raise ValueError("BINチャンクが不完全です")
        if model["asset"]["version"] != "2.0" or not model.get("meshes"):
            raise ValueError("メッシュを含む glTF 2.0 が必要です")


def digest(path):
    with path.open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def archive(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
        stage = Path(tmp.name)
    try:
        shutil.copyfile(source, stage)
        validate_glb(stage)
        checksum = digest(stage)
        try:
            if os.name == "nt":
                stage.rename(target)  # Windows rename fails if the target exists.
            else:
                os.link(stage, target)
        except FileExistsError:
            if digest(target) != checksum:
                raise ValueError(f"異なる内容の保存先が既にあります: {target}")
        print(f"{target}\nSHA-256 {checksum}")
    finally:
        stage.unlink(missing_ok=True)


def switch_off(scope, label):
    switch = scope.get_by_text(label, exact=True).locator("..").get_by_role("switch")
    if switch.is_checked():
        switch.click()
    if switch.get_attribute("aria-checked") != "false":
        raise ValueError(f"{label} をオフにできませんでした")


def configure(page):
    page.get_by_role("button", name="HDモデル", exact=True).click()
    page.get_by_role("combobox").filter(has_text="H3.5 プレビュー版").wait_for()
    page.get_by_text("ジオメトリ・テクスチャ", exact=True).click()
    panel = page.get_by_role("dialog", name="ジオメトリ・テクスチャ")
    for label in ("ウルトラメッシュ品質", "パーツ補完", "テクスチャ"):
        switch_off(panel, label)
    page.keyboard.press("Escape")
    for label in ("パーツごとに生成", "8Kテクスチャ"):
        switch_off(page, label)
    page.get_by_role("combobox").filter(has_text="H3.5 プレビュー版").wait_for()
    page.get_by_role("combobox").filter(has_text="リンク限定公開").wait_for()


def quote(page):
    balance = page.get_by_role("banner").locator("p[title]").filter(
        has_text=re.compile(r"^\s*\d[\d,]*\s*$"))
    remaining = int(balance.inner_text().strip().replace(",", ""))
    button = page.get_by_role("button", name=GENERATE)
    # The first price is current. Studio displays the old price struck through after it.
    price = int(GENERATE.fullmatch(" ".join(button.inner_text().split()))[1].replace(",", ""))
    return remaining, price


def generate(page, args, char):
    image = args.image.resolve(strict=True)
    if image.suffix.lower() not in {".jpg", ".jpeg", ".webp", ".png"} or image.stat().st_size > 20_000_000:
        raise ValueError("Studio入力は20MB以内の JPG / PNG / WEBP です")
    configure(page)
    remaining, cost = quote(page)
    if cost > min(remaining, args.max_credits):
        raise ValueError(f"見積 {cost}、残高 {remaining}、上限 {args.max_credits}")
    print(f"{char.name}: {image}\nH3.5・形状のみ・リンク限定公開 | 残高 {remaining} | 1件 {cost}")
    if input("この画像をアップロードして1件生成しますか [y/N] ").lower() != "y":
        return
    with page.expect_file_chooser() as chooser:
        page.get_by_text("アップロード", exact=True).click()
    chooser.value.set_files(str(image))
    page.get_by_role("button", name="マルチビューを生成").wait_for()
    if quote(page) != (remaining, cost):
        raise ValueError("アップロード後に料金または残高が変わりました。生成を中止します")
    print("送信開始。受付が不明な場合はStudioのアセット一覧で確認してください。", flush=True)
    page.get_by_role("button", name=GENERATE).click()
    page.wait_for_url(re.compile(re.escape(WORKSPACE) + r"/[^/?#]+"), timeout=90_000)
    job = UUID(page.url.rstrip("/").split("/")[-1][-36:])
    print(f"{char.name} 生成受付 {job}\n{WORKSPACE}/{job}", flush=True)
    page.get_by_role("button", name=EXPORT, exact=True).wait_for(timeout=900_000)
    input("プレビューを確認したら Enter ")
    print(f"保存: python Tools/Tripo/tripo.py -c {char.parent.name}/{char.name} studio export {job}")


def export(page, target):
    page.get_by_role("button", name=EXPORT, exact=True).click(timeout=900_000)
    panel = page.get_by_role("dialog", name=EXPORT)
    fmt = panel.get_by_role("combobox")
    if fmt.inner_text().strip() != "GLB":
        fmt.click()
        page.get_by_role("option", name="GLB", exact=True).click()
    if fmt.inner_text().strip() != "GLB":
        raise ValueError("GLB を選択できませんでした")
    panel.get_by_role("textbox").fill(target.stem)
    with page.context.expect_event("download", timeout=180_000) as event:
        panel.get_by_role("button", name=EXPORT, exact=True).click()
    archive(event.value.path(), target)


def main(argv, char):
    parser = argparse.ArgumentParser(prog="tripo.py studio")
    subs = parser.add_subparsers(dest="action", required=True)
    subs.add_parser("login", help="専用ChromeプロファイルでStudioにログイン")
    create = subs.add_parser("generate", help="公式画像1枚から形状を生成し、プレビューを開く")
    create.add_argument("image", type=Path, help="画像の絶対パスまたは実行場所からの相対パス")
    create.add_argument("--max-credits", type=int, required=True)
    for name in ("export", "save"):
        sub = subs.add_parser(name, help="StudioからGLBを保存" if name == "export" else "ダウンロード済みGLBを保存")
        sub.add_argument("job", type=UUID)
        if name == "save":
            sub.add_argument("file", type=Path)
        sub.add_argument("--date", type=date.fromisoformat, default=date.today(), help="保存日 YYYY-MM-DD")
    args = parser.parse_args(argv)
    if args.action != "login" and char is None:
        parser.error("tripo.py -c 番号 studio ... の順に指定してください")
    try:
        target = None
        if args.action in {"export", "save"}:
            target = char / "TripoGenerated" / "studio" / args.date.isoformat() / f"{char.name}-{args.job}.glb"
        if args.action == "save":
            archive(args.file, target)
            return
        if target and target.exists():
            validate_glb(target)
            print(f"保存済み {target}\nSHA-256 {digest(target)}")
            return
        from playwright.sync_api import Error, sync_playwright
        profile = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "100BeautiesLab" / "TripoStudio"
        with sync_playwright() as playwright:
            ctx = playwright.chromium.launch_persistent_context(
                str(profile), channel="chrome", headless=False, locale="ja-JP", accept_downloads=True)
            try:
                page = ctx.new_page()
                url = WORKSPACE if args.action != "export" else f"{WORKSPACE}/{args.job}"
                page.goto(url, wait_until="domcontentloaded")
                if args.action == "login":
                    input("このChromeでStudioへのログインを完了したら Enter ")
                elif args.action == "generate":
                    generate(page, args, char)
                else:
                    export(page, target)
            except Error as exc:
                parser.exit(1, f"Studioの画面操作を完了できませんでした。ログインとアセット一覧を確認してください。\n{exc}\n")
            finally:
                ctx.close()
    except ModuleNotFoundError as exc:
        if exc.name != "playwright":
            raise
        parser.exit(1, "Studioのブラウザ操作には python -m pip install playwright が必要です\n")
    except (OSError, ValueError, EOFError, KeyError, struct.error) as exc:
        parser.exit(1, f"Studio: {exc}\n")
