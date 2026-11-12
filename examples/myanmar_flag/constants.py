#!/usr/bin/env python3
"""MNTJP(缅甸民族真理与正义党)党旗例子的全部设计参数.

是什么:
    只放数值 / 颜色 / 开关, 不放几何算法. 四组部件(花环 / 齿轮 / 结 / 国土轮廓)的
    参数与 myama 仓库 `miko_wiki_resource/constants.py` 完全一致 —— 那些值是 myama
    阶段从 800x532 参考位图回归出来的, 这里作为冻结输入沿用, 不再重新拟合.

为什么:
    - 单一参数源: 想改旗子的比例/位置, 只改这一个文件, 各部件模块自动跟着变;
    - 保留 myama 的"设计单位": 部件几何用设计单位(1 参考像素 = SCALE 设计单位)计算,
      拼进 800x532 旗面时每组套一个 scale(1/SCALE), 这样部件几何可以独立预览/复用,
      而不是把每个坐标都预先除成旗面像素;
    - 半像素约定: 参考位图的像素中心与 SVG 用户坐标差半个像素, 花环/齿轮拟合时用的是
      "像素索引 = 中心", 结/国土用的是 "中心 = i+0.5", 所以 PART_PIXEL_OFFSETS 里
      前两者的修正不同, 直接照搬 myama 的实测值.

元信息: 2026-11-12; 参数与来源见 examples/myanmar_flag/README.md.
"""

# ---- 旗面: 坐标与颜色 ----
SCALE = 4.3088  # 1 参考图像素 = 多少个设计单位
FLAG_WIDTH_PX = 800
FLAG_HEIGHT_PX = 532
O_X_PX = 392.4  # 花环圆心 O 在旗面上的像素坐标(myama 拟合结果)
O_Y_PX = 295.23
FLAG_RED = "#ff1010"  # 参考旗面红底采样值
EMBLEM_WHITE = "#ffffff"  # 旗徽图形统一白色

# 部件局部原点落到旗面像素时的半像素修正; 原因见上面 docstring 的"半像素约定".
PART_PIXEL_OFFSETS = {
    "wreath": (0.5, 0.5),
    "gear": (0.5, 0.5),
    "root": (0.0, 0.0),
    "map": (0.0, 0.0),
}

# ---- 麦粒 / 麦穗(花环) ----
EAR_LENGTH = 190.374  # 麦粒长边: 卷弧后变成切向长度
EAR_HEIGHT = 65.496  # 麦粒短边: 卷弧后变成径向宽度
EAR_OFFSET = 46.532  # 麦粒斜度: 上下底的水平错位
EAR_TOP_RADIUS = 55.249  # 靠穗尖那圈圆角(小)
EAR_ROOT_RADIUS = 101.963  # 靠根部那圈圆角(大)
EAR_GAP = 5.564  # 一枚麦穗里两粒麦子之间的缝(麦秆)
EAR_PIVOT_RATIO = 0.5  # 卷弧圆心在麦穗高度上的比例
TWIST_DEG = 20.0  # 单枚麦穗自己卷弧的总角度(度)

# ---- 花环排列 ----
RADIUS = 470.995  # 麦穗卷弧半径 = 圆心 O 到麦穗中轴的距离, 同时决定扭转角
SPACING = 0.532  # 相邻两枚麦穗之间的角度缝(度)
MIRRORED_CENTER_DEG = 24.408  # 对称排列的中心方向(度): 0 = 正右, 90 = 正下
COUNT = 3  # 每侧并排的麦穗枚数

# ---- 顶端橄榄 ----
TIP_OLIVE_LENGTH = 211.828  # 橄榄长轴长度
TIP_OLIVE_THICKNESS = 76.049  # 橄榄最大厚度
TIP_OLIVE_GAP_DEG = 2.879  # 橄榄下尖端离穗尖的角度缝(度)
TIP_OLIVE_BASE_OFFSET = 10.297  # 橄榄下尖端相对缝圆(半径 RADIUS)的径向外偏(设计单位)

# ---- 芒(三道同心弧, 每道再镜像一份) ----
ARC_WIDTH = 17.461  # 弧线宽度
ARC_INNER_RATIO = 0.0  # 内侧弧在麦穗径向范围里的位置: 0 = 贴内侧边
ARC_INNER_SPAN_DEG = 41.597
ARC_INNER_END_OFFSET_DEG = 1.042
ARC_MIDDLE_RATIO = 0.5
ARC_MIDDLE_SPAN_DEG = 20.371
ARC_MIDDLE_END_OFFSET_DEG = 1.511
ARC_OUTER_RATIO = 1.0
ARC_OUTER_SPAN_DEG = 52.624
ARC_OUTER_END_OFFSET_DEG = 0.355
# 收在穗尖/橄榄尖那一端再往图形内部多走的角度: 端点用圆头, 不埋进去会露在图形外面.
ARC_END_INSERT_DEG = 4.0

