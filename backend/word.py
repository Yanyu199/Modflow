import matplotlib.pyplot as plt
import matplotlib.patches as patches

# -------------------------- 全局样式配置（完全匹配第一张图风格） --------------------------
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']  # 解决中文显示
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10
plt.rcParams['figure.dpi'] = 150  # 高清输出

# 颜色方案（1:1匹配第一张图）
COLORS = {
    'user_layer': '#0066CC',       # 用户层蓝色（匹配第二张图顶部）
    'app_layer': '#FF9933',        # 应用层橙色
    'platform_layer': '#88CC66',   # 平台层绿色
    'data_layer': '#AA88CC',       # 数据层紫色
    'infra_layer': '#6699CC',      # 基础设施层蓝色
    'module_bg': '#FFFFFF',        # 模块背景白色
    'text_white': '#FFFFFF',       # 白色文字
    'text_black': '#000000',       # 黑色文字
    'border': '#666666'            # 边框灰色
}

# 画布尺寸
FIG_WIDTH = 16
FIG_HEIGHT = 10

# -------------------------- 创建画布和坐标轴 --------------------------
fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
ax.set_xlim(0, FIG_WIDTH)
ax.set_ylim(0, FIG_HEIGHT)
ax.axis('off')  # 隐藏坐标轴

# -------------------------- 绘制垂直侧边栏（第一张图标志性元素） --------------------------
# 左侧：标准规范体系
ax.add_patch(patches.Rectangle((0.5, 1), 0.8, FIG_HEIGHT-2, color='#F0F0F0', ec=COLORS['border']))
ax.text(0.9, FIG_HEIGHT/2, '标准规范体系', rotation=90, ha='center', va='center',
        fontsize=12, fontweight='bold')

# 右侧：安全保障体系
ax.add_patch(patches.Rectangle((FIG_WIDTH-1.3, 1), 0.8, FIG_HEIGHT-2, color='#F0F0F0', ec=COLORS['border']))
ax.text(FIG_WIDTH-0.9, FIG_HEIGHT/2, '安全保障体系', rotation=270, ha='center', va='center',
        fontsize=12, fontweight='bold')

# -------------------------- 定义各层位置和高度 --------------------------
layer_heights = [1.2, 1.8, 3.0, 2.5, 1.0]  # 从下到上各层高度
layer_y = [1.0]
for h in layer_heights[:-1]:
    layer_y.append(layer_y[-1] + h)

# 各层左右边界（留出侧边栏空间）
left = 1.5
right = FIG_WIDTH - 1.5
width = right - left

# -------------------------- 1. 基础设施层（最底层） --------------------------
y_bottom = layer_y[0]
y_top = layer_y[1]
ax.add_patch(patches.Rectangle((left, y_bottom), width, y_top-y_bottom,
                               color=COLORS['infra_layer'], ec=COLORS['border']))
ax.text(left + width/2, y_top-0.2, '基础设施层', ha='center', va='center',
        fontsize=11, fontweight='bold', color=COLORS['text_white'])

# 基础设施模块
infra_modules = [
    ('计算环境：私有云', 0.15),
    ('存储：数据库、存储设备', 0.5),
    ('网络环境：局域网|互联网', 0.85)
]
for name, x_pos in infra_modules:
    x = left + width * x_pos
    ax.text(x, y_bottom + 0.3, name, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=COLORS['module_bg'], ec=COLORS['border']))

# -------------------------- 2. 统一数据层 --------------------------
y_bottom = layer_y[1]
y_top = layer_y[2]
ax.add_patch(patches.Rectangle((left, y_bottom), width, y_top-y_bottom,
                               color=COLORS['data_layer'], ec=COLORS['border']))
ax.text(left + width/2, y_top-0.2, '统一数据层', ha='center', va='center',
        fontsize=11, fontweight='bold', color=COLORS['text_white'])

# 2.1 多源数据分析与融合
ax.add_patch(patches.Rectangle((left+0.2, y_top-1.1), width-0.4, 0.9,
                               facecolor=COLORS['module_bg'], ec=COLORS['border']))
ax.text(left + width/2, y_top-0.4, '多源数据分析与融合', ha='center', va='center', fontweight='bold')

