#!/usr/bin/env python3
"""SVG 文档对象: 根元素 <svg>、画布尺寸与序列化入口.

是什么:
    - Svg(width, height, viewbox=None): 一个 SVG 文档, 收集子元素后 render() 成文本;
    - save(path): 按 UTF-8 写文件(末尾不带 BOM);
    - viewBox 默认与宽高一致(`0 0 width height`), 这样 1 用户单位 = 1 px,
      几何坐标可以直接当像素读, 不用在心上再换算一次.

为什么:
    - 把"根元素长什么样"收敛到一个类: xmlns / width / height / viewBox 的顺序固定,
      避免每个脚本各写一份头;
    - width/height 与 viewBox 同值: 缩放交给使用者(浏览器/Inkscape 都能按容器自适应),
      几何代码里只维护一套坐标;
    - 不自动加 xmlns:xlink / inkscape 命名空间: 用不到就不写, 输出更干净.

元信息: 2026-11-12.
"""

from __future__ import annotations

from pathlib import Path

from .serialize import attrs_text, fmt
from .shapes import Element

_SVG_NS = "http://www.w3.org/2000/svg"


class Svg:
    """SVG 文档根: `<svg xmlns=... width=... height=... viewBox=...>`."""

    def __init__(
        self,
        width: float | str,
        height: float | str,
        *,
        viewbox: str | None = None,
        attrs: dict[str, str] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        self.viewbox = viewbox
        self.extra_attributes = dict(attrs or {})
        self.children: list[Element] = []

    def add(self, *children: Element) -> "Svg":
        """追加顶层元素, 返回自身以便链式调用."""
        self.children.extend(children)
        return self

    def _root_attributes(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = [
            ("xmlns", _SVG_NS),
            ("width", _dimension_text(self.width)),
            ("height", _dimension_text(self.height)),
            (
                "viewBox",
                self.viewbox
                if self.viewbox is not None
                else f"0 0 {_dimension_text(self.width)} {_dimension_text(self.height)}",
            ),
        ]
        pairs.extend(self.extra_attributes.items())
        return pairs

    def render(self) -> str:
        """序列化为完整 SVG 文本(以换行结尾)."""
        opening = f"<svg{attrs_text(self._root_attributes())}>\n"
        body = "".join(child.render(1) for child in self.children)
        return f"{opening}{body}</svg>\n"

    def save(self, path: str | Path) -> Path:
        """写 UTF-8 文件并返回路径; 父目录不存在时自动创建."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render(), encoding="utf-8")
        return target


def _dimension_text(value: float | str) -> str:
    """宽高可以是数字(px)或带单位的字符串(如 "100%"), 数字走统一格式."""
    if isinstance(value, str):
        return value
    return fmt(float(value))
