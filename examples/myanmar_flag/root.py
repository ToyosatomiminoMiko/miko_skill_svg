#!/usr/bin/env python3
"""根系部件: 旗徽底部两根相交的笔锋状枝棒 + 中间圆角矩形结.

是什么:
    移植自 myama 的 `miko_wiki_resource/parts/root.py`:
    - 枝棒拆成长端/短端两段"臂", 每段是一条笔锋(中心线弯曲、粗细非线性变化、末端按
      形状常量收笔). 长端是捺(收窄 + 平端面), 短端是撇(半圆头);
    - 第二根棒 = 第一根关于"过结中心的竖线"的镜像;
    - 结 = 长 ROOT_KNOT_LENGTH、厚 ROOT_KNOT_THICKNESS、四角半径
      ROOT_KNOT_CORNER_RADIUS 的圆角矩形, 按 ROOT_KNOT_ANGLE_DEG 摆放;
    - 结端与臂外侧边的四个"凹坑"用一段与两边都相切的三次贝塞尔填平(填坑多边形).
    参数全部来自本目录 constants.py 的"根/结"一节; 坐标原点 = 结中心, y 向下, 设计单位.

    导出 `root_elements()`: 四个枝棒多边形(长/短臂各一 + 各自镜像) + 一个
    `<rect rx>`(结) + 四个填坑多边形, 统一白色填充.

为什么(以下几条是 myama 的原设计理由, 移植时保留):
    - 镜像轴必须过结中心: 两根棒是同一根棒的两个镜像, 交点才会正落在结中心上;
      轴放在别处, 镜像出来的那根和原来的不会在结上相交, 整个 X 就散了;
    - 棒的侧边不能用直线: 参考图里长端外侧在圆头前略鼓、根部向交点收窄, 中心线还带
      一点弯, 是笔锋而不是"由细到粗的圆锥"; 中心线用二次贝塞尔, 粗细用
      (1-s)*交点厚 + s*端头厚 + 鼓肚*4s(1-s);
    - 两段臂各自建多边形、同色填充取并集: 交点处的缺口/搭接由不透明并集自然形成,
      不需要布尔运算; 交点在结内部, 两段臂在交点处的平口被结盖住, 看不到接缝;
    - 结用真正的 `<rect rx>`: myama 原先采样成圆角矩形点列, 这里按技能契约改为图元;
      结是独立元素叠在棒上面, 不做布尔合并;
    - 结端凹坑必须填掉: 结比臂厚, 结端收圆处和臂的外侧边相交会形成尖锐凹坑;
      填坑用"与臂边、结边都相切的三次贝塞尔"补齐, 而不是削角(见 junction_fillet);
    - 长度不对称(长端约 203 / 短端约 160): 交点不在棒的中点, 这是从目标图量出来的,
      不要为了"好看"强行对称, 否则两端尖会和目标错开约 10px;
    - 短端(撇的细尖)端头用半圆: 放大到像素级是圆的, 不是平切也不是尖头;
    - 长端(捺)端头不用半圆: 先按 TIP_LEN 收窄、按 TIP_FACE 收到较窄的端面, 再用三次
      贝塞尔样条收口(TIP_CAP_ELONGATION=0.5 时端面接近平的收笔);
    - 长端底边再用平滑 min 压平一句是楷书"捺"的脚: 末尾底部走平, 不是圆头收口.

元信息: 2026-11-12; 移植自 myama parts/root.py, 点列公式未改动.
        相对 myama 的改动: 去掉供拟合用的 overrides 参数、去掉结的采样点列(改用 Rect).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from svgkit import Element, Polygon, Rect  # noqa: E402  (先补好 sys.path 再导入 svgkit)
from svgkit.geom import rotate_transform  # noqa: E402

import constants as c  # noqa: E402

Point = tuple[float, float]

# 四块主体与四块填坑的键名(与 myama 相同的稳定英文名).
ROD_LONG_NAME = "rod-long"
ROD_SHORT_NAME = "rod-short"
ROD_LONG_MIRROR_NAME = "rod-long-mirror"
ROD_SHORT_MIRROR_NAME = "rod-short-mirror"
FILLET_TOP_LEFT_NAME = "fillet-top-left"
FILLET_TOP_RIGHT_NAME = "fillet-top-right"
FILLET_BOTTOM_LEFT_NAME = "fillet-bottom-left"
FILLET_BOTTOM_RIGHT_NAME = "fillet-bottom-right"

# 本文件自己的形状风格常量(与 myama root.py 一致, 不参与拟合):
# 一段臂的侧边按弧长均匀取点、端头/收尖段单独取样; 段数按"放大 10 倍也看不出折线"取.
ARM_SIDE_SEGMENTS = 48
ARM_CAP_SEGMENTS = 24
ARM_TIP_SEGMENTS = 24
# 捺脚压平的平滑尺度(设计单位): 用 log-sum-exp 做平滑 min, 平底与侧边交角被倒圆.
FOOT_SOFTNESS = 0.9
# 结端凹坑填平: FILLET_OUT 是从结端往外、沿臂方向多长开始起弧(越大肩部越宽越缓).
FILLET_OUT = 11.0
# 长端收尖端头的样条控制系数: 控制点沿切线伸出的距离 = 系数 * 端面半径.
# 0 = 完全平的端面, 4/3 ≈ 半圆, 取 0.5 = 端面基本平、只有很小的倒角.
TIP_CAP_ELONGATION = 0.5

# root_geometry 用到的参数名(顺序即 myama root.py 的参数顺序; 长/短指长端与短端).
ROOT_PARAM_NAMES = (
    "ROOT_ROD_ANGLE_DEG",
    "ROOT_ROD_LONG_LEN",
    "ROOT_ROD_SHORT_LEN",
    "ROOT_ROD_LONG_THICK",
    "ROOT_ROD_SHORT_THICK",
    "ROOT_ROD_CROSS_THICK",
    "ROOT_ROD_LONG_BOW",
    "ROOT_ROD_SHORT_BOW",
    "ROOT_ROD_LONG_SWELL",
    "ROOT_ROD_SHORT_SWELL",
    "ROOT_ROD_LONG_FOOT",
    "ROOT_ROD_LONG_TIP_LEN",
    "ROOT_ROD_LONG_TIP_FACE",
    "ROOT_CROSS_OFFSET_Y",
    "ROOT_KNOT_LENGTH",
    "ROOT_KNOT_THICKNESS",
    "ROOT_KNOT_ANGLE_DEG",
    "ROOT_KNOT_CORNER_RADIUS",
)


# --------------------------------------------------------------------------- #
# 向量与曲线小工具(逐行移植自 myama root.py)
# --------------------------------------------------------------------------- #

def _axes(angle_deg: float) -> tuple[Point, Point]:
    """返回沿 angle_deg 的单位向量 u 和它的法线 n(屏幕坐标, y 向下).

    u = (cos, sin); n = (-sin, cos) 是 u 逆时针转 90°(屏幕上看起来是朝"下侧").
    这里只用 u 定棒的方向, 用 n 把棒厚摊到两侧, 两个方向正交即可, 不区分正负.
    """
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return (cos_a, sin_a), (-sin_a, cos_a)


def _quadratic(p0: Point, p1: Point, p2: Point, s: float) -> Point:
    """二次贝塞尔在参数 s∈[0,1] 处的点(三个控制点都是 (x, y) 元组)."""
    w0 = (1.0 - s) ** 2
    w1 = 2.0 * (1.0 - s) * s
    w2 = s * s
    return (w0 * p0[0] + w1 * p1[0] + w2 * p2[0], w0 * p0[1] + w1 * p1[1] + w2 * p2[1])


def _quadratic_derivative(p0: Point, p1: Point, p2: Point, s: float) -> Point:
    """二次贝塞尔的导数(未归一化), 用来求切线方向."""
    return (
        2.0 * (1.0 - s) * (p1[0] - p0[0]) + 2.0 * s * (p2[0] - p1[0]),
        2.0 * (1.0 - s) * (p1[1] - p0[1]) + 2.0 * s * (p2[1] - p1[1]),
    )


def _unit(vec: Point) -> Point:
    """把二维向量归一化; 零向量返回 (1, 0), 避免拟合出退化参数时除零."""
    length = math.hypot(vec[0], vec[1])
    if length < 1e-12:
        return (1.0, 0.0)
    return (vec[0] / length, vec[1] / length)


def _smooth_min(a: float, b: float, softness: float) -> float:
    """返回 a、b 的平滑最小值(log-sum-exp): 比 min(a,b) 多出一个宽度约 softness 的圆角.

    为什么不用硬 min: 捺脚的下边缘用硬 min 会在"平底与斜边相交"处留下一个尖折点,
    放大后是折线而不是笔锋; softness 取 0.2 目标像素量级, 肉眼是圆角、量测上是亚像素.
    先减最大值再取指数, 避免 exp 上溢/下溢(a/b 是坐标量级, 直接 exp 会全是 0).
    """
    x = -a / softness
    y = -b / softness
    top = max(x, y)
    return -softness * (top + math.log(math.exp(x - top) + math.exp(y - top)))


def _smoothstep(t: float) -> float:
    """三次 smoothstep: t²(3-2t); 两端导数为 0, 用来让"收尖"的宽度变化在两端都平滑."""
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _bezier3(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    """三次贝塞尔在参数 t 处的点."""
    a = (1.0 - t) ** 3
    b = 3.0 * (1.0 - t) ** 2 * t
    c = 3.0 * (1.0 - t) * t * t
    d = t**3
    return (
        a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
        a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
    )


def _interp_y(points: list[Point], x: float) -> float | None:
    """在折线上按 x 线性插值 y; x 超出折线范围时返回 None."""
    for index in range(len(points) - 1):
        x0, y0 = points[index]
        x1, y1 = points[index + 1]
        if x0 == x1:
            continue
        if (x0 - x) * (x1 - x) <= 0.0:
            return y0 + (x - x0) / (x1 - x0) * (y1 - y0)
    return None


# --------------------------------------------------------------------------- #
# 枝棒轮廓
# --------------------------------------------------------------------------- #

def arm_outline(
    crossing: Point,
    tip: Point,
    cross_thick: float,
    end_thick: float,
    bow: float,
    swell: float,
    foot: float = 0.0,
    tip_len: float = 0.0,
    tip_face: float = 0.0,
) -> tuple[list[Point], list[Point]]:
    """返回 (一段臂的闭合轮廓, 外侧边点列); 点列都是设计单位, 外侧边从交点走到端头.

    几何:
        - 弦方向 u = (tip - crossing) 归一化, 法线 n 是 u 逆时针转 90°(屏幕 y 向下);
        - 主体中心线 = 二次贝塞尔: 起点 K, 终点 C(收尖段的起点), 控制点 = 弦中点 + bow*n;
          bow > 0 往 n 一侧鼓, 负值往另一侧;
        - 主体粗细(全宽): b(s) = (1-s)*cross_thick + s*end_thick + swell*4s(1-s),
          s = 0 在 K, s = 1 在 C; 中段 4s(1-s) 项就是非线性收放(鼓肚);
        - 收尖段(tip_len > 0 时, 只给长端): 中心线沿 C 点切线再走 tip_len 到 E,
          宽度用 smoothstep 从 end_thick 收成 tip_face, 侧边因此是样条曲线而不是直线;
        - 端头: 收尖时用一段三次贝塞尔样条(起点/终点在两侧边端, 控制点沿切线伸出),
          不再是圆弧; 不收尖时(短端)仍是半径 end_thick/2 的半圆帽;
        - 轮廓顺序: K 出发沿 +n 侧 -> 收尖段 -> 端头 -> -n 侧回到 K,
          最后在 K 处直边闭合(这条直边埋在结里, 看不见).
        - 外侧边点列(返回值第二项)就是"-n 侧"从 K 到端头的顺序点列, 供填坑取切线.

    foot > 0 时(只给长端用): 取轮廓下侧距尖端 foot 处的高度 y_flat, 再把整块轮廓的 y
    用平滑 min 压到 y_flat 以下: 尖端下侧变成"平底 + 样条过渡"的捺脚, 平底长度由 foot
    控制; 上侧边完全不动.
    """
    dx, dy = tip[0] - crossing[0], tip[1] - crossing[1]
    u = _unit((dx, dy))
    n = (-u[1], u[0])

    if tip_len > 0.0 and tip_face > 0.0:
        face_radius = tip_face / 2.0
        # 端头样条沿切线伸出的长度: 三次贝塞尔两端控制点各伸出 cap_reach 时, 曲线最外点
        # = 0.75*cap_reach.
        cap_reach = TIP_CAP_ELONGATION * face_radius
        extreme_len = 0.75 * cap_reach
        # 先按弦方向把"收尖段 + 端头"的总长从尖端往回收, 得到 C; 再按 C 点的真实切线走,
        # 避免收尖段接在贝塞尔末端时出现折角(拟合出的 bow 会让末端切线偏离弦方向约 2°).
        reach = tip_len + extreme_len
        c_guess = (tip[0] - reach * u[0], tip[1] - reach * u[1])
        control = (
            (crossing[0] + c_guess[0]) / 2.0 + bow * n[0],
            (crossing[1] + c_guess[1]) / 2.0 + bow * n[1],
        )
        c_point = c_guess
        body_tangent = _unit(_quadratic_derivative(crossing, control, c_point, 1.0))
        # 用真实切线重放一次 C, 让收尖段顺着主体末端方向, 不产生折角
        c_point = (
            tip[0] - (tip_len + extreme_len) * body_tangent[0],
            tip[1] - (tip_len + extreme_len) * body_tangent[1],
        )
        control = (
            (crossing[0] + c_point[0]) / 2.0 + bow * n[0],
            (crossing[1] + c_point[1]) / 2.0 + bow * n[1],
        )
        body_tangent = _unit(_quadratic_derivative(crossing, control, c_point, 1.0))
        end_center = (
            c_point[0] + tip_len * body_tangent[0],
            c_point[1] + tip_len * body_tangent[1],
        )
        end_normal = (-body_tangent[1], body_tangent[0])

        left: list[Point] = []
        right: list[Point] = []
        for index in range(ARM_SIDE_SEGMENTS + 1):
            s = index / ARM_SIDE_SEGMENTS
            px, py = _quadratic(crossing, control, c_point, s)
            tangent = _unit(_quadratic_derivative(crossing, control, c_point, s))
            nx, ny = -tangent[1], tangent[0]
            half = (
                (1.0 - s) * cross_thick + s * end_thick + swell * 4.0 * s * (1.0 - s)
            ) / 2.0
            left.append((px + nx * half, py + ny * half))
            right.append((px - nx * half, py - ny * half))
        # 收尖段: 中心线直走, 宽度按 smoothstep 从 end_thick 收到 tip_face
        for index in range(1, ARM_TIP_SEGMENTS + 1):
            t = index / ARM_TIP_SEGMENTS
            px = c_point[0] + tip_len * t * body_tangent[0]
            py = c_point[1] + tip_len * t * body_tangent[1]
            half = (end_thick + (tip_face - end_thick) * _smoothstep(t)) / 2.0
            left.append((px + end_normal[0] * half, py + end_normal[1] * half))
            right.append((px - end_normal[0] * half, py - end_normal[1] * half))
        # 端头: 三次贝塞尔样条(不是圆). 起点 = +n 侧边端, 终点 = -n 侧边端,
        # 两个控制点都沿尖端切线方向伸出 cap_reach, 所以与两侧边在连接处切线连续.
        upper_end = (
            end_center[0] + end_normal[0] * face_radius,
            end_center[1] + end_normal[1] * face_radius,
        )
        lower_end = (
            end_center[0] - end_normal[0] * face_radius,
            end_center[1] - end_normal[1] * face_radius,
        )
        ctrl_upper = (
            upper_end[0] + body_tangent[0] * cap_reach,
            upper_end[1] + body_tangent[1] * cap_reach,
        )
        ctrl_lower = (
            lower_end[0] + body_tangent[0] * cap_reach,
            lower_end[1] + body_tangent[1] * cap_reach,
        )
        cap: list[Point] = []
        for index in range(1, ARM_CAP_SEGMENTS):
            t = index / ARM_CAP_SEGMENTS
            cap.append(
                (
                    (1 - t) ** 3 * upper_end[0]
                    + 3 * (1 - t) ** 2 * t * ctrl_upper[0]
                    + 3 * (1 - t) * t * t * ctrl_lower[0]
                    + t**3 * lower_end[0],
                    (1 - t) ** 3 * upper_end[1]
                    + 3 * (1 - t) ** 2 * t * ctrl_upper[1]
                    + 3 * (1 - t) * t * t * ctrl_lower[1]
                    + t**3 * lower_end[1],
                )
            )
        tip_extreme = (
            end_center[0] + extreme_len * body_tangent[0],
            end_center[1] + extreme_len * body_tangent[1],
        )
        points = left + cap + list(reversed(right))
        lower_side = list(reversed(right))  # K -> 端头下端, 也就是下侧轮廓
        # 下侧轮廓里找出距尖端点 foot 的点, 用它所在的高度作为平底线
        y_flat = None
        best_delta = None
        for px, py in lower_side:
            delta = abs(math.hypot(px - tip_extreme[0], py - tip_extreme[1]) - foot)
            if best_delta is None or delta < best_delta:
                best_delta, y_flat = delta, py
        if foot > 0.0 and y_flat is not None:
            points = [(x, _smooth_min(y, y_flat, FOOT_SOFTNESS)) for x, y in points]
        return points, right

    # ---- 没有收尖时的老路径: 整宽半圆帽(短端仍在用) ----
    control = (
        (crossing[0] + tip[0]) / 2.0 + bow * n[0],
        (crossing[1] + tip[1]) / 2.0 + bow * n[1],
    )
    tip_tangent = _unit(_quadratic_derivative(crossing, control, tip, 1.0))
    radius = end_thick / 2.0
    cap_center = (tip[0] - tip_tangent[0] * radius, tip[1] - tip_tangent[1] * radius)
    cap_control = (
        (crossing[0] + cap_center[0]) / 2.0 + bow * n[0],
        (crossing[1] + cap_center[1]) / 2.0 + bow * n[1],
    )
    cap_tangent = _unit(_quadratic_derivative(crossing, cap_control, cap_center, 1.0))

    left = []
    right = []
    for index in range(ARM_SIDE_SEGMENTS + 1):
        s = index / ARM_SIDE_SEGMENTS
        px, py = _quadratic(crossing, cap_control, cap_center, s)
        tangent = _unit(_quadratic_derivative(crossing, cap_control, cap_center, s))
        nx, ny = -tangent[1], tangent[0]
        half = (
            (1.0 - s) * cross_thick + s * end_thick + swell * 4.0 * s * (1.0 - s)
        ) / 2.0
        left.append((px + nx * half, py + ny * half))
        right.append((px - nx * half, py - ny * half))
    a0 = math.atan2(cap_tangent[1], cap_tangent[0])
    cap = []
    for index in range(1, ARM_CAP_SEGMENTS):
        angle = a0 + math.pi / 2.0 - math.pi * index / ARM_CAP_SEGMENTS
        cap.append(
            (cap_center[0] + radius * math.cos(angle), cap_center[1] + radius * math.sin(angle))
        )
    points = left + cap + list(reversed(right))
    if foot > 0.0:
        arm_length = math.hypot(
            cap_center[0] - crossing[0], cap_center[1] - crossing[1]
        )
        if arm_length > 1e-9:
            start_s = max(0.0, 1.0 - foot / arm_length)
            index = min(
                ARM_SIDE_SEGMENTS,
                max(0, int(round(start_s * ARM_SIDE_SEGMENTS))),
            )
            lower = right if max(p[1] for p in right) > max(p[1] for p in left) else left
            y_flat = lower[index][1]
            points = [(x, _smooth_min(y, y_flat, FOOT_SOFTNESS)) for x, y in points]
    return points, right


def mirror_points(points: list[Point], axis_x: float) -> list[Point]:
    """把点集关于竖直线 x = axis_x 镜像(x 取反, y 不变)."""
    return [(2.0 * axis_x - x, y) for x, y in points]


# --------------------------------------------------------------------------- #
# 结端填坑
# --------------------------------------------------------------------------- #

def junction_fillet(
    outer_side: list[Point],
    horizontal_dir: float,
    vertical_sign: float,
    half_length: float,
    half_thickness: float,
    corner_radius: float,
) -> list[Point] | None:
    """返回结端与臂交界处的一块"填坑"多边形(设计单位); 边界是一段三次贝塞尔.

    要解决的问题: 圆角矩形结比臂厚, 结端收圆的地方和臂的外侧边相交, 外轮廓会出现一个
    明显的凹坑; 直接贴着光栅图拟合会把这个凹坑画深, 放大后像被捏了一下.
    做法: 在结的平直段上取 B 点, 在臂的外侧边上取 A 点(都在原来白色的边界上), 用一段
    与两边相切的三次贝塞尔 A->B 替换掉凹坑边界; 多边形其余部分压进结/臂内部, 只露出
    这条样条, 所以是"填平"而不是"削角", 也不是固定半径的圆角.

    参数:
        outer_side: 臂的外侧边点列(从交点 K 到端头), 用来取 A 点和 A 处切线;
        horizontal_dir: 结相对该臂的方向(+1 = 结在 +x 侧, 即左臂; -1 = 右臂);
        vertical_sign: 外侧边的方向(+1 = 下侧/长臂, -1 = 上侧/短臂);
        half_length / half_thickness / corner_radius: 结的圆角矩形参数.
    返回 None 表示这段找不到可用的臂边(参数越界时跳过, 不崩).

    移植说明: myama 的签名里还有一个 knot 点列参数, 但函数体内从未使用
    (B 点按解析式放), 结改用 <rect rx> 后没有点列可传, 故删去.
    """
    x_a = -horizontal_dir * (half_length + FILLET_OUT)
    x_b = -horizontal_dir * (half_length - corner_radius)
    y_a = _interp_y(outer_side, x_a)
    if y_a is None:
        return None
    a = (x_a, y_a)
    b = (x_b, vertical_sign * half_thickness)
    # A 处切线: 沿着臂的外侧边朝结的方向
    y_a_next = _interp_y(outer_side, x_a + horizontal_dir * 2.0)
    if y_a_next is None:
        tangent_a = _unit((b[0] - a[0], b[1] - a[1]))
    else:
        tangent_a = _unit((horizontal_dir * 2.0, y_a_next - y_a))
    span = math.hypot(b[0] - a[0], b[1] - a[1])
    c1 = (a[0] + tangent_a[0] * 0.5 * span, a[1] + tangent_a[1] * 0.5 * span)
    c2 = (b[0] - horizontal_dir * 0.5 * span, b[1])
    samples = [_bezier3(a, c1, c2, b, index / 12.0) for index in range(1, 12)]
    # 多边形下半部分压进白色内部: B 侧到结中心线, A 侧到臂内部, 两点连线都在白区里
    b_low = (b[0], -vertical_sign * half_thickness * 0.5)
    a_low = (a[0], a[1] - vertical_sign * min(6.0, half_thickness * 0.5))
    return [a] + samples + [b, b_low, a_low]


# --------------------------------------------------------------------------- #
# 几何与图元
# --------------------------------------------------------------------------- #

def root_geometry() -> dict[str, list[Point]]:
    """返回枝棒/镜像枝棒/四块填坑的点列(原点 = 结中心, 设计单位).

    结不在返回值里: 它是真正的 <rect rx>, 由 `_knot_rect()` 生成.
    点列坐标与 myama root.py 的 root_geometry() 完全一致; 已去掉供拟合用的 overrides
    参数(技能例子不做参数拟合).
    """
    values = {name: float(getattr(c, name)) for name in ROOT_PARAM_NAMES}
    knot_center = (0.0, 0.0)
    crossing = (0.0, values["ROOT_CROSS_OFFSET_Y"])
    angle = values["ROOT_ROD_ANGLE_DEG"]
    u, _n = _axes(angle)
    long_tip = (
        crossing[0] - values["ROOT_ROD_LONG_LEN"] * u[0],
        crossing[1] - values["ROOT_ROD_LONG_LEN"] * u[1],
    )
    short_tip = (
        crossing[0] + values["ROOT_ROD_SHORT_LEN"] * u[0],
        crossing[1] + values["ROOT_ROD_SHORT_LEN"] * u[1],
    )
    rod_long, outer_long = arm_outline(
        crossing,
        long_tip,
        values["ROOT_ROD_CROSS_THICK"],
        values["ROOT_ROD_LONG_THICK"],
        values["ROOT_ROD_LONG_BOW"],
        values["ROOT_ROD_LONG_SWELL"],
        foot=values["ROOT_ROD_LONG_FOOT"],
        tip_len=values["ROOT_ROD_LONG_TIP_LEN"],
        tip_face=values["ROOT_ROD_LONG_TIP_FACE"],
    )
    rod_short, outer_short = arm_outline(
        crossing,
        short_tip,
        values["ROOT_ROD_CROSS_THICK"],
        values["ROOT_ROD_SHORT_THICK"],
        values["ROOT_ROD_SHORT_BOW"],
        values["ROOT_ROD_SHORT_SWELL"],
    )
    half_length = values["ROOT_KNOT_LENGTH"] / 2.0
    half_thickness = values["ROOT_KNOT_THICKNESS"] / 2.0
    corner_radius = values["ROOT_KNOT_CORNER_RADIUS"]
    geometry: dict[str, list[Point]] = {
        ROD_LONG_NAME: rod_long,
        ROD_SHORT_NAME: rod_short,
        ROD_LONG_MIRROR_NAME: mirror_points(rod_long, axis_x=knot_center[0]),
        ROD_SHORT_MIRROR_NAME: mirror_points(rod_short, axis_x=knot_center[0]),
    }
    # 结两端各有两个凹坑: 长臂外下侧一个, 短臂外上侧一个; 先算左半边的两块, 再镜像出右半边.
    bottom_left = junction_fillet(
        outer_long,
        horizontal_dir=1.0,
        vertical_sign=1.0,
        half_length=half_length,
        half_thickness=half_thickness,
        corner_radius=corner_radius,
    )
    top_right = junction_fillet(
        outer_short,
        horizontal_dir=-1.0,
        vertical_sign=-1.0,
        half_length=half_length,
        half_thickness=half_thickness,
        corner_radius=corner_radius,
    )
    for name, points, mirrored in (
        (FILLET_BOTTOM_LEFT_NAME, bottom_left, False),
        (FILLET_TOP_RIGHT_NAME, top_right, False),
        (FILLET_TOP_LEFT_NAME, top_right, True),
        (FILLET_BOTTOM_RIGHT_NAME, bottom_left, True),
    ):
        if points is None:
            continue
        geometry[name] = mirror_points(points, axis_x=knot_center[0]) if mirrored else points
    return geometry


def _knot_rect() -> Rect:
    """结: 真正的圆角矩形 <rect rx>, 居中于原点, 绕原点旋转 ROOT_KNOT_ANGLE_DEG.

    为什么不用点列多边形: 技能契约要求圆角矩形用 <rect rx ry> 表达, 圆角是精确圆弧;
    结作为独立元素叠在四块枝棒多边形上面, 不做布尔合并(同色, 视觉上就是并集).
    """
    half_length = c.ROOT_KNOT_LENGTH / 2.0
    half_thickness = c.ROOT_KNOT_THICKNESS / 2.0
    # 与 myama 的 rounded_rect_svg_element 相同: 角半径夹到短边/长边的一半以内, 防止自交.
    radius = max(0.0, min(c.ROOT_KNOT_CORNER_RADIUS, half_thickness, half_length))
    return Rect(
        -half_length,
        -half_thickness,
        c.ROOT_KNOT_LENGTH,
        c.ROOT_KNOT_THICKNESS,
        rx=radius,
        transform=rotate_transform(c.ROOT_KNOT_ANGLE_DEG),
        fill=c.EMBLEM_WHITE,
    )


def root_elements() -> list[Element]:
    """返回根系部件的图元: 四块枝棒多边形 + 结 <rect rx> + 四块填坑多边形.

    坐标: 结中心 = 原点, 设计单位, y 向下; 白色填充.
    绘制顺序与 myama 一致: 枝棒 -> 结 -> 填坑(同色, 顺序只影响可读性).
    """
    geometry = root_geometry()
    elements: list[Element] = [
        Polygon(geometry[name], fill=c.EMBLEM_WHITE)
        for name in (
            ROD_LONG_NAME,
            ROD_SHORT_NAME,
            ROD_LONG_MIRROR_NAME,
            ROD_SHORT_MIRROR_NAME,
        )
    ]
    elements.append(_knot_rect())
    elements.extend(
        Polygon(geometry[name], fill=c.EMBLEM_WHITE)
        for name in (
            FILLET_TOP_LEFT_NAME,
            FILLET_TOP_RIGHT_NAME,
            FILLET_BOTTOM_LEFT_NAME,
            FILLET_BOTTOM_RIGHT_NAME,
        )
        if name in geometry
    )
    return elements
