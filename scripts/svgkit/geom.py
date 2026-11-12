#!/usr/bin/env python3
"""几何助手: 点列变换、圆弧采样与常见图元的派生公式.

是什么:
    - 坐标约定: 屏幕坐标, x 向右, y 向下, 角度单位是度, 0° = 正右, 角度增大 = 屏幕顺时针;
    - 点列变换: translate / rotate / scale / mirror, 以及 bbox / centroid;
    - 圆弧: angle_point / arc_points(采样成点列) / arc_path_d(生成真正的 A 圆弧命令);
    - 图元配方: regular_polygon(正多边形) / regular_star(正星形) / lens_path_d(透镜形);
    - transform 串: translate_transform / rotate_transform / scale_transform.

为什么:
    - 几何优先的画法要能一眼看出"这是个正 6 边形"而不是一堆手写坐标, 所以把
      可参数化的形状做成公式, 调用方只给圆心/半径/边数;
    - 真圆弧用 <path> 的 A 命令表达, 不要用贝塞尔硬拼, 也不要用几十点折线冒充;
      需要多边形的地方才用 arc_points 采样;
    - 镜像统一按"关于竖直/水平轴线镜像"描述(axis_x 是竖直线 x=axis_x),
      与数学教材里"关于 y 轴/ x 轴"的说法区分开, 避免写反方向.

元信息: 2026-11-12.
"""

from __future__ import annotations

import math

from .serialize import fmt

Point = tuple[float, float]


# --------------------------------------------------------------------------- #
# 点列与变换
# --------------------------------------------------------------------------- #

def points_text(points: list[Point]) -> str:
    """把点列写成 SVG 的 points 属性文本: `x1,y1 x2,y2 ...`."""
    return " ".join(f"{fmt(x)},{fmt(y)}" for x, y in points)


def translate(points: list[Point], dx: float, dy: float) -> list[Point]:
    """整体平移点列."""
    return [(x + dx, y + dy) for x, y in points]


def scale(points: list[Point], sx: float, sy: float | None = None) -> list[Point]:
    """整体缩放点列; sy 省略时两轴同比例."""
    if sy is None:
        sy = sx
    return [(x * sx, y * sy) for x, y in points]


def rotate(points: list[Point], deg: float, origin: Point = (0.0, 0.0)) -> list[Point]:
    """绕 origin 旋转点列; 正角度 = 屏幕顺时针(y 向下的坐标系里与数学正方向相反)."""
    angle = math.radians(deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    ox, oy = origin
    rotated: list[Point] = []
    for x, y in points:
        dx, dy = x - ox, y - oy
        rotated.append((ox + cos_a * dx - sin_a * dy, oy + sin_a * dx + cos_a * dy))
    return rotated


def mirror(
    points: list[Point],
    *,
    axis_x: float | None = None,
    axis_y: float | None = None,
) -> list[Point]:
    """关于竖直/水平轴线镜像点列.

    是什么:
        - axis_x: 竖直轴线 x = axis_x, 镜像后 x' = 2*axis_x - x;
        - axis_y: 水平轴线 y = axis_y, 镜像后 y' = 2*axis_y - y;
        - 两个轴可以同时给, 等价于关于交点做中心对称.

    为什么:
        麦穗、根部这类左右对称部件靠镜像生成, 用轴描述比写"翻转 x 坐标"更不容易错.
    """
    if axis_x is None and axis_y is None:
        raise ValueError("mirror() 至少需要 axis_x 或 axis_y 之一")
    mirrored: list[Point] = []
    for x, y in points:
        if axis_x is not None:
            x = 2.0 * axis_x - x
        if axis_y is not None:
            y = 2.0 * axis_y - y
        mirrored.append((x, y))
    return mirrored


def bbox(points: list[Point]) -> tuple[float, float, float, float]:
    """点列外接框, 返回 (min_x, min_y, max_x, max_y)."""
    if not points:
        raise ValueError("bbox() 需要非空点列")
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def centroid(points: list[Point]) -> Point:
    """多边形面积质心; 退化成零面积时回退到顶点平均.

    为什么:
        国土轮廓这类不规则多边形做旋转/缩放时, 绕"面积质心"比绕外接框中心更稳;
        面积公式 A = 1/2 * Σ(xi*yi+1 - xi+1*yi), Cx = 1/(6A) * Σ(xi+xi+1)*cross.
    """
    if not points:
        raise ValueError("centroid() 需要非空点列")
    twice_area = 0.0
    cx = 0.0
    cy = 0.0
    count = len(points)
    for index in range(count):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % count]
        cross = x0 * y1 - x1 * y0
        twice_area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(twice_area) < 1e-12:
        return (
            sum(x for x, _ in points) / count,
            sum(y for _, y in points) / count,
        )
    return cx / (3.0 * twice_area), cy / (3.0 * twice_area)


