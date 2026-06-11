"""
05A_XZ_Ritumenzu_Generator.py
集水桝 XZ立面図生成ツール（手前面から見た正面図）

【入出力】
  入力 : masu_params.json
         masu_coords.json
  出力 : masu_XZ.dxf
         dimension_XZ.json

【描画方針】
  全ボックスのエッジ12本をXZ投影で描画（選別なし）
  床掘・切り欠き : 破線
  その他         : 実線
"""

import json
import os
import sys

try:
    import ezdxf
except ImportError:
    print("ezdxfがインストールされていません。pip install ezdxf を実行してください。")
    sys.exit(1)

PARAM_FILE = "masu_params.json"
COORD_FILE = "masu_coords.json"
DXF_OUT    = "masu_XZ.dxf"
DIM_JSON   = "dimension_XZ.json"

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

def xz(pt):
    """3D座標からXZ投影（mm変換）Z軸が縦軸"""
    return (pt[0] * MM, pt[2] * MM)


def add_line(msp, p1, p2, layer, lt="Continuous"):
    if abs(p1[0] - p2[0]) < 0.001 and abs(p1[1] - p2[1]) < 0.001:
        return  # 同一点は描画しない
    msp.add_line(
        (p1[0], p1[1], 0),
        (p2[0], p2[1], 0),
        dxfattribs={"layer": layer, "linetype": lt}
    )


def draw_box_xz(msp, box, layer, lt="Continuous"):
    """
    ボックスの全エッジ12本をXZ投影で描画。
    底面4本・天端4本・縦4本。
    """
    top = box["天"]
    btm = box["底"]

    keys = BOX_KEYS
    # 底面ループ
    for i in range(4):
        k0 = keys[i]
        k1 = keys[(i + 1) % 4]
        add_line(msp, xz(btm[k0]), xz(btm[k1]), layer, lt)
    # 天端ループ
    for i in range(4):
        k0 = keys[i]
        k1 = keys[(i + 1) % 4]
        add_line(msp, xz(top[k0]), xz(top[k1]), layer, lt)
    # 縦線
    for k in keys:
        add_line(msp, xz(btm[k]), xz(top[k]), layer, lt)


def draw_saiseki(msp, coords):
    """
    砕石のXZ投影。
    通常のボックス12本 + 外壁底面より外側のはみ出し上辺。
    """
    draw_box_xz(msp, coords["砕石"], L_BASE)

    # 外壁底面X座標
    gai_btm = coords["外壁"]["底"]
    sai_top = coords["砕石"]["天"]

    gai_lf_x = gai_btm["LF"][0] * MM
    gai_rf_x = gai_btm["RF"][0] * MM
    sai_lf_x = sai_top["LF"][0] * MM
    sai_rf_x = sai_top["RF"][0] * MM
    z_sai    = sai_top["RF"][2] * MM

    # 左はみ出し（砕石左端→外壁左端）
    if abs(sai_lf_x - gai_lf_x) > 0.1:
        add_line(msp, (sai_lf_x, z_sai), (gai_lf_x, z_sai), L_BASE)
    # 右はみ出し（外壁右端→砕石右端）
    if abs(sai_rf_x - gai_rf_x) > 0.1:
        add_line(msp, (gai_rf_x, z_sai), (sai_rf_x, z_sai), L_BASE)


