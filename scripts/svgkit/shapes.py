#!/usr/bin/env python3
"""SVG 元素对象: 每个类对应一个 SVG 元素, 统一属性顺序与自闭合写法.

是什么:
    - Element: 所有元素的公共底座(id / transform / fill / stroke / opacity / mask ...);
    - Group: <g> 容器, 可以嵌套;
    - 几何元素: Rect / Circle / Ellipse / Line / Polyline / Polygon / Path / Text;
    - 每个元素在 render() 时输出一段文本, 子元素缩进 2 空格.

为什么:
    - 图元优先: 能用 <rect> / <circle> / <polygon> 表达的几何, 不要退化成 <path>
      里的手写坐标; 类名本身就是"这是什么形状"的声明, 后续改参数只动数值;
    - <path> 只留给真曲线(圆弧/贝塞尔): 直线多边形一律 <polygon>, 圆角矩形一律
      <rect rx ry>, 圆/椭圆一律 <circle> / <ellipse>;
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


class Group(Element):
    """<g> 容器: 放一组子元素, 可以嵌套并带自己的 transform / 样式."""

    TAG = "g"

    def __init__(self, *children: Element, **style) -> None:
        super().__init__(**style)
        self.children: list[Element] = list(children)

    def add(self, *children: Element) -> "Group":
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
