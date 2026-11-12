#!/usr/bin/env python3
"""拼装 OGAS 徽标: 纯黑底 + 11 块 45° 等腰梯形, 输出 960x720 SVG.

是什么:
    - 外圈 4 个白色 chevron 由同一份几何(顶点朝上的 V)绕徽标中心每 90° 旋转生成;
    - 内圈 3 块彩色(绿 "Γ" / 蓝 "<" / 黄 "∧")按各自顶点与朝向落位;
    - 全部图元放进一个 <g transform="translate(CENTER)">, 坐标为“相对徽标中心”的
      局部设计坐标(1 单位 = 1 画布 px), 与参考位图像素一一对应。

为什么:
    - 用局部坐标 + 一次平移, 而不是把中心写死进每个点的坐标: 挪徽标只改 CENTER,
      参数文件保持可读;
    - 11 个 <polygon> 各自成元素、各自带 id, 没有 mask、没有复合 path、没有 style,
      打开后能逐块选中改色;
    - 每个 chevron 的两根臂是独立的等腰梯形(外圈留 2px 折缝), 内圈两臂贴合则合成
      一个 6 点 V 形, 避免拼缝处的抗锯齿细线。

用法:
    python3 build.py                  # 写 assets/ogas_logo.svg
    python3 build.py /tmp/ogas.svg    # 写到指定路径(例如放回位图旁边做对照)

元信息: 作者 Haojiren Galactic, 2026-11-12。
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
sys.path.insert(0, str(HERE))

import constants as c  # noqa: E402  (先补好 sys.path 再导入本地模块)
import parts  # noqa: E402
from svgkit import Group, Polygon, Rect, Svg, translate_transform  # noqa: E402
from svgkit.geom import angle_point  # noqa: E402

# 外圈 4 个 chevron: (名字, 顶点方位角(geom 约定: 0°=正右), chevron 朝向)
# geom 约定 0°=正右、顺时针为正; parts.chevron 约定 0°=正上、顺时针为正, 两者差 90°。
OUTER_CHEVRONS = (
    ("n", -90.0, 0.0),
    ("e", 0.0, 90.0),
    ("s", 90.0, 180.0),
    ("w", 180.0, 270.0),
)

# 内圈 3 块彩色图形: (名字, 顶点, 朝向, 臂厚*√2, 顶点到末端距离, 颜色)
INNER_SHAPES = (
    ("green", c.GREEN_APEX, c.GREEN_ROT, c.GREEN_LEG, c.GREEN_REACH, c.GREEN),
    ("blue", c.BLUE_APEX, c.BLUE_ROT, c.INNER_LEG, c.INNER_REACH, c.BLUE),
    ("yellow", c.YELLOW_APEX, c.YELLOW_ROT, c.INNER_LEG, c.INNER_REACH, c.YELLOW),
)


def outer_elements() -> list[Polygon]:
    """外圈 4 个白色 chevron 的多边形(局部坐标 = 相对徽标中心)."""
    elements: list[Polygon] = []
    for name, apex_deg, rot_deg in OUTER_CHEVRONS:
        apex = angle_point(0.0, 0.0, c.OUTER_RADIUS, apex_deg)
        arms = parts.chevron(apex, rot_deg, c.OUTER_LEG, c.OUTER_REACH, c.OUTER_GAP)
        for index, points in enumerate(arms):
            elements.append(Polygon(points, fill=c.WHITE, id=f"chevron-{name}-{index}"))
    return elements


def inner_elements() -> list[Polygon]:
    """内圈 3 块彩色图形的多边形(局部坐标 = 相对徽标中心)."""
    elements: list[Polygon] = []
    for name, apex, rot_deg, leg, reach, color in INNER_SHAPES:
        for index, points in enumerate(parts.chevron(apex, rot_deg, leg, reach)):
            suffix = "" if index == 0 else f"-{index}"
            elements.append(Polygon(points, fill=color, id=f"inner-{name}{suffix}"))
    return elements


def build_svg(*, with_background: bool = True) -> Svg:
    """构造徽标文档(默认带纯黑底; with_background=False 得到透明底图形层)."""
    width, height = c.CANVAS
    svg = Svg(width, height)
    if with_background:
        svg.add(Rect(0, 0, width, height, fill=c.BACKGROUND, id="background"))
    svg.add(
        Group(
            *outer_elements(),
            *inner_elements(),
            id="emblem",
            stroke="none",
            transform=translate_transform(*c.CENTER),
        )
    )
    return svg


def main() -> None:
    """命令行入口: 生成 SVG, 打印路径与图元统计."""
    if len(sys.argv) > 2:
        raise SystemExit("用法: python3 build.py [输出路径]")
    if len(sys.argv) == 2:
        out_path = Path(sys.argv[1])
    else:
        out_path = SKILL_ROOT / "assets" / "ogas_logo.svg"
    saved = build_svg().save(out_path)
    width, height = c.CANVAS
    polygons = len(outer_elements()) + len(inner_elements())
    print(f"已生成 {saved} ({width}x{height}, {polygons} 个 polygon, 背景 {c.BACKGROUND})")


if __name__ == "__main__":
    main()
