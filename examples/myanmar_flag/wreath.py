#!/usr/bin/env python3
"""MNTJP 花环(6 枚麦穗 / 12 粒麦子 + 2 枚顶端橄榄 + 6 道芒)的图元组装.

是什么:
    wreath_elements() 返回花环的全部图元, 坐标是设计单位、原点在花环圆心 O、
    y 向下、角度 0° = 正右且顺时针为正:
    - 12 粒麦子: 每粒一个 <polygon>; 两粒组成一枚麦穗, 中间留麦秆缝;
      每粒各自闭合, 不把两粒硬接成一个自接触多边形(原因见 wreath_elements 的 docstring);
    - 2 枚顶端橄榄: 每枚一条 <path>, 两条同半径劣弧围成的透镜形;
    - 6 道芒: 每道一条 <path>, 真圆弧 A 命令, 只描边不填充, 端点圆头.

为什么:
    - 麦穗是"弯曲的平行四边形", 橄榄是"两条劣弧夹出的透镜", 芒是同心圆弧,
      没有贝塞尔曲线, 所以全部能落到简单图元上: 轮廓密采样后交给 <polygon>,
      真曲线交给 <path> 的 A 命令;
    - 参数一律从本目录 constants.py 取(冻结参数, 从参考位图回归), 本文件不重复抄数值;
    - 坐标保持在"原点 O 的设计单位"里, 拼旗面时由 build.py 套 translate + scale,
      部件可以单独预览, 不用把每个坐标预先换算成旗面像素.

元信息: 2026-11-12; 移植自 myama 仓库 miko_wiki_resource/parts/ 下的
    parallelogram.py(麦粒轮廓与卷弧)、arrange.py(沿圆弧排列与顶端橄榄定位)、
    mirror.py(竖直镜像)、arcs.py(三道同心弧)、olive.py(透镜形公式);
    只搬几何, 删掉了原来的画布/预览/SVG 字符串拼装. myama 的 PART_PADDING 只给
    单件画布留白, 在"输出相对 O"的坐标里整体平移会抵消, 所以没有移植.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from svgkit import Element, Path, Polygon, arc_path_d, lens_path_d
from svgkit.geom import bbox, mirror, rotate

import constants as c

Point = tuple[float, float]
EarPolygon = list[Point]
OliveGeometry = tuple[Point, float, float, float]


class _EarSpec(NamedTuple):
    """一枚麦穗的生成参数(不含扭转角, 扭转角由圆弧半径反推)."""

    length: float
    height: float
    offset: float
    top_radius: float
    root_radius: float
    gap: float
    pivot_ratio: float


class _OliveSpec(NamedTuple):
    """一枚橄榄的长轴长度与最大厚度."""

    length: float
    thickness: float


class _ArcSpec(NamedTuple):
    """一道同心芒: 名称、径向比例、终止角与角跨度(度)."""

    name: str
    radial_ratio: float
    end_deg: float
    span_deg: float


class _Corner(NamedTuple):
    """一粒麦子钝角处的圆角: 两切点、圆心、半径、进入方向、切点离顶点的长度."""

    start: Point
    end: Point
    center: Point
    radius: float
    in_dir: Point
    tangent: float


class _TwistedEar(NamedTuple):
    """卷弧后的一枚麦穗: 左右两粒的轮廓、弯曲圆心、弯曲半径, 四者同一坐标系."""

    left: list[Point]
    right: list[Point]
    center: Point
    bend_radius: float


# --------------------------------------------------------------------------- #
# 单粒麦子: 平行四边形 -> 立起来 -> 轮廓采样 -> 卷弧
# --------------------------------------------------------------------------- #

def _grain_points(length: float, height: float, offset: float) -> list[Point]:
    """一粒麦子(平行四边形)的四个顶点, 顺序为 左上、右上、右下、左下.

    以左下角为基准: 底边水平长 length, 顶边相对底边右移 offset, 垂直高 height.
    旋转 90° 前, 这个平行四边形的两条斜边就是两粒相对拼成麦穗时的麦秆缝方向.
    """
    return [
        (offset, 0.0),  # 左上
        (offset + length, 0.0),  # 右上
        (length, height),  # 右下
        (0.0, height),  # 左下
    ]


def _signed_area(points: list[Point]) -> float:
    """鞋带公式求有向面积; 屏幕坐标 y 向下时, 结果 > 0 表示顶点顺序为顺时针."""
    total = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _unit(dx: float, dy: float) -> Point:
    """把向量归一化成单位向量."""
    magnitude = math.hypot(dx, dy)
    return dx / magnitude, dy / magnitude


def _build_corners(
    points: list[Point], radii: list[float]
) -> list[_Corner | None]:
    """按每个顶点各自的半径算钝角圆角; 锐角/直角/零半径返回 None(保持尖角).

    圆角圆弧与两条邻边相切, 切点离顶点 t = radius / tan(θ/2), θ 为内角;
    圆心在图形内部, 由顶点顺序决定的内法线偏移 radius: 屏幕坐标 y 向下时
    顺时针顶点序的内部在行进方向右侧, 取 (-dy, dx), 逆时针取 (dy, -dx).
    最后校验同一条边上两个圆角的切点长度之和不超过该边长, 放不下就报错而不是画出烂形.
    """
    count = len(points)
    right_angle = math.pi / 2 + 1e-9
    clockwise = _signed_area(points) > 0
    corners: list[_Corner | None] = []
    for index in range(count):
        radius = radii[index]
        if radius <= 0:
            corners.append(None)
            continue
        previous = points[index - 1]
        current = points[index]
        following = points[(index + 1) % count]
        in_dir = _unit(current[0] - previous[0], current[1] - previous[1])
        out_dir = _unit(following[0] - current[0], following[1] - current[1])
        interior = math.acos(
            max(
                -1.0,
                min(
                    1.0,
                    -(in_dir[0] * out_dir[0] + in_dir[1] * out_dir[1]),
                ),
            )
        )
        if interior <= right_angle:  # 直角 / 锐角不圆角
            corners.append(None)
            continue
        tangent = radius / math.tan(interior / 2.0)
        start = (
            current[0] - in_dir[0] * tangent,
            current[1] - in_dir[1] * tangent,
        )
        end = (
            current[0] + out_dir[0] * tangent,
            current[1] + out_dir[1] * tangent,
        )
        normal = (-in_dir[1], in_dir[0]) if clockwise else (in_dir[1], -in_dir[0])
        center = (start[0] + normal[0] * radius, start[1] + normal[1] * radius)
        if not math.isclose(math.dist(center, end), radius, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("圆角几何计算异常: 圆弧半径与切点位置不自洽")
        corners.append(_Corner(start, end, center, radius, in_dir, tangent))

    for index in range(count):
        following = (index + 1) % count
        used = (corners[index].tangent if corners[index] else 0.0) + (
            corners[following].tangent if corners[following] else 0.0
        )
        edge = math.dist(points[index], points[following])
        if used > edge + 1e-9:
            raise ValueError("圆角放不下: 同一顶点半径相对边长太大")
    return corners


def _outline_points(
    points: list[Point],
    radii: list[float],
    *,
    arc_steps: int = 18,
    line_steps: int = 10,
) -> list[Point]:
    """把一粒麦子的轮廓(含钝角圆角)采样成一圈点, 给卷弧用.

    为什么不能只用四个顶点: 卷弧会把直边掰成曲线, 必须先沿边采样;
    圆角圆弧同理按角度步进采样, arc_steps / line_steps 控制采样精度.
    每段采样都不含终点(避免与下一段重复), 最后一点自然靠近首点,
    闭合边留给 <polygon> 的 Z 命令.
    """
    if all(radius <= 0 for radius in radii):
        return list(points)

    corners = _build_corners(points, radii)
    count = len(points)
    samples: list[Point] = []

    def add_line(start: Point, end: Point) -> None:
        """沿线段均匀取 line_steps 个点(不含终点)."""
        for step in range(line_steps):
            t = step / line_steps
            samples.append(
                (
                    start[0] + (end[0] - start[0]) * t,
                    start[1] + (end[1] - start[1]) * t,
                )
            )

    def add_arc(corner: _Corner) -> None:
        """沿圆角圆弧取点(含起点, 不含终点), 方向与该圆角的两切点一致."""
        start_angle = math.atan2(
            corner.start[1] - corner.center[1],
            corner.start[0] - corner.center[0],
        )
        end_angle = math.atan2(
            corner.end[1] - corner.center[1],
            corner.end[0] - corner.center[0],
        )
        delta = (end_angle - start_angle + math.pi) % (2 * math.pi) - math.pi
        for step in range(arc_steps):
            angle = start_angle + delta * step / arc_steps
            samples.append(
                (
                    corner.center[0] + corner.radius * math.cos(angle),
                    corner.center[1] + corner.radius * math.sin(angle),
                )
            )

    first = corners[0]
    cursor = points[0]
    if first is not None:
        cursor = first.start
        add_arc(first)
        cursor = first.end
    for index in range(1, count):
        corner = corners[index]
        if corner is None:
            add_line(cursor, points[index])
            cursor = points[index]
        else:
            add_line(cursor, corner.start)
            add_arc(corner)
            cursor = corner.end
    add_line(cursor, first.start if first is not None else points[0])
    return samples


def _grain_radii(points: list[Point], top_radius: float, root_radius: float) -> list[float]:
    """按高度给同一粒麦子的顶点分配圆角半径: 靠下的(根部)用大圆角, 靠上的用小圆角.

    锐角顶点本来就不会被圆角, 分到哪个半径都无所谓.
    """
    ys = [y for _, y in points]
    mid_y = (min(ys) + max(ys)) / 2.0
    return [root_radius if y > mid_y else top_radius for _, y in points]


def _bend_points(
    points: list[Point],
    center: Point,
    radius: float,
    direction: float,
) -> list[Point]:
    """把平面卷成圆弧: 竖直线变成以 center 为圆心的同心弧.

    映射关系: 角度 θ = direction * (y - center_y) / radius,
    半径 r = radius + (x - center_x), 输出 = center + r * (cos θ, sin θ).
    于是每条竖直线 x = const 变成半径恒定的圆弧(多条竖直线即同心弧),
    原来的水平线变成从圆心射出的径向线, 圆角弧也跟着弯成小圆弧.
    """
    bent: list[Point] = []
    for x, y in points:
        theta = direction * (y - center[1]) / radius
        r = radius + (x - center[0])
        bent.append(
            (
                center[0] + r * math.cos(theta),
                center[1] + r * math.sin(theta),
            )
        )
    return bent


def _rotated_grain(length: float, height: float, offset: float) -> list[Point]:
    """一粒麦子绕自身中心顺时针转 90° 立起来, 再把外接框归一化到 (0, 0).

    屏幕坐标 y 向下, 顺时针 90° 的映射是 (x, y) -> (cx - (y - cy), cy + (x - cx));
    归一化后旋转图形的外接框宽 = 原高度 H, 高 = 原底边跨度 (L + D).
    """
    points = _grain_points(length, height, offset)
    min_x, min_y, max_x, max_y = bbox(points)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    rotated = [
        (center_x - (y - center_y), center_y + (x - center_x)) for x, y in points
    ]
    min_x, min_y, _, _ = bbox(rotated)
    return [(x - min_x, y - min_y) for x, y in rotated]


def _twisted_ear(ear: _EarSpec, twist_deg: float) -> _TwistedEar:
    """把左右两粒麦子拼成一枚麦穗再卷成圆弧, 返回轮廓、弯曲圆心与半径(只算几何).

    两粒关于麦穗中线镜像, 中间 gap 就是麦秆缝; 以采样后轮廓外接框的
    (水平中点, max_y - pivot_ratio * 高) 为弯曲圆心, 曲率由 twist_deg 给出:
    bend_radius = 高 / |twist_deg(弧度)|, 负角度则往反方向卷.
    轮廓点减去弯曲圆心就是"相对 O"的坐标, 摆到圆上时只差一次绕 O 旋转.
    """
    if ear.length <= 0 or ear.height <= 0:
        raise ValueError("麦粒的长和高必须为正")
    if ear.offset < 0:
        raise ValueError("麦粒斜度 offset 不能为负")
    if ear.gap < 0:
        raise ValueError("麦秆缝 gap 不能为负")
    if min(ear.top_radius, ear.root_radius) < 0:
        raise ValueError("圆角半径不能为负")
    if not 0 <= ear.pivot_ratio < 1:
        raise ValueError("pivot_ratio 必须在 [0, 1) 之内")
    if twist_deg == 0:
        raise ValueError("twist_deg 不能为 0")

    rotated = _rotated_grain(ear.length, ear.height, ear.offset)
    min_x, min_y, max_x, _ = bbox(rotated)
    shape_width = max_x - min_x
    left = [(x - min_x, y - min_y) for x, y in rotated]
    right = [(shape_width + ear.gap + max_x - x, y - min_y) for x, y in rotated]

    left_outline = _outline_points(
        left, _grain_radii(left, ear.top_radius, ear.root_radius)
    )
    right_outline = _outline_points(
        right, _grain_radii(right, ear.top_radius, ear.root_radius)
    )

    min_x, min_y, max_x, max_y = bbox(left_outline + right_outline)
    center = ((min_x + max_x) / 2.0, max_y - ear.pivot_ratio * (max_y - min_y))
    width = max_x - min_x
    height_span = max_y - min_y
    direction = 1.0 if twist_deg > 0 else -1.0
    bend_radius = height_span / abs(math.radians(twist_deg))
    if bend_radius <= width / 2.0:
        raise ValueError("twist_deg 太大: 弯曲半径小于图形半宽")

    return _TwistedEar(
        left=_bend_points(left_outline, center, bend_radius, direction),
        right=_bend_points(right_outline, center, bend_radius, direction),
        center=center,
        bend_radius=bend_radius,
    )


# --------------------------------------------------------------------------- #
# 排列: 沿同一段圆弧首尾相接, 再竖直镜像
# --------------------------------------------------------------------------- #

def _ear_spec() -> _EarSpec:
    """从 constants.py 取麦粒/麦穗参数组装 _EarSpec(唯一参数源)."""
    return _EarSpec(
        length=c.EAR_LENGTH,
        height=c.EAR_HEIGHT,
        offset=c.EAR_OFFSET,
        top_radius=c.EAR_TOP_RADIUS,
        root_radius=c.EAR_ROOT_RADIUS,
        gap=c.EAR_GAP,
        pivot_ratio=c.EAR_PIVOT_RATIO,
    )


def _ear_on_circle(ear: _EarSpec, radius: float) -> tuple[list[Point], list[Point], float]:
    """生成弯曲半径正好等于 radius 的一枚麦穗, 返回 (左粒, 右粒, 弧角).

    弧角由半径反推: 旋转后麦穗高度 = length + offset, 卷弧半径
    R = 高 / |弧角(弧度)|, 所以弧角 = degrees(高 / radius).
    这样每枚麦穗的弯曲圆心才会都落在 O 上.
    """
    if radius <= 0:
        raise ValueError("radius 必须为正")
    arc_deg = math.degrees((ear.length + ear.offset) / radius)
    geometry = _twisted_ear(ear, arc_deg)
    if not math.isclose(geometry.bend_radius, radius, rel_tol=1e-9):
        raise ValueError("弯曲半径和 radius 对不上: 麦穗 span 高度的算法可能变了")
    center_x, center_y = geometry.center
    left = [(x - center_x, y - center_y) for x, y in geometry.left]
    right = [(x - center_x, y - center_y) for x, y in geometry.right]
    return left, right, arc_deg


def _arranged_outlines(
    ear: _EarSpec,
    *,
    radius: float,
    spacing: float,
    center_deg: float,
    count: int,
) -> tuple[list[EarPolygon], float]:
    """按 arrange 的排法摆好 count 枚麦穗, 返回 (轮廓列表, 弧段起点角).

    每枚的弧角由半径反推, 总跨度 = count * 弧角 + (count - 1) * 缝;
    整组以 center_deg 为中心方向. 每枚的旋转角取
    "段首 + index * (弧角 + 缝) + 弧角 / 2", 于是每枚的局部中点正好落在自己弧段的中间.
    每条轮廓是左右两粒之一, 两者都已相对 O(原点就是弯曲圆心).
    """
    if spacing < 0:
        raise ValueError("spacing 不能为负")
    if count < 1:
        raise ValueError("count 至少为 1")
    left, right, arc_deg = _ear_on_circle(ear, radius)
    total_deg = count * arc_deg + (count - 1) * spacing
    start_deg = center_deg - total_deg / 2.0

    shapes: list[EarPolygon] = []
    for index in range(count):
        rotation = start_deg + index * (arc_deg + spacing) + arc_deg / 2.0
        shapes.append(rotate(left, rotation))
        shapes.append(rotate(right, rotation))
    return shapes, start_deg


def _mirror_vertical(shapes: list[EarPolygon]) -> list[EarPolygon]:
    """把一批轮廓沿过 O 的竖线(x = 0)镜像: 只把每个点的 x 取反, O 留在原地.

    为什么镜像轴必须过 O: 麦穗是绕 O 卷弯的圆弧, 只有圆心不动, 镜像后的弧
    才和原弧落在同一个圆上; 若轴不经过 O, 镜像出的弯曲圆心会跑到轴的另一侧.
    """
    return [mirror(shape, axis_x=0.0) for shape in shapes]


def _tip_olive(
    tip_deg: float,
    radius: float,
    spec: _OliveSpec,
    *,
    gap_deg: float,
    base_offset: float,
) -> OliveGeometry:
    """把一枚橄榄摆到穗尖外侧, 让上尖端压在半径 radius 的缝圆上、下尖端径向外偏.

    返回 (弦中点, 长, 厚, 朝向角), 坐标相对弯曲圆心 O.
    radius 是每枚麦穗内外两粒之间那道麦秆缝所在的圆(缝中线到 O 的距离).
    定位规则(参考图量测, 见 myama arrange._tip_olive):
    - 下尖端(靠穗尖那端): 角度 = tip_deg - gap_deg, 半径 = radius + base_offset;
    - 上尖端: 按设计仍压在缝圆上, 且到下尖端距离正好等于 spec.length, 所以取
      「以 O 为心、半径 radius 的圆」与「以下尖端为心、半径 length 的圆」的两个交点里
      角度更小(屏幕上更逆时针 / 远离穗尖)的那个;
    - 弦中点 = 两尖端中点, 朝向 = 下尖端 -> 上尖端.
    base_offset = 0 时两尖端都落在缝圆上, 退化成"长轴是缝圆的弦".
    """
    if radius <= 0:
        raise ValueError("radius 必须为正")
    base_deg = tip_deg - gap_deg
    base_radius = radius + base_offset
    if base_radius <= 0:
        raise ValueError("下尖端半径必须为正: base_offset 把尖端翻到了圆心另一侧")
    base_rad = math.radians(base_deg)
    base_x, base_y = base_radius * math.cos(base_rad), base_radius * math.sin(base_rad)

    # 两圆交点: 圆心连线上垂足距下尖端 along, 半弦高 across.
    center_distance = math.hypot(base_x, base_y)
    along = (
        center_distance * center_distance + spec.length * spec.length - radius * radius
    ) / (2.0 * center_distance)
    across_sq = spec.length * spec.length - along * along
    if across_sq <= 1e-9:
        raise ValueError("橄榄放不下: 以它为半径的圆与缝圆没有交点, 上尖端落不到缝圆上")
    across = math.sqrt(across_sq)
    toward_x, toward_y = -base_x / center_distance, -base_y / center_distance
    foot_x = base_x + along * toward_x
    foot_y = base_y + along * toward_y
    candidate_a = (foot_x + across * -toward_y, foot_y + across * toward_x)
    candidate_b = (foot_x - across * -toward_y, foot_y - across * toward_x)
    # 上尖端取角度更小的那个: 屏幕上角度增大是顺时针, 更小即沿圆逆时针、远离穗尖.
    far_x, far_y = min(
        (candidate_a, candidate_b),
        key=lambda point: math.atan2(point[1], point[0]),
    )
    center = ((base_x + far_x) / 2.0, (base_y + far_y) / 2.0)
    heading = math.degrees(math.atan2(far_y - base_y, far_x - base_x))
    return center, spec.length, spec.thickness, heading


def _mirrored_geometry(
    ear: _EarSpec,
    *,
    radius: float,
    spacing: float,
    center_deg: float,
    count: int,
    tip_olive: _OliveSpec | None,
    tip_olive_gap_deg: float,
    tip_olive_base_offset: float,
) -> tuple[list[EarPolygon], list[OliveGeometry], float]:
    """返回「原排列 + 竖直镜像」的几何(坐标相对 O, 未平移): (轮廓, 橄榄, 弧段起点角).

    橄榄每项是 (弦中点, 长, 厚, 朝向角); 镜像那枚只需弦中点 x 取反、朝向角取
    180° - heading —— 透镜形关于自己的长轴对称, 所以不用重算两段弧,
    也不会镜像出方向相反的怪形状.
    第三个返回值是原排列的弧段起点角(右侧穗尖所在端), 三道芒按它定位终点.
    """
    shapes, start_deg = _arranged_outlines(
        ear,
        radius=radius,
        spacing=spacing,
        center_deg=center_deg,
        count=count,
    )
    olive_geoms: list[OliveGeometry] = []
    if tip_olive is not None:
        center, length, thickness, heading = _tip_olive(
            start_deg,
            radius,
            tip_olive,
            gap_deg=tip_olive_gap_deg,
            base_offset=tip_olive_base_offset,
        )
        olive_geoms.append((center, length, thickness, heading))
        olive_geoms.append(((-center[0], center[1]), length, thickness, 180.0 - heading))
    return shapes + _mirror_vertical(shapes), olive_geoms, start_deg


# --------------------------------------------------------------------------- #
# 芒: 径向范围 -> 中心线半径 -> 圆弧参数
# --------------------------------------------------------------------------- #

def _ear_radial_range(shapes: list[EarPolygon]) -> tuple[float, float]:
    """麦穗轮廓到 O 的距离范围, 即麦穗内侧边 / 外侧边的半径 (r_inner, r_outer).

    麦穗是按「到 O 的距离 = radius + x'」卷出来的, 所以轮廓上每点到 O 的距离
    就是它原来所在竖直线到弯曲圆心的距离; 取所有轮廓点的最小 / 最大即两条边.
    """
    radii = [math.hypot(x, y) for shape in shapes for x, y in shape]
    return min(radii), max(radii)


def _olive_tip_angles(geometry: OliveGeometry) -> tuple[float, float]:
    """一枚橄榄两个尖端相对 O 的角度(度): 返回 (远端角, 近端角), 远端更靠左上.

    几何是 (弦中点, 长, 厚, 朝向角); 两个尖端 = 弦中点 ± (长/2) * 朝向单位向量.
    上尖端(远端)按设计压在缝圆上, 中间那道芒就收在它上面.
    """
    center, length, _thickness, heading = geometry
    unit_x = math.cos(math.radians(heading))
    unit_y = math.sin(math.radians(heading))
    half = length / 2.0
    angles = sorted(
        math.degrees(
            math.atan2(
                center[1] + sign * half * unit_y,
                center[0] + sign * half * unit_x,
            )
        )
        for sign in (-1, 1)
    )
    return angles[0], angles[1]


def _mirror_arc_spec(spec: _ArcSpec) -> _ArcSpec:
    """把一道芒沿过 O 的竖线(x = 0)镜像成另一道, 半径、线宽、角跨度都不变.

    镜像把点的 x 取反, 对角度就是 θ -> 180° - θ; 原弧从 start 扫到 end,
    镜像后从 180° - end 扫到 180° - start(仍是角度增大方向),
    所以新 spec 的 end_deg = 180° - (end_deg - span_deg).
    """
    start_deg = spec.end_deg - spec.span_deg
    return _ArcSpec(
        f"镜像{spec.name}",
        spec.radial_ratio,
        end_deg=180.0 - start_deg,
        span_deg=spec.span_deg,
    )


def _arc_center_radius(
    radial_ratio: float,
    r_inner: float,
    r_outer: float,
    width: float,
) -> float:
    """把径向比例换成芒的中心线半径.

    ratio = 0 取 r_inner + width/2(线内侧边正好等于 r_inner);
    ratio = 1 取 r_outer - width/2(线外侧边正好等于 r_outer);
    中间线性插值, ratio = 0.5 正好落在内外侧边正中间.
    """
    if not 0.0 <= radial_ratio <= 1.0:
        raise ValueError("radial_ratio 必须在 [0, 1] 之内")
    inner_center = r_inner + width / 2.0
    outer_center = r_outer - width / 2.0
    if inner_center > outer_center:
        raise ValueError("芒的线宽超过了麦穗的径向厚度")
    return inner_center + radial_ratio * (outer_center - inner_center)


# --------------------------------------------------------------------------- #
# 几何组装与图元输出
# --------------------------------------------------------------------------- #

def wreath_geometry() -> dict:
    """按 constants.py 组装花环几何, 坐标以 O 为原点(y 向下, 角度顺时针为正).

    返回 dict:
    - "shapes": 12 条麦粒轮廓 = 6 枚麦穗 x 2 粒(原排列 3 枚 + 竖直镜像 3 枚);
    - "olives": 2 枚顶端橄榄, 每项是 (弦中点, 长, 厚, 朝向角);
    - "arc_specs": 右半边三道芒的参数(左半边由 _mirror_arc_spec 镜像, 不在这里);
    - "start_deg": 原排列的弧段起点角(右侧穗尖所在端);
    - "r_inner" / "r_outer": 麦穗轮廓到 O 的径向范围(内侧边 / 外侧边半径).
    为什么单独暴露几何: 拼装时要的是「O = 原点」的原始几何(不要画布平移),
    与 wreath_elements() 共用同一套参数与同一份计算.
    """
    ear = _ear_spec()
    tip_olive = _OliveSpec(
        length=c.TIP_OLIVE_LENGTH,
        thickness=c.TIP_OLIVE_THICKNESS,
    )
    shapes, olive_geoms, start_deg = _mirrored_geometry(
        ear,
        radius=c.RADIUS,
        spacing=c.SPACING,
        center_deg=c.MIRRORED_CENTER_DEG,
        count=c.COUNT,
        tip_olive=tip_olive,
        tip_olive_gap_deg=c.TIP_OLIVE_GAP_DEG,
        tip_olive_base_offset=c.TIP_OLIVE_BASE_OFFSET,
    )
    r_inner, r_outer = _ear_radial_range(shapes)
    # 右侧那半边的橄榄 = 弦中点 x 为正的一枚; 中间芒收在它离穗尖更远的那一端
    # (上尖端, 该端按设计压在缝圆上)
    right_olive = max(olive_geoms, key=lambda geometry: geometry[0][0])
    far_tip_deg, _ = _olive_tip_angles(right_olive)

    # 每道芒的"长度"就是 span_deg, 终点默认收在尖端上:
    # 内 / 外侧芒收在右侧穗尖(start_deg), 中间芒收在橄榄上尖端(far_tip_deg);
    # END_OFFSET 是终点相对尖端的角度偏移. 收在尖端的那一端再延长
    # ARC_END_INSERT_DEG, 把圆头端点埋进白色图形里; end_deg 与 span_deg 同时加,
    # start_deg = end_deg - span_deg 保持不变, 所以自由端不动.
    insert_deg = c.ARC_END_INSERT_DEG
    arc_specs = [
        _ArcSpec(
            "内侧弧",
            c.ARC_INNER_RATIO,
            end_deg=start_deg + c.ARC_INNER_END_OFFSET_DEG + insert_deg,
            span_deg=c.ARC_INNER_SPAN_DEG + insert_deg,
        ),
        _ArcSpec(
            "中间弧",
            c.ARC_MIDDLE_RATIO,
            end_deg=far_tip_deg + c.ARC_MIDDLE_END_OFFSET_DEG + insert_deg,
            span_deg=c.ARC_MIDDLE_SPAN_DEG + insert_deg,
        ),
        _ArcSpec(
            "外侧弧",
            c.ARC_OUTER_RATIO,
            end_deg=start_deg + c.ARC_OUTER_END_OFFSET_DEG + insert_deg,
            span_deg=c.ARC_OUTER_SPAN_DEG + insert_deg,
        ),
    ]
    return {
        "shapes": shapes,
        "olives": olive_geoms,
        "arc_specs": arc_specs,
        "start_deg": start_deg,
        "r_inner": r_inner,
        "r_outer": r_outer,
    }


def wreath_elements() -> list[Element]:
    """返回花环的全部 svgkit 图元: 12 粒麦子 Polygon + 2 枚橄榄 Path + 6 道芒 Path.

    坐标是设计单位、原点 O、y 向下; 颜色统一白(c.EMBLEM_WHITE), 芒只描边不填充.
    层序与 myama 一致: 麦粒在下, 橄榄其次, 芒在最上层, 端点压在穗尖 / 橄榄尖上.

    为什么每粒麦子一个 <polygon>, 而不是把两粒并成一个:
        两粒轮廓的绕向相反(镜像生成), 硬接成一个多边形会得到自接触的顶点列;
        虽然 nonzero 填充规则下两块都实心、缝隙不可见, 但自接触多边形在编辑器里
        容易产生歧义, 也不利于单独选中/改色. 每粒一个简单多边形最稳.
    """
    geometry = wreath_geometry()
    shapes = geometry["shapes"]
    olive_geoms = geometry["olives"]
    arc_specs = geometry["arc_specs"]
    r_inner = geometry["r_inner"]
    r_outer = geometry["r_outer"]

    elements: list[Element] = [
        Polygon(points, fill=c.EMBLEM_WHITE) for points in shapes
    ]

    elements.extend(
        Path(
            lens_path_d(
                center,
                length=length,
                thickness=thickness,
                heading_deg=heading,
            ),
            fill=c.EMBLEM_WHITE,
        )
        for center, length, thickness, heading in olive_geoms
    )

    drawing_specs = list(arc_specs) + [_mirror_arc_spec(spec) for spec in arc_specs]
    elements.extend(
        Path(
            arc_path_d(
                0.0,
                0.0,
                _arc_center_radius(
                    spec.radial_ratio, r_inner, r_outer, c.ARC_WIDTH
                ),
                spec.end_deg - spec.span_deg,
                spec.end_deg,
            ),
            fill="none",
            stroke=c.EMBLEM_WHITE,
            stroke_width=c.ARC_WIDTH,
            stroke_linecap="round",
        )
        for spec in drawing_specs
    )
    return elements
