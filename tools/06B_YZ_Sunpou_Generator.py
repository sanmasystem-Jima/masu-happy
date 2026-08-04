"""
06B_YZ_Sunpou_Generator.py
集水桝 YZ立面図 寸法線生成ツール

05B_XZ_Sunpou_Generator.py と同じロジック。
X→Y、左右→手前奥 に読み替え。
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
DIM_FILE   = "dimension_YZ.json"
DXF_FILE   = "masu_YZ.dxf"

L_DIM    = "MASU_DIM"
DIFF_THR = 1.0


def setup_dimstyle(doc, scale_n):
    txt_h   = 3.5 * scale_n
    arr_sz  = 4.5 * scale_n
    ext_ext = 1.0 * scale_n
    sname   = "MASU_DIM_STYLE"
    if sname in doc.dimstyles:
        doc.dimstyles.delete(sname)
    ds = doc.dimstyles.new(sname)
    ds.dxf.dimtxt  = txt_h
    ds.dxf.dimasz  = arr_sz
    ds.dxf.dimexo  = 0
    ds.dxf.dimexe  = ext_ext
    ds.dxf.dimtad  = 1
    ds.dxf.dimclrd = 7
    ds.dxf.dimclre = 7
    ds.dxf.dimclrt = 7
    ds.dxf.dimlwd  = -4
    ds.dxf.dimlwe  = -4
    ds.dxf.dimblk  = "OPEN"
    ds.dxf.dimblk1 = "OPEN"
    ds.dxf.dimblk2 = "OPEN"
    return sname


def dim_h(msp, x1, x2, ref_y, dim_y, sty):
    x1, x2 = round(x1, 3), round(x2, 3)
    if abs(x1 - x2) < 0.01:
        return
    msp.add_linear_dim(
        base=(x1, dim_y), p1=(x1, ref_y), p2=(x2, ref_y),
        angle=0, dimstyle=sty, dxfattribs={"layer": L_DIM}
    ).render()


def dim_v(msp, z1, z2, ref_x, dim_x, sty):
    z1, z2 = round(z1, 3), round(z2, 3)
    if abs(z1 - z2) < 0.01:
        return
    msp.add_linear_dim(
        base=(dim_x, z1), p1=(ref_x, z1), p2=(ref_x, z2),
        angle=90, dimstyle=sty, dxfattribs={"layer": L_DIM}
    ).render()


def is_diff(a, b):
    return abs(a - b) > DIFF_THR


class DimColumn:
    def __init__(self, base_pos, direction, scale_n):
        self.base    = base_pos
        self.dir     = direction
        self.scale_n = scale_n
        self.slots   = {}

    def get_pos(self, slot):
        if slot <= 0:
            return self.base
        first = 30.0 * self.scale_n
        step  =  8.0 * self.scale_n
        return self.base + self.dir * (first + step * (slot - 1))

    def assign(self, lo, hi, preferred=1):
        slot = preferred
        while True:
            existing = self.slots.get(slot, [])
            conflict = any(
                not (hi + 0.01 <= r[0] or lo - 0.01 >= r[1])
                for r in existing
            )
            if not conflict:
                self.slots.setdefault(slot, []).append((lo, hi))
                return slot
            slot += 1


# dimension_YZ.json アクセスヘルパー [y_mm, z_mm]
def ty(box, key): return box["天"][key][0]  # 天端Y
def tz(box, key): return box["天"][key][1]  # 天端Z
def by_(box, key): return box["底"][key][0]  # 底面Y
def bz(box, key): return box["底"][key][1]  # 底面Z


def add_top_dims(msp, dim_data, params, sty, scale_n,
                 sai_ymin, sai_ymax, gai_zmax, fuki_zmax):

    ref_off    =  5.0 * scale_n
    ref_z_top  = gai_zmax  + ref_off
    ref_z_fuki = fuki_zmax + ref_off
    col        = DimColumn(gai_zmax + ref_off, +1, scale_n)

    obj   = dim_data["オブジェクト"]
    gai   = obj["外壁"]
    nai   = obj["内腔"]
    fuki  = obj["床掘"]
    kiris = dim_data.get("切り欠き", [])

    gai_ymin = min(ty(gai, k) for k in ["RF","LF","LB","RB"])
    gai_ymax = max(ty(gai, k) for k in ["RF","LF","LB","RB"])
    nai_ymin = min(ty(nai, k) for k in ["RF","LF","LB","RB"])
    nai_ymax = max(ty(nai, k) for k in ["RF","LF","LB","RB"])

    # YZ立面図では手前=LF/RF（Y小）、奥=LB/RB（Y大）
    fuki_ymin_r = min(ty(fuki,"RF"), ty(fuki,"RB"))
    fuki_ymax_r = max(ty(fuki,"RF"), ty(fuki,"RB"))
    fuki_ymin_l = min(ty(fuki,"LF"), ty(fuki,"LB"))
    fuki_ymax_l = max(ty(fuki,"LF"), ty(fuki,"LB"))

    # 段1: 切り欠き幅（矩形・右左面のみ）
    for k in kiris:
        if k["断面形状"] != "矩形" or k["取付面"] not in ["右","左"]:
            continue
        lo = k["y_lo_mm"]; hi = k["y_hi_mm"]
        slot = col.assign(lo, hi, 1)
        dim_h(msp, lo, hi, ref_z_top, col.get_pos(slot), sty)

    # 段2: 壁厚・内腔Y・壁厚
    slot = col.assign(gai_ymin, gai_ymax, 2)
    pos  = col.get_pos(slot)
    dim_h(msp, gai_ymin, nai_ymin, ref_z_top, pos, sty)
    dim_h(msp, nai_ymin, nai_ymax, ref_z_top, pos, sty)
    dim_h(msp, nai_ymax, gai_ymax, ref_z_top, pos, sty)

    # 段3: 外壁幅Y
    slot = col.assign(gai_ymin, gai_ymax, 3)
    dim_h(msp, gai_ymin, gai_ymax, ref_z_top, col.get_pos(slot), sty)

    # 段4: 掘削幅（右面側）
    slot = col.assign(fuki_ymin_r, fuki_ymax_r, 4)
    dim_h(msp, fuki_ymin_r, fuki_ymax_r, ref_z_fuki, col.get_pos(slot), sty)

    # 段5: 掘削幅（左面側・異なるとき）
    if is_diff(fuki_ymin_l, fuki_ymin_r) or is_diff(fuki_ymax_l, fuki_ymax_r):
        slot = col.assign(fuki_ymin_l, fuki_ymax_l, 5)
        dim_h(msp, fuki_ymin_l, fuki_ymax_l, ref_z_fuki, col.get_pos(slot), sty)


def add_bottom_dims(msp, dim_data, params, sty, scale_n,
                    sai_ymin, sai_ymax, sai_zmin, fuki_zmin):

    ref_off    =  5.0 * scale_n
    ref_z_sai  = sai_zmin  - ref_off
    ref_z_fuki = fuki_zmin - ref_off
    col        = DimColumn(sai_zmin - ref_off, -1, scale_n)

    obj   = dim_data["オブジェクト"]
    sai   = obj["砕石"]
    fuki  = obj["床掘"]
    kiris = dim_data.get("切り欠き", [])

    sai_ymin2 = min(by_(sai, k) for k in ["RF","LF","LB","RB"])
    sai_ymax2 = max(by_(sai, k) for k in ["RF","LF","LB","RB"])

    fuki_ymin_r = min(by_(fuki,"RF"), by_(fuki,"RB"))
    fuki_ymax_r = max(by_(fuki,"RF"), by_(fuki,"RB"))
    fuki_ymin_l = min(by_(fuki,"LF"), by_(fuki,"LB"))
    fuki_ymax_l = max(by_(fuki,"LF"), by_(fuki,"LB"))

    # 段1: 切り欠き幅（矩形・手前奥面のみ）
    for k in kiris:
        if k["断面形状"] != "矩形" or k["取付面"] not in ["手前","奥"]:
            continue
        lo = k["y_lo_mm"]; hi = k["y_hi_mm"]
        slot = col.assign(lo, hi, 1)
        dim_h(msp, lo, hi, ref_z_sai, col.get_pos(slot), sty)

    # 段2: 砕石幅Y
    slot = col.assign(sai_ymin2, sai_ymax2, 2)
    dim_h(msp, sai_ymin2, sai_ymax2, ref_z_sai, col.get_pos(slot), sty)

    # 段3: 掘削幅（右面側）
    slot = col.assign(fuki_ymin_r, fuki_ymax_r, 3)
    dim_h(msp, fuki_ymin_r, fuki_ymax_r, ref_z_fuki, col.get_pos(slot), sty)

    # 段4: 掘削幅（左面側・異なるとき）
    if is_diff(fuki_ymin_l, fuki_ymin_r) or is_diff(fuki_ymax_l, fuki_ymax_r):
        slot = col.assign(fuki_ymin_l, fuki_ymax_l, 4)
        dim_h(msp, fuki_ymin_l, fuki_ymax_l, ref_z_fuki, col.get_pos(slot), sty)


def add_side_dims(msp, dim_data, params, sty, scale_n,
                  sai_ymin, sai_ymax):

    ref_off    =  5.0 * scale_n
    inner_off  = 10.0 * scale_n
    inner_step =  8.0 * scale_n

    obj         = dim_data["オブジェクト"]
    gai         = obj["外壁"]
    nai         = obj["内腔"]
    sai         = obj["砕石"]
    fuki        = obj["床掘"]
    kiris       = dim_data.get("切り欠き", [])
    kiri_params = params.get("切り欠き", [])

    c            = params.get("地盤条件", {})
    totsutsu_umu = c.get("突出有無", "無")
    totsutsu_h   = c.get("突出高さ", 0.0) * 1000.0  # mm換算

    # YZ立面図のコーナー対応
    # 手前側=RF/LF（Y小）、奥側=RB/LB（Y大）
    # 右側=RF/RB（X大）、左側=LF/LB（X小）
    # YZ投影では右側・左側を「手前(F)・奥(B)」として扱う
    pts = {}
    for key in ["RF","RB","LF","LB"]:
        pts[key] = {
            "gai_top":  tz(gai,  key),
            "nai_top":  tz(nai,  key),
            "nai_btm":  bz(nai,  key),
            "sai_top":  tz(sai,  key),
            "sai_btm":  bz(sai,  key),
            "fuki_top": tz(fuki, key),
            "fuki_btm": bz(fuki, key),
        }

    bt_top_z  = pts["RF"]["nai_btm"]
    sai_top_z = pts["RF"]["sai_top"]

    nai_ymin_mm = min(ty(nai, k) for k in ["RF","LF"])
    nai_ymax_mm = max(ty(nai, k) for k in ["RB","LB"])
    gai_ymax_mm = max(ty(gai, k) for k in ["RB","LB"])

    ref_y_l = sai_ymin - ref_off  # 手前側（Y小）
    ref_y_r = sai_ymax + ref_off  # 奥側（Y大）
    col_l   = DimColumn(sai_ymin - ref_off, -1, scale_n)
    col_r   = DimColumn(sai_ymax + ref_off, +1, scale_n)

    # 手前側（Y小）= RF/LF
    rf = pts["RF"]; lf = pts["LF"]
    # 奥側（Y大）= RB/LB
    rb = pts["RB"]; lb = pts["LB"]

    # ------------------------------------------
    # 底版基準切り欠き → 桝内側
    # ------------------------------------------
    inner_bases = {
        "右":   nai_ymax_mm - inner_off,
        "左":   nai_ymin_mm + inner_off,
        "手前": nai_ymin_mm + inner_off,
        "奥":   nai_ymax_mm - inner_off,
    }
    inner_used = {"右": 0, "左": 0, "手前": 0, "奥": 0}

    for k, kp in zip(kiris, kiri_params):
        if kp.get("管底高さ基準") != "内壁底からの上がり":
            continue
        face       = k["取付面"]
        z_pipe_btm = k["管底Z_mm"]
        z_pipe_top = k["管頂Z_mm"]
        n          = inner_used[face]

        if face in ["右", "奥"]:
            pos_y = inner_bases[face] - n * inner_step
        else:
            pos_y = inner_bases[face] + n * inner_step
        inner_used[face] += 1

        dim_v(msp, bt_top_z,   z_pipe_btm, pos_y, pos_y, sty)
        dim_v(msp, z_pipe_btm, z_pipe_top, pos_y, pos_y, sty)

    # ------------------------------------------
    # 天端基準切り欠き → 手前・奥外側
    # ------------------------------------------
    front_kiri_count = 0
    back_kiri_count  = 0

    for k, kp in zip(kiris, kiri_params):
        if kp.get("管底高さ基準") != "外壁天端からの下がり":
            continue
        face       = k["取付面"]
        z_pipe_btm = k["管底Z_mm"]
        z_pipe_top = k["管頂Z_mm"]

        if face == "手前":
            side = "front"
        elif face == "奥":
            side = "back"
        else:
            ofs = kp.get("オフセット", 0.0)
            if abs(ofs) < 0.001:
                side = "front" if front_kiri_count <= back_kiri_count else "back"
            else:
                side = "back" if ofs > 0 else "front"

        if side == "front":
            z_gai_top = rf["gai_top"]
            slot = col_l.assign(z_pipe_btm, z_gai_top, 1)
            pos  = col_l.get_pos(slot)
            dim_v(msp, z_pipe_top, z_gai_top,  ref_y_l, pos, sty)
            dim_v(msp, z_pipe_btm, z_pipe_top, ref_y_l, pos, sty)
            front_kiri_count += 1
        else:
            z_gai_top = rb["gai_top"]
            slot = col_r.assign(z_pipe_btm, z_gai_top, 1)
            pos  = col_r.get_pos(slot)
            dim_v(msp, z_pipe_top, z_gai_top,  ref_y_r, pos, sty)
            dim_v(msp, z_pipe_btm, z_pipe_top, ref_y_r, pos, sty)
            back_kiri_count += 1

    # ------------------------------------------
    # 手前側（Y小）構造寸法
    # ------------------------------------------
    cur = 2

    slot = col_l.assign(sai_top_z, rf["nai_top"], cur)
    pos  = col_l.get_pos(slot)
    dim_v(msp, rf["nai_btm"], rf["nai_top"], ref_y_l, pos, sty)
    dim_v(msp, sai_top_z, rf["nai_btm"],    ref_y_l, pos, sty)
    cur = slot + 1

    if is_diff(lf["nai_top"], rf["nai_top"]) or is_diff(lf["nai_btm"], rf["nai_btm"]):
        slot = col_l.assign(lf["nai_btm"], lf["nai_top"], cur)
        dim_v(msp, lf["nai_btm"], lf["nai_top"], ref_y_l, col_l.get_pos(slot), sty)
        cur = slot + 1

    slot = col_l.assign(rf["sai_btm"], rf["gai_top"], cur)
    pos  = col_l.get_pos(slot)
    dim_v(msp, rf["sai_btm"], rf["sai_top"], ref_y_l, pos, sty)
    dim_v(msp, rf["sai_top"], rf["gai_top"], ref_y_l, pos, sty)
    cur = slot + 1

    if is_diff(lf["gai_top"], rf["gai_top"]):
        slot = col_l.assign(lf["sai_top"], lf["gai_top"], cur)
        dim_v(msp, lf["sai_top"], lf["gai_top"], ref_y_l, col_l.get_pos(slot), sty)
        cur = slot + 1

    slot = col_l.assign(rf["fuki_btm"], rf["fuki_top"], cur)
    pos  = col_l.get_pos(slot)
    dim_v(msp, rf["fuki_btm"], rf["fuki_top"], ref_y_l, pos, sty)
    if totsutsu_umu == "有":
        z_ground = rf["gai_top"] - totsutsu_h
        dim_v(msp, z_ground, rf["gai_top"], ref_y_l, pos, sty)
    cur = slot + 1

    if is_diff(lf["fuki_top"], rf["fuki_top"]) or is_diff(lf["fuki_btm"], rf["fuki_btm"]):
        slot = col_l.assign(lf["fuki_btm"], lf["fuki_top"], cur)
        dim_v(msp, lf["fuki_btm"], lf["fuki_top"], ref_y_l, col_l.get_pos(slot), sty)

    # ------------------------------------------
    # 奥側（Y大）構造寸法
    # ------------------------------------------
    cur = 2

    if is_diff(rb["nai_top"], rf["nai_top"]) or is_diff(rb["nai_btm"], rf["nai_btm"]):
        slot = col_r.assign(rb["nai_btm"], rb["nai_top"], cur)
        dim_v(msp, rb["nai_btm"], rb["nai_top"], ref_y_r, col_r.get_pos(slot), sty)
        cur = slot + 1

    if is_diff(lb["nai_top"], rb["nai_top"]) or is_diff(lb["nai_btm"], rb["nai_btm"]):
        slot = col_r.assign(lb["nai_btm"], lb["nai_top"], cur)
        dim_v(msp, lb["nai_btm"], lb["nai_top"], ref_y_r, col_r.get_pos(slot), sty)
        cur = slot + 1

    if is_diff(rb["sai_top"], rf["sai_top"]):
        slot = col_r.assign(rb["sai_top"], bt_top_z, cur)
        dim_v(msp, rb["sai_top"], bt_top_z, ref_y_r, col_r.get_pos(slot), sty)
        cur = slot + 1

    if is_diff(rb["gai_top"], rf["gai_top"]):
        slot = col_r.assign(rb["sai_btm"], rb["gai_top"], cur)
        pos  = col_r.get_pos(slot)
        dim_v(msp, rb["sai_btm"], rb["sai_top"], ref_y_r, pos, sty)
        dim_v(msp, rb["sai_top"], rb["gai_top"], ref_y_r, pos, sty)
        cur = slot + 1

    if is_diff(lb["gai_top"], rb["gai_top"]):
        slot = col_r.assign(lb["sai_top"], lb["gai_top"], cur)
        dim_v(msp, lb["sai_top"], lb["gai_top"], ref_y_r, col_r.get_pos(slot), sty)
        cur = slot + 1

    if is_diff(rb["fuki_top"], rf["fuki_top"]) or is_diff(rb["fuki_btm"], rf["fuki_btm"]):
        slot = col_r.assign(rb["fuki_btm"], rb["fuki_top"], cur)
        dim_v(msp, rb["fuki_btm"], rb["fuki_top"], ref_y_r, col_r.get_pos(slot), sty)
        cur = slot + 1

    if is_diff(lb["fuki_top"], rb["fuki_top"]) or is_diff(lb["fuki_btm"], rb["fuki_btm"]):
        slot = col_r.assign(lb["fuki_btm"], lb["fuki_top"], cur)
        dim_v(msp, lb["fuki_btm"], lb["fuki_top"], ref_y_r, col_r.get_pos(slot), sty)


def main():
    print("\n" + "="*50)
    print("  集水桝 YZ寸法線  06B_YZ_Sunpou_Generator.py")
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

    sty = setup_dimstyle(doc, scale_n)

    obj  = dim_data["オブジェクト"]
    sai  = obj["砕石"]
    gai  = obj["外壁"]
    fuki = obj["床掘"]

    sai_ys   = [sai["天"][k][0] for k in ["RF","LF","LB","RB"]] + \
               [sai["底"][k][0] for k in ["RF","LF","LB","RB"]]
    sai_ymin = min(sai_ys)
    sai_ymax = max(sai_ys)

    gai_zmax  = max(gai["天"][k][1] for k in ["RF","LF","LB","RB"])
    sai_zmin  = min(sai["底"][k][1] for k in ["RF","LF","LB","RB"])
    fuki_zmax = max(fuki["天"][k][1] for k in ["RF","LF","LB","RB"])
    fuki_zmin = min(fuki["底"][k][1] for k in ["RF","LF","LB","RB"])

    add_top_dims(msp, dim_data, params, sty, scale_n,
                 sai_ymin, sai_ymax, gai_zmax, fuki_zmax)
    add_bottom_dims(msp, dim_data, params, sty, scale_n,
                    sai_ymin, sai_ymax, sai_zmin, fuki_zmin)
    add_side_dims(msp, dim_data, params, sty, scale_n,
                  sai_ymin, sai_ymax)

    doc.saveas(DXF_FILE)
    print(f"  [OK] YZ寸法線追加: {DXF_FILE}")
    print()


if __name__ == "__main__":
    main()