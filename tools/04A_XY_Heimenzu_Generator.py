"""
04A_XY_Heimenzu_Generator.py
集水桝 XY平面図生成ツール（図形描画のみ・寸法線なし）

【入出力】
  入力 : masu_params.json
         masu_coords.json
  出力 : masu_XY.dxf
         dimension_XY.json  （寸法線ツール用座標データ）

【座標系】
  天端XY座標をそのまま使用（Z抜き）
  単位: メートル → mm変換して出力

【レイヤ】
  MASU_CONC  : 外壁・内腔（白）
  MASU_BASE  : 砕石（黄）
  MASU_GRAT  : 受枠（シアン）
  MASU_KIRI  : 切り欠き（マゼンタ・破線）
  MASU_EARTH : 床掘（緑・破線）

【切り欠き平面表現】
  取付面の幅端2点を内壁・外壁でつなぐ4本線（破線）
  右・左面 → Y方向に幅、X方向に壁厚
  手前・奥面 → X方向に幅、Y方向に壁厚
"""

import json
import os
import sys

try:
    import ezdxf
except ImportError:
    print("ezdxfがインストールされていません。pip install ezdxf を実行してください。")
    sys.exit(1)

PARAM_FILE  = "masu_params.json"
COORD_FILE  = "masu_coords.json"
DXF_OUT     = "masu_XY.dxf"
DIM_JSON    = "dimension_XY.json"

MM = 1000.0

LAYERS = {
    "MASU_CONC":  7,
    "MASU_BASE":  2,
    "MASU_GRAT":  4,
    "MASU_KIRI":  6,
    "MASU_EARTH": 3,
}

L_CONC  = "MASU_CONC"
L_BASE  = "MASU_BASE"
L_GRAT  = "MASU_GRAT"
L_KIRI  = "MASU_KIRI"
L_EARTH = "MASU_EARTH"

BOX_KEYS = ["RF", "LF", "LB", "RB"]


# ==========================================
# ヘルパー
# ==========================================

def mm2(pt):
    """XY座標をmm変換（Z無視）"""
    return (pt[0] * MM, pt[1] * MM)


def add_line(msp, p1, p2, layer, lt="Continuous"):
    msp.add_line(
        (p1[0], p1[1], 0),
        (p2[0], p2[1], 0),
        dxfattribs={"layer": layer, "linetype": lt}
    )


def draw_rect(msp, pts_mm, layer, lt="Continuous"):
    """4点の矩形を描画（閉じる）"""
    n = len(pts_mm)
    for i in range(n):
        add_line(msp, pts_mm[i], pts_mm[(i + 1) % n], layer, lt)


# ==========================================
# 図形描画
# ==========================================

def draw_box_top(msp, box, layer, lt="Continuous"):
    """ボックスの天端XYを矩形描画"""
    top = box["天"]
    pts = [mm2(top[k]) for k in BOX_KEYS]
    draw_rect(msp, pts, layer, lt)


def draw_fukibori(msp, box):
    """
    床掘りの平面描画（すべて破線）
    天端外形・底面外形・4隅の斜め線
    """
    top = box["天"]
    btm = box["底"]
    top_pts = [mm2(top[k]) for k in BOX_KEYS]
    btm_pts = [mm2(btm[k]) for k in BOX_KEYS]
    draw_rect(msp, top_pts, L_EARTH, "DASHED")
    draw_rect(msp, btm_pts, L_EARTH, "DASHED")
    for t, b in zip(top_pts, btm_pts):
        add_line(msp, t, b, L_EARTH, "DASHED")


def draw_kirinuki(msp, kiri_list, wt_mm):
    """
    切り欠きの平面投影を描画。
    取付面の幅端2点を内壁・外壁でつなぐ4本線（破線）。
    """
    for k in kiri_list:
        face = k["取付面"]
        pts_in  = k["内面_pts"]
        pts_out = k["外面_pts"]

        if face in ["右", "左"]:
            # Y方向に幅を持つ → Y最小・最大を使う
            y_vals_in  = [p[1] * MM for p in pts_in]
            y_vals_out = [p[1] * MM for p in pts_out]
            x_in  = pts_in[0][0]  * MM
            x_out = pts_out[0][0] * MM
            y_lo = min(y_vals_in)
            y_hi = max(y_vals_in)

            # 内壁線・外壁線・つなぎ線2本
            add_line(msp, (x_in,  y_lo), (x_in,  y_hi), L_KIRI, "DASHED")
            add_line(msp, (x_out, y_lo), (x_out, y_hi), L_KIRI, "DASHED")
            add_line(msp, (x_in,  y_lo), (x_out, y_lo), L_KIRI, "DASHED")
            add_line(msp, (x_in,  y_hi), (x_out, y_hi), L_KIRI, "DASHED")

        else:  # 手前・奥
            # X方向に幅を持つ
            x_vals_in  = [p[0] * MM for p in pts_in]
            x_vals_out = [p[0] * MM for p in pts_out]
            y_in  = pts_in[0][1]  * MM
            y_out = pts_out[0][1] * MM
            x_lo = min(x_vals_in)
            x_hi = max(x_vals_in)

            add_line(msp, (x_lo, y_in),  (x_hi, y_in),  L_KIRI, "DASHED")
            add_line(msp, (x_lo, y_out), (x_hi, y_out), L_KIRI, "DASHED")
            add_line(msp, (x_lo, y_in),  (x_lo, y_out), L_KIRI, "DASHED")
            add_line(msp, (x_hi, y_in),  (x_hi, y_out), L_KIRI, "DASHED")


