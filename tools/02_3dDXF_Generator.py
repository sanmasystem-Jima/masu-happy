"""
02_3dDXF_Generator.py
集水桝 座標計算 + 座標JSON出力 + 3D DXFファイル生成ツール
"""

import json
import math
import os
import sys
import traceback

try:
    import ezdxf
except ImportError:
    print("ezdxfがインストールされていません。'pip install ezdxf' を実行してください。")
    sys.exit(1)

# ==========================================
# 定数
# ==========================================

PARAM_FILE = "masu_params.json"
COORD_FILE = "masu_coords.json"
DXF_3D_OUT = "masu_3d.dxf"

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

FACE_NORMAL = {
    "右":   ( 1,  0, 0),
    "左":   (-1,  0, 0),
    "奥":   ( 0,  1, 0),
    "手前": ( 0, -1, 0),
}

# ==========================================
# 座標計算
# ==========================================

def calc_coordinates(p):
    ix  = p["内腔寸法"]["X"]
    iy  = p["内腔寸法"]["Y"]
    zl  = p["内腔寸法"]["Z低"]
    wt  = p["構造寸法"]["壁厚"]
    bt  = p["構造寸法"]["底版厚"]
    st  = p["構造寸法"]["砕石厚"]
    so  = p["構造寸法"]["砕石張出"]
    yw  = p["床掘"]["余裕幅"]
    thr = p["床掘"]["勾配使用深さ閾値"]

    c            = p["地盤条件"]
    totsutsu_umu = c["突出有無"]
    keisha_umu   = c["傾斜有無"]

    grad       = 0.0
    keisha_dir = None
    low_side   = None

    if keisha_umu == "有":
        keisha_dir = c.get("傾斜方向", "X")
        low_side   = c.get("低い側", "右")
        method     = c.get("天端指定方法", "勾配")
        if method == "勾配":
            grad = c.get("勾配_percent", 0.0) / 100.0
        else:
            span = ix if keisha_dir == "X" else iy
            grad = c.get("高低差", 0.0) / span if span != 0 else 0.0

    z_saiseki_top = st
    z_naiko_btm   = st + bt

    def get_top_z(x, y):
        if keisha_umu != "有":
            return z_naiko_btm + zl
        if keisha_dir == "X":
            dist = (ix / 2) - x if low_side == "右" else x + (ix / 2)
        else:
            dist = y + (iy / 2) if low_side == "手前" else (iy / 2) - y
        return z_naiko_btm + zl + dist * grad

    def get_ground_z(x, y):
        if totsutsu_umu == "有":
            return z_naiko_btm + zl - c["突出高さ"]
        return get_top_z(x, y)

    nx, ny, nz = 0.0, 0.0, 1.0
    if keisha_umu == "有":
        if keisha_dir == "X":
            nx = grad if low_side == "右" else -grad
        else:
            ny = grad if low_side == "手前" else -grad
    length = math.sqrt(nx**2 + ny**2 + nz**2)
    un = (nx / length, ny / length, nz / length)

    ox = ix / 2 + wt
    oy = iy / 2 + wt
    hx = ix / 2
    hy = iy / 2
    sx, sy = ox + so, oy + so

    saiseki = {
        "底": {"RF": ( sx, -sy, 0.0), "LF": (-sx, -sy, 0.0), "LB": (-sx,  sy, 0.0), "RB": ( sx,  sy, 0.0)},
        "天": {"RF": ( sx, -sy, z_saiseki_top), "LF": (-sx, -sy, z_saiseki_top), "LB": (-sx,  sy, z_saiseki_top), "RB": ( sx,  sy, z_saiseki_top)},
    }

    gaiheki = {
        "底": {"RF": ( ox, -oy, z_saiseki_top), "LF": (-ox, -oy, z_saiseki_top), "LB": (-ox,  oy, z_saiseki_top), "RB": ( ox,  oy, z_saiseki_top)},
        "天": {"RF": ( ox, -oy, get_top_z( ox, -oy)), "LF": (-ox, -oy, get_top_z(-ox, -oy)), "LB": (-ox,  oy, get_top_z(-ox,  oy)), "RB": ( ox,  oy, get_top_z( ox,  oy))},
    }

    naiko = {
        "底": {"RF": ( hx, -hy, z_naiko_btm), "LF": (-hx, -hy, z_naiko_btm), "LB": (-hx,  hy, z_naiko_btm), "RB": ( hx,  hy, z_naiko_btm)},
        "天": {"RF": ( hx, -hy, get_top_z( hx, -hy)), "LF": (-hx, -hy, get_top_z(-hx, -hy)), "LB": (-hx,  hy, get_top_z(-hx,  hy)), "RB": ( hx,  hy, get_top_z( hx,  hy))},
    }

    fx, fy = ox + yw, oy + yw
    hirogari = any(
        (get_ground_z(x, y) if totsutsu_umu == "有" else get_top_z(x, y)) > thr
        for x, y in [( ox, -oy), (-ox, -oy), (-ox,  oy), ( ox,  oy)]
    )

    fuki_btm = {
        "RF": ( fx, -fy, 0.0), "LF": (-fx, -fy, 0.0),
        "LB": (-fx,  fy, 0.0), "RB": ( fx,  fy, 0.0),
    }
    fuki_top = {}
    for key, (bx, by, _) in fuki_btm.items():
        gz = get_ground_z(bx, by)
        if not hirogari:
            fuki_top[key] = (bx, by, gz)
        else:
            if keisha_umu == "有" and totsutsu_umu == "無":
                if keisha_dir == "X":
                    s     =  grad if low_side == "左" else -grad
                    z_ref = get_ground_z(0.0, by)
                    sign  = 1 if bx > 0 else -1
                    denom = 1 - s * sign * 0.5
                    gz    = (z_ref + s * bx) / denom if abs(denom) > 0.001 else gz
                else:
                    s     =  grad if low_side == "手前" else -grad
                    z_ref = get_ground_z(bx, 0.0)
                    sign  = 1 if by > 0 else -1
                    denom = 1 - s * sign * 0.5
                    gz    = (z_ref + s * by) / denom if abs(denom) > 0.001 else gz
            dist = gz * 0.5
            tx = bx + (dist if bx > 0 else -dist)
            ty = by + (dist if by > 0 else -dist)
            fuki_top[key] = (tx, ty, gz)

    grating = None
    if p["グレーチング"]["有無"] == "有":
        gx = p["グレーチング"]["受枠X"] / 2
        gy = p["グレーチング"]["受枠Y"] / 2
        gt = p["グレーチング"]["受枠厚"]
        g_top = {
            "RF": ( gx, -gy, get_top_z( gx, -gy)), "LF": (-gx, -gy, get_top_z(-gx, -gy)),
            "LB": (-gx,  gy, get_top_z(-gx,  gy)), "RB": ( gx,  gy, get_top_z( gx,  gy)),
        }
        if keisha_umu == "有" and keisha_dir == "X":
            dx = gt * grad * (-1 if low_side == "右" else 1)
            dy = 0.0
        elif keisha_umu == "有" and keisha_dir == "Y":
            dx = 0.0
            dy = gt * grad * (1 if low_side == "手前" else -1)
        else:
            dx = 0.0
            dy = 0.0
        g_btm = {k: (pt[0] + dx, pt[1] + dy, pt[2] - gt) for k, pt in g_top.items()}
        grating = {"天": g_top, "底": g_btm}

    kiri_list = []
    for k in p["切り欠き"]:
        face = k["取付面"]
        ofs  = k["オフセット"]

        if k["管底高さ基準"] == "内壁底からの上がり":
            z_pipe = z_naiko_btm + k["管底高さ"]
        else:
            ref_x = ox  if face == "右"  else -ox if face == "左"  else ofs
            ref_y = oy  if face == "奥"  else -oy if face == "手前" else ofs
            z_pipe = get_top_z(ref_x, ref_y) - k["管底高さ"]

        if face == "右":
            ix_w, ox_w, iy_w, oy_w = hx,  ox,  ofs, ofs
        elif face == "左":
            ix_w, ox_w, iy_w, oy_w = -hx, -ox, ofs, ofs
        elif face == "奥":
            ix_w, ox_w, iy_w, oy_w = ofs, ofs, hy,  oy
        else:  # 手前
            ix_w, ox_w, iy_w, oy_w = ofs, ofs, -hy, -oy

        if k["断面形状"] == "矩形":
            w2    = k["寸法"]["幅"] / 2
            h     = k["寸法"]["高さ"]
            z_top = z_pipe + h
            if face in ["右", "左"]:
                inner_pts = [[ix_w, iy_w-w2, z_pipe], [ix_w, iy_w+w2, z_pipe], [ix_w, iy_w+w2, z_top], [ix_w, iy_w-w2, z_top]]
                outer_pts = [[ox_w, oy_w-w2, z_pipe], [ox_w, oy_w+w2, z_pipe], [ox_w, oy_w+w2, z_top], [ox_w, oy_w-w2, z_top]]
            else:
                inner_pts = [[ix_w-w2, iy_w, z_pipe], [ix_w+w2, iy_w, z_pipe], [ix_w+w2, iy_w, z_top], [ix_w-w2, iy_w, z_top]]
                outer_pts = [[ox_w-w2, oy_w, z_pipe], [ox_w+w2, oy_w, z_pipe], [ox_w+w2, oy_w, z_top], [ox_w-w2, oy_w, z_top]]
            haba_tan = [ofs - w2, ofs + w2]

        else:  # 円形
            r     = k["寸法"]["直径"] / 2
            z_top = z_pipe + 2 * r
            N     = 32
            inner_pts = []
            outer_pts = []
            for i in range(N):
                a = 2 * math.pi * i / N
                if face in ["右", "左"]:
                    inner_pts.append([ix_w, iy_w + r*math.cos(a), z_pipe + r + r*math.sin(a)])
                    outer_pts.append([ox_w, oy_w + r*math.cos(a), z_pipe + r + r*math.sin(a)])
                else:
                    inner_pts.append([ix_w + r*math.cos(a), iy_w, z_pipe + r + r*math.sin(a)])
                    outer_pts.append([ox_w + r*math.cos(a), oy_w, z_pipe + r + r*math.sin(a)])
            haba_tan = [ofs - r, ofs + r]

        kiri_list.append({
            "番号":     k["番号"],
            "取付面":   face,
            "面法線":   list(FACE_NORMAL[face]),
            "断面形状": k["断面形状"],
            "内面_pts": inner_pts,
            "外面_pts": outer_pts,
            "管底Z":    z_pipe,
            "管頂Z":    z_top,
            "幅端":     haba_tan,
            "壁ライン": {"内": [ix_w, iy_w], "外": [ox_w, oy_w]},
        })

    return {
        "砕石":     saiseki,
        "外壁":     gaiheki,
        "内腔":     naiko,
        "床掘":     {"底": fuki_btm, "天": fuki_top},
        "受枠":     grating,
        "切り欠き": kiri_list,
    }


