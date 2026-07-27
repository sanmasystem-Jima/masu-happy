"""
06A_YZ_Ritumenzu_Generator.py
集水桝 YZ立面図生成ツール（右面から見た側面図）

【座標変換】
  描画X = 元のY座標 × MM
  描画Y = 元のZ座標 × MM
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
DXF_OUT    = "masu_YZ.dxf"
DIM_JSON   = "dimension_YZ.json"

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


def yz(pt):
    """3D座標からYZ投影（mm変換）"""
    return (pt[1] * MM, pt[2] * MM)


def add_line(msp, p1, p2, layer, lt="Continuous"):
    if abs(p1[0] - p2[0]) < 0.001 and abs(p1[1] - p2[1]) < 0.001:
        return
    msp.add_line(
        (p1[0], p1[1], 0),
        (p2[0], p2[1], 0),
        dxfattribs={"layer": layer, "linetype": lt}
    )


def draw_box_yz(msp, box, layer, lt="Continuous"):
    """ボックスの全エッジ12本をYZ投影で描画"""
    top = box["天"]
    btm = box["底"]
    keys = BOX_KEYS

    for i in range(4):
        k0 = keys[i]; k1 = keys[(i + 1) % 4]
        add_line(msp, yz(btm[k0]), yz(btm[k1]), layer, lt)
        add_line(msp, yz(top[k0]), yz(top[k1]), layer, lt)
        add_line(msp, yz(btm[k0]), yz(top[k0]), layer, lt)


def draw_saiseki_yz(msp, coords):
    """砕石のYZ投影 + 外壁底面より外側のはみ出し上辺"""
    draw_box_yz(msp, coords["砕石"], L_BASE)

    gai_btm = coords["外壁"]["底"]
    sai_top = coords["砕石"]["天"]

    gai_lf_y = gai_btm["LF"][1] * MM
    gai_rf_y = gai_btm["RF"][1] * MM
    sai_lf_y = sai_top["LF"][1] * MM
    sai_rf_y = sai_top["RF"][1] * MM
    z_sai    = sai_top["RF"][2] * MM

    # 手前はみ出し（砕石手前端→外壁手前端）
    if abs(sai_lf_y - gai_lf_y) > 0.1:
        add_line(msp, (sai_lf_y, z_sai), (gai_lf_y, z_sai), L_BASE)
    # 奥はみ出し（外壁奥端→砕石奥端）
    if abs(sai_rf_y - gai_rf_y) > 0.1:
        add_line(msp, (gai_rf_y, z_sai), (sai_rf_y, z_sai), L_BASE)


def draw_kirinuki_yz(msp, coords):
    """切り欠きのYZ投影（すべて破線）"""
    for k in coords.get("切り欠き", []):
        face    = k["取付面"]
        pts_in  = k["内面_pts"]
        pts_out = k["外面_pts"]

        if face in ["手前", "奥"]:
            # Y方向に壁厚 → YZ投影では内壁・外壁のY位置に縦線
            y_in  = pts_in[0][1]  * MM
            y_out = pts_out[0][1] * MM
            zs    = [p[2] * MM for p in pts_in]
            z_lo  = min(zs); z_hi = max(zs)
            add_line(msp, (y_in,  z_lo), (y_in,  z_hi), L_KIRI, "DASHED")
            add_line(msp, (y_out, z_lo), (y_out, z_hi), L_KIRI, "DASHED")
            add_line(msp, (y_in,  z_lo), (y_out, z_lo), L_KIRI, "DASHED")
            add_line(msp, (y_in,  z_hi), (y_out, z_hi), L_KIRI, "DASHED")

        else:  # 右・左面
            # X方向の切り欠き → YZ投影で正面に見える
            ys = [p[1] * MM for p in pts_in]
            zs = [p[2] * MM for p in pts_in]
            y_lo = min(ys); y_hi = max(ys)
            z_lo = min(zs); z_hi = max(zs)
            cy = (y_lo + y_hi) / 2
            cz = (z_lo + z_hi) / 2
            ry = (y_hi - y_lo) / 2

            if k["断面形状"] == "円形":
                msp.add_circle((cy, cz, 0), ry,
                               dxfattribs={"layer": L_KIRI, "linetype": "DASHED"})
            else:
                add_line(msp, (y_lo, z_lo), (y_hi, z_lo), L_KIRI, "DASHED")
                add_line(msp, (y_hi, z_lo), (y_hi, z_hi), L_KIRI, "DASHED")
                add_line(msp, (y_hi, z_hi), (y_lo, z_hi), L_KIRI, "DASHED")
                add_line(msp, (y_lo, z_hi), (y_lo, z_lo), L_KIRI, "DASHED")


def make_dim_json(coords, params, scale_n):
    def top_yz(box):
        return {k: [box["天"][k][1] * MM, box["天"][k][2] * MM]
                for k in BOX_KEYS}
    def btm_yz(box):
        return {k: [box["底"][k][1] * MM, box["底"][k][2] * MM]
                for k in BOX_KEYS}

    obj = {}
    for name in ["砕石", "外壁", "内腔", "床掘"]:
        if coords.get(name):
            obj[name] = {"天": top_yz(coords[name]), "底": btm_yz(coords[name])}
    if coords.get("受枠"):
        obj["受枠"] = {"天": top_yz(coords["受枠"]), "底": btm_yz(coords["受枠"])}

    n  = params["内腔寸法"]
    wt = params["構造寸法"]["壁厚"]
    st = params["構造寸法"]["砕石厚"]
    bt = params["構造寸法"]["底版厚"]

    return {
        "図面情報": {
            "種別":          "YZ立面図",
            "縮尺":          scale_n,
            "文字高さ_mm":   scale_n * 3.5,
            "矢印サイズ_mm": scale_n * 2.5,
        },
        "構造寸法": {
            "内腔Y_mm":  n["Y"] * MM,
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
                "y_lo_mm":  min(p[1] for p in k["内面_pts"]) * MM,
                "y_hi_mm":  max(p[1] for p in k["内面_pts"]) * MM,
            }
            for k in coords.get("切り欠き", [])
        ],
    }


def main():
    print("\n" + "="*50)
    print("  集水桝 YZ立面図  06A_YZ_Ritumenzu_Generator.py")
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
    doc.header["$INSUNITS"] = 4

    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[4.0, 2.0])

    for name, color in LAYERS.items():
        lyr = doc.layers.new(name)
        lyr.color = color

    msp = doc.modelspace()

    draw_box_yz(msp, coords["外壁"], L_CONC)
    draw_box_yz(msp, coords["内腔"], L_CONC)
    draw_saiseki_yz(msp, coords)
    draw_box_yz(msp, coords["床掘"], L_EARTH, "DASHED")
    if coords.get("受枠"):
        draw_box_yz(msp, coords["受枠"], L_GRAT)
    draw_kirinuki_yz(msp, coords)

    doc.saveas(DXF_OUT)
    print(f"  [OK] YZ立面図 出力: {DXF_OUT}")

    dim = make_dim_json(coords, params, scale_n)
    with open(DIM_JSON, "w", encoding="utf-8") as f:
        json.dump(dim, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 寸法線用JSON出力: {DIM_JSON}")
    print()


if __name__ == "__main__":
    main()