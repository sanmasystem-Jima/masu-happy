"""
03_Suuryouhyou_Generator.py
集水桝 数量計算書生成ツール
"""

import json
import math
import os
import sys

PARAM_FILE  = "masu_params.json"
COORD_FILE  = "masu_coords.json"
OUTPUT_FILE = "masu_suuryou.txt"

KIRI_MIN_AREA = 0.071  # m2  これ以下の切り欠きは控除対象外
NOTE_TEXT = "※令和７年度土木工事数量算出要領による"

# ==========================================
# ヘルパー
# ==========================================

def r3(v):
    """小数点以下3桁に四捨五入"""
    return round(v, 3)

def r4(v):
    """小数点以下4桁に四捨五入"""
    return round(v, 4)

def box_volume(box):
    """
    底面積 x 天端Z平均で台形柱体積を近似。
    戻り値: (base_area, width_x, width_y, height, volume, height_expr)
    """
    btm = box["底"]
    top = box["天"]
    xs = [pt[0] for pt in btm.values()]
    ys = [pt[1] for pt in btm.values()]
    width_x   = r3(max(xs) - min(xs))
    width_y   = r3(max(ys) - min(ys))
    base_area = r4(width_x * width_y)
    z_btm_avg = sum(pt[2] for pt in btm.values()) / 4

    top_zs = sorted([pt[2] for pt in top.values()])
    z_lo = r3((top_zs[0] + top_zs[1]) / 2)
    z_hi = r3((top_zs[2] + top_zs[3]) / 2)
    z_btm_avg = r3(z_btm_avg)

    h_lo = r3(z_lo - z_btm_avg)
    h_hi = r3(z_hi - z_btm_avg)

    if abs(h_hi - h_lo) < 0.001:
        height_expr = f"{h_lo:.3f}"
        height = h_lo
    else:
        height_expr = f"({h_lo:.3f}+{h_hi:.3f})/2"
        height = r3((h_lo + h_hi) / 2)

    volume = r4(base_area * height)
    return base_area, width_x, width_y, height, volume, height_expr


def face_height_expr(top_pts, btm_pts, keys):
    """
    型枠面の高さ計算式文字列を返す。
    傾斜ありなら (Z低+Z高)/2、水平なら単一値。
    """
    z_vals = sorted([top_pts[k][2] for k in keys])
    z_btm  = r3(btm_pts[keys[0]][2])
    z_lo   = r3(z_vals[0])
    z_hi   = r3(z_vals[-1])
    h_lo   = r3(z_lo - z_btm)
    h_hi   = r3(z_hi - z_btm)
    if abs(h_hi - h_lo) < 0.001:
        return f"{h_lo:.3f}", h_lo
    else:
        return f"({h_lo:.3f}+{h_hi:.3f})/2", r3((h_lo + h_hi) / 2)


def kiri_cross_area(k):
    """切り欠きの断面積・寸法を返す (area, d1, d2)"""
    if k["断面形状"] == "円形":
        r = r3((k["管頂Z"] - k["管底Z"]) / 2)
        return r4(math.pi * r ** 2), r3(r * 2), None
    else:
        pts = k["内面_pts"]
        xs  = [p[0] for p in pts]
        ys  = [p[1] for p in pts]
        zs  = [p[2] for p in pts]
        kw  = r3(max(max(xs) - min(xs), max(ys) - min(ys)))
        kh  = r3(max(zs) - min(zs))
        return r4(kw * kh), kw, kh


def kiri_perimeter(k):
    """切り欠きの周囲長"""
    if k["断面形状"] == "円形":
        r = r3((k["管頂Z"] - k["管底Z"]) / 2)
        return r3(math.pi * r3(r * 2))
    else:
        pts = k["内面_pts"]
        xs  = [p[0] for p in pts]
        ys  = [p[1] for p in pts]
        zs  = [p[2] for p in pts]
        kw  = r3(max(max(xs) - min(xs), max(ys) - min(ys)))
        kh  = r3(max(zs) - min(zs))
        return r3((kw + kh) * 2)


# ==========================================
# 数量計算
# ==========================================

