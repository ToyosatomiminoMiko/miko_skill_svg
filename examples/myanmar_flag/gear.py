#!/usr/bin/env python3
"""齿轮部件: 14 齿齿圈被国土的两道缺口剪成两段, 每段一个简单闭合多边形.

是什么:
    移植自 myama 的 `miko_wiki_resource/parts/gear.py`:
    - 齿形公式 `_tooth_points` / `outer_outline_points`: 齿根弧 + 直线齿侧 + 齿顶倒圆;
    - 缺口切边的延长 `_extend_edge`: 把量测折线沿两端切线方向延长到齿圈之外.
    参数来自本目录 constants.py: GEAR_R_* / GEAR_TOOTH_* 是从参考位图回归的冻结值,
    GEAR_CUT_EDGE_* 是四条缺口切边的量测点(顺序: 齿顶侧 -> 内孔侧).

    导出 `gear_elements()`: 齿轮局部坐标(圆心 = 原点, 设计单位, y 向下)下的一组
    `<polygon>`, 每个多边形自身闭合、不挖洞.

为什么:
    myama 的最终形态 = 完整齿轮复合 path(外轮廓一条子路径 + 内孔一条子路径,
    fill-rule="evenodd" 挖洞) 被两处缺口 mask 遮掉. 本技能要求"简单几何图元",
    所以这里既不用 mask, 也不用带洞的复合 path:
    两处缺口把齿圈切成两段, 每段自己就是一个简单闭合环带多边形,
    两块并集 = 完整齿圈 - 两道缺口.

    每段多边形的边界由四段拼成(与 myama 缺口 mask 的边界是同一份几何):
        一侧切边(内孔 -> 齿顶) + 外轮廓一段(齿顶 -> 齿顶)
        + 另一侧切边(齿顶 -> 内孔) + 内孔圆弧一段(内孔 -> 内孔), 首尾闭合.
    - 切边先延长到 r_inner - GEAR_CUT_MARGIN / r_tip + GEAR_CUT_MARGIN 之外, 再与
      "齿外轮廓折线"和"内孔圆"求交: 环带之外的部分本来就不可见, 交点就是切边真正
      落在环带上的端点;
    - 外轮廓点列按齿角递增排列, 所以每段取"起始切边交点 -> 结束切边交点"递增的那一段
      外轮廓; 内孔圆弧反向(角度递减)从结束端点回到起始端点, 多边形不会自交.

    两段的配对由缺口位置决定(齿角递增方向):
        左下半段 = BOTTOM_B -> TOP_A, 右段 = TOP_B -> BOTTOM_A.
    (顶部缺口在 TOP_A/TOP_B 之间, 右下缺口在 BOTTOM_A/BOTTOM_B 之间.)

元信息: 2026-11-12; 移植自 myama parts/gear.py, 齿形公式与四条切边的数据未改动.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from svgkit import Element, Polygon  # noqa: E402  (先补好 sys.path 再导入 svgkit)

import constants as c  # noqa: E402

Point = tuple[float, float]


# --------------------------------------------------------------------------- #
# 齿形公式(逐行移植自 myama gear.py, 注释保留原推导)
# --------------------------------------------------------------------------- #

def _rotate(x: float, y: float, deg: float) -> Point:
    """把点绕原点旋转 deg 度(屏幕坐标 y 向下, 角度增大 = 屏幕上顺时针)."""
    rad = math.radians(deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return x * cos_a - y * sin_a, x * sin_a + y * cos_a


def _arc_points(
    radius: float, start_deg: float, end_deg: float, step_deg: float = 2.0
) -> list[Point]:
    """在半径 radius 的圆上从 start_deg 扫到 end_deg(有向, 允许递减), 返回含两端的采样点.

    采样只为把圆弧变成可计算的折线: 步长 2° 时弦高误差约 r*(1-cos1°)≈0.0002r,
    对 r≈336 的设计单位是 0.06, 远小于目标图一个像素(4.3 单位), 可以忽略.
    """
    span = end_deg - start_deg
    count = max(2, int(math.ceil(abs(span) / step_deg)) + 1)
    points: list[Point] = []
    for index in range(count):
        deg = start_deg + span * index / (count - 1)
        rad = math.radians(deg)
        points.append((radius * math.cos(rad), radius * math.sin(rad)))
    return points


def _tooth_points(
    r_root: float,
    r_tip: float,
    half_root_deg: float,
    half_tip_deg: float,
    tip_round: float,
) -> list[Point]:
    """返回一个齿的轮廓点(齿中线在 +x 方向), 从左侧齿根点经齿顶到右侧齿根点.

    几何:
        - 左侧齿根点 B_L = (r_root, -half_root), 未倒圆的齿顶角 V_L = (r_tip, -half_tip);
        - 齿侧就是线段 B_L->V_L, 但齿顶角 V_L 要用半径 tip_round 的圆倒角;
        - 倒角圆(圆心 C)同时内切于齿顶圆、外切于齿侧直线:
              |C| = r_tip - tip_round            (内切于齿顶圆)
              dist(C, 齿侧直线) = tip_round        (外切于齿侧)
          把 C 写成 C = B_L + t*u + n*tip_round(u 为齿侧单位方向, n 为指向齿内的单位法线),
          代进 |C| = r_tip - tip_round 得到关于 t 的一元二次方程, 取靠近齿顶的那个根;
        - 两个切点: 齿侧上的 T_flank = B_L + t*u, 齿顶圆上的 T_tip = C/|C|*r_tip;
          角点圆弧就是 C 为圆心、从 T_flank 到 T_tip 的那一小段.
        右侧与左侧关于齿中线镜像, 所以只算左侧再把 y 取反.
    """
    half_root = math.radians(half_root_deg)
    half_tip = math.radians(half_tip_deg)
    # 左侧: 角度取负(屏幕坐标里 -half 在齿中线的另一侧)
    base_left = (r_root * math.cos(-half_root), r_root * math.sin(-half_root))
    tip_left = (r_tip * math.cos(-half_tip), r_tip * math.sin(-half_tip))

    ux = tip_left[0] - base_left[0]
    uy = tip_left[1] - base_left[1]
    length = math.hypot(ux, uy)
    ux, uy = ux / length, uy / length

    # 指向齿内的法线: 两个候选里挑与"齿中线上的齿顶点"同侧的那个
    candidate_a = (-uy, ux)
    candidate_b = (uy, -ux)
    tip_center = (r_tip, 0.0)
    normal = max(
        (candidate_a, candidate_b),
        key=lambda n: n[0] * (tip_center[0] - base_left[0])
        + n[1] * (tip_center[1] - base_left[1]),
    )
    nx, ny = normal

    # 解 |B_L + t*u + n*rc|^2 = (r_tip - rc)^2
    corner_x = base_left[0] + nx * tip_round
    corner_y = base_left[1] + ny * tip_round
    b_coef = 2.0 * (ux * corner_x + uy * corner_y)
    c_coef = corner_x * corner_x + corner_y * corner_y - (r_tip - tip_round) ** 2
    discriminant = max(b_coef * b_coef - 4.0 * c_coef, 0.0)
    t = (-b_coef + math.sqrt(discriminant)) / 2.0

    center = (base_left[0] + t * ux + nx * tip_round, base_left[1] + t * uy + ny * tip_round)
    tangent_flank = (base_left[0] + t * ux, base_left[1] + t * uy)
    center_len = math.hypot(*center)
    tangent_tip = (center[0] * r_tip / center_len, center[1] * r_tip / center_len)

    # 齿顶角圆弧: 从齿侧切点绕到齿顶切点(取短的那一边)
    angle_a = math.atan2(
        tangent_flank[1] - center[1], tangent_flank[0] - center[0]
    )
    angle_b = math.atan2(tangent_tip[1] - center[1], tangent_tip[0] - center[0])
    delta = (angle_b - angle_a + math.pi) % (2.0 * math.pi) - math.pi
    corner_steps = 5
    corner = [
        (
            center[0] + tip_round * math.cos(angle_a + delta * index / (corner_steps - 1)),
            center[1] + tip_round * math.sin(angle_a + delta * index / (corner_steps - 1)),
        )
        for index in range(corner_steps)
    ]

    left = [base_left, tangent_flank]
    left.extend(corner[1:])  # corner[0] 就是 tangent_flank
    # 齿顶弧: 左侧齿顶切点 -> 右侧齿顶切点(角度增大)
    tip_angle = math.atan2(tangent_tip[1], tangent_tip[0])
    tip_points = _arc_points(r_tip, math.degrees(tip_angle), -math.degrees(tip_angle), 2.0)
    left.extend(tip_points[1:])
    # 右侧倒角: 左侧倒角关于齿中线镜像后反向
    right_corner = [(x, -y) for (x, y) in corner][::-1]
    left.extend(right_corner[1:])
    base_right = (r_root * math.cos(half_root), r_root * math.sin(half_root))
    left.append(base_right)
    return left


def outer_outline_points(
    tooth_centers_deg: list[float] | tuple[float, ...],
    r_root: float,
    r_tip: float,
    half_root_deg: float,
    half_tip_deg: float,
    tip_round: float,
) -> list[Point]:
    """按齿角顺序拼出齿轮外轮廓的闭合折线(不含内孔)."""
    teeth = sorted(float(a) % 360.0 for a in tooth_centers_deg)
    if not teeth:
        return []
    tooth_local = _tooth_points(r_root, r_tip, half_root_deg, half_tip_deg, tip_round)
    points: list[Point] = []
    for index, center_deg in enumerate(teeth):
        previous = teeth[index - 1] if index > 0 else teeth[-1] - 360.0
        # 齿根圆弧: 上一齿右齿根 -> 本齿左齿根
        points.extend(_arc_points(r_root, previous + half_root_deg, center_deg - half_root_deg))
        # 齿身: 跳过第一个点(就是本齿左齿根, 根弧已经采到)
        rotated = [_rotate(x, y, center_deg) for (x, y) in tooth_local]
        points.extend(rotated[1:])
    # 收尾: 最后一齿右齿根 -> 第一齿左齿根(+360°)
    points.extend(
        _arc_points(r_root, teeth[-1] + half_root_deg, teeth[0] + 360.0 - half_root_deg)
    )
    # 相邻重复点去掉(圆弧端点与下一段起点重合)
    cleaned: list[Point] = []
    for point in points:
        if not cleaned or math.hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]) > 1e-9:
            cleaned.append(point)
    return cleaned


# --------------------------------------------------------------------------- #
# 缺口切边: 延长、求交、裁剪
# --------------------------------------------------------------------------- #

def _extend_edge(
    points: list[Point], radius_low: float, radius_high: float
) -> list[Point]:
    """把一条切边(采样点, 从齿顶侧到内孔侧)线性外插到内/外两个半径之外.

    切边本身只量到 r_tip / r_inner; 和 myama 的缺口 mask 一样, 两端要沿各自端段的
    切线方向延长到 r_high / r_low 两个圆上, 这样切边一定完整穿过齿圈;
    多出来的部分在齿轮外/内孔里, 不可见.
    """
    (x0, y0), (x1, y1) = points[0], points[1]
    ux, uy = x0 - x1, y0 - y1
    length = math.hypot(ux, uy)
    ux, uy = ux / length, uy / length
    # |p + t*u| = R 的较大根(t > 0 才有意义)
    disc = (x0 * ux + y0 * uy) ** 2 - (x0 * x0 + y0 * y0) + radius_high * radius_high
    t_out = -(x0 * ux + y0 * uy) + math.sqrt(max(disc, 0.0))
    outer = (x0 + t_out * ux, y0 + t_out * uy)

    (a0, b0), (a1, b1) = points[-1], points[-2]
    vx, vy = a0 - a1, b0 - b1
    length = math.hypot(vx, vy)
    vx, vy = vx / length, vy / length
    disc = (a0 * vx + b0 * vy) ** 2 - (a0 * a0 + b0 * b0) + radius_low * radius_low
    t_in = -(a0 * vx + b0 * vy) + math.sqrt(max(disc, 0.0))
    inner = (a0 + t_in * vx, b0 + t_in * vy)
    return [outer, *points, inner]


def _segment_hit(p1: Point, p2: Point, p3: Point, p4: Point) -> tuple[float, float] | None:
    """两条线段求交, 返回 (第一条线段参数 t, 第二条线段参数 u); 平行/退化返回 None.

    叉积形式解 P1 + t*(P2-P1) = P3 + u*(P4-P3).
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / denom
    eps = 1e-9
    if -eps <= t <= 1.0 + eps and -eps <= u <= 1.0 + eps:
        return t, u
    return None


