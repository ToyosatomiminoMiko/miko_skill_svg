#!/usr/bin/env python3
"""文字内嵌字体底座: 字体子集 + `<defs><style>@font-face</style></defs>` + 墨迹居中修正.

是什么:
    - sfnt_format(font_bytes): 按 sfnt 首 4 字节认出 TrueType / OpenType, 返回
      (mime, format()), 供 @font-face 的 src/format 使用;
    - subset_font(source, text, dest=None): 用 fontTools 把字体裁成只含 text 用到的
      字形, 返回子集字节(也可顺便落盘当项目资产);
    - font_face_style_lines(family, font_bytes, ...): 把子集字节 base64 后写成可直接
      拼进 `<svg>` 的 `<defs><style type="text/css"><![CDATA[ ... ]]></style></defs>`;
    - ink_center_offsets(font_source, text, font_size): 返回 (dx, dy), 让
      `<text text-anchor="middle">` 的**墨迹 bbox 中心**落在期望锚点上.

为什么需要:
    - `<text>` 的最终字形取决于查看端装了什么字体; 要保证“打开就是设计稿里的字体”,
      只能把字体子集按 base64 内嵌. 这是 miko_svg_editor 成品 SVG 的口径;
    - 只打包用到的字形: 一份子集通常几 KB, 不需要随包整份字体;
    - SVG 的文字锚点是基线 + advance 中线, 不是墨迹中心; 想按参考位图对位时,
      用 ink_center_offsets() 把偏差补掉, 比拿 ascender/descender 估算准.

边界:
    - 只支持 sfnt(TrueType `glyf` 或 OpenType `CFF`); woff/woff2 是容器, 查看器不一定
      能解, 不做内嵌;
    - ink_center_offsets() 只按 hmtx 累加 advance, 不计 GPOS kerning, 误差通常 <0.5px;
    - subset_font()/ink_center_offsets() 需要 fontTools(`pip install fonttools`);
      font_face_style_lines()/sfnt_format() 只用标准库;
    - 分发含字体子集的成品时, 别忘了附上字体的许可原文(见 references/text-font.md).

元信息: 作者 Haojiren Galactic, 2026-11-13; 口径来自 miko_svg_editor 的成品导出。
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

# sfnt 首 4 字节: TrueType / 'true' / 'typ1' / 'OTTO'(CFF)
_SFNT_TRUETYPE = (0x00010000, 0x74727565, 0x74797031)
_SFNT_CFF = 0x4F54544F

# 竖排与数字签名相关表对横排单行文字没用, 裁掉可以让子集更小; 保留 GSUB/GPOS.
DEFAULT_DROP_TABLES = ("DSIG", "vhea", "vmtx", "VORG", "VVAR")


def sfnt_format(font_bytes: bytes) -> tuple[str, str]:
    """按 sfnt 首 4 字节返回 (mime, format()); 不能内嵌的容器直接报错."""
    if len(font_bytes) < 4:
        raise ValueError("字体字节不足 4 字节")
    tag = int.from_bytes(font_bytes[:4], "big")
    if tag == _SFNT_CFF:
        return "font/otf", "opentype"
    if tag in _SFNT_TRUETYPE:
        return "font/ttf", "truetype"
    raise ValueError(
        f"不是可内嵌的 sfnt 字体(首 4 字节 0x{tag:08X}); woff/woff2 是容器, 不能直接内嵌"
    )


def subset_font(
    source: str | Path,
    text: str,
    *,
    dest: str | Path | None = None,
    drop_tables: tuple[str, ...] = DEFAULT_DROP_TABLES,
) -> bytes:
    """把 source 字体裁成只含 text 里字形的子集, 返回子集字节(给 dest 时同时落盘)."""
    try:
        from fontTools import subset
    except ImportError as error:  # pragma: no cover - 只在缺依赖时触发
        raise ImportError(
            "字体子集化需要 fontTools: `pip install fonttools`"
        ) from error
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"找不到字体文件 {source_path}")
    options = subset.Options()
    options.name_IDs = ["*"]  # 保留版权/许可等 name 记录(OFL 分发时需要)
    options.name_languages = ["*"]
    options.drop_tables = list(drop_tables)
    font = subset.load_font(str(source_path), options)
    try:
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=text)
        subsetter.subset(font)
        if dest is None:
            buffer = io.BytesIO()
            font.save(buffer)
            return buffer.getvalue()
        target = Path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        font.save(str(target))
        return target.read_bytes()
    finally:
        font.close()


def font_face_style_lines(
    family: str,
    font_bytes: bytes,
    *,
    weight: int = 400,
    style: str = "normal",
    licence_note: str | None = None,
    indent: str = "  ",
) -> list[str]:
    """把一份子集字体写成 `<defs><style>@font-face</style></defs>` 的行列表.

    返回的每一行都已带缩进, 直接拼到 `<svg ...>` 开标签之后即可; CSS 行本身不加缩进,
    与 miko_svg_editor 成品里的写法保持一致.
    """
    mime, sfnt = sfnt_format(font_bytes)
    encoded = base64.b64encode(font_bytes).decode("ascii")
    rule = (
        f'@font-face {{ font-family: "{family}"; font-style: {style}; '
        f"font-weight: {weight}; "
        f'src: url("data:{mime};base64,{encoded}") format("{sfnt}"); }}'
    )
    lines = [
        f"{indent}<defs>",
        f'{indent}  <style type="text/css"><![CDATA[',
    ]
    if licence_note:
        lines.append(licence_note)
    lines.extend(
        [
            rule,
            "]]></style>",
            f"{indent}</defs>",
        ]
    )
    return lines


def _load_font(font_source: str | Path | bytes):
    from fontTools.ttLib import TTFont

    if isinstance(font_source, (bytes, bytearray)):
        return TTFont(io.BytesIO(bytes(font_source)))
    return TTFont(str(font_source))


def ink_center_offsets(
    font_source: str | Path | bytes,
    text: str,
    font_size: float,
) -> tuple[float, float]:
    """返回 (dx, dy): 把 `<text>` 的墨迹 bbox 中心对到期望点要加到 x/y 上的修正量.

    用法(想让这个词的墨迹中心落在 (cx, cy), 并绕该点旋转):
        dx, dy = ink_center_offsets(font, word, size)
        Text(cx + dx, cy + dy, word, text_anchor="middle",
             transform=f"rotate({angle} {cx} {cy})")
    为什么需要 dx: `text-anchor="middle"` 按 advance 宽度居中, 而参考位图量到的是墨迹
    bbox 中心, 两者差一个字形侧边距(通常 <0.5px); dy 则把基线换到墨迹 bbox 竖直中心.
    """
    font = _load_font(font_source)
    try:
        cmap = font.getBestCmap()
        glyf = font["glyf"]
        hmtx = font["hmtx"]
        units_per_em = font["head"].unitsPerEm
        pen = 0
        x_min: float | None = None
        x_max: float | None = None
        y_min: float | None = None
        y_max: float | None = None
        for char in text:
            glyph_name = cmap.get(ord(char))
            if glyph_name is None:
                raise KeyError(f"字体里没有字形 {char!r}")
            advance = hmtx[glyph_name][0]
            glyph = glyf[glyph_name]
            if glyph.numberOfContours != 0:
                left = pen + glyph.xMin
                right = pen + glyph.xMax
                x_min = left if x_min is None else min(x_min, left)
                x_max = right if x_max is None else max(x_max, right)
                y_min = glyph.yMin if y_min is None else min(y_min, glyph.yMin)
                y_max = glyph.yMax if y_max is None else max(y_max, glyph.yMax)
            pen += advance
    finally:
        font.close()
    if x_min is None or y_min is None or x_max is None or y_max is None:
        raise ValueError(f"文字 {text!r} 没有可用的轮廓字形")
    scale = font_size / units_per_em
    advance_center = pen / 2
    ink_center_x = (x_min + x_max) / 2
    # 锚点(advance 中线)与墨迹中心之差; 加 dx 后墨迹中心落到期望点.
    dx = (advance_center - ink_center_x) * scale
    # SVG 的 y 向下: 墨迹中心相对基线在 (yMin+yMax)/2 处(向下为正).
    dy = (y_max + y_min) / 2 * scale
    return dx, dy
