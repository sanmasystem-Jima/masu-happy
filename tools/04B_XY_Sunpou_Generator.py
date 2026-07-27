"""
04B_XY_Sunpou_Generator.py
集水桝 XY平面図 寸法線生成ツール

【入出力】
  入力 : masu_params.json
         dimension_XY.json
  出力 : masu_XY.dxf（既存に寸法線を追加）

【寸法列】（図面上mm・実寸は×縮尺）
  30mm列: 切り欠き幅（重複時24mm→18mm列に退避）
  36mm列: 壁厚・内腔X・壁厚 連続3本（X上／Y左）
  42mm列: 外壁全幅（X上）・外壁全高（Y左）

【補助線処理】
  X寸法線: 計測点のX座標のみ使用、Y座標=砕石外周Y±5mm×縮尺
  Y寸法線: 計測点のY座標のみ使用、X座標=砕石外周X±5mm×縮尺
  dimexo=0 で補助線を延ばさない → 刺さらない

【共通】
  色        : 白(7)
  文字高さ  : 3.5 × 縮尺 mm
  矢印      : V型開矢印 4.5 × 縮尺 mm
  文字位置  : 寸法線の上
  補助線突出: 1 × 縮尺 mm
  線幅      : 細線
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
DIM_FILE   = "dimension_XY.json"
DXF_FILE   = "masu_XY.dxf"

L_DIM = "MASU_DIM"


# ==========================================
# 寸法スタイル登録
# ==========================================

def setup_dimstyle(doc, scale_n):
    txt_h   = 3.5 * scale_n
    arr_sz  = 4.5 * scale_n
    ext_ext = 1.0 * scale_n   # 補助線突き出し

    style_name = "MASU_DIM_STYLE"
    if style_name in doc.dimstyles:
        doc.dimstyles.delete(style_name)

    dstyle = doc.dimstyles.new(style_name)
    dstyle.dxf.dimtxt  = txt_h
    dstyle.dxf.dimasz  = arr_sz
    dstyle.dxf.dimexo  = 0       # 補助線オフセットなし（計測点を外側に設定済み）
    dstyle.dxf.dimexe  = ext_ext
    dstyle.dxf.dimtad  = 1       # 文字を寸法線の上
    dstyle.dxf.dimclrd = 7       # 寸法線色: 白
    dstyle.dxf.dimclre = 7       # 補助線色: 白
    dstyle.dxf.dimclrt = 7       # 文字色:   白
    dstyle.dxf.dimlwd  = -4      # 細線
    dstyle.dxf.dimlwe  = -4      # 補助線も細線
    dstyle.dxf.dimblk  = "OPEN"
    dstyle.dxf.dimblk1 = "OPEN"
    dstyle.dxf.dimblk2 = "OPEN"

    return style_name


# ==========================================
# 寸法線描画ヘルパー
# ==========================================

def dim_h(msp, x1, x2, ref_y, dim_y, style_name):
    """
    水平寸法線。
    計測点のX座標のみ使用、Y座標=ref_y（砕石外周から5mm外側）。
    dim_y: 寸法線のY位置。
    """
    msp.add_linear_dim(
        base=(x1, dim_y),
        p1=(x1, ref_y),
        p2=(x2, ref_y),
        angle=0,
        dimstyle=style_name,
        dxfattribs={"layer": L_DIM}
    ).render()


def dim_v(msp, y1, y2, ref_x, dim_x, style_name):
    """
    垂直寸法線。
    計測点のY座標のみ使用、X座標=ref_x（砕石外周から5mm外側）。
    dim_x: 寸法線のX位置。
    """
    msp.add_linear_dim(
        base=(dim_x, y1),
        p1=(ref_x, y1),
        p2=(ref_x, y2),
        angle=90,
        dimstyle=style_name,
        dxfattribs={"layer": L_DIM}
    ).render()


# ==========================================
# 切り欠き幅寸法（30mm列・重複時24→18mm退避）
# ==========================================

def add_kiri_dims(msp, dim_data, style_name, scale_n,
                  sai_xmin, sai_xmax, sai_ymin, sai_ymax):

    off_base = 30.0 * scale_n
    off_step =  6.0 * scale_n
    ref_off  =  5.0 * scale_n   # 砕石外周から補助線起点までの離れ
    kiris    = dim_data.get("切り欠き", [])

    faces = {"右": [], "左": [], "手前": [], "奥": []}
    for k in kiris:
        faces[k["取付面"]].append(k)

    def overlap(a_lo, a_hi, b_lo, b_hi):
        return not (a_hi <= b_lo or b_hi <= a_lo)

    def assign_cols(klist, axis):
        ranges = []
        for k in klist:
            ranges.append((k["y_lo"], k["y_hi"]) if axis == "Y"
                          else (k["x_lo"], k["x_hi"]))
        cols = [0] * len(klist)
        for i in range(len(klist)):
            for col in range(3):
                conflict = any(
                    cols[j] == col and overlap(
                        ranges[i][0], ranges[i][1],
                        ranges[j][0], ranges[j][1]
                    )
                    for j in range(i)
                )
                if not conflict:
                    cols[i] = col
                    break
        return cols

    # 右面（垂直寸法・X右外側）
    if faces["右"]:
        cols = assign_cols(faces["右"], "Y")
        ref_x = sai_xmax + ref_off
        for k, col in zip(faces["右"], cols):
            dim_x = sai_xmax + off_base - col * off_step
            dim_v(msp, k["y_lo"], k["y_hi"], ref_x, dim_x, style_name)

    # 左面（垂直寸法・X左外側）
    if faces["左"]:
        cols = assign_cols(faces["左"], "Y")
        ref_x = sai_xmin - ref_off
        for k, col in zip(faces["左"], cols):
            dim_x = sai_xmin - off_base + col * off_step
            dim_v(msp, k["y_lo"], k["y_hi"], ref_x, dim_x, style_name)

    # 手前面（水平寸法・Y手前外側）
    if faces["手前"]:
        cols = assign_cols(faces["手前"], "X")
        ref_y = sai_ymin - ref_off
        for k, col in zip(faces["手前"], cols):
            dim_y = sai_ymin - off_base + col * off_step
            dim_h(msp, k["x_lo"], k["x_hi"], ref_y, dim_y, style_name)

    # 奥面（水平寸法・Y奥外側）
    if faces["奥"]:
        cols = assign_cols(faces["奥"], "X")
        ref_y = sai_ymax + ref_off
        for k, col in zip(faces["奥"], cols):
            dim_y = sai_ymax + off_base - col * off_step
            dim_h(msp, k["x_lo"], k["x_hi"], ref_y, dim_y, style_name)


# ==========================================
# 36mm列：壁厚・内腔・壁厚
# ==========================================

def add_36mm_dims(msp, dim_data, style_name, scale_n,
                  sai_xmin, sai_xmax, sai_ymin, sai_ymax):

    offset  = 36.0 * scale_n
    ref_off =  5.0 * scale_n
    obj     = dim_data["オブジェクト"]
    gaiheki = obj["外壁"]
    naiko   = obj["内腔"]

    gai_xmin = min(v[0] for v in gaiheki.values())
    gai_xmax = max(v[0] for v in gaiheki.values())
    gai_ymin = min(v[1] for v in gaiheki.values())
    gai_ymax = max(v[1] for v in gaiheki.values())
    nai_xmin = min(v[0] for v in naiko.values())
    nai_xmax = max(v[0] for v in naiko.values())
    nai_ymin = min(v[1] for v in naiko.values())
    nai_ymax = max(v[1] for v in naiko.values())

    dim_y_top  = sai_ymax + offset
    dim_x_left = sai_xmin - offset
    ref_y_top  = sai_ymax + ref_off
    ref_x_left = sai_xmin - ref_off

    # X方向上側：左壁厚・内腔X・右壁厚
    dim_h(msp, gai_xmin, nai_xmin, ref_y_top, dim_y_top, style_name)
    dim_h(msp, nai_xmin, nai_xmax, ref_y_top, dim_y_top, style_name)
    dim_h(msp, nai_xmax, gai_xmax, ref_y_top, dim_y_top, style_name)

    # Y方向左側：手前壁厚・内腔Y・奥壁厚
    dim_v(msp, gai_ymin, nai_ymin, ref_x_left, dim_x_left, style_name)
    dim_v(msp, nai_ymin, nai_ymax, ref_x_left, dim_x_left, style_name)
    dim_v(msp, nai_ymax, gai_ymax, ref_x_left, dim_x_left, style_name)


# ==========================================
# 42mm列：外壁全幅・全高
# ==========================================

def add_42mm_dims(msp, dim_data, style_name, scale_n,
                  sai_xmin, sai_xmax, sai_ymin, sai_ymax):

    offset  = 42.0 * scale_n
    ref_off =  5.0 * scale_n
    obj     = dim_data["オブジェクト"]
    gaiheki = obj["外壁"]

    gai_xmin = min(v[0] for v in gaiheki.values())
    gai_xmax = max(v[0] for v in gaiheki.values())
    gai_ymin = min(v[1] for v in gaiheki.values())
    gai_ymax = max(v[1] for v in gaiheki.values())

    dim_y_top  = sai_ymax + offset
    dim_x_left = sai_xmin - offset
    ref_y_top  = sai_ymax + ref_off
    ref_x_left = sai_xmin - ref_off

    # X方向上側：外壁全幅
    dim_h(msp, gai_xmin, gai_xmax, ref_y_top, dim_y_top, style_name)

    # Y方向左側：外壁全高
    dim_v(msp, gai_ymin, gai_ymax, ref_x_left, dim_x_left, style_name)


# ==========================================
# グレーチング受枠寸法テキスト
# ==========================================

def add_grating_text(msp, params, scale_n, sai_xmin, sai_xmax, sai_ymin):
    """
    平面図下にグレーチング受枠寸法を表示。
    グレーチングなしの場合は何も描かない。
    """
    g = params.get("グレーチング", {})
    if g.get("有無") != "有":
        return

    gx  = g["受枠X"] * 1000
    gy  = g["受枠Y"] * 1000
    gt  = g["受枠厚"] * 1000
    txt = f"グレーチング受枠  X={gx:.0f}  Y={gy:.0f}  t={gt:.0f}"

    txt_h   = 3.5 * scale_n
    center_x = (sai_xmin + sai_xmax) / 2
    pos_y    = sai_ymin - 60.0 * scale_n

    msp.add_text(
        txt,
        dxfattribs={
            "layer":  L_DIM,
            "height": txt_h,
            "color":  7,
        }
    ).set_placement(
        (center_x, pos_y),
        align=ezdxf.enums.TextEntityAlignment.CENTER
    )


# ==========================================
# メイン
# ==========================================

def main():
    print("\n" + "="*50)
    print("  集水桝 XY寸法線  04B_XY_Sunpou_Generator.py")
    print("="*50)

    for fname in [PARAM_FILE, DIM_FILE, DXF_FILE]:
        if not os.path.exists(fname):
            print(f"[ERROR] {fname} が見つかりません。")
            sys.exit(1)

    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        params = json.load(f)
    with open(DIM_FILE, "r", encoding="utf-8") as f:
        dim_data = json.load(f)

    scale_n = params["図面設定"]["2D縮尺"]

    doc = ezdxf.readfile(DXF_FILE)
    msp = doc.modelspace()

    if L_DIM not in doc.layers:
        lyr = doc.layers.new(L_DIM)
        lyr.color = 7

    style_name = setup_dimstyle(doc, scale_n)

    # 砕石外周座標
    obj = dim_data["オブジェクト"]
    sai = obj.get("砕石", obj.get("外壁"))
    xs  = [v[0] for v in sai.values()]
    ys  = [v[1] for v in sai.values()]
    sai_xmin = min(xs);  sai_xmax = max(xs)
    sai_ymin = min(ys);  sai_ymax = max(ys)

    add_kiri_dims(msp, dim_data, style_name, scale_n,
                  sai_xmin, sai_xmax, sai_ymin, sai_ymax)
    add_36mm_dims(msp, dim_data, style_name, scale_n,
                  sai_xmin, sai_xmax, sai_ymin, sai_ymax)
    add_42mm_dims(msp, dim_data, style_name, scale_n,
                  sai_xmin, sai_xmax, sai_ymin, sai_ymax)
    add_grating_text(msp, params, scale_n, sai_xmin, sai_xmax, sai_ymin)

    doc.saveas(DXF_FILE)
    print(f"  [OK] XY寸法線追加: {DXF_FILE}")
    print()


if __name__ == "__main__":
    main()