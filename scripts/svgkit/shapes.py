#!/usr/bin/env python3
"""SVG 元素对象: 每个类对应一个 SVG 元素, 统一属性顺序与自闭合写法.

是什么:
    - Element: 所有元素的公共底座(id / transform / fill / stroke / opacity / mask ...);
    - _Container: 带子元素的容器底座(子元素各占一行、缩进 2 空格);
    - Group / Defs: <g> 分组容器 / <defs> 定义容器(渐变、字体等"被引用"的内容);
    - 渐变: RadialGradient / LinearGradient 作容器装 Stop, 图元用 fill="url(#id)" 引用;
    - 几何元素: Rect / Circle / Ellipse / Line / Polyline / Polygon / Path / Text;
    - 每个元素在 render() 时输出一段文本, 子元素缩进 2 空格.

为什么:
    - 图元优先: 能用 <rect> / <circle> / <polygon> 表达的几何, 不要退化成 <path>
      里的手写坐标; 类名本身就是"这是什么形状"的声明, 后续改参数只动数值;
    - <path> 只留给真曲线(圆弧/贝塞尔): 直线多边形一律 <polygon>, 圆角矩形一律
      <rect rx ry>, 圆/椭圆一律 <circle> / <ellipse>;
    - 渐变/图案是 paint server: 定义放 <defs>, 图元只写 fill="url(#id)"; 不用滤镜
      模拟渐变(跨渲染器差异大、不可编辑);
    - 表现属性写成一等属性而不是 style="", Inkscape 和浏览器都能直接改;
    - 属性顺序固定: id -> 几何 -> transform -> 表现属性 -> 额外属性, 输出稳定可 diff;
    - 子元素缩进由 render(level) 传入, 不靠字符串替换, 嵌套层级清晰.

元信息: 2026-11-12.
"""

from __future__ import annotations

from .geom import points_text
from .serialize import attrs_text, escape_text, fmt

# 表现属性的固定输出顺序. 只写调用方显式给值的那几项, None 一律跳过.
_PRESENTATION_ORDER = (
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-opacity",
    "opacity",
    "mask",
    "clip-path",
)

# 字体相关属性的固定输出顺序(只用于 Text).
_FONT_ORDER = (
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-anchor",
    "letter-spacing",
)

_INDENT = "  "


