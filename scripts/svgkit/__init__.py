#!/usr/bin/env python3
"""svgkit: 几何优先的 SVG 构建小库(纯标准库).

是什么:
    把"用简单几何图元拼 SVG"需要的东西收在一起:
    - doc.Svg            文档根(width/height/viewBox/save);
    - shapes.*           Rect / Circle / Ellipse / Line / Polyline / Polygon / Path / Text /
                         Group / Defs / RadialGradient / LinearGradient / Stop;
    - geom.*             点列变换(平移/旋转/镜像/缩放)、圆弧采样与 A 命令、正多边形/星形/透镜形配方;
    - serialize.*        确定性数字格式、XML 转义、属性拼装.

为什么:
    直接写 SVG 字符串最容易滑向"所有图形都塞进一条 path"和"数字格式随手 str()";
    这里用元素类声明图形类型(rect / circle / polygon ...), 用公式生成派生几何,
    用固定格式保证同一份参数重复生成时输出逐字节一致.
    只有真曲线(圆弧、贝塞尔)或需要 fill-rule 的复合轮廓才用 Path.

典型用法:
    from svgkit import Svg, Polygon
    from svgkit.geom import regular_star
    Svg(512, 512).add(
        Polygon(regular_star(256, 256, 200, 80, 5), fill="#ff1010")
    ).save("star.svg")

元信息: 2026-11-12.
"""

from .doc import Svg
from .geom import (
    angle_point,
    arc_path_d,
    arc_points,
    bbox,
    centroid,
    circle_points,
    lens_path_d,
    mirror,
    points_text,
    regular_polygon,
    regular_star,
    rotate,
    rotate_transform,
    scale,
    scale_transform,
    translate,
    translate_transform,
)
from .serialize import fmt
from .shapes import (
    Circle,
    Defs,
    Ellipse,
    Element,
    Group,
    Line,
    LinearGradient,
    Path,
    Polygon,
    Polyline,
    RadialGradient,
    Rect,
    Stop,
    Text,
)

__all__ = [
    "Svg",
    "Element",
    "Group",
    "Defs",
    "Rect",
    "Circle",
    "Ellipse",
    "Line",
    "Polyline",
    "Polygon",
    "Path",
    "Text",
    "Stop",
    "RadialGradient",
    "LinearGradient",
    "fmt",
    "angle_point",
    "arc_path_d",
    "arc_points",
    "bbox",
    "centroid",
    "circle_points",
    "lens_path_d",
    "mirror",
    "points_text",
    "regular_polygon",
    "regular_star",
    "rotate",
    "rotate_transform",
    "scale",
    "scale_transform",
    "translate",
    "translate_transform",
]
