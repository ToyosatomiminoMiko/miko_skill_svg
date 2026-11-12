"""位图 → 多边形拟合(只跑一轮,给"有参考图"时用).

是什么:把一张参考位图切成色块连通域,描出每个色块的外轮廓,用 RDP 简化为直边多边形,
输出 JSON(每块: 颜色/面积/质心/顶点列)。拿到这份顶点列后,人工/程序把它折算成
几何图元(矩形、45° 等腰梯形、圆弧...),再交给 svgkit 输出确定性 SVG。

为什么这么设计:
- 不做"自动矢量化到底"。自动描边结果顶点很多、带像素抖动,不可编辑也违反几何优先;
  本脚本只负责给出**一轮准确的顶点证据**,后续一律回到参数化重建。
- 轮廓提取用 Moore 邻域径向扫描 + RDP:抗锯齿边会先变成阶梯,再被 RDP 拉成直线,
  45°/90° 边会自然收敛到一条线段,顶点误差约 1px。
- 按颜色分组而不是全图一次二值化:同图多色块(logo/徽标)必须分开,否则相邻色块会被
  连成一个连通域。
- 连通域用 4 邻接:8 邻接会把对角相邻的两个块粘在一起。

依赖: PIL(Pillow) + numpy。两者都不是标准库,属于"已有依赖"范围。

元信息: 作者 Haojiren Galactic, 2026-11-12。
"""

import json
import sys
from collections import deque

import numpy as np


# ---------------------------------------------------------------- 载入与配色

def load_rgb(path):
    """读图并转 RGB,返回 uint8 数组 (h, w, 3)。"""
    from PIL import Image

    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def palette(rgb, min_luma=72, sat=28, top=12):
    """统计"像图形的"像素主色,返回 [(hex, 像素数), ...] 从多到少。"""
    r, g, b = (rgb[..., i].astype(np.int32) for i in range(3))
    luma = (299 * r + 587 * g + 114 * b) // 1000  # 必须 int32: int16 下 299*255 就溢出了
    chroma = rgb.max(axis=2).astype(np.int32) - rgb.min(axis=2).astype(np.int32)
    mask = (luma >= min_luma) | (chroma >= sat)
    picked = rgb[mask].astype(np.int32) >> 3 << 3  # 量化到 8 级,抵消抗锯齿
    keys, counts = np.unique(picked.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(-counts)[:top]
    return [("#%02x%02x%02x" % tuple(int(v) for v in keys[i]), int(counts[i])) for i in order]


def foreground(rgb, min_luma=72, sat=28):
    """前景 = 够亮 或 够彩。背景(纯色/渐变)靠亮度上限与低饱和排除。"""
    r, g, b = (rgb[..., i].astype(np.int32) for i in range(3))
    luma = (299 * r + 587 * g + 114 * b) // 1000  # 必须 int32: int16 下 299*255 就溢出了
    chroma = rgb.max(axis=2).astype(np.int32) - rgb.min(axis=2).astype(np.int32)
    return (luma >= min_luma) | (chroma >= sat)


# ---------------------------------------------------------------- 连通域

def components(mask):
    """4 邻接连通域标记,返回 (labels, count)。用 BFS,纯 numpy + deque。"""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    cur = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if labels[y0, x0]:
            continue
        cur += 1
        labels[y0, x0] = cur
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = cur
                    q.append((ny, nx))
    return labels, cur


# ---------------------------------------------------------------- 轮廓与简化

_NEIGHBORS = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
_INDEX = {d: i for i, d in enumerate(_NEIGHBORS)}


def trace(mask):
    """Moore 邻域径向扫描描外轮廓,返回像素中心点列(首尾不重复)。

    为什么从"最上最左"的像素起:它一定是外轮廓上的一点,且其 NW 邻居必为背景,
    这样起始扫描方向有确定值,不需要额外判据。
    """
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return []
    start = (int(ys[0]), int(xs[0]))
    contour = [start]
    # 进入起始像素时的"来向":从 NW 进入,即先看来向顺时针的下一个方向
    back_dir = _INDEX[(-1, -1)]
    cur = start
    for _ in range(4 * h * w):
        found = None
        for k in range(8):
            d = (back_dir + 1 + k) % 8
            dy, dx = _NEIGHBORS[d]
            ny, nx = cur[0] + dy, cur[1] + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx]:
                found = (ny, nx)
                back_dir = _INDEX[(-_NEIGHBORS[d][0], -_NEIGHBORS[d][1])]
                break
        if not found:
            break
        cur = found
        if cur == start and len(contour) > 2:
            break
        contour.append(cur)
    return [(x, y) for y, x in contour]


