"""
01_MasuCondition_input.py
集水桝 条件入力ツール

【役割】
  集水桝の設計パラメータを対話入力し、masu_params.json として保存する。
  前回の json が存在する場合は前回値をデフォルトとして表示し、
  Enterキーのみでそのまま採用できる。

【入出力】
  入力 : masu_params.json (存在すれば前回値として読み込み)
  出力 : masu_params.json (カレントディレクトリに保存)

【呼び出し元】
  00_Masu_Tougou.py から subprocess で呼ばれる。
  cwd は base_dir（親ツールと同じフォルダ）に設定される。

【地盤条件 JSONキー仕様】
  突出有無     : "有" / "無"
  突出高さ     : float (M)  ※突出有のみ有効
  傾斜有無     : "有" / "無"
  傾斜方向     : "X" / "Y"  ※傾斜有のみ有効
  低い側       : "右"/"左"(X方向) / "手前"/"奥"(Y方向)  ※傾斜有のみ有効
  天端指定方法 : "勾配" / "高低差"  ※傾斜有のみ有効
  勾配_percent : float       ※天端指定方法=勾配のみ有効
  高低差       : float (M)   ※天端指定方法=高低差のみ有効  Z低からの差分
"""

import copy
import json
import os
import sys

PARAM_FILE = "masu_params.json"

DEFAULT_PARAMS = {
    "プロジェクト名": "",
    "地盤条件": {
        "突出有無":     "無",
        "突出高さ":     0.0,
        "傾斜有無":     "無",
        "傾斜方向":     "X",
        "低い側":       "右",
        "天端指定方法": "勾配",
        "勾配_percent": 0.0,
        "高低差":       0.0
    },
    "内腔寸法": {
        "X":   0.6,
        "Y":   0.6,
        "Z低": 0.6
    },
    "構造寸法": {
        "壁厚":     0.15,
        "底版厚":   0.15,
        "砕石厚":   0.10,
        "砕石張出": 0.05
    },
    "グレーチング": {
        "有無": "無",
    },
    "切り欠き_デフォルト": {
        "管底高さ_内壁底":    0.15,
        "管底高さ_天端下がり": 0.50,
        "開口幅":  0.3,
        "開口高さ": 0.3,
        "管径":    0.2,
    },
    "切り欠き": [],
    "床掘": {
        "余裕幅":           0.5,
        "床掘勾配の閾値": 1.0
    },
    "図面設定": {
        "2D縮尺": 20
    }
}

# ==========================================
# 入力補助関数
# ==========================================

def input_float(prompt, existing=None, unit="M"):
    """浮動小数点入力。Enterで existing を返す。unitで単位表示を切替。"""
    while True:
        default_str = f"{existing}{unit}" if existing is not None else "-"
        val = input(f"  {prompt} [現在: {default_str}] > ").strip()
        if val == "" and existing is not None:
            return existing
        try:
            return float(val)
        except ValueError:
            print("    ※ 数値を入力してください。")


def input_int(prompt, existing=None):
    while True:
        default_str = str(existing) if existing is not None else "-"
        val = input(f"  {prompt} [現在: {default_str}] > ").strip()
        if val == "" and existing is not None:
            return existing
        try:
            return int(val)
        except ValueError:
            print("    ※ 整数を入力してください。")


def input_choice(prompt, choices, existing=None):
    numbered = "  /  ".join(f"{i+1}:{c}" for i, c in enumerate(choices))
    while True:
        default_str = existing if existing is not None else "-"
        val = input(f"  {prompt} [{numbered}] [現在: {default_str}] > ").strip()
        if val == "" and existing is not None:
            return existing
        if val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        if val in choices:
            return val
        print("    ※ 選択肢から選ぶか番号を入力してください。")


def input_yn(prompt, existing=None):
    return input_choice(prompt, ["有", "無"], existing)


def section(title):
    print(f"\n{'─'*45}")
    print(f"  ■ {title}")
    print(f"{'─'*45}")


# ==========================================
# 入力ロジック
# ==========================================

def input_project_name(p):
    """
    プロジェクト名。保存フォルダ名（デスクトップの成果品フォルダ名も含む）
    にそのまま使われるため、空欄は許可しない。
    """
    section("プロジェクト名")
    existing = p.get("プロジェクト名", "")
    while True:
        default_str = existing if existing else "-"
        val = input(f"  プロジェクト名（保存フォルダ名になります） [現在: {default_str}] > ").strip()
        if val == "":
            if existing:
                return
            print("    ※ プロジェクト名を入力してください。")
            continue
        p["プロジェクト名"] = val
        return