# --------------------------------------------------------------------------- #
# 圆弧
# --------------------------------------------------------------------------- #

def angle_point(cx: float, cy: float, radius: float, deg: float) -> Point:
    """圆上角度 deg 处的点(屏幕坐标, 0° = 正右, 顺时针为正)."""
    angle = math.radians(deg)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _arc_delta(start_deg: float, end_deg: float, clockwise: bool) -> float:
    """把起止角换成"沿指定方向要转过的正角度"(0, 360)."""
    delta = (end_deg - start_deg) % 360.0
    if not clockwise:
        delta = 360.0 - delta
    return delta


def arc_points(
    cx: float,
    cy: float,
    radius: float,
    start_deg: float,
    end_deg: float,
    *,
    clockwise: bool = True,
    segments: int | None = None,
    step_deg: float = 2.0,
) -> list[Point]:
    """把圆弧采样成点列(默认采样步长 2°), 首尾各含一个点.

    为什么:
        齿轮内孔、切边这些最终要以多边形边界参与填充, 只能用折线近似;
        步长按角度而不是固定段数给, 大圆弧和小圆弧的折线误差才一致.
    """
    delta = _arc_delta(start_deg, end_deg, clockwise)
    if delta <= 0:
        raise ValueError("arc_points() 的起止角不能相同")
    count = segments if segments is not None else max(2, int(math.ceil(delta / step_deg)))
    direction = 1.0 if clockwise else -1.0
    return [
        angle_point(cx, cy, radius, start_deg + direction * delta * index / count)
        for index in range(count + 1)
    ]


def arc_path_d(
    cx: float,
    cy: float,
    radius: float,
    start_deg: float,
    end_deg: float,
    *,
    clockwise: bool = True,
) -> str:
    """生成一段真圆弧的 <path> d 串(用 A 命令, 不用贝塞尔近似).

    为什么:
        SVG 的 A 命令就是"解析几何意义下的圆弧", 半径/起止角都由调用方给出,
        比用 4 段三次贝塞尔拼圆更短、更准, 编辑时也能看出这是圆弧;
        large-arc 由扫过的角度是否超过 180° 决定, sweep 由方向决定.
    """
    delta = _arc_delta(start_deg, end_deg, clockwise)
    if delta <= 0:
        raise ValueError("arc_path_d() 的起止角不能相同")
    start_x, start_y = angle_point(cx, cy, radius, start_deg)
    end_x, end_y = angle_point(cx, cy, radius, end_deg)
    large_arc = 1 if delta > 180.0 else 0
    sweep = 1 if clockwise else 0
    return (
        f"M{fmt(start_x)},{fmt(start_y)} "
        f"A{fmt(radius)},{fmt(radius)} 0 {large_arc} {sweep} "
        f"{fmt(end_x)},{fmt(end_y)}"
    )


def circle_points(
    cx: float,
    cy: float,
    radius: float,
    *,
    segments: int = 128,
    phase_deg: float = 0.0,
) -> list[Point]:
    """整圆采样成点列(不重复首尾点), 用于必须折线化的场合.

    为什么:
        能用 <circle> 就优先用 <circle>; 这个函数只服务"圆要参与多边形布尔/拼边"的场景,
        比如齿轮内孔边缘要和切边连成一个闭合多边形.
    """
    return [
        angle_point(cx, cy, radius, phase_deg + 360.0 * index / segments)
        for index in range(segments)
    ]


# --------------------------------------------------------------------------- #
# 形状配方
# --------------------------------------------------------------------------- #