# ==========================================
# JSON シリアライズ補助
# ==========================================

def to_serializable(obj):
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    return obj


# ==========================================
# 3D DXF 出力
# ==========================================

def mm3(pt):
    return (pt[0] * MM, pt[1] * MM, pt[2] * MM)


def output_3d_dxf(coords):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm

    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[4.0, 2.0])

    for name, color in LAYERS.items():
        lyr = doc.layers.new(name)
        lyr.color = color

    msp = doc.modelspace()

    def add_line(p1, p2, layer, lt="Continuous"):
        msp.add_line(mm3(p1), mm3(p2), dxfattribs={"layer": layer, "linetype": lt})

    def draw_box(box, layer, lt="Continuous"):
        btm = box["底"]
        top = box["天"]
        for i in range(4):
            k0 = BOX_KEYS[i]
            k1 = BOX_KEYS[(i + 1) % 4]
            add_line(btm[k0], btm[k1], layer, lt)
            add_line(top[k0], top[k1], layer, lt)
            add_line(btm[k0], top[k0], layer, lt)

    draw_box(coords["砕石"], L_BASE)
    draw_box(coords["外壁"], L_CONC)
    draw_box(coords["内腔"], L_CONC)
    draw_box(coords["床掘"], L_EARTH, "DASHED")

    if coords["受枠"]:
        draw_box(coords["受枠"], L_GRAT)

    # 切り欠き（add_polyline3dを使わずadd_lineで描画）
    for k in coords["切り欠き"]:
        p_in  = k["内面_pts"]
        p_out = k["外面_pts"]
        n     = len(p_in)

        # 内面ポリゴン
        for i in range(n):
            add_line(p_in[i], p_in[(i+1) % n], L_KIRI, "DASHED")

        # 外面ポリゴン
        for i in range(n):
            add_line(p_out[i], p_out[(i+1) % n], L_KIRI, "DASHED")

        # 貫通線（8本に間引き）
        step = max(1, n // 8)
        for i in range(0, n, step):
            add_line(p_in[i], p_out[i], L_KIRI, "DASHED")

    print(f"  DXF保存先: {os.path.abspath(DXF_3D_OUT)}")
    doc.saveas(DXF_3D_OUT)
    print(f"  [OK] 3D DXF 出力: {DXF_3D_OUT}")


# ==========================================
# メイン
# ==========================================

def main():
    print("\n" + "="*50)
    print("  集水桝 3D DXF生成ツール  02_3dDXF_Generator.py")
    print("="*50)

    if not os.path.exists(PARAM_FILE):
        print(f"[ERROR] {PARAM_FILE} が見つかりません。")
        sys.exit(1)

    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        p = json.load(f)
    print(f"  パラメータ読み込み: {PARAM_FILE}")

    print("  座標計算中...")
    coords = calc_coordinates(p)

    with open(COORD_FILE, "w", encoding="utf-8") as f:
        json.dump(to_serializable(coords), f, ensure_ascii=False, indent=2)
    print(f"  [OK] 座標JSON出力: {COORD_FILE}")

    try:
        output_3d_dxf(coords)
    except Exception as e:
        print(f"[ERROR] DXF出力中にエラーが発生しました: {e}")
        traceback.print_exc()
        sys.exit(1)

    n = p["内腔寸法"]
    c = p["地盤条件"]
    print("\n  ── 座標計算サマリー ─────────────────")
    print(f"  内腔寸法   : X={n['X']}M  Y={n['Y']}M  Z低={n['Z低']}M")
    if c["突出有無"] == "有":
        print(f"  地盤条件   : 突出あり  高さ={c['突出高さ']}M")
    elif c["傾斜有無"] == "有":
        method = c.get("天端指定方法", "勾配")
        val = f"勾配={c.get('勾配_percent',0)}%" if method == "勾配" else f"高低差={c.get('高低差',0)}M"
        print(f"  地盤条件   : 傾斜あり  {c.get('傾斜方向','X')}方向  低い側={c.get('低い側','右')}  {val}")
    else:
        print(f"  地盤条件   : 水平")

    top_zs = [v[2] for v in coords["外壁"]["天"].values()]
    if max(top_zs) - min(top_zs) > 0.0001:
        print(f"  外壁天端Z  : {min(top_zs):.4f}M 〜 {max(top_zs):.4f}M")
    else:
        print(f"  外壁天端Z  : {top_zs[0]:.4f}M（水平）")

    print(f"  切り欠き   : {len(coords['切り欠き'])}箇所")
    for k in coords["切り欠き"]:
        print(f"    {k['番号']}. {k['取付面']}面  {k['断面形状']}  管底Z={k['管底Z']:.4f}M  管頂Z={k['管頂Z']:.4f}M")
    print("  ───────────────────────────────────")
    print()


if __name__ == "__main__":
    main()