# ---- 齿轮 ----
GEAR_TEETH = 14
GEAR_CENTER_OFFSET_X = 4.739  # 齿轮圆心相对花环圆心 O 的偏移(设计单位)
GEAR_CENTER_OFFSET_Y = 7.3811
GEAR_PHASE_A_DEG = 13.0297
GEAR_PHASE_B_DEG = 2.9268
GEAR_R_INNER = 235.642  # 齿圈内孔半径
GEAR_R_ROOT = 293.1572  # 齿根圆半径
GEAR_R_TIP = 336.6154  # 齿顶圆半径
GEAR_TOOTH_HALF_ROOT_DEG = 7.2235  # 齿在齿根圆处的半角
GEAR_TOOTH_HALF_TIP_DEG = 5.6265  # 齿在齿顶圆处的半角(倒圆前)
GEAR_TIP_ROUND = 8.5066  # 齿顶两角倒圆半径
# 14 个齿的角位置(度, 屏幕坐标); 缺口里的 4 个齿位由两侧线性补间.
GEAR_TOOTH_CENTERS_DEG = (
    2.9268, 28.6411, 59.4068, 90.1726, 115.8869, 141.6011, 167.3154,
    193.0297, 218.744, 241.9326, 265.1211, 288.3097, 311.4983, 337.2126,
)
# 两道缺口的切边采样点(齿轮局部坐标, 设计单位, 从齿顶侧到内孔侧):
# 参考图里国土从齿轮上穿过, 把齿圈剪成两段, 切边是"近似直线、带一点平缓弯曲"的曲线.
GEAR_CUT_EDGE_TOP_A = (
    (-247.88, -231.84), (-238.5, -213.4), (-227.36, -196.38),
    (-214.49, -180.82), (-199.9, -166.71), (-183.54, -154.01),
)
GEAR_CUT_EDGE_TOP_B = (
    (228.95, -257.07), (216.93, -239.56), (203.12, -224.27),
    (187.58, -211.31), (170.32, -200.7), (151.3, -192.43),
)
GEAR_CUT_EDGE_BOTTOM_A = (
    (229.53, 247.11), (222.84, 226.98), (214.69, 207.81),
    (205.07, 189.69), (194.01, 172.67), (181.53, 156.8),
)
GEAR_CUT_EDGE_BOTTOM_B = (
    (76.67, 327.88), (77.22, 306.93), (75.89, 286.39),
    (72.66, 266.33), (67.53, 246.8), (60.47, 227.8),
)
GEAR_CUT_MARGIN = 45.0  # 缺口多边形在 r_tip 之外 / r_inner 之内多盖出的距离

# ---- 根/结: 旗徽底部两根相交的枝棒 + 中间圆角矩形结 ----
ROOT_ROD_ANGLE_DEG = -8.9056  # 一根枝棒的方向; 另一根由竖直镜像得到
ROOT_ROD_LONG_LEN = 202.9492  # 交点 -> 长端尖端
ROOT_ROD_SHORT_LEN = 159.7935  # 交点 -> 短端尖端
ROOT_ROD_LONG_THICK = 22.4149
ROOT_ROD_SHORT_THICK = 13.9773
ROOT_ROD_CROSS_THICK = 13.1705  # 交点处棒厚(收腰)
ROOT_ROD_LONG_BOW = -7.4612  # 长臂中心线中点沿法线的偏移
ROOT_ROD_SHORT_BOW = -5.0886
ROOT_ROD_LONG_SWELL = 0.5261  # 长臂中段鼓肚(设计单位, 全宽)
ROOT_ROD_SHORT_SWELL = 0.7468
ROOT_ROD_LONG_FOOT = 38.1646  # 长端捺脚: 从尖端往回收多长开始压平下侧轮廓
ROOT_ROD_LONG_TIP_LEN = 12.8416  # 长端收尖段长度
ROOT_ROD_LONG_TIP_FACE = 11.4223  # 长端收尖后的端面宽度
ROOT_CROSS_OFFSET_Y = -1.2249  # 两根棒交点相对结中心的竖直偏移
ROOT_KNOT_LENGTH = 87.9262  # 结的长度
ROOT_KNOT_THICKNESS = 44.8142  # 结的厚度
ROOT_KNOT_ANGLE_DEG = 0.0554  # 结的朝向(0 = 水平)
ROOT_KNOT_CORNER_RADIUS = 16.7549  # 结的角半径
ROOT_CENTER_OFFSET_X = 5.0648  # 结中心相对花环圆心 O 的偏移(设计单位)
ROOT_CENTER_OFFSET_Y = 483.0277

# ---- 国土轮廓 ----
MAP_SCALE = 0.6086  # 设计单位 / map.svg 用户单位
MAP_ROTATION_DEG = 0.189  # 绕轮廓质心的旋转角(度, 顺时针为正)
MAP_CENTER_OFFSET_X = 13.1274  # 轮廓质心相对花环圆心 O 的水平偏移(设计单位)
MAP_CENTER_OFFSET_Y = -256.219