def _lerp(p1: Point, p2: Point, t: float) -> Point:
    """线段上参数 t 处的点."""
    return p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t


def _outer_crossing(
    edge: list[Point], outline: list[Point]
) -> tuple[Point, int, int]:
    """切边(外->内)与齿外轮廓折线的第一个交点, 返回 (交点, 切边段号, 外轮廓段号).

    为什么取"第一个": 切边从 r_tip 之外出发往内走, 第一次穿过外轮廓就是它进入齿圈
    的位置; 之后即便再与别的齿相交, 也已经在环带内部, 不是缺口边界了.
    """
    for edge_index in range(len(edge) - 1):
        best_t = None
        best_outline_index = -1
        for outline_index in range(len(outline)):
            hit = _segment_hit(
                edge[edge_index],
                edge[edge_index + 1],
                outline[outline_index],
                outline[(outline_index + 1) % len(outline)],
            )
            if hit is None:
                continue
            t, _u = hit
            if best_t is None or t < best_t:
                best_t = t
                best_outline_index = outline_index
        if best_t is not None and best_outline_index >= 0:
            point = _lerp(edge[edge_index], edge[edge_index + 1], best_t)
            return point, edge_index, best_outline_index
    raise ValueError("齿轮切边没有穿过齿外轮廓, 检查 GEAR_CUT_EDGE_* 与齿形参数")


