# 文字与字体

SVG 的 `<text>` 是“请渲染器用某个字体把这段字排出来”,不是“把字形转成路径”。
本技能只保证输出合法、锚点正确、字体栈合理;**不做字宽测量,也不做自动换行/自动居中**。

## 基本写法

```python
Text(x, y, "缅甸民族真理与正义党",
     font_family='"Noto Sans CJK SC", "Source Han Sans SC", sans-serif',
     font_size=24, text_anchor="middle", fill="#ffffff")
```

- `x`/`y` 是基线位置(不是文字外框中心);需要“视觉居中”时自己估一个偏移;
- `text-anchor`: `start` / `middle` / `end`,决定 x 是左端/中心/右端;
- 中文务必给 CJK 字体栈并保留 `sans-serif` 兜底;只写一个字体名时,缺字体就回退到
  系统默认,度量全变;
- 需要字距时用 `letter-spacing`,不要逐字摆 x。

## 内嵌自定义字体子集(@font-face)

`<text>` 最终用哪个字体的字形由查看端决定。要让成品在任何机器上都按设计字体渲染,
就把**只含用到字形**的字体子集 base64 内嵌进 `<defs><style>`。口径与 miko_svg_editor
的成品导出一致;底座在本技能 `scripts/font_embed.py`(`pip install fonttools`;
拼 `@font-face` 与判断 sfnt 格式本身只用标准库):

```python
import sys
sys.path.insert(0, "$S/scripts")
from font_embed import font_face_style_lines, ink_center_offsets, subset_font

# 1) 只裁用到的字形; 给 dest 时顺便落盘成项目资产(推荐: 出图不再依赖系统字体版本)
font_bytes = subset_font("/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
                         "общегосударственная", dest="fonts/NotoSans-subset.ttf")
# 2) 写成 <defs><style><![CDATA[ @font-face ... ]]> 的行, 拼到 <svg ...> 开标签之后
lines = font_face_style_lines(
    "Noto Sans", font_bytes, weight=400,
    licence_note="/* Noto Sans Regular, SIL OFL 1.1; 许可原文见 LICENSE-NotoSans-OFL.txt */",
)
# 3) <text> 的 font-family 写内嵌族名, 后面照样留系统回退栈
#    font-family="'Noto Sans', 'PT Sans', 'DejaVu Sans', sans-serif"
```

放置文字时 `text-anchor="middle"` 的锚点是 advance 中线, 不是墨迹中心。想按参考位图
对位, 用 `ink_center_offsets()` 把偏差补掉(按 hmtx + glyf 算, 不计 kerning):

```python
dx, dy = ink_center_offsets(font, word, font_size)   # font 可以是路径或字节
Text(cx + dx, cy + dy, word, text_anchor="middle",
     transform=f"rotate({angle} {cx} {cy})")         # 绕墨迹中心旋转
```

- 只支持 sfnt(TrueType `glyf` 或 OpenType `CFF`);woff/woff2 是容器, 查看器不一定能解。
- Chromium/WebKit 认 base64 `data:` 字体, **Inkscape 不认**(会回退本机同名字体);
  所以内嵌族名沿用字体原族名, 本机装了同款字体时回退也几乎不变形, 目检用浏览器截图。
- 许可: 内嵌子集也是“字体软件”, 分发成品时要附字体许可原文(OFL 要求), 并在注释里
  写清来源;子集化默认保留 `name` 表里的版权/许可记录。
- 改词之后要重裁子集, 否则新字形会静默回退到系统字体。
- 一族字重一份 `@font-face`;`<text font-weight>` 要和声明的字重匹配。

## 为什么不做文字测量

同一段文字在 VS Code 预览、Chrome、Inkscape 里的实际宽度可能不同(字体回退、字距、
OpenType 特性都不同)。在这里假装能算出宽度,只会让“看起来对齐”在别的环境里错位。
需要精确排版时的选择:

1. 交给设计工具(Inkscape/Figma)排完再导出;
2. 用支持字体度量的库(如 harfbuzz)先算宽度,再把结果当参数传进来;
3. 换成 `<path>` 文字轮廓(转曲),代价是文字不可再编辑。

## 转曲与子集化

- **转曲**:把文字变成 `<path>`。只有用户明确要求“文字不可编辑/保证渲染一致”时才做,
  且要保留原始文字到 `<title>` 或注释里,方便以后改;
- **字体子集化**:见上文「内嵌自定义字体子集」, 底座是 `scripts/font_embed.py`;
  分发时按字体许可要求附上许可原文。

## 常见坑

- 字体名里带空格时,`font-family` 里要加引号:`"Noto Sans CJK SC"`;
- 中文用 `font-weight="bold"` 时,很多环境没有对应粗体字重,会伪粗体,慎用;
- 行高/多行文本没有原生支持:多行就用多个 `<text>` 手动摆 y,或者接受用户环境自行换行;
- `text-anchor` 在 Inkscape 里有时按“选中框”解释,和浏览器有细微差异,别把关键对齐
  只压在一行文字上;
- 导出 PNG 时字体没装会变成方块或别的字体——要交付的是 SVG,提醒用户环境字体即可。
- 内嵌了 `@font-face` 的 SVG 在 Inkscape 里看不到内嵌字体(它不解析 data URI), 会回退到本机同名字体;用浏览器验收。