class Element:
    """所有 SVG 元素的公共底座.

    是什么:
        保存 id / transform / 表现属性 / 额外属性, 并在 render() 里按固定顺序拼装;
        子类只需实现 _geometry_attributes() 返回自己的几何属性.

    为什么:
        把"属性顺序 + 转义 + 数字格式"收敛到一处, 新加图元不会各自发明一套写法.
    """

    TAG = ""

    def __init__(
        self,
        *,
        id: str | None = None,
        transform: str | None = None,
        attrs: dict[str, str] | None = None,
        fill: str | None = None,
        fill_opacity: float | None = None,
        fill_rule: str | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        stroke_linecap: str | None = None,
        stroke_linejoin: str | None = None,
        stroke_opacity: float | None = None,
        opacity: float | None = None,
        mask: str | None = None,
        clip_path: str | None = None,
    ) -> None:
        self.element_id = id
        self.transform = transform
        self.extra_attributes = dict(attrs or {})
        self._presentation = {
            "fill": fill,
            "fill-opacity": fill_opacity,
            "fill-rule": fill_rule,
            "stroke": stroke,
            "stroke-width": stroke_width,
            "stroke-linecap": stroke_linecap,
            "stroke-linejoin": stroke_linejoin,
            "stroke-opacity": stroke_opacity,
            "opacity": opacity,
            "mask": mask,
            "clip-path": clip_path,
        }

    # -- 子类覆盖点 --------------------------------------------------------- #

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        """返回本元素的几何属性(已格式化的字符串对)."""
        raise NotImplementedError

    def _style_attributes(self) -> list[tuple[str, str]]:
        """返回表现属性(已格式化的字符串对), 默认按固定顺序输出非 None 项."""
        return [
            (name, _format_number(self._presentation[name]))
            for name in _PRESENTATION_ORDER
            if self._presentation[name] is not None
        ]

    # -- 渲染 --------------------------------------------------------------- #

    def _attributes(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        if self.element_id:
            pairs.append(("id", self.element_id))
        pairs.extend(self._geometry_attributes())
        if self.transform:
            pairs.append(("transform", self.transform))
        pairs.extend(self._style_attributes())
        pairs.extend(self.extra_attributes.items())
        return pairs

    def render(self, level: int = 0) -> str:
        """输出一段以换行结尾的 SVG 文本."""
        pad = _INDENT * level
        return f"{pad}<{self.TAG}{attrs_text(self._attributes())}/>\n"

    def __str__(self) -> str:
        return self.render()


class _Container(Element):
    """带子元素的容器底座: 子元素各占一行, 缩进 2 空格.

    是什么:
        Group / Defs / RadialGradient / LinearGradient 的共同实现 ——
        开标签 + 子元素 + 闭标签.

    为什么:
        这四种容器的正文渲染规则完全一样(渐变的多个 <stop> 也是子元素), 抽一层
        避免各写一遍; 新容器只要给个 TAG 就能用.
    """

    def __init__(self, *children: Element, **style) -> None:
        super().__init__(**style)
        self.children: list[Element] = list(children)

    def add(self, *children: Element) -> "_Container":
        """追加子元素, 返回自身以便链式调用."""
        self.children.extend(children)
        return self

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return []

    def render(self, level: int = 0) -> str:
        pad = _INDENT * level
        opening = f"{pad}<{self.TAG}{attrs_text(self._attributes())}>\n"
        body = "".join(child.render(level + 1) for child in self.children)
        return f"{opening}{body}{pad}</{self.TAG}>\n"


class Group(_Container):
    """<g> 容器: 放一组子元素, 可以嵌套并带自己的 transform / 样式."""

    TAG = "g"


class Defs(_Container):
    """<defs>: 放"被引用而不直接绘制"的定义(渐变、图案、字体等).

    为什么需要:
        渐变/图案/字体定义放在 <defs> 里, 图元用 fill="url(#id)" 引用; 这样定义
        只写一份, 多个图元共用, 打开后也能在 Inkscape 里直接改色标.
    """

    TAG = "defs"


class Stop(Element):
    """<stop>: 渐变上的一个色标; offset 0~1, 颜色加可选不透明度.

    为什么单独成类:
        stop 的属性是 offset / stop-color / stop-opacity, 与几何图元的 fill/stroke
        不是一套; 写成 Element 子类比往 attrs 里塞字符串更好读、也保证数字格式.
    """

    TAG = "stop"

    def __init__(
        self,
        offset: float,
        color: str,
        *,
        opacity: float | None = None,
        **style,
    ) -> None:
        super().__init__(**style)
        self.offset = float(offset)
        self.color = color
        self.stop_opacity = opacity

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = [
            ("offset", fmt(self.offset)),
            ("stop-color", self.color),
        ]
        if self.stop_opacity is not None:
            pairs.append(("stop-opacity", _format_number(self.stop_opacity)))
        return pairs


class RadialGradient(_Container):
    """<radialGradient>: 径向渐变, 子元素是 Stop(offset 必须递增).

    坐标口径:
        gradient_units 省略(objectBoundingBox)时 cx/cy/r 写 0~1 的相对值;
        画布级背景用 gradient_units="userSpaceOnUse", 此时是画布用户单位(px).
        只给一部分参数也可以, 其余用 SVG 默认值(50% / 50% / 50%).
    """

    TAG = "radialGradient"

    def __init__(
        self,
        *stops: Stop,
        cx: float | str | None = None,
        cy: float | str | None = None,
        r: float | str | None = None,
        fx: float | str | None = None,
        fy: float | str | None = None,
        gradient_units: str | None = None,
        spread_method: str | None = None,
        **style,
    ) -> None:
        super().__init__(*stops, **style)
        self.cx, self.cy, self.r = cx, cy, r
        self.fx, self.fy = fx, fy
        self.gradient_units = gradient_units
        self.spread_method = spread_method

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for name, value in (
            ("cx", self.cx),
            ("cy", self.cy),
            ("r", self.r),
            ("fx", self.fx),
            ("fy", self.fy),
        ):
            if value is not None:
                pairs.append((name, _format_number(value)))
        for name, value in (
            ("gradientUnits", self.gradient_units),
            ("spreadMethod", self.spread_method),
        ):
            if value is not None:
                pairs.append((name, str(value)))
        return pairs


class LinearGradient(_Container):
    """<linearGradient>: 线性渐变, 子元素是 Stop(offset 必须递增)."""

    TAG = "linearGradient"

    def __init__(
        self,
        *stops: Stop,
        x1: float | str | None = None,
        y1: float | str | None = None,
        x2: float | str | None = None,
        y2: float | str | None = None,
        gradient_units: str | None = None,
        spread_method: str | None = None,
        **style,
    ) -> None:
        super().__init__(*stops, **style)
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.gradient_units = gradient_units
        self.spread_method = spread_method

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for name, value in (
            ("x1", self.x1),
            ("y1", self.y1),
            ("x2", self.x2),
            ("y2", self.y2),
        ):
            if value is not None:
                pairs.append((name, _format_number(value)))
        for name, value in (
            ("gradientUnits", self.gradient_units),
            ("spreadMethod", self.spread_method),
        ):
            if value is not None:
                pairs.append((name, str(value)))
        return pairs


class Rect(Element):
    """<rect>: 矩形或圆角矩形(rx/ry 控制圆角)."""

    TAG = "rect"

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        rx: float | None = None,
        ry: float | None = None,
        **style,
    ) -> None:
        super().__init__(**style)
        self.x, self.y = float(x), float(y)
        self.width, self.height = float(width), float(height)
        if rx is None and ry is not None:
            rx = ry
        if ry is None and rx is not None:
            ry = rx
        self.rx, self.ry = rx, ry

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        pairs = [
            ("x", fmt(self.x)),
            ("y", fmt(self.y)),
            ("width", fmt(self.width)),
            ("height", fmt(self.height)),
        ]
        if self.rx is not None:
            pairs.append(("rx", fmt(float(self.rx))))
        if self.ry is not None:
            pairs.append(("ry", fmt(float(self.ry))))
        return pairs


