#!/usr/bin/env python3
"""拼装 MNTJP 党旗: 红底 + 白色花环 / 齿轮 / 结 / 国土轮廓, 输出 800x532 SVG.

是什么:
    - 四个部件模块(gear / map / root / wreath)各自输出"局部坐标系、设计单位"的图元;
    - 这里给每个部件套一层 <g transform="translate(原点) scale(1/SCALE)">, 落到 800x532
      旗面像素坐标上, 红底垫在最下面;
    - 默认写 assets/flag.svg(红底整旗)与 assets/emblem.svg(透明底部件层).

为什么:
    - 部件几何用设计单位(1 参考像素 = SCALE 设计单位): 部件可以独立预览/组合,
      拼旗面时只做平移+缩放, 不用把每个坐标都换算成旗面像素;
    - 原点偏移直接取自 constants.py 的拟合结果(齿轮/结/轮廓质心相对花环圆心 O),
      没有新的自由参数; PART_PIXEL_OFFSETS 是位图像素中心与 SVG 用户坐标的半像素修正;
    - 缩放写 6 位小数(而不是 4 位): 最外圈麦穗的芒对缩放更敏感, 4 位会让端点差 0.01px 量级;
    - 部件几何全部是简单图元(Polygon / Rect / 圆弧 path), 不用 mask、不用带洞的复合 path,
      打开后可以直接在编辑器里选中、拖动、改色.

用法:
    python3 build.py                 # 写 assets/flag.svg 与 assets/emblem.svg
    python3 build.py /tmp/out.svg    # 只写整旗到指定路径(透明底部件层不写)

元信息: 2026-11-12; 拼装规则移植自 myama 的 miko_wiki_resource/build/assemble.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
sys.path.insert(0, str(HERE))

import constants as c  # noqa: E402  (先补好 sys.path 再导入本地模块)
import gear  # noqa: E402
import map as map_part  # noqa: E402
import root  # noqa: E402
import wreath  # noqa: E402
from svgkit import Group, Rect, Svg, translate_transform  # noqa: E402

# 部件层顺序: 全部同色, 层序不影响并集, 只按"花环 -> 齿轮 -> 结 -> 国土"的可读顺序画.
PART_ORDER = ("wreath", "gear", "root", "map")

_PART_BUILDERS = {
    "wreath": wreath.wreath_elements,
    "gear": gear.gear_elements,
    "root": root.root_elements,
    "map": map_part.map_elements,
}


def part_origins() -> dict[str, tuple[float, float]]:
    """各部件局部原点在旗面像素坐标里的位置.

    是什么:
        花环原点就是 O; 齿轮/结/国土轮廓的原点相对 O 的偏移在 constants.py 里(设计单位),
        这里除以 SCALE 换成旗面像素, 再加各自的半像素修正.

    为什么:
        myama 拟合时, 花环/齿轮用"像素索引 = 中心"的 numpy 约定, 结/国土用
        "中心 = i+0.5" 的光栅化约定; 两种约定差半个像素, 所以要分开修正(实测值).
    """
    origins: dict[str, tuple[float, float]] = {}
    for name in PART_ORDER:
        offset_x, offset_y = c.PART_PIXEL_OFFSETS[name]
        origins[name] = (c.O_X_PX + offset_x, c.O_Y_PX + offset_y)

    gear_dx, gear_dy = c.PART_PIXEL_OFFSETS["gear"]
    origins["gear"] = (
        c.O_X_PX + gear_dx + c.GEAR_CENTER_OFFSET_X / c.SCALE,
        c.O_Y_PX + gear_dy + c.GEAR_CENTER_OFFSET_Y / c.SCALE,
    )
    root_dx, root_dy = c.PART_PIXEL_OFFSETS["root"]
    origins["root"] = (
        c.O_X_PX + root_dx + c.ROOT_CENTER_OFFSET_X / c.SCALE,
        c.O_Y_PX + root_dy + c.ROOT_CENTER_OFFSET_Y / c.SCALE,
    )
    map_dx, map_dy = c.PART_PIXEL_OFFSETS["map"]
    origins["map"] = (
        c.O_X_PX + map_dx + c.MAP_CENTER_OFFSET_X / c.SCALE,
        c.O_Y_PX + map_dy + c.MAP_CENTER_OFFSET_Y / c.SCALE,
    )
    return origins


def _group_transform(origin_x: float, origin_y: float) -> str:
    """部件组的变换: 先按 1/SCALE 缩到旗面像素, 再平移到原点(transform 从右往左作用)."""
    scale_text = f"{1.0 / c.SCALE:.6f}"
    return f"{translate_transform(origin_x, origin_y)} scale({scale_text})"


def build_svg(*, with_background: bool) -> Svg:
    """构造整旗(with_background=True)或透明底部件层(False)的 Svg 文档."""
    svg = Svg(c.FLAG_WIDTH_PX, c.FLAG_HEIGHT_PX)
    if with_background:
        svg.add(
            Rect(
                0,
                0,
                c.FLAG_WIDTH_PX,
                c.FLAG_HEIGHT_PX,
                fill=c.FLAG_RED,
                id="background",
            )
        )
    origins = part_origins()
    for name in PART_ORDER:
        origin_x, origin_y = origins[name]
        svg.add(
            Group(
                *_PART_BUILDERS[name](),
                id=name,
                fill=c.EMBLEM_WHITE,
                stroke="none",
                transform=_group_transform(origin_x, origin_y),
            )
        )
    return svg


def main() -> None:
    """命令行入口: 生成整旗(以及透明底部件层), 打印输出路径与部件原点."""
    if len(sys.argv) > 2:
        raise SystemExit("用法: python3 build.py [整旗输出路径]")
    if len(sys.argv) == 2:
        flag_path = build_svg(with_background=True).save(sys.argv[1])
        print(f"已生成 {flag_path} (整旗, {c.FLAG_WIDTH_PX}x{c.FLAG_HEIGHT_PX})")
        return

    flag_path = build_svg(with_background=True).save(SKILL_ROOT / "assets" / "flag.svg")
    emblem_path = build_svg(with_background=False).save(
        SKILL_ROOT / "assets" / "emblem.svg"
    )
    print(f"已生成 {flag_path} (整旗, {c.FLAG_WIDTH_PX}x{c.FLAG_HEIGHT_PX})")
    print(f"已生成 {emblem_path} (透明底部件层)")
    print(f"缩放: 1 设计单位 = 1/{c.SCALE:g} 旗面像素; 红底={c.FLAG_RED} 图形={c.EMBLEM_WHITE}")
    for name, (x, y) in part_origins().items():
        print(f"  {name:6s} 原点(旗面像素) = ({x:.3f}, {y:.3f})")


if __name__ == "__main__":
    main()