def regular_polygon(
    cx: float,
    cy: float,
    radius: float,
    sides: int,
    *,
    phase_deg: float = 0.0,
) -> list[Point]:
    """正多边形顶点列(半径 = 外接圆半径); phase_deg 决定第一个顶点的方向."""
    if sides < 3:
        raise ValueError("regular_polygon() 至少 3 条边")
    return [
        angle_point(cx, cy, radius, phase_deg + 360.0 * index / sides)
        for index in range(sides)
    ]


def regular_star(
    cx: float,
    cy: float,
    outer_radius: float,
    inner_radius: float,
    points: int,
    *,
    phase_deg: float = 0.0,
) -> list[Point]:
    """正星形顶点列(外顶点/内顶点交替, 外顶点在 phase_deg 方向上).

    为什么:
        星形是最容易被"用一条 path 里手写 10 个坐标"画坏的图元; 用两个半径 + 点数
        生成顶点后直接交给 <polygon>, 改尖角比例只改一个参数.
    """
    if points < 3:
        raise ValueError("regular_star() 至少 3 个角")
    if not 0.0 < inner_radius < outer_radius:
        raise ValueError("regular_star() 要求 0 < inner_radius < outer_radius")
    vertices: list[Point] = []
    step = 360.0 / points
    for index in range(points):
        outer_angle = phase_deg + index * step
        inner_angle = outer_angle + step / 2.0
        vertices.append(angle_point(cx, cy, outer_radius, outer_angle))
        vertices.append(angle_point(cx, cy, inner_radius, inner_angle))
    return vertices


def lens_path_d(
    center: Point,
    *,
    length: float,
    thickness: float,
    heading_deg: float = 0.0,
) -> str:
    """透镜形(两条同半径劣弧围成的两头尖形状)的 <path> d 串.

    是什么:
        center 是长轴(弦)的中点, length 是弦长, thickness 是最大厚度,
        heading_deg 是长轴方向(0 = 正右, 顺时针为正).

    为什么:
        橄榄形/叶片形在图元层面没有对应形状, 只能用两条圆弧闭合; 弧半径由
        弦半长 a = L/2 与半厚 b = T/2 反解: R = (a^2 + b^2) / (2b),
        保证弧顶到弦的距离恰好是 T/2. 两条 A 命令的 sweep 都取 1, 不论朝向
        都围出关于长轴对称的透镜形, 一条闭合 path 即可.
    """
    if length <= 0:
        raise ValueError("lens_path_d() 要求 length > 0")
    if thickness <= 0:
        raise ValueError("lens_path_d() 要求 thickness > 0")
    if thickness >= 2 * length:
        raise ValueError("lens_path_d() 要求 thickness < 2*length, 否则两段弧退化成整圆")
    half_length = length / 2.0
    half_thickness = thickness / 2.0
    radius = (half_length**2 + half_thickness**2) / (2.0 * half_thickness)
    angle = math.radians(heading_deg)
    unit_x, unit_y = math.cos(angle), math.sin(angle)
    start_x = center[0] - half_length * unit_x
    start_y = center[1] - half_length * unit_y
    end_x = center[0] + half_length * unit_x
    end_y = center[1] + half_length * unit_y
    return (
        f"M{fmt(start_x)},{fmt(start_y)} "
        f"A{fmt(radius)},{fmt(radius)} 0 0 1 {fmt(end_x)},{fmt(end_y)} "
        f"A{fmt(radius)},{fmt(radius)} 0 0 1 {fmt(start_x)},{fmt(start_y)} Z"
    )


# --------------------------------------------------------------------------- #
# transform 串
# --------------------------------------------------------------------------- #

def translate_transform(dx: float, dy: float) -> str:
    """`translate(x,y)` 串."""
    return f"translate({fmt(dx)},{fmt(dy)})"


def rotate_transform(deg: float, cx: float = 0.0, cy: float = 0.0) -> str:
    """`rotate(deg,cx,cy)` 串; 旋转中心省略时绕原点."""
    return f"rotate({fmt(deg)},{fmt(cx)},{fmt(cy)})"


def scale_transform(sx: float, sy: float | None = None) -> str:
    """`scale(sx,sy)` 串; sy 省略时两轴同比例."""
    if sy is None:
        return f"scale({fmt(sx)})"
    return f"scale({fmt(sx)},{fmt(sy)})"
