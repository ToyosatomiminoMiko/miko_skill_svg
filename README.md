# miko_skill_svg

DSH 技能:**几何优先**地用 Python(纯标准库)拼 SVG。矩形/圆/椭圆/直线/折线/多边形
就是对应元素,圆角矩形用 `<rect rx>`,真圆弧用 `<path>` 的 `A` 命令;只有贝塞尔和
需要 `fill-rule` 挖洞的复合轮廓才用大段 path。输出确定性、可编辑、能直接进版本库。

共享 svgkit 底座 + 一个内置范例(MNTJP 党旗重建)+ 契约/配方/踩坑文档。
新图**照范例改**,不要从零手写坐标。**具体某张图的脚本放那张图自己的项目目录**,
技能里只放可复用的底座(见 `SKILL.md` 的“出图脚本放哪”)。

## 预览

- `assets/flag.svg` — 800×532 范例成图(红底 + 白色党徽)
- `assets/emblem.svg` — 透明底部件层(花环 / 齿轮 / 结 / 国土轮廓,各自成组)

## 安装

技能目录固定为 `~/.dsh/skills/miko-skill-svg`(DSH 从这里发现技能):

```sh
git clone https://github.com/ToyosatomiminoMiko/miko_skill_svg.git ~/.dsh/skills/miko-skill-svg
```

项目级安装可放到 `<项目>/.dsh/skills/miko-skill-svg`。

依赖:Python 3.9+(在 3.15 上开发)。**生成 SVG 只用标准库**;只有 `scripts/fit.py`
(位图参考的一轮拟合,不默认执行)需要 Pillow + numpy。

## 用法

```sh
S=~/.dsh/skills/miko-skill-svg
python3 "$S/examples/myanmar_flag/build.py"   # -> $S/assets/flag.svg + emblem.svg
python3 "$S/scripts/fit.py" ref.png ref.json  # 有参考位图时:一轮拟合,只给顶点证据
```

```python
import sys; sys.path.insert(0, "~/.dsh/skills/miko-skill-svg/scripts")
from svgkit import Svg, Rect, Circle, Polygon
from svgkit.geom import regular_star

Svg(512, 512).add(
    Rect(0, 0, 512, 512, fill="#0b3d2e"),
    Circle(256, 256, 190, fill="#ffffff"),
    Polygon(regular_star(256, 256, 150, 60, 5), fill="#c8102e"),
).save("badge.svg")
```

更完整的 API 与工作流见 `SKILL.md` 与 `references/`。

## 结构

```
scripts/svgkit/           # 构建底座: Svg / 图元 / 几何助手 / 确定性序列化
scripts/fit.py            # 位图 -> 色块轮廓顶点(一轮,不默认执行)
examples/myanmar_flag/    # 内置范例: 参数 -> 四部件 -> 拼装整旗

references/               # 几何配方、输出契约、文字、踩坑、拟合(仅有参考图时)
assets/                   # 范例产物
```

## 与两个来源仓库的关系

- **myama**(`__resources_wikipedia/myama`):MNTJP 党旗的位图拟合项目。其几何参数
  作为冻结输入迁入本技能范例;该仓库已冻结(README 有横幅),不再开发。
  拟合/量测代码留在原仓库,不在本技能内维护;本技能只保留**一轮**证据提取
  (`scripts/fit.py`),不做渲染比对与迭代调参。
- **miko_svg_editor**(`__projects_web/miko_svg_editor`):交互式 SVG 编辑器,仍是独立产品,
  本技能不接管它的代码;两者共享“几何优先 + 确定性输出”的设计取向,规范文档以本技能为准。

## 许可与来源

- 本仓库代码: GPL-3.0(见 `LICENSE`)。
- `examples/myanmar_flag/` 的几何公式与参数移植自用户自己的 myama 仓库(未单独声明
  许可,但作者即本仓库作者,允许在本仓库使用);已在其 README 中注明来源与冻结状态。
- 范例画的是 MNTJP 党旗,仅用于技术演示;实际使用请自行确认相关标识的使用条件。