def _inner_crossing(edge: list[Point], radius: float) -> tuple[Point, int]:
    """切边(外->内)与内孔圆 |p| = radius 的交点, 返回 (交点, 切边段号).

    切边从圆外走进圆内, 沿折线第一个进入圆的交点就是缺口在内孔上的端点;
    二次方程每段最多两个根, 取沿切边方向先到的那个.
    """
    for edge_index in range(len(edge) - 1):
        (x0, y0), (x1, y1) = edge[edge_index], edge[edge_index + 1]
        dx, dy = x1 - x0, y1 - y0
        a = dx * dx + dy * dy
        if a < 1e-18:
            continue
        b = 2.0 * (x0 * dx + y0 * dy)
        cc = x0 * x0 + y0 * y0 - radius * radius
        disc = b * b - 4.0 * a * cc
        if disc < 0.0:
            continue
        root = math.sqrt(disc)
        for t in sorted(((-b - root) / (2.0 * a), (-b + root) / (2.0 * a))):
            if -1e-9 <= t <= 1.0 + 1e-9:
                return _lerp(edge[edge_index], edge[edge_index + 1], t), edge_index
    raise ValueError("齿轮切边没有穿过内孔圆, 检查 GEAR_CUT_EDGE_* 与 r_inner")


def _edge_between(
    edge: list[Point],
    outer_hit: tuple[Point, int, int],
    inner_hit: tuple[Point, int],
) -> list[Point]:
    """切边落在齿圈内的那一段: 从外轮廓交点走到内孔交点(外->内, 含两端点).

    外轮廓/内孔交点一般不在切边的原采样顶点上, 所以用交点替换两端;
    中间的原始量测点原样保留(切边本来就是折线). 两个 hit 的第 1 项都是切边段号.
    """
    outer_point, outer_index = outer_hit[0], outer_hit[1]
    inner_point, inner_index = inner_hit[0], inner_hit[1]
    points: list[Point] = [outer_point]
    points.extend(edge[outer_index + 1 : inner_index + 1])
    points.append(inner_point)
    return points