def _dist_to_seg(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def rdp(points, eps=1.6, closed=True):
    """Ramer-Douglas-Peucker 折线简化。closed=True 时按闭合多边形处理。"""
    pts = list(points)
    if closed and len(pts) > 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return pts

    def simplify(seq):
        if len(seq) < 3:
            return seq
        a, b = seq[0], seq[-1]
        best_i, best_d = 0, -1.0
        for i in range(1, len(seq) - 1):
            d = _dist_to_seg(seq[i], a, b)
            if d > best_d:
                best_i, best_d = i, d
        if best_d <= eps:
            return [a, b]
        left = simplify(seq[: best_i + 1])
        right = simplify(seq[best_i:])
        return left[:-1] + right

    if not closed:
        return simplify(pts)
    # 闭合:先把首点当固定点,对它到最远点的两段分别简化
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    if far == 0:
        return [pts[0]]
    first = simplify(pts[: far + 1])
    second = simplify(pts[far:] + [pts[0]])
    return first[:-1] + second[:-1]


def signed_area(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- 一轮拟合

def fit(path, min_area=400, eps=1.6, min_luma=72, sat=28):
    """一轮:前景 → 连通域 → 轮廓 → RDP → 归类。

    返回 dict: size / palette / shapes[ {color, area, bbox, centroid, polygon, angles} ]。
    area 是像素面积,面积太小的块(文字、噪点)直接丢掉。
    """
    rgb = load_rgb(path)
    h, w = rgb.shape[:2]
    fg = foreground(rgb, min_luma=min_luma, sat=sat)
    labels, count = components(fg)
    shapes = []
    for lab in range(1, count + 1):
        sel = labels == lab
        area = int(sel.sum())
        if area < min_area:
            continue
        ys, xs = np.nonzero(sel)
        poly = rdp(trace(sel), eps=eps)
        if len(poly) < 3:
            continue
        mean = rgb[sel].mean(axis=0)
        poly_a = abs(signed_area(poly))
        shapes.append({
            "color": "#%02x%02x%02x" % tuple(int(round(v)) for v in mean),
            "area": area,
            "area_poly": round(poly_a, 1),
            "bbox": [round(v, 1) for v in bbox(poly)],
            "centroid": [round(float(xs.mean()), 2), round(float(ys.mean()), 2)],
            "polygon": [[round(x, 2), round(y, 2)] for x, y in poly],
        })
    shapes.sort(key=lambda s: -s["area"])
    return {"size": [w, h], "palette": palette(rgb, min_luma=min_luma, sat=sat), "shapes": shapes}


def main(argv):
    if len(argv) < 2:
        print("用法: python3 fit.py <图片> [输出.json]")
        return 1
    data = fit(argv[1])
    print(f"# {argv[1]}  {data['size'][0]}x{data['size'][1]}")
    print("# palette:", data["palette"][:8])
    for i, s in enumerate(data["shapes"]):
        n = len(s["polygon"])
        print(f"[{i}] {s['color']} area={s['area']} poly={n}pts "
              f"bbox={s['bbox']} centroid={s['centroid']}")
        for x, y in s["polygon"]:
            print(f"    ({x}, {y})")
    if len(argv) > 2:
        with open(argv[2], "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print(f"# -> {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