# ==========================================
# dimension_XY.json 生成
# ==========================================

def make_dim_json(coords, params, scale_n):
    """寸法線ツール用の座標JSONを生成"""
    def top_xy(box):
        return {k: [box["天"][k][0] * MM, box["天"][k][1] * MM] for k in BOX_KEYS}

    obj = {}
    for name in ["砕石", "外壁", "内腔", "床掘"]:
        if coords.get(name):
            obj[name] = top_xy(coords[name])
    if coords.get("受枠"):
        obj["受枠"] = top_xy(coords["受枠"])

    kiri = []
    for k in coords.get("切り欠き", []):
        face = k["取付面"]
        pts_in  = k["内面_pts"]
        pts_out = k["外面_pts"]
        if face in ["右", "左"]:
            y_lo = min(p[1] for p in pts_in) * MM
            y_hi = max(p[1] for p in pts_in) * MM
            x_in  = pts_in[0][0]  * MM
            x_out = pts_out[0][0] * MM
            kiri.append({
                "番号": k["番号"], "取付面": face, "断面形状": k["断面形状"],
                "x_内壁": x_in, "x_外壁": x_out,
                "y_lo": y_lo, "y_hi": y_hi,
            })
        else:
            x_lo = min(p[0] for p in pts_in) * MM
            x_hi = max(p[0] for p in pts_in) * MM
            y_in  = pts_in[0][1]  * MM
            y_out = pts_out[0][1] * MM
            kiri.append({
                "番号": k["番号"], "取付面": face, "断面形状": k["断面形状"],
                "y_内壁": y_in, "y_外壁": y_out,
                "x_lo": x_lo, "x_hi": x_hi,
            })

    n  = params["内腔寸法"]
    wt = params["構造寸法"]["壁厚"]

    return {
        "図面情報": {
            "種別":       "平面図 XY",
            "縮尺":       scale_n,
            "文字高さ_mm": scale_n * 3.5,
            "矢印サイズ_mm": scale_n * 2.5,
        },
        "構造寸法": {
            "内腔X_mm":  n["X"]  * MM,
            "内腔Y_mm":  n["Y"]  * MM,
            "壁厚_mm":   wt      * MM,
        },
        "オブジェクト": obj,
        "切り欠き":     kiri,
    }


# ==========================================
# メイン
# ==========================================

def main():
    print("\n" + "="*50)
    print("  集水桝 XY平面図  04A_XY_Heimenzu_Generator.py")
    print("="*50)

    for fname in [PARAM_FILE, COORD_FILE]:
        if not os.path.exists(fname):
            print(f"[ERROR] {fname} が見つかりません。")
            sys.exit(1)

    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        params = json.load(f)
    with open(COORD_FILE, "r", encoding="utf-8") as f:
        coords = json.load(f)

    scale_n = params["図面設定"]["2D縮尺"]
    wt_mm   = params["構造寸法"]["壁厚"] * MM

    # DXF生成
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm

    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[4.0, 2.0])

    for name, color in LAYERS.items():
        lyr = doc.layers.new(name)
        lyr.color = color

    msp = doc.modelspace()

    # 図形描画
    draw_box_top(msp, coords["砕石"], L_BASE)
    draw_box_top(msp, coords["外壁"], L_CONC)
    draw_box_top(msp, coords["内腔"], L_CONC)
    draw_fukibori(msp, coords["床掘"])
    if coords.get("受枠"):
        draw_box_top(msp, coords["受枠"], L_GRAT)

    draw_kirinuki(msp, coords.get("切り欠き", []), wt_mm)

    doc.saveas(DXF_OUT)
    print(f"  [OK] XY平面図 出力: {DXF_OUT}")

    # dimension_XY.json 出力
    dim = make_dim_json(coords, params, scale_n)
    with open(DIM_JSON, "w", encoding="utf-8") as f:
        json.dump(dim, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 寸法線用JSON出力: {DIM_JSON}")
    print()


if __name__ == "__main__":
    main()