multi_source_modules = ['基础地质', '水文地质', '钻探', '物探', '工程地质', '水文监测', '密闭监测', '排水系统']
for i, name in enumerate(multi_source_modules):
    x = left + 0.5 + (width-1.0) * (i / 7)
    ax.text(x, y_top-0.9, name, ha='center', va='center', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.2', facecolor=COLORS['data_layer'], ec=COLORS['border']))

# 2.2 数据治理、融合与分类存储
ax.add_patch(patches.Rectangle((left+0.2, y_bottom+0.2), width-0.4, 1.0,
                               facecolor=COLORS['module_bg'], ec=COLORS['border']))
ax.text(left + width/2, y_bottom+0.9, '数据治理、融合与分类存储', ha='center', va='center', fontweight='bold')

governance_modules = ['单位变换服务', '数据清洗补齐', '数据集成服务']
for i, name in enumerate(governance_modules):
    x = left + 1.0 + (width/2-2.0) * (i / 2)
    ax.text(x, y_bottom+0.4, name, ha='center', va='center', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.2', facecolor=COLORS['data_layer'], ec=COLORS['border']))

storage_modules = ['空间数据库', '时序数据库', '专题数据库', '非结构化数据库']
for i, name in enumerate(storage_modules):
    x = left + width/2 + 0.5 + (width/2-2.0) * (i / 3)
    ax.text(x, y_bottom+0.4, name, ha='center', va='center', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.2', facecolor=COLORS['data_layer'], ec=COLORS['border']))

# -------------------------- 3. 统一模型底座层 --------------------------
y_bottom = layer_y[2]
y_top = layer_y[3]
ax.add_patch(patches.Rectangle((left, y_bottom), width, y_top-y_bottom,
                               color=COLORS['platform_layer'], ec=COLORS['border']))
ax.text(left + width/2, y_top-0.2, '统一模型底座', ha='center', va='center',
        fontsize=11, fontweight='bold', color=COLORS['text_white'])

# 3.1 地质模型+工程模型
ax.add_patch(patches.Rectangle((left+0.2, y_top-1.3), width-0.4, 1.1,
                               facecolor=COLORS['module_bg'], ec=COLORS['border']))
ax.text(left + width/2, y_top-0.5, '地质模型+工程模型', ha='center', va='center', fontweight='bold')

model_modules = ['含水层模型', '隔水层模型', '断层模型', '导水裂隙带模型', '积水区模型', '堆积体模型', '工程模型']
for i, name in enumerate(model_modules):
    x = left + 0.5 + (width-1.0) * (i / 6)
    ax.text(x, y_top-1.0, name, ha='center', va='center', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.2', facecolor=COLORS['platform_layer'], ec=COLORS['border']))

# 3.2 数据接口与数据服务
ax.add_patch(patches.Rectangle((left+0.2, y_bottom+0.2), width-0.4, 1.2,
                               facecolor=COLORS['module_bg'], ec=COLORS['border']))
ax.text(left + width/2, y_bottom+1.0, '数据接口与数据服务', ha='center', va='center', fontweight='bold')

interface_modules_top = ['三维运算与分析', '虚拟钻孔服务', '模型剖切服务', '模型动态更新', '煤机数据交互']
for i, name in enumerate(interface_modules_top):
    x = left + 0.5 + (width-1.0) * (i / 4)
    ax.text(x, y_bottom+0.7, name, ha='center', va='center', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.2', facecolor=COLORS['platform_layer'], ec=COLORS['border']))

interface_modules_bottom = ['数据模型发布', '三维GIS服务', '监测数据服务接口', '数据共享服务', '服务访问控制']
for i, name in enumerate(interface_modules_bottom):
    x = left + 0.5 + (width-1.0) * (i / 4)
    ax.text(x, y_bottom+0.3, name, ha='center', va='center', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.2', facecolor=COLORS['platform_layer'], ec=COLORS['border']))

# -------------------------- 4. 集成应用层 --------------------------
y_bottom = layer_y[3]
y_top = layer_y[4]
ax.add_patch(patches.Rectangle((left, y_bottom), width, y_top-y_bottom,
                               color=COLORS['app_layer'], ec=COLORS['border']))
ax.text(left + width/2, y_top-0.2, '集成应用层', ha='center', va='center',
        fontsize=11, fontweight='bold', color=COLORS['text_white'])

# 应用主模块
ax.add_patch(patches.Rectangle((left+0.2, y_bottom+0.2), width-0.4, 1.2,
                               facecolor=COLORS['module_bg'], ec=COLORS['border']))
ax.text(left + width/2, y_bottom+1.1, '储水空间与水位动态精准三维可视化分析', ha='center', va='center', fontweight='bold')

app_modules = ['三维模型分析', '储水参数预测', '储水状态监测', '坝体状态监测', '水位超限预警']
for i, name in enumerate(app_modules):
    x = left + 0.8 + (width-2.0) * (i / 4)
    ax.text(x, y_bottom+0.5, name, ha='center', va='center', fontsize=10,
            bbox=dict(boxstyle='round,pad=0.3', facecolor=COLORS['app_layer'], ec=COLORS['border']))

# -------------------------- 5. 用户角色层（最顶层） --------------------------
y_bottom = layer_y[4]
y_top = layer_y[4] + layer_heights[4]
ax.add_patch(patches.Rectangle((left, y_bottom), width, y_top-y_bottom,
                               color=COLORS['user_layer'], ec=COLORS['border']))

user_modules = ['技术员', '决策者', '平台维护人员']
for i, name in enumerate(user_modules):
    x = left + width/6 + (width/3) * i
    ax.text(x, y_bottom + 0.5, name, ha='center', va='center', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=COLORS['user_layer'], ec=COLORS['text_white'], color=COLORS['text_white']))

# -------------------------- 保存和显示 --------------------------
plt.tight_layout()
plt.savefig('储水空间与水位动态分析平台架构图.png', bbox_inches='tight', dpi=300)
plt.show()