"""
00_Masu_Tougou.py
集水桝 一括生成ツール - 統合親ツール
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ==========================================
# 定数
# ==========================================

STEPS = [
    (1, "01_MasuCondition_input.py",          ["masu_params.json"],                        False),
    (2, "02_3dDXF_Generator.py",              ["masu_coords.json", "masu_3d.dxf"],         False),
    (3, "03_Suuryouhyou_Generator.py",        ["masu_suuryou.txt"],                        True),
    (4, "04A_XY_Heimenzu_Generator.py",       ["masu_XY.dxf", "dimension_XY.json"],        False),
    (5, "04B_XY_Sunpou_Generator.py",         ["masu_XY.dxf"],                             True),
    (6, "05A_XZ_Ritumenzu_Generator.py",      ["masu_XZ.dxf", "dimension_XZ.json"],        False),
    (7, "05B_XZ_Sunpou_Generator.py",         ["masu_XZ.dxf"],                             True),
    (8, "06A_YZ_Ritumenzu_Generator.py",      ["masu_YZ.dxf", "dimension_YZ.json"],        False),
    (9, "06B_YZ_Sunpou_Generator.py",         ["masu_YZ.dxf"],                             True),
]

STEP_LABELS = {
    1: "条件入力",
    2: "3D DXF生成",
    3: "数量計算書",
    4: "XY平面図",
    5: "XY寸法線",
    6: "XZ立面図",
    7: "XZ寸法線",
    8: "YZ立面図",
    9: "YZ寸法線",
}

# 成果品として最終的にデスクトップへ書き出すファイル（DXF4個 + 数量計算書）
DELIVERABLE_FILES = [
    "masu_3d.dxf",
    "masu_XY.dxf",
    "masu_XZ.dxf",
    "masu_YZ.dxf",
    "masu_suuryou.txt",
]

# ==========================================
# ユーティリティ
# ==========================================

def yn_input(prompt):
    while True:
        val = input(f"{prompt} [Y/N]: ").strip().upper()
        if val in ("Y", "N"):
            return val == "Y"
        print("  ※ Y か N を入力してください。")


def make_output_folder_name(base_dir, params_path):
    try:
        with open(params_path, "r", encoding="utf-8") as f:
            p = json.load(f)
        x  = p["内腔寸法"]["X"]
        y  = p["内腔寸法"]["Y"]
        zl = p["内腔寸法"]["Z低"]

        def fmt(v):
            s = f"{v:.4f}".rstrip("0")
            if s.endswith("."): s += "0"
            return s

        base_name = f"output_Masu_{fmt(x)}×{fmt(y)}×{fmt(zl)}"
    except Exception:
        base_name = "output_Masu"

    candidate = base_dir / base_name
    if not candidate.exists():
        return candidate

    n = 2
    while True:
        candidate = base_dir / f"{base_name}_{n}"
        if not candidate.exists():
            return candidate
        n += 1


def print_separator(char="=", width=50):
    print(char * width)


def print_header(title):
    print_separator()
    print(f"  {title}")
    print_separator()


def set_hidden_attribute(path, hidden=True):
    """Windows で出力フォルダを隠し属性にします。"""
    if os.name != "nt":
        return

    import ctypes

    FILE_ATTRIBUTE_HIDDEN = 0x2
    INVALID_FILE_ATTRIBUTES = -1

    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == INVALID_FILE_ATTRIBUTES:
            return

        if hidden:
            new_attrs = attrs | FILE_ATTRIBUTE_HIDDEN
        else:
            new_attrs = attrs & ~FILE_ATTRIBUTE_HIDDEN

        ctypes.windll.kernel32.SetFileAttributesW(str(path), new_attrs)
    except Exception:
        pass


def hide_output_tree(path):
    """出力フォルダ配下を再帰的に隠し属性にします。"""
    if not path.exists():
        return

    for root, dirs, files in os.walk(path):
        current_root = Path(root)
        for name in dirs + files:
            set_hidden_attribute(current_root / name, True)


def get_desktop_dir():
    return Path.home() / "Desktop"


def export_deliverables(output_dir):
    """DXF4個と数量計算書を、デスクトップ上のフォルダに書き出します。"""
    desktop_dir = get_desktop_dir()
    dest_name = output_dir.name
    if dest_name.startswith("output_"):
        dest_name = dest_name[len("output_"):]
    dest_dir = desktop_dir / dest_name

    dest_dir.mkdir(parents=True, exist_ok=True)

    copied, missing = [], []
    for fname in DELIVERABLE_FILES:
        src = output_dir / fname
        if src.exists():
            shutil.copy2(str(src), str(dest_dir / fname))
            copied.append(fname)
        else:
            missing.append(fname)

    return dest_dir, copied, missing


# ==========================================
# メイン処理
# ==========================================

def run_session(base_dir, tools_dir, prev_params_path=None, skip_input=False):
    results = []
    step_no, script, required_files, skippable = STEPS[0]
    script_path = tools_dir / script
    temp_params = base_dir / "masu_params.json"

    # 前回パラメータを base_dir に一時配置
    if prev_params_path and prev_params_path.exists():
        shutil.copy2(prev_params_path, temp_params)
        print(f"\n  前回のパラメータを引き継ぎます: {prev_params_path.parent.name}")

    print(f"\n--- STEP {step_no}: {STEP_LABELS[step_no]} ---")

    if skip_input:
        if not temp_params.exists():
            print(f"[ERROR] masu_params.json が見つかりません。")
            sys.exit(1)
        print("  [SKIP] 既存パラメータを使用します。")
        results.append((step_no, STEP_LABELS[step_no], "SKIP", "条件入力スキップ"))
    else:
        if not script_path.exists():
            print(f"[ERROR] {script} が tools/ フォルダに見つかりません。")
            sys.exit(1)
        try:
            subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(base_dir),
                check=True
            )
        except subprocess.CalledProcessError:
            print(f"\n[ERROR] STEP {step_no} が異常終了しました。")
            results.append((step_no, STEP_LABELS[step_no], "ERROR", script))
            print_summary(results, output_dir=None)
            sys.exit(1)
        results.append((step_no, STEP_LABELS[step_no], "OK", "masu_params.json"))

    if not temp_params.exists():
        print(f"\n[ERROR] masu_params.json が生成されませんでした。")
        sys.exit(1)

    # output_dir の決定
    if skip_input and prev_params_path:
        # 既存フォルダを選択した場合 → そのフォルダに上書き
        output_dir = prev_params_path.parent
        shutil.copy2(str(temp_params), str(output_dir / "masu_params.json"))
        temp_params.unlink()
        set_hidden_attribute(output_dir, True)
        hide_output_tree(output_dir)
    else:
        # 新規入力の場合 → 新フォルダを作成
        output_dir = make_output_folder_name(base_dir, temp_params)
        output_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_params), str(output_dir / "masu_params.json"))
        set_hidden_attribute(output_dir, True)
        hide_output_tree(output_dir)

    print(f"  出力フォルダ: {output_dir.name}")

    # STEP 2〜6
    for step_no, script, required_files, skippable in STEPS[1:]:
        script_path = tools_dir / script
        label = STEP_LABELS[step_no]

        print(f"\n--- STEP {step_no}: {label} ---")

        if not script_path.exists():
            if skippable:
                print(f"  [{script}] が見つかりません。スキップします。（未実装）")
                results.append((step_no, label, "SKIP", "未実装"))
                continue
            else:
                print(f"[ERROR] {script} が tools/ フォルダに見つかりません。")
                results.append((step_no, label, "ERROR", "スクリプト不在"))
                print_summary(results, output_dir)
                sys.exit(1)

        try:
            subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(output_dir),
                check=True
            )
        except subprocess.CalledProcessError:
            print(f"\n[ERROR] STEP {step_no} が異常終了しました。")
            results.append((step_no, label, "ERROR", script))
            print_summary(results, output_dir)
            sys.exit(1)

        missing = [f for f in required_files if not (output_dir / f).exists()]
        if missing:
            print(f"[ERROR] 必須出力ファイルが見つかりません: {missing}")
            results.append((step_no, label, "ERROR", f"出力なし: {missing}"))
            print_summary(results, output_dir)
            sys.exit(1)

        results.append((step_no, label, "OK", " / ".join(required_files)))

    desktop_dir, copied, missing_deliverables = export_deliverables(output_dir)
    if missing_deliverables:
        results.append((None, "成果品書き出し", "ERROR", f"見つからず: {missing_deliverables}"))
    else:
        results.append((None, "成果品書き出し", "OK", desktop_dir.name))

    print_summary(results, output_dir, desktop_dir)
    return output_dir


def print_summary(results, output_dir, desktop_dir=None):
    print()
    print_header("集水桝 一括生成ツール 完了サマリー")
    for step_no, label, status, note in results:
        tag = f"[{status:<4}]"
        no_str = f"{step_no:02d}" if step_no is not None else "  "
        print(f"  {tag}  {no_str} {label:<12}  {note}")
    print_separator()
    if output_dir:
        print(f"  出力フォルダ: {output_dir}")
    if desktop_dir:
        print(f"  成果品フォルダ（デスクトップ）: {desktop_dir}")
    print_separator()


# ==========================================
# エントリーポイント
# ==========================================

def main():
    base_dir  = Path(__file__).parent.resolve()
    tools_dir = base_dir / "tools"

    print_header("集水桝 一括生成ツール  00_Masu_Tougou.py")

    if not tools_dir.exists():
        tools_dir.mkdir()
        print(f"  tools/ フォルダを作成しました。子ツールを配置してから再実行してください。")
        sys.exit(0)

    # 既存フォルダの一覧表示と選択
    skip_input = False
    prev_params_path = None

    # 初回は無条件で新規入力に進む（選択不要）
    skip_input = False
    prev_params_path = None

    existing_folders = sorted([
        d for d in base_dir.iterdir()
        if d.is_dir()
        and d.name.startswith("output_Masu_")
        and (d / "masu_params.json").exists()
    ])

    print("\n  既存パラメータの使用方法を選んでください:")
    print("    0: 新規作成")
    if existing_folders:
        print("    1: 既存条件をそのまま使用")
        print("    2: 既存条件を部分変更")
    while True:
        sel = input("  番号 > ").strip()
        if sel == "0":
            break
        if sel in ("1", "2") and existing_folders:
            print("\n  使用するフォルダを選んでください:")
            for i, folder in enumerate(existing_folders, 1):
                print(f"    {i}: {folder.name}")
            while True:
                fsel = input("  番号 > ").strip()
                if fsel.isdigit() and 1 <= int(fsel) <= len(existing_folders):
                    prev_params_path = existing_folders[int(fsel) - 1] / "masu_params.json"
                    shutil.copy2(prev_params_path, base_dir / "masu_params.json")
                    print(f"  読み込み元: {prev_params_path.parent.name}")
                    skip_input = (sel == "1")
                    break
                print("    ※ 番号を入力してください。")
            break
        print("    ※ 番号を入力してください。")

    session = 1

    while True:
        print(f"\n{'='*50}")
        print(f"  桝 {session} 枚目の処理を開始します")
        print(f"{'='*50}")

        output_dir = run_session(base_dir, tools_dir, prev_params_path, skip_input)

        print()
        if not yn_input("続いて次の集水桝の入力をしますか？"):
            print("\n  終了します。お疲れ様でした。")
            break


        # 次の桝：既存フォルダ選択から始める
        skip_input = False
        prev_params_path = None

        session = 1

        existing_folders = sorted([
            d for d in base_dir.iterdir()
            if d.is_dir()
            and d.name.startswith("output_Masu_")
            and (d / "masu_params.json").exists()
        ])

        print("\n  既存パラメータの使用方法を選んでください:")
        print("    0: 新規作成")
        if existing_folders:
            print("    1: 既存条件をそのまま使用")
            print("    2: 既存条件を部分変更")
        while True:
            sel = input("  番号 > ").strip()
            if sel == "0":
                break
            if sel in ("1", "2") and existing_folders:
                print("\n  使用するフォルダを選んでください:")
                for i, folder in enumerate(existing_folders, 1):
                    print(f"    {i}: {folder.name}")
                while True:
                    fsel = input("  番号 > ").strip()
                    if fsel.isdigit() and 1 <= int(fsel) <= len(existing_folders):
                        prev_params_path = existing_folders[int(fsel) - 1] / "masu_params.json"
                        shutil.copy2(prev_params_path, base_dir / "masu_params.json")
                        print(f"  読み込み元: {prev_params_path.parent.name}")
                        skip_input = (sel == "1")
                        break
                    print("    ※ 番号を入力してください。")
                break
            print("    ※ 番号を入力してください。")
        session += 1

        


if __name__ == "__main__":
    main()