def input_chibanjouten(p):
    section("地盤条件")
    c = p["地盤条件"]

    c["突出有無"] = input_yn("地盤からの突出", c.get("突出有無", "無"))

    if c["突出有無"] == "有":
        c["突出高さ"]     = input_float("突出高さ", c.get("突出高さ", 0.0))
        c["傾斜有無"]     = "無"
        c["勾配_percent"] = 0.0
        c["高低差"]       = 0.0

    else:
        c["突出高さ"] = 0.0
        c["傾斜有無"] = input_yn("地盤傾斜", c.get("傾斜有無", "無"))

        if c["傾斜有無"] == "有":
            dir_existing = "X方向" if c.get("傾斜方向", "X") == "X" else "Y方向"
            dir_sel = input_choice("傾斜方向", ["X方向", "Y方向"], dir_existing)
            c["傾斜方向"] = "X" if dir_sel == "X方向" else "Y"

            if c["傾斜方向"] == "X":
                low_choices = ["右", "左"]
            else:
                low_choices = ["手前", "奥"]

            existing_low = c.get("低い側")
            if existing_low not in low_choices:
                existing_low = low_choices[0]
            c["低い側"] = input_choice("低い側", low_choices, existing_low)

            method_existing = "勾配(%)" if c.get("天端指定方法", "勾配") == "勾配" else "高低差(M)"
            method_sel = input_choice(
                "天端の指定方法", ["勾配(%)", "高低差(M)"], method_existing
            )
            if method_sel == "勾配(%)":
                c["天端指定方法"] = "勾配"
                c["勾配_percent"] = input_float(
                    "勾配  ※ 低い側から高い側への上がり率",
                    c.get("勾配_percent", 0.0),
                    unit="%"
                )
                c["高低差"] = 0.0
            else:
                c["天端指定方法"] = "高低差"
                c["高低差"] = input_float(
                    "高低差  ※ Z低からの差分（高い側 - 低い側）",
                    c.get("高低差", 0.0),
                    unit="M"
                )
                c["勾配_percent"] = 0.0

        else:
            c["勾配_percent"] = 0.0
            c["高低差"]       = 0.0

    p["地盤条件"] = c


def input_naikosunpo(p):
    section("内腔寸法")
    n = p["内腔寸法"]
    n["X"]   = input_float("内腔 X", n.get("X",   0.6))
    n["Y"]   = input_float("内腔 Y", n.get("Y",   0.6))
    n["Z低"] = input_float("内腔 Z 低い方", n.get("Z低", 0.6))
    p["内腔寸法"] = n


def input_kozosupo(p):
    section("構造寸法")
    s = p["構造寸法"]
    d = DEFAULT_PARAMS["構造寸法"]
    s["壁厚"]     = input_float("壁厚",     s.get("壁厚",     d["壁厚"]))
    s["底版厚"]   = input_float("底版厚",   s.get("底版厚",   d["底版厚"]))
    s["砕石厚"]   = input_float("砕石厚",   s.get("砕石厚",   d["砕石厚"]))
    s["砕石張出"] = input_float("砕石張出", s.get("砕石張出", d["砕石張出"]))
    p["構造寸法"] = s


def input_grating(p):
    """
    グレーチング受枠の入力。
    受枠X/Y = 内腔X/Y + 壁厚（片側）を毎回計算して提示。
    受枠厚  = (内腔X + 壁厚) / 10 を毎回計算して提示。
    """
    section("グレーチング受枠")
    g = p["グレーチング"]
    n = p["内腔寸法"]
    s = p["構造寸法"]

    preset_x = round(n["X"] + s["壁厚"], 4)
    preset_y = round(n["Y"] + s["壁厚"], 4)
    preset_t = round((n["X"] + s["壁厚"]) / 10, 4)

    g["有無"] = input_yn("グレーチング", g.get("有無", "無"))
    if g["有無"] == "有":
        g["受枠X"]  = input_float("受枠 X", preset_x)
        g["受枠Y"]  = input_float("受枠 Y", preset_y)
        g["受枠厚"] = input_float("受枠厚", preset_t)
    p["グレーチング"] = g


def input_kirinuki(p):
    section("切り欠き（流入管・流出管）")
    old_list = p.get("切り欠き", [])
    kd = DEFAULT_PARAMS["切り欠き_デフォルト"]
    num_k = input_int("切り欠き数", len(old_list))

    new_k = []
    for i in range(num_k):
        print(f"\n  ---- 切り欠き {i+1} 個目 ----")
        old = old_list[i] if i < len(old_list) else {}

        k = {}
        k["番号"]         = i + 1
        k["取付面"]       = input_choice(
            "取付面", ["右", "左", "手前", "奥"],
            old.get("取付面")
        )
        k["断面形状"]     = input_choice(
            "断面形状", ["矩形", "円形"],
            old.get("断面形状")
        )
        k["オフセット"]   = input_float(
            "管中心 横方向オフセット", old.get("オフセット", 0.0)
        )
        k["管底高さ基準"] = input_choice(
            "管底高さ基準",
            ["内壁底からの上がり", "外壁天端からの下がり"],
            old.get("管底高さ基準")
        )
        if k["管底高さ基準"] == "内壁底からの上がり":
            preset_h = kd["管底高さ_内壁底"]
        else:
            preset_h = kd["管底高さ_天端下がり"]
        k["管底高さ"] = input_float(
            "管底高さ", old.get("管底高さ", preset_h)
        )

        k["寸法"] = {}
        if k["断面形状"] == "矩形":
            k["寸法"]["幅"]   = input_float(
                "開口幅",  old.get("寸法", {}).get("幅",  kd["開口幅"])
            )
            k["寸法"]["高さ"] = input_float(
                "開口高さ", old.get("寸法", {}).get("高さ", kd["開口高さ"])
            )
        else:
            k["寸法"]["直径"] = input_float(
                "管径", old.get("寸法", {}).get("直径", kd["管径"])
            )

        new_k.append(k)

    p["切り欠き"] = new_k