def draw_kirinuki_xz(msp, coords):
    """
    切り欠きのXZ投影（すべて破線）
    右・左面 : X位置に内壁・外壁の縦線と上下横線
    手前・奥面: XZ投影で矩形
    """
    for k in coords.get("切り欠き", []):
        face    = k["取付面"]
        pts_in  = k["内面_pts"]
        pts_out = k["外面_pts"]

        if face in ["右", "左"]:
            x_in  = pts_in[0][0]  * MM
            x_out = pts_out[0][0] * MM
            zs    = [p[2] * MM for p in pts_in]
            z_lo  = min(zs)
            z_hi  = max(zs)
            add_line(msp, (x_in,  z_lo), (x_in,  z_hi), L_KIRI, "DASHED")
            add_line(msp, (x_out, z_lo), (x_out, z_hi), L_KIRI, "DASHED")
            add_line(msp, (x_in,  z_lo), (x_out, z_lo), L_KIRI, "DASHED")
            add_line(msp, (x_in,  z_hi), (x_out, z_hi), L_KIRI, "DASHED")

        else:  # 手前・奥
            xs = [p[0] * MM for p in pts_in]
            zs = [p[2] * MM for p in pts_in]
            x_lo = min(xs); x_hi = max(xs)
            z_lo = min(zs); z_hi = max(zs)
            cx = (x_lo + x_hi) / 2
            cz = (z_lo + z_hi) / 2
            rx = (x_hi - x_lo) / 2
            rz = (z_hi - z_lo) / 2
            if k["断面形状"] == "円形":
                # 正円で描画（手前・奥面は正面から見えるので正円）
                msp.add_circle((cx, cz, 0), rx,
                               dxfattribs={"layer": L_KIRI, "linetype": "DASHED"})
            else:
                add_line(msp, (x_lo, z_lo), (x_hi, z_lo), L_KIRI, "DASHED")
                add_line(msp, (x_hi, z_lo), (x_hi, z_hi), L_KIRI, "DASHED")
                add_line(msp, (x_hi, z_hi), (x_lo, z_hi), L_KIRI, "DASHED")
                add_line(msp, (x_lo, z_hi), (x_lo, z_lo), L_KIRI, "DASHED")


# ==========================================
# dimension_XZ.json 生成
# ==========================================

def make_dim_json(coords, params, scale_n):
    def top_xz(box):
        return {k: [box["天"][k][0] * MM, box["天"][k][2] * MM]
                for k in BOX_KEYS}
    def btm_xz(box):
        return {k: [box["底"][k][0] * MM, box["底"][k][2] * MM]
                for k in BOX_KEYS}

    obj = {}
    for name in ["砕石", "外壁", "内腔", "床掘"]:
        if coords.get(name):
            obj[name] = {"天": top_xz(coords[name]), "底": btm_xz(coords[name])}
    if coords.get("受枠"):
        obj["受枠"] = {"天": top_xz(coords["受枠"]), "底": btm_xz(coords["受枠"])}

    n  = params["内腔寸法"]
    wt = params["構造寸法"]["壁厚"]
    st = params["構造寸法"]["砕石厚"]
    bt = params["構造寸法"]["底版厚"]

    return {
        "図面情報": {
            "種別":          "XZ立面図",
            "縮尺":          scale_n,
            "文字高さ_mm":   scale_n * 3.5,
            "矢印サイズ_mm": scale_n * 2.5,
        },
        "構造寸法": {
            "内腔X_mm":  n["X"] * MM,
            "壁厚_mm":   wt     * MM,
            "底版厚_mm": bt     * MM,
            "砕石厚_mm": st     * MM,
        },
        "オブジェクト": obj,
        "切り欠き": [
            {
                "番号":     k["番号"],
                "取付面":   k["取付面"],
                "断面形状": k["断面形状"],
                "管底Z_mm": k["管底Z"] * MM,
                "管頂Z_mm": k["管頂Z"] * MM,
                "x_lo_mm":  min(p[0] for p in k["内面_pts"]) * MM,
                "x_hi_mm":  max(p[0] for p in k["内面_pts"]) * MM,
            }
            for k in coords.get("切り欠き", [])
        ],
    }


# ==========================================
# メイン
# ==========================================

def main():
    print("\n" + "="*50)
    print("  集水桝 XZ立面図  05A_XZ_Ritumenzu_Generator.py")
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

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm

    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[4.0, 2.0])

    for name, color in LAYERS.items():
        lyr = doc.layers.new(name)
        lyr.color = color

    msp = doc.modelspace()

    draw_box_xz(msp, coords["外壁"], L_CONC)
    draw_box_xz(msp, coords["内腔"], L_CONC)
    draw_saiseki(msp, coords)
    draw_box_xz(msp, coords["床掘"], L_EARTH, "DASHED")
    if coords.get("受枠"):
        draw_box_xz(msp, coords["受枠"], L_GRAT)
    draw_kirinuki_xz(msp, coords)

    doc.saveas(DXF_OUT)
    print(f"  [OK] XZ立面図 出力: {DXF_OUT}")

    dim = make_dim_json(coords, params, scale_n)
    with open(DIM_JSON, "w", encoding="utf-8") as f:
        json.dump(dim, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 寸法線用JSON出力: {DIM_JSON}")
    print()


if __name__ == "__main__":
    main()