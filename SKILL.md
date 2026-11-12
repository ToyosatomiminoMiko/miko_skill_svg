---
name: miko-skill-svg
description: 用 Python(纯标准库)以几何图元拼装 SVG:矩形/圆/椭圆/直线/折线/多边形/圆弧;只有真曲线(圆弧、贝塞尔)和需要 fill-rule 的复合轮廓才交给 path。输出确定性、可编辑、可直接在浏览器/Inkscape 里改。当用户要画或重画由简单几何图形组成的矢量图(徽标、旗帜、齿轮、星形、示意图、装饰图形),或要把一张位图重建成干净可编辑的 SVG 时使用。
whenToUse: 用户要求生成/修改 SVG,且图形由矩形、圆、多边形、圆弧等几何图元组成;或已有几何参数(角度/半径/齿数/间距)需要画成矢量图;或要把位图重建为可编辑 SVG。不适合照片级插画、手绘曲线、以文字排版为主的海报。
---

# 几何优先的 SVG:用简单图形拼图,而不是一条 path 画到底

核心主张:**先想清楚这张图由哪些几何图元组成,再选元素**。矩形就是 `<rect>`,圆就是
`<circle>`,正多边形/星形就是 `<polygon>`,圆角矩形就是 `<rect rx>`,真圆弧就用 `<path>`
的 `A` 命令。只有确实没有图元对应的形状(贝塞尔曲线、需要 evenodd 挖洞的复合轮廓)才用
`<path>` 拼。

共享底座 + 一个完整范例 + 契约/陷阱文档;新图**照范例改**,不要从零手写坐标。

## 快速开始

技能根记为 `S`(默认安装:`~/.dsh/skills/miko-skill-svg`)。

```python
import sys
sys.path.insert(0, "$S/scripts")
from svgkit import Svg, Rect, Circle, Polygon
from svgkit.geom import regular_star

svg = Svg(512, 512)                                   # 512x512, viewBox 默认 0 0 512 512
svg.add(Rect(0, 0, 512, 512, fill="#0b3d2e"))         # 背景
svg.add(Circle(256, 256, 190, fill="#ffffff"))        # 中圆
svg.add(Polygon(regular_star(256, 256, 150, 60, 5), fill="#c8102e"))  # 五角星
svg.save("badge.svg")
```

```sh
S=~/.dsh/skills/miko-skill-svg
python3 "$S/examples/myanmar_flag/build.py"     # 完整范例: 800x532 党旗 -> $S/assets/flag.svg
```

## 图元选择阶梯(从上往下选,能不上升就不上升)

| 形状 | 用什么 | 说明 |
| --- | --- | --- |
| 矩形 / 圆角矩形 | `<rect>` / `<rect rx>` | 不要用 4 条线或 path 拼 |
| 圆 / 椭圆 | `<circle>` / `<ellipse>` | 不要在 path 里用两段 A 硬拼 |
| 直线 / 折线 / 多边形 | `<line>` / `<polyline>` / `<polygon>` | 顶点用点列给,自动格式化成 `points` |
| 正多边形 / 星形 | `geom.regular_polygon` / `geom.regular_star` → `<polygon>` | 不要手写 10 个坐标 |
| 真圆弧 | `geom.arc_path_d` → `<path d="M... A...">` | 解析几何意义的圆弧,一条 A 命令 |
| 透镜形(两头尖) | `geom.lens_path_d` → `<path>` | 两条劣弧闭合,半径由弦长/厚度反解 |
| 贝塞尔曲线 / 复合轮廓 | `<path>`(必要时 `fill-rule="evenodd"`) | 只有到这一步才允许大量 path |
| 文字 | `<text>` | 只保证合法与锚点,不做自动排版 |

旋转/镜像/阵列优先用 `<g transform>` 或几何助手生成点列,**不要**手工重算坐标:
`geom.rotate / geom.mirror / geom.translate / geom.scale`;多个部件共享同一坐标系时用嵌套 `<g>`。

## 目录

```
miko-skill-svg/
├── SKILL.md
├── scripts/svgkit/            # 纯标准库小库
│   ├── doc.py                 # Svg: 根元素 / viewBox / save
│   ├── shapes.py              # Rect/Circle/Ellipse/Line/Polyline/Polygon/Path/Text/Group
│   ├── geom.py                # 点列变换、圆弧、圆/多边形采样、正多边形/星形/透镜形
│   └── serialize.py           # 确定性数字格式、XML 转义、属性顺序
├── examples/myanmar_flag/     # 完整范例: 从冻结参数重绘整面旗
│   ├── constants.py           # 全部数值参数(唯一调参入口)
│   ├── wreath.py / gear.py / root.py / map.py   # 四个部件,各自输出局部坐标的图元
│   ├── build.py               # 拼装并输出 assets/flag.svg、assets/emblem.svg
│   └── README.md              # 来源、口径、与旧产物的差异
├── references/
│   ├── geometry-first.md      # 工作流 + 常见几何配方(齿轮/花环/放射阵列/轮廓)
│   ├── contract.md            # 输出契约: 单位/确定性/属性/可编辑性
│   ├── text-font.md           # 文字与字体
│   ├── pitfalls.md            # 两仓踩过的坑
│   └── fitting-with-reference.md  # 只有拿到参考位图时才用的参数拟合思路
└── assets/                    # 范例产物(flag.svg / emblem.svg)
```