def input_yukibori(p):
    section("床掘")
    b = p["床掘"]
    b["余裕幅"]           = input_float(
        "床掘 余裕幅",           b.get("余裕幅",           0.5)
    )
    b["勾配使用深さ閾値"] = input_float(
        "勾配掘り適用 深さ閾値", b.get("勾配使用深さ閾値", 1.0)
    )
    p["床掘"] = b


def input_zumensettei(p):
    section("図面設定")
    d = p["図面設定"]
    d["2D縮尺"] = input_int(
        "2D図面 縮尺 (1/n の n)", d.get("2D縮尺", 20)
    )
    p["図面設定"] = d


# ==========================================
# 確認サマリー表示
# ==========================================

def print_confirm(p):
    n = p["内腔寸法"]
    s = p["構造寸法"]
    c = p["地盤条件"]
    g = p["グレーチング"]

    print("\n  ── 入力確認 ─────────────────────────")
    print(f"  プロジェクト名: {p.get('プロジェクト名', '')}")
    print(f"  内腔寸法    : X={n['X']}M  Y={n['Y']}M  Z低={n['Z低']}M")
    print(f"  壁厚/底版厚 : {s['壁厚']}M / {s['底版厚']}M")
    print(f"  砕石        : 厚={s['砕石厚']}M  張出={s['砕石張出']}M")

    if c["突出有無"] == "有":
        print(f"  地盤条件    : 突出あり  高さ={c['突出高さ']}M")
    elif c["傾斜有無"] == "有":
        dir_label = f"{c['傾斜方向']}方向  低い側={c['低い側']}"
        if c["天端指定方法"] == "勾配":
            val_label = f"勾配={c['勾配_percent']}%"
        else:
            val_label = f"高低差={c['高低差']}M"
        print(f"  地盤条件    : 傾斜あり  {dir_label}  {val_label}")
    else:
        print(f"  地盤条件    : 水平")

    print(f"  グレーチング: {g['有無']}", end="")
    if g["有無"] == "有":
        print(f"  受枠={g['受枠X']}×{g['受枠Y']}M  厚={g['受枠厚']}M", end="")
    print()

    print(f"  切り欠き    : {len(p['切り欠き'])}箇所")
    for k in p["切り欠き"]:
        if k["断面形状"] == "矩形":
            dim = f"幅={k['寸法']['幅']}M×高さ={k['寸法']['高さ']}M"
        else:
            dim = f"φ{k['寸法']['直径']}M"
        print(f"    {k['番号']}. {k['取付面']}面  {k['断面形状']}({dim})"
              f"  ofs={k['オフセット']}M  管底={k['管底高さ']}M({k['管底高さ基準']})")

    print(f"  床掘余裕幅  : {p['床掘']['余裕幅']}M")
    print(f"  2D縮尺      : 1/{p['図面設定']['2D縮尺']}")
    print("  ─────────────────────────────────────")


# ==========================================
# メイン
# ==========================================

def main():
    print("\n" + "="*50)
    print("  集水桝 条件入力ツール  01_MasuCondition_input.py")
    print("="*50)
    print("  ※ Enterキーのみで現在値をそのまま採用します。")

    if os.path.exists(PARAM_FILE):
        with open(PARAM_FILE, "r", encoding="utf-8") as f:
            p = json.load(f)
        print(f"\n  前回のパラメータを読み込みました: {PARAM_FILE}")
    else:
        p = copy.deepcopy(DEFAULT_PARAMS)
        print("\n  初回起動 - デフォルト値で開始します。")

    input_project_name(p)
    input_chibanjouten(p)
    input_naikosunpo(p)
    input_kozosupo(p)
    input_grating(p)
    input_kirinuki(p)
    input_yukibori(p)
    input_zumensettei(p)

    with open(PARAM_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)

    print(f"\n  [OK] パラメータを保存しました: {PARAM_FILE}")
    print_confirm(p)


if __name__ == "__main__":
    main()