class Circle(Element):
    """<circle>."""

    TAG = "circle"

    def __init__(self, cx: float, cy: float, r: float, **style) -> None:
        super().__init__(**style)
        self.cx, self.cy, self.r = float(cx), float(cy), float(r)

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return [("cx", fmt(self.cx)), ("cy", fmt(self.cy)), ("r", fmt(self.r))]


class Ellipse(Element):
    """<ellipse>."""

    TAG = "ellipse"

    def __init__(self, cx: float, cy: float, rx: float, ry: float, **style) -> None:
        super().__init__(**style)
        self.cx, self.cy = float(cx), float(cy)
        self.rx, self.ry = float(rx), float(ry)

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return [
            ("cx", fmt(self.cx)),
            ("cy", fmt(self.cy)),
            ("rx", fmt(self.rx)),
            ("ry", fmt(self.ry)),
        ]


class Line(Element):
    """<line>."""

    TAG = "line"

    def __init__(self, x1: float, y1: float, x2: float, y2: float, **style) -> None:
        super().__init__(**style)
        self.x1, self.y1 = float(x1), float(y1)
        self.x2, self.y2 = float(x2), float(y2)

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return [
            ("x1", fmt(self.x1)),
            ("y1", fmt(self.y1)),
            ("x2", fmt(self.x2)),
            ("y2", fmt(self.y2)),
        ]


class Polyline(Element):
    """<polyline>: 不闭合的折线."""

    TAG = "polyline"

    def __init__(self, points: list[tuple[float, float]], **style) -> None:
        super().__init__(**style)
        self.points = [(float(x), float(y)) for x, y in points]

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return [("points", points_text(self.points))]


class Polygon(Element):
    """<polygon>: 闭合多边形(顶点自动首尾相连)."""

    TAG = "polygon"

    def __init__(self, points: list[tuple[float, float]], **style) -> None:
        super().__init__(**style)
        self.points = [(float(x), float(y)) for x, y in points]

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return [("points", points_text(self.points))]


class Path(Element):
    """<path>: 只放真曲线(圆弧 / 贝塞尔)或需要 fill-rule 的复合轮廓.

    为什么保留:
        直线多边形不该用 path, 但圆弧(A 命令)、两条弧围成的透镜形、以及需要
        fill-rule="evenodd" 挖洞的复合轮廓只能由 path 表达.
    """

    TAG = "path"

    def __init__(self, d: str, **style) -> None:
        super().__init__(**style)
        self.d = d

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return [("d", self.d)]


class Text(Element):
    """<text>: 文本节点; 字宽由渲染器决定, 不做自动换行/自动居中.

    为什么不做文字测量:
        SVG 文本的最终宽度取决于打开它的环境(VS Code 预览、浏览器、Inkscape 的字体回退
        都不同), 本库只保证输出合法的 text 元素与合理的字体栈; 需要精确排版时,
        应该把文字交给设计工具或改用已有排版库, 不要在这里假装能算出字宽.
    """

    TAG = "text"

    def __init__(
        self,
        x: float,
        y: float,
        text: str,
        *,
        font_family: str | None = None,
        font_size: float | None = None,
        font_weight: str | int | None = None,
        font_style: str | None = None,
        text_anchor: str | None = None,
        letter_spacing: float | None = None,
        **style,
    ) -> None:
        super().__init__(**style)
        self.x, self.y = float(x), float(y)
        self.text = text
        self._font = {
            "font-family": font_family,
            "font-size": font_size,
            "font-weight": font_weight,
            "font-style": font_style,
            "text-anchor": text_anchor,
            "letter-spacing": letter_spacing,
        }

    def _geometry_attributes(self) -> list[tuple[str, str]]:
        return [("x", fmt(self.x)), ("y", fmt(self.y))]

    def _style_attributes(self) -> list[tuple[str, str]]:
        font_pairs = [
            (name, _format_number(self._font[name]))
            for name in _FONT_ORDER
            if self._font[name] is not None
        ]
        return font_pairs + super()._style_attributes()

    def render(self, level: int = 0) -> str:
        pad = _INDENT * level
        opening = f"{pad}<{self.TAG}{attrs_text(self._attributes())}>"
        return f"{opening}{escape_text(self.text)}</{self.TAG}>\n"


def _format_number(value):
    """表现属性里的数值(如 fill-opacity / stroke-width)走统一的小数格式.

    为什么:
        直接 str(0.5) 能过, 但 str(1/3) 会得到一长串浮点噪声; 统一交给 fmt.
        字符串属性(颜色 / 名称 / url(...))原样返回.
    """
    if isinstance(value, str):
        return value
    return fmt(float(value))