def _outline_between(
    outline: list[Point],
    start_hit: tuple[Point, int, int],
    end_hit: tuple[Point, int, int],
) -> list[Point]:
    """外轮廓从起始交点走到结束交点的点列(沿下标增大 = 齿角增大方向).

    起始交点已经在上一段(切边)里, 所以这里不重复包含它; 结束交点包含在内.
    两个 hit 的第 2 项是外轮廓段号.
    """
    start_index = start_hit[2]
    end_point, end_index = end_hit[0], end_hit[2]
    count = len(outline)
    span = (end_index - start_index) % count
    if span == 0:
        raise ValueError("两处切边交点落在齿外轮廓的同一条边上, 无法围成环带")
    points = [outline[(start_index + step) % count] for step in range(1, span + 1)]
    points.append(end_point)
    return points


def _ring_segment(
    start_edge: tuple[Point, ...],
    end_edge: tuple[Point, ...],
    outline: list[Point],
) -> list[Point]:
    """一段环带多边形: 起始切边 -> 外轮廓 -> 结束切边 -> 内孔圆弧, 首尾闭合.

    起始/结束按齿角递增方向给: 起始切边在角小的一侧, 结束切边在角大的一侧.
    内孔圆弧与外侧方向相反(角度递减), 所以多边形是一个不自交的"弯月环带".
    """
    r_inner = c.GEAR_R_INNER
    r_low = r_inner - c.GEAR_CUT_MARGIN
    r_high = c.GEAR_R_TIP + c.GEAR_CUT_MARGIN
    start_ext = _extend_edge(list(start_edge), r_low, r_high)
    end_ext = _extend_edge(list(end_edge), r_low, r_high)
    start_outer_hit = _outer_crossing(start_ext, outline)
    end_outer_hit = _outer_crossing(end_ext, outline)
    start_inner_hit = _inner_crossing(start_ext, r_inner)
    end_inner_hit = _inner_crossing(end_ext, r_inner)

    start_cut = _edge_between(start_ext, start_outer_hit, start_inner_hit)  # 外->内
    end_cut = _edge_between(end_ext, end_outer_hit, end_inner_hit)  # 外->内
    outer_part = _outline_between(outline, start_outer_hit, end_outer_hit)

    # 内孔圆弧: 从结束切边的内端点回到起始切边的内端点, 角度递减(与外侧反向).
    end_deg = math.degrees(math.atan2(end_inner_hit[0][1], end_inner_hit[0][0]))
    start_deg = math.degrees(math.atan2(start_inner_hit[0][1], start_inner_hit[0][0]))
    # 递减方向的跨度: 使 start_deg 落在 end_deg 的 (end_deg-360°, end_deg] 内.
    span = -((end_deg - start_deg) % 360.0)
    inner_arc = _arc_points(r_inner, end_deg, end_deg + span)

    polygon: list[Point] = list(reversed(start_cut))  # 内孔 -> 齿顶, 含 start_outer
    polygon.extend(outer_part)  # 齿顶 -> 齿顶, 不含 start_outer、含 end_outer
    polygon.extend(end_cut[1:])  # 齿顶 -> 内孔, 不含 end_outer、含 end_inner
    polygon.extend(inner_arc[1:-1])  # 内孔 -> 内孔, 不含两端(首尾已由切边给出)
    return polygon