def calc_suuryou(p, coords):
    wt = p["構造寸法"]["壁厚"]
    st = p["構造寸法"]["砕石厚"]

    lines = []
    def L(s=""):
        lines.append(s)

    # ------------------------------------------
    # 表題部
    # ------------------------------------------
    n  = p["内腔寸法"]
    c  = p["地盤条件"]

    # Z表記
    top_zs = sorted([v[2] for v in coords["内腔"]["天"].values()])
    z_lo_val = r3((top_zs[0] + top_zs[1]) / 2)
    z_hi_val = r3((top_zs[2] + top_zs[3]) / 2)

    z_btm_val = r3(coords["内腔"]["底"]["RF"][2])
    h_lo = r3(z_lo_val - z_btm_val)
    h_hi = r3(z_hi_val - z_btm_val)

    if abs(h_hi - h_lo) < 0.001:
        z_label = f"Z={h_lo:.3f}"
    else:
        z_label = f"Z={h_lo:.3f}～{h_hi:.3f}"

    L("=" * 57)
    L("  集水桝 数量計算書")
    L(f"  内腔寸法: X={r3(n['X']):.3f}M  Y={r3(n['Y']):.3f}M  {z_label}M")
    L("=" * 57)

    # ------------------------------------------
    # コンクリート
    # ------------------------------------------
    L()
    L("【コンクリート】")

    _, gai_x, gai_y, gai_h, gai_vol, gai_expr = box_volume(coords["外壁"])
    L(f"  外壁体積")
    L(f"    {gai_x:.3f} x {gai_y:.3f} x {gai_expr} = {gai_vol:.4f} m3")

    _, nai_x, nai_y, nai_h, nai_vol, nai_expr = box_volume(coords["内腔"])
    L(f"  内腔控除")
    L(f"    {nai_x:.3f} x {nai_y:.3f} x {nai_expr} = -{nai_vol:.4f} m3")

    L(f"  切り欠き控除")
    kiri_vol_total = 0.0
    has_excluded = False
    for k in coords["切り欠き"]:
        area, d1, d2 = kiri_cross_area(k)
        label = f"円形 φ{d1:.3f}M" if k["断面形状"] == "円形" else f"矩形 {d1:.3f}x{d2:.3f}M"
        if area <= KIRI_MIN_AREA:
            has_excluded = True
            L(f"    No.{k['番号']} {k['取付面']}面 {label}"
              f"  断面積={area:.4f}m2  ※対象外")
        else:
            vol = r4(area * r3(wt))
            kiri_vol_total += vol
            L(f"    No.{k['番号']} {k['取付面']}面 {label}"
              f"  {area:.4f} x {r3(wt):.3f}(壁厚) = -{vol:.4f} m3")

    grat_vol = 0.0
    if coords["受枠"]:
        _, rx, ry, rh, grat_vol, grat_expr = box_volume(coords["受枠"])
        L(f"  受枠控除")
        L(f"    {rx:.3f} x {ry:.3f} x {grat_expr} = -{grat_vol:.4f} m3")

    conc_vol = r4(gai_vol - nai_vol - kiri_vol_total - grat_vol)
    L(f"  {'─'*47}")
    L(f"  コンクリート合計 : {conc_vol:.4f} m3")

    # ------------------------------------------
    # 型枠（内面側面 + 外面側面）
    # ------------------------------------------
    L()
    L("【型枠】")

    def calc_face_areas(top_pts, btm_pts, label_prefix):
        face_data = {
            f"{label_prefix}右面":   (["RF", "RB"], "Y"),
            f"{label_prefix}左面":   (["LF", "LB"], "Y"),
            f"{label_prefix}手前面": (["RF", "LF"], "X"),
            f"{label_prefix}奥面":   (["LB", "RB"], "X"),
        }
        areas = {}
        for fname, (keys, axis) in face_data.items():
            h_expr, h_val = face_height_expr(top_pts, btm_pts, keys)
            p0 = btm_pts[keys[0]]
            p1 = btm_pts[keys[1]]
            w  = r3(abs(p1[1] - p0[1]) if axis == "Y" else abs(p1[0] - p0[0]))
            area = r4(w * h_val)
            areas[fname] = (w, h_val, area)
            L(f"  {fname}  {w:.3f} x {h_expr} = {area:.4f} m2")
        return areas

    L("  ■内面")
    nai_top_pts = coords["内腔"]["天"]
    nai_btm_pts = coords["内腔"]["底"]
    face_areas_nai = calc_face_areas(nai_top_pts, nai_btm_pts, "内_")

    L("  ■外面")
    gai_top_pts = coords["外壁"]["天"]
    gai_btm_pts = coords["外壁"]["底"]
    face_areas_gai = calc_face_areas(gai_top_pts, gai_btm_pts, "外_")

    face_areas_all = {**face_areas_nai, **face_areas_gai}

    # 切り欠き控除（断面積×2）
    L(f"  切り欠き控除（断面×2）")
    kiri_kata_dan = 0.0
    for k in coords["切り欠き"]:
        area, d1, d2 = kiri_cross_area(k)
        if area <= KIRI_MIN_AREA:
            L(f"    No.{k['番号']} {k['取付面']}面  ※対象外")
            continue
        ded = r4(area * 2)
        kiri_kata_dan += ded
        L(f"    No.{k['番号']} {k['取付面']}面  {area:.4f} x 2 = -{ded:.4f} m2")

    # 切り欠き追加（周囲長×壁厚）
    L(f"  切り欠き追加（周囲長×壁厚）")
    kiri_kata_peri = 0.0
    for k in coords["切り欠き"]:
        area, d1, d2 = kiri_cross_area(k)
        if area <= KIRI_MIN_AREA:
            L(f"    No.{k['番号']} {k['取付面']}面  ※対象外")
            continue
        peri = kiri_perimeter(k)
        add  = r4(peri * r3(wt))
        kiri_kata_peri += add
        if k["断面形状"] == "円形":
            L(f"    No.{k['番号']} {k['取付面']}面  π×{d1:.3f} x {r3(wt):.3f}(壁厚) = +{add:.4f} m2")
        else:
            L(f"    No.{k['番号']} {k['取付面']}面  ({d1:.3f}+{d2:.3f})x2 x {r3(wt):.3f}(壁厚) = +{add:.4f} m2")

    grat_kata = 0.0
    if coords["受枠"]:
        gt = r3(p["グレーチング"]["受枠厚"])
        gx = r3(p["グレーチング"]["受枠X"])
        gy = r3(p["グレーチング"]["受枠Y"])
        grat_kata = r4((gx * 2 + gy * 2) * gt)
        L(f"  受枠控除  ({gx:.3f}+{gy:.3f})x2 x {gt:.3f}(厚) = -{grat_kata:.4f} m2")

    kataku_total = r4(
        sum(v[2] for v in face_areas_all.values())
        - kiri_kata_dan + kiri_kata_peri - grat_kata
    )
    L(f"  {'─'*47}")
    L(f"  型枠合計 : {kataku_total:.4f} m2")

    # ------------------------------------------
    # 砕石
    # ------------------------------------------
    L()
    L("【砕石】")
    sai_btm      = coords["砕石"]["底"]
    xs           = [pt[0] for pt in sai_btm.values()]
    ys           = [pt[1] for pt in sai_btm.values()]
    sai_x        = r3(max(xs) - min(xs))
    sai_y        = r3(max(ys) - min(ys))
    sai_area_val = r4(sai_x * sai_y)
    sai_vol      = r4(sai_area_val * r3(st))
    L(f"  {sai_x:.3f} x {sai_y:.3f} = {sai_area_val:.4f} m2"
      f"  (t={r3(st):.3f}M  体積={sai_vol:.4f} m3)")

    # ------------------------------------------
    # 土工
    # ------------------------------------------
    L()
    L("【土工】")
    _, fuki_x, fuki_y, fuki_h, fuki_vol, fuki_expr = box_volume(coords["床掘"])
    L(f"  床掘")
    L(f"    {fuki_x:.3f} x {fuki_y:.3f} x {fuki_expr} = {fuki_vol:.4f} m3")

    umemodoshi = r4(fuki_vol - conc_vol - sai_vol)
    L(f"  埋戻し")
    L(f"    床掘 - コンクリート - 砕石")
    L(f"    {fuki_vol:.4f} - {conc_vol:.4f} - {sai_vol:.4f} = {umemodoshi:.4f} m3")

    # ------------------------------------------
    # 集計表
    # ------------------------------------------
    L()
    L("=" * 57)
    L("  【数量集計】")
    L("=" * 57)
    L(f"  コンクリート : {conc_vol:.4f} m3")
    L(f"  型枠         : {kataku_total:.4f} m2")
    L(f"  砕石         : {sai_area_val:.4f} m2  (t={r3(st):.3f}M)")
    L(f"  床掘         : {fuki_vol:.4f} m3")
    L(f"  埋戻し       : {umemodoshi:.4f} m3")
    L("=" * 57)

    # 対象外注記
    if has_excluded:
        L()
        L(NOTE_TEXT)

    return lines


# ==========================================
# メイン
# ==========================================

def main():
    print("\n" + "="*50)
    print("  集水桝 数量計算書  03_Suuryouhyou_Generator.py")
    print("="*50)

    for fname in [PARAM_FILE, COORD_FILE]:
        if not os.path.exists(fname):
            print(f"[ERROR] {fname} が見つかりません。")
            sys.exit(1)

    with open(PARAM_FILE, "r", encoding="utf-8") as f:
        p = json.load(f)
    with open(COORD_FILE, "r", encoding="utf-8") as f:
        coords = json.load(f)

    lines = calc_suuryou(p, coords)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"  [OK] 数量計算書出力: {OUTPUT_FILE}")
    print()
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()