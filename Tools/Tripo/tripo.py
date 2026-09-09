#!/usr/bin/env python3
"""
tripo.py — 100BeautiesLab-CharacterVRMs 用の Tripo AI 薄いラッパー

`Tools/Tripo/scripts/tripo_cli.py` (Tripo 3D Studio の CLI 複製) を、
キャラクター単位のフォルダを正本として呼び出す。

  python Tools/Tripo/tripo.py doctor
  python Tools/Tripo/tripo.py balance
  python Tools/Tripo/tripo.py --list
  python Tools/Tripo/tripo.py -c Corefolder-16 image2model CoreFolder-16.png --preset draft
  python Tools/Tripo/tripo.py -c 16 multiview2model --front Training/front.png --back Training/back.png
  python Tools/Tripo/tripo.py -c 16 status <task_id>

-c / --character で指定したキャラクターのフォルダ
  100BeautiesLab-CharacterNative/<series>/Corefolder-<N>/
をカレントディレクトリにして CLI を実行するため、入力画像はそのフォルダからの相対パスで書ける。
成果物と台帳 (jobs.jsonl) は同フォルダ配下の TripoGenerated/ に保存される。

環境変数 (.env はリポジトリ直下 → Tools/Tripo/ の順に読む。OS の環境変数が最優先):
  TRIPO_API_KEY            必須。エージェントは値を読まない・出力しない。
  TRIPO_DEFAULT_VERSION    任意。既定モデルバージョン上書き。
  TRIPO_DROPBOX_ROOT       任意。Tripo 3D Studio の Dropbox 同期先 (context 参照用)。
"""
from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent                 # Tools/Tripo
REPO_ROOT = HERE.parent.parent                          # リポジトリ直下
CLI = HERE / "scripts" / "tripo_cli.py"
NATIVE_ROOT = REPO_ROOT / "100BeautiesLab-CharacterNative"
DEFAULT_SERIES = "NumberTales"
GENERATED_DIRNAME = "TripoGenerated"
# キャラクター指定なしでも実行できるサブコマンド (成果物を書かないもの)
NO_CHARACTER_OK = {"doctor", "balance", "status", "context", "-h", "--help"}


def die(msg: str, code: int = 1) -> None:
    print(f"[tripo] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_dotenv(path: Path) -> None:
    """最小実装の .env 読み込み。既存の環境変数は上書きしない。値は表示しない。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def list_characters() -> list[tuple[str, str]]:
    """(series, Corefolder-N) の一覧。"""
    found: list[tuple[str, str]] = []
    if not NATIVE_ROOT.is_dir():
        return found
    for series in sorted(p for p in NATIVE_ROOT.iterdir() if p.is_dir()):
        for ch in sorted(p for p in series.iterdir() if p.is_dir() and p.name.lower().startswith("corefolder")):
            found.append((series.name, ch.name))
    return found


def resolve_character(spec: str, series: str) -> Path:
    """'16' / 'Corefolder-16' / 'NumberTales/Corefolder-16' を実フォルダに解決する。"""
    spec = spec.strip().replace("\\", "/")
    if "/" in spec:
        series, spec = spec.split("/", 1)
    name = spec if spec.lower().startswith("corefolder") else f"Corefolder-{spec}"
    d = NATIVE_ROOT / series / name
    if d.is_dir():
        return d
    # 大文字小文字違いを救済
    parent = NATIVE_ROOT / series
    if parent.is_dir():
        for p in parent.iterdir():
            if p.is_dir() and p.name.lower() == name.lower():
                return p
    avail = ", ".join(f"{s}/{c}" for s, c in list_characters()) or "(なし)"
    die(f"キャラクターフォルダが見つかりません: {series}/{name}\n  利用可能: {avail}")
    raise AssertionError  # unreachable


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="tripo.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="python Tools/Tripo/tripo.py [-c CHARACTER] [--series SERIES] <tripo_cli サブコマンド> [args...]",
    )
    ap.add_argument("-c", "--character", metavar="CHAR",
                    help="対象キャラクター: 16 / Corefolder-16 / NumberTales/Corefolder-16")
    ap.add_argument("--series", default=DEFAULT_SERIES,
                    help=f"作品シリーズフォルダ名 (既定: {DEFAULT_SERIES})")
    ap.add_argument("--list", action="store_true", help="キャラクターフォルダ一覧を表示して終了")
    ap.add_argument("cli", nargs=argparse.REMAINDER, help="tripo_cli.py へ渡す引数")
    args = ap.parse_args()

    if args.list:
        for s, c in list_characters():
            gen = NATIVE_ROOT / s / c / GENERATED_DIRNAME
            mark = " (TripoGenerated あり)" if gen.is_dir() else ""
            print(f"{s}/{c}{mark}")
        return

    if not CLI.is_file():
        die(f"CLI が見つかりません: {CLI}")
    if not args.cli:
        ap.print_help()
        sys.exit(2)

    # .env: リポジトリ直下 → Tools/Tripo (CLI 側でも読むが順序を明示)。OS 環境変数が最優先。
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(HERE / ".env")

    subcmd = args.cli[0]
    if args.character:
        char_dir = resolve_character(args.character, args.series)
        gen_dir = char_dir / GENERATED_DIRNAME
        os.environ["TRIPO_OUTPUT_DIR"] = str(gen_dir)
        os.environ["TRIPO_LOG_DIR"] = str(gen_dir)
        os.chdir(char_dir)
        print(f"[tripo] character = {char_dir.relative_to(REPO_ROOT).as_posix()}")
        print(f"[tripo] outputs   = {gen_dir.relative_to(REPO_ROOT).as_posix()}/")
    elif subcmd not in NO_CHARACTER_OK:
        die(f"'{subcmd}' は成果物を書き出すため -c/--character の指定が必要です "
            f"(一覧: python Tools/Tripo/tripo.py --list)")
    else:
        # キャラ指定なし: Tools/Tripo/outputs (.gitignore 済) に落ちる
        os.environ.setdefault("TRIPO_OUTPUT_DIR", str(HERE / "outputs"))
        os.environ.setdefault("TRIPO_LOG_DIR", str(HERE / "logs"))

    sys.argv = [str(CLI), *args.cli]
    runpy.run_path(str(CLI), run_name="__main__")


if __name__ == "__main__":
    main()