# --------------------------------------------------------------------------- #
# 对外接口
# --------------------------------------------------------------------------- #

def gear_elements() -> list[Element]:
    """返回齿轮最终形态的图元: 两段简单闭合多边形, 并集 = 齿圈减两道缺口.

    坐标: 齿轮局部坐标(圆心 = 原点, 设计单位, y 向下); 白色填充.
    两段按齿角递增方向配对: 左下半段(BOTTOM_B -> TOP_A), 右段(TOP_B -> BOTTOM_A).
    """
    outline = outer_outline_points(
        c.GEAR_TOOTH_CENTERS_DEG,
        c.GEAR_R_ROOT,
        c.GEAR_R_TIP,
        c.GEAR_TOOTH_HALF_ROOT_DEG,
        c.GEAR_TOOTH_HALF_TIP_DEG,
        c.GEAR_TIP_ROUND,
    )
    segment_pairs = (
        (c.GEAR_CUT_EDGE_BOTTOM_B, c.GEAR_CUT_EDGE_TOP_A),  # 左下半段
        (c.GEAR_CUT_EDGE_TOP_B, c.GEAR_CUT_EDGE_BOTTOM_A),  # 右段
    )
    return [
        Polygon(_ring_segment(start_edge, end_edge, outline), fill=c.EMBLEM_WHITE)
        for start_edge, end_edge in segment_pairs
    ]
