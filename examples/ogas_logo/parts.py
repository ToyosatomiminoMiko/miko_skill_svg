#!/usr/bin/env python3
"""45° 网格上的 chevron: 用两根等腰梯形臂拼出 V 形/箭头形.

是什么:
    chevron(apex, rot_deg, leg, reach, gap) -> list[list[(x, y)]], 每个内层列表是
    一块闭合多边形的点列(局部设计坐标, 已旋转并平移到 apex)。

为什么:
    - 目标图里的每一块都是“等腰梯形, 底角 45°”: 梯形的两条腰一条平行、一条垂直
      于 chevron 的对称轴, 两条底边都在 45° 方向上。于是不需要自由多边形,
      (顶点, 朝向, 臂厚, 顶点到末端面的距离, 两臂缝隙) 五个参数就唯一确定一根臂;
    - 两根臂共用同一个顶点: gap > 0(白色外圈, 2px 折缝)时输出两块独立梯形;
      gap == 0(彩色内圈)时两臂沿对称轴贴合, 直接输出合成后的 6 点 V 形,
      避免拼缝处出现半像素细线;
    - 4 个外圈 chevron 严格是同一个几何旋转 90° 得到的, 内圈靠各自 (顶点, 朝向)
      摆放; 所以整张图只有 11 个多边形, 全部可单独选中、改色、改参数。

坐标系:
    - 局部坐标先按“chevron 指向上(-y)、对称轴是 y 轴”定义, 再绕原点旋转 rot_deg、
      平移 apex 落位;
    - 角度约定沿用 svgkit.geom: 0° = 指向上(N), 增大 = 屏幕顺时针, 右(E)=90,
      下(S)=180, 左(W)=270; 对角线用 -45(西北)。
    - leg = 臂厚 * sqrt(2), 即端面斜切边长(梯形的两条腰);
      reach = 顶点沿对称轴到臂末端面的距离(轴向距离, 不是臂长)。

单根臂的 4 个角(局部坐标, side = -1 左臂 / +1 右臂):
    V1 = (side*gap/2,        gap/2)          顶点侧端面 × 外侧底边
    V2 = (side*gap/2,        gap/2 + leg)    顶点侧端面 × 内侧底边
    V3 = (side*(reach-leg),  reach)          末端面 × 内侧底边
    V4 = (side*reach,        reach)          末端面 × 外侧底边
两条腰(顶点侧端面、末端面)分别平行/垂直于对称轴, 与 45° 的底边成 45° 角。

元信息: 作者 Haojiren Galactic, 2026-11-12。
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from svgkit.geom import rotate, translate  # noqa: E402

Point = tuple[float, float]


def arm_points(side: int, leg: float, reach: float, gap: float) -> list[Point]:
    """一根臂的 4 个角(局部坐标, chevron 指向上).

    是什么: 一根等腰梯形臂的闭合点列, side=-1 左臂, side=+1 右臂。
    为什么: V1/V2 在顶点侧端面上, V3/V4 在末端面上; 顶点侧端面偏移 gap/2
            就留出了两臂之间的折缝, 所以缝隙不用另外处理。
    """
    half = gap / 2.0
    return [
        (side * half, half),
        (side * half, half + leg),
        (side * (reach - leg), reach),
        (side * reach, reach),
    ]


def union_points(leg: float, reach: float) -> list[Point]:
    """gap == 0 时两根臂贴合后的合成轮廓(6 点 V 形, 局部坐标).

    是什么: 顶点(0, 0) → 右臂外底 → 右臂末端面 → 右臂内底 → 左臂内底 →
            左臂末端面 → 左臂外底, 逆时针闭合。
    为什么: 两臂沿对称轴共边, 分开画会在共边处露出抗锯齿细线; 合成一个多边形
            对渲染器和后续编辑都更干净。
    """
    return [
        (-reach, reach),
        (0.0, 0.0),
        (reach, reach),
        (reach - leg, reach),
        (0.0, leg),
        (leg - reach, reach),
    ]


def chevron(
    apex: Point,
    rot_deg: float,
    leg: float,
    reach: float,
    gap: float = 0.0,
) -> list[list[Point]]:
    """生成一个 chevron 的多边形点列列表(已落位到 apex)。

    是什么: gap > 0 返回两根独立臂 [[..., 4 点], [..., 4 点]];
            gap == 0 返回一个合成 V 形 [[..., 6 点]]。
    为什么: 调用方直接把返回的每个点列塞给 Polygon, 不必关心旋转/镜像细节。
    """
    if gap > 0:
        shapes = [arm_points(-1, leg, reach, gap), arm_points(1, leg, reach, gap)]
    else:
        shapes = [union_points(leg, reach)]
    placed: list[list[Point]] = []
    for shape in shapes:
        rotated = rotate(shape, rot_deg)
        placed.append(translate(rotated, apex[0], apex[1]))
    return placed