## svgkit 速查

```python
from svgkit import Svg, Group, Rect, Circle, Ellipse, Line, Polyline, Polygon, Path, Text
from svgkit.geom import (
    arc_path_d, arc_points, angle_point, circle_points,
    lens_path_d, regular_polygon, regular_star,
    translate, rotate, mirror, scale, bbox, centroid, points_text,
    translate_transform, rotate_transform, scale_transform,
)
from svgkit.serialize import fmt

svg = Svg(800, 532)                 # width/height 数字 = px; viewBox 默认 0 0 w h
svg.add(*elements)                  # 返回 self, 可链式
svg.save("out.svg")                 # UTF-8; 父目录自动创建

rect = Rect(x, y, w, h, rx=12, fill="#fff")
circ = Circle(cx, cy, r, fill="none", stroke="#000", stroke_width=3)
poly = Polygon(points, fill="#fff")            # points: [(x, y), ...]
path = Path(d, fill="none", stroke="#fff", stroke_width=17.461, stroke_linecap="round")
text = Text(x, y, "文字", font_size=24, text_anchor="middle", fill="#fff")
group = Group(*children, id="wreath", transform="translate(392.4,295.23) scale(0.232083)")
```

所有元素都接受公共样式参数:`id / transform / fill / fill-opacity / fill-rule / stroke /
stroke-width / stroke-linecap / stroke-linejoin / stroke-opacity / opacity / mask / clip-path`,
以及 `attrs={"custom": "..."}` 追加任意属性。

## 工作流

1. **拆图元清单**:把目标图分解成 rect / circle / polygon / 圆弧 的清单,写清每个形状的
   参数(中心、半径、边数、角度、间距)。分解不出来时,先问"这张图原本是怎么画的"。
2. **定坐标模型**:一套单位、一个原点、一份画布尺寸。部件用局部坐标,拼装时靠
   `<g transform>` 平移/缩放;不要把每个坐标预先乘成画布坐标。
3. **参数化**:会重复/对称/阵列的东西写成公式(见 `references/geometry-first.md`),
   数值集中到一个常量文件/字典,不要散在绘制代码里。
4. **画**:图元阶梯从上往下选;优先复用本库的配方,不要手写点列。
5. **输出**:`Svg.save()`,默认写到 `assets/` 或用户指定路径。
6. **交付**:给用户看 SVG 文件。本技能不内置渲染器/目检流程,不做像素比对;
   是否满意由用户在浏览器/Inkscape 里打开判断。

## 确定性契约(必须遵守)

- 数字统一走 `svgkit.serialize.fmt`:4 位小数、去尾随 0、整数不带小数点、`-0` 归一;
  **不要**在绘制代码里自己 `str(float)` / `toFixed`。
- 属性顺序固定:id → 几何 → transform → 表现属性 → 额外属性;不要用 `style=""`。
- 同一个参数重复生成必须逐字节一致(生成物可以直接进版本库/diff)。
- 文本用 `<text>`,字体给合理回退栈;不要指望自动测量字宽。

## 范例: MNTJP 党旗重建

`examples/myanmar_flag/` 是完整例子:红底 + 白色花环(6 枚麦穗 + 2 枚顶端橄榄 + 6 道芒)
+ 齿轮 + 底部结 + 缅甸国土轮廓,输出 800x532。它演示了:

- 参数全部来自 `constants.py`(冻结值),四个部件模块各自输出局部坐标的图元;
- 麦穗轮廓/切边用 `<polygon>`,橄榄/芒用真正的圆弧 `<path>`,结用 `<rect rx>`,
  齿轮齿圈拆成简单多边形(不用 mask、不用带洞复合 path);
- 拼装时每个部件套 `translate + scale` 组,而不是改坐标。

```sh
python3 examples/myanmar_flag/build.py      # -> assets/flag.svg, assets/emblem.svg
```

来源与口径见 `examples/myanmar_flag/README.md` 与 `references/contract.md`。

## 参考

- `references/geometry-first.md` — 几何拆解方法、齿轮/花环/放射阵列/轮廓配方
- `references/contract.md` — 输出契约与可编辑性要求
- `references/text-font.md` — 文字、字体栈、中文
- `references/pitfalls.md` — 两仓踩过的坑(数字格式、mask、手改回流、分辨率天花板等)
- `references/fitting-with-reference.md` — 只有拿到参考位图时才用的参数拟合流程(不默认执行)
