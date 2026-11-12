#!/usr/bin/env python3
"""SVG 文本序列化底座: 数字格式、XML 转义与属性拼装.

是什么:
    - fmt(value): 把数值写成确定性的 SVG 文本;
    - escape_text / escape_attr: XML 文本节点与属性值的转义;
    - attrs_text(pairs): 把有序的 (属性名, 值) 序列拼成 ` name="value"` 串.

为什么:
    - 确定性: 同一份几何重复生成必须逐字节相同, 否则 diff 永远是噪声. Python 的
      str(float) 会给出 1e-05 这样的科学计数法, 也会保留浮点末位噪声; 这里统一四舍五入
      到 4 位小数、去掉尾随 0、整数不写小数点, 并把 -0 归一成 0;
    - 不用 style="": 表现属性(fill / stroke / ...)写成一等属性, 浏览器和 Inkscape
      都直接认, 改样式时不用解析 CSS 串;
    - 属性顺序由调用方按固定顺序给出: 顺序稳定, 几何没变时 diff 必然为空;
    - 控制字符(除 \\t \\n \\r)会让 XML 直接非法, 这里遇到就报错, 不悄悄输出坏文件.

元信息: 2026-11-12.
"""

from __future__ import annotations

import math

# 保留的小数位数: 800px 级画布上 4 位小数 = 0.0001px, 远小于任何可见误差.
PRECISION = 4

# 允许出现在 XML 文本里的空白控制字符; 其余 C0 控制字符一律视为错误.
_ALLOWED_CONTROLS = frozenset("\t\n\r")

_TEXT_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
_ATTR_ESCAPES = {**_TEXT_ESCAPES, '"': "&quot;"}


def fmt(value: float) -> str:
    """把数值写成确定性的 SVG 文本.

    是什么:
        - 整数(含四舍五入后是整数的情况)输出 `12`, 不输出 `12.0`;
        - 其余保留 4 位小数并去掉尾随 0, 例如 `0.5` / `3.1416`;
        - `-0.0` 输出 `0`, 避免同一个位置在两次运行里出现 `-0` 和 `0` 两种写法.

    为什么:
        SVG 数值允许科学计数法, 但确定性输出不希望同一坐标出现多种文本表示;
        先 round 再格式化, 保证"同一个 float 只有一种写法".
    """
    if isinstance(value, bool):
        raise TypeError("fmt() 不接受 bool")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"fmt() 不接受非有限数值: {value!r}")
    rounded = round(number, PRECISION)
    if rounded == 0:
        return "0"
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.{PRECISION}f}".rstrip("0").rstrip(".")


def _check_controls(text: str, kind: str) -> None:
    """拒绝 XML 1.0 不允许的控制字符, 并在报错信息里提供足够定位的码位."""
    for index, char in enumerate(text):
        code = ord(char)
        if code < 0x20 and char not in _ALLOWED_CONTROLS:
            raise ValueError(
                f"{kind}里出现 XML 不允许的控制字符 U+{code:04X} (位置 {index})"
            )


def escape_text(text: str) -> str:
    """转义 XML 文本节点(& < >); 同时拒绝非法控制字符."""
    _check_controls(text, "文本")
    return "".join(_TEXT_ESCAPES.get(char, char) for char in text)


def escape_attr(text: str) -> str:
    """转义 XML 属性值(& < > "); 同时拒绝非法控制字符."""
    _check_controls(text, "属性值")
    return "".join(_ATTR_ESCAPES.get(char, char) for char in text)


def attrs_text(pairs) -> str:
    """把有序的 (属性名, 值) 序列拼成 ` name="value"` 串; 值为 None 的项跳过.

    为什么用有序序列而不是 dict:
        属性输出顺序影响 diff 的可读性, 顺序必须由调用方明确控制;
        本仓库统一为 id -> 几何 -> transform -> 表现属性 -> 额外属性.
    """
    parts: list[str] = []
    for name, value in pairs:
        if value is None:
            continue
        parts.append(f' {name}="{escape_attr(str(value))}"')
    return "".join(parts)
