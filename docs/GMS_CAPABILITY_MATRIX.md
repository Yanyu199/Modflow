# GMS Capability Matrix

本矩阵仅覆盖第一阶段 MODFLOW 6 常用地下水流工作流，不覆盖完整 GMS 功能集。状态分类如下：

- 已实现：代码中有可追踪的 UI/API/FloPy/结果链路。
- 部分实现：已有主要代码，但存在明显缺口或只覆盖窄场景。
- UI 已存在但后端未实现：页面有入口，但没有后端 API 或没有创建 FloPy package。
- 后端已实现但 UI 未接入：后端 API/逻辑存在，当前页面未使用。
- 存在明显错误：代码链路不一致或很可能无法按设计工作。
- 无法确认：需要运行验证、数值基准或外部数据确认。

## MODFLOW 6 Groundwater Flow Capability Matrix

| 工作流能力 | GMS-like 第一阶段期望 | 当前状态 | 分类 | 第一阶段完成条件 |
|---|---|---|---|---|
| 项目创建与保存 | 项目包含边界、坐标系、单位、网格、地层、packages、运行记录 | 已有 `modflow_project` v1.0 和后端 project.json；前端项目包仍靠 state/CSV 恢复地质缓存 | 部分实现 | 建立 geology/flow/run schema；保存/打开后可无损复现同一 MF6 输入文件 |
| CRS 和单位 | 明确 CRS、长度单位、时间单位、流量单位 | Project Schema 已要求 CRS 和 `m/day/m3/day` 单位；Shapefile CRS 读取/转换未实现 | 部分实现 | 导入时检查 CRS；需要转换时显式记录；API 返回单位 |
| 边界导入 | 支持面边界，多 polygon、内洞、属性检查 | 读取首个 shp 的首个外环 | 部分实现 | 支持选择/合并 polygon；保存 CRS；报告面积和坐标范围 |
| 钻孔导入 | 校验列名、坐标、层序、Top/Bottom/厚度 | 能读 CSV/XLSX 并推算 Top/Bottom | 部分实现 | 严格 schema 校验；异常行报告；层序和厚度检查 |
| 地层建模 | 可复现的地层面、尖灭处理、层厚下限规则 | RBF/nearest 插值，强制层序不交叉 | 部分实现 | 插值算法参数化；基准钻孔案例验证；保存地层面 |
| 断层建模 | 断层几何和水力属性进入模型或明确只影响地质 | 只用于地层插值分块 | 部分实现 | 明确“地质断层”和“水力断层”分离；如建模阻水需实现 HFB 或等效方案 |
| 结构化网格 DIS | X/Y 尺寸或数量、活动区、地层 top/botm | 后端已创建 DIS | 部分实现 | 前后端共用同一网格生成结果；支持 inactive 和薄层规则 |
| 非结构化网格 | DISV/DISU 或网格导入 | 无 | 无法确认/未实现 | 第一阶段可不做；路线图后置 |
| 全局渗透系数 K | NPF k 数组 | 已创建 NPF | 已实现 | 增加单位和取值验证；保存到项目 |
| 分区/分层 K | 按层、分区、多参数 | UI 支持点选单元变 K；后端覆盖数组 | 部分实现 | 支持空间分区和按地层默认值；导出检查 K 数组 |
| 各向异性 K | k33/k22/angle 等 | 无 | 未实现 | 第一阶段至少明确不支持并阻止 UI 暗示 |
| 初始水头 IC | 可设置全局/分区/按层初始水头 | 后端强制使用顶板 top_layer 作为 strt | 部分实现 | UI/API 支持 strt；与 CHD 解耦；保存到项目 |
| 定水头 CHD | 线/面/单元边界，可设置水头 | UI 可设置，后端创建 layer 0 CHD | 部分实现 | 支持层选择、时间序列、单位验证；基准模型对照 |
| 河流 RIV | stage/cond/rbot 全部进入 RIV | UI 有字段；后端只用 stage，cond/rbot 固定 | 存在明显错误 | 后端使用 UI cond/rbot；支持层选择；测试 MF6 输入文件 |
| 排水沟 DRN | elev/cond 进入 DRN package | UI 有字段，后端未创建 DRN | UI 已存在但后端未实现 | 创建 `ModflowGwfdrn`，写入测试验证 |
| 通用水头 GHB | bhead/cond 进入 GHB package | UI 有字段，后端未创建 GHB | UI 已存在但后端未实现 | 创建 `ModflowGwfghb`，写入测试验证 |
| 无流边界 | 默认外部 inactive/no-flow | 通过 idomain 和边界外 inactive 隐式存在 | 部分实现 | 明确 no-flow 规则；与边界线段配置交互一致 |
| 井 WEL | 井位置、层、抽/注水量 | UI 点选单元，后端创建 WEL | 部分实现 | row/col 与后端网格一致；单位和正负号规则；测试 WEL 文件 |
| 补给 RCH | 面分区/栅格/散点插值进入 RCH | 后端可用面分区；UI 调用不存在的 scatter 接口 | 存在明显错误 | 统一数据结构；实现 scatter 或改 UI 接 `/upload-zone`；测试 RCHA |
| 蒸发 EVT | rate/surface/depth 可配置 | 后端 EVTA 固定 depth=2.0；UI 数据链路错误 | 存在明显错误 | UI/API 支持 surface/rate/depth；测试 EVTA |
| 稳定流 | 明确定义 steady period 和验收 | TDIS 单应力期，未显式 steady/transient 语义 | 部分实现 | 明确 steady 配置；收敛和水量平衡通过 |
| 非稳定流 | 多应力期、时间序列 packages | 无 | 未实现 | 后续阶段实现多 period schema 和 UI |
| 求解器设置 | IMS 参数可配置/可记录 | 后端固定 COMPLEX 和迭代上限 | 部分实现 | 保存 solver 设置；失败日志结构化 |
| MF6 可执行路径 | 可配置、可检测、跨机器 | 已支持 `FLOPY_MF6_EXE`、`MF6_EXE_PATH`、仓库相对路径和 PATH | 已实现 | 继续记录版本到正式 run manifest |
| MODFLOW 运行目录 | 每次运行可复核、可清理 | 已使用独立目录；失败默认保留；成功保留可配置 | 部分实现 | 增加正式 run manifest 和清理策略 |
| 水头结果 | 读取 hds 并展示 | 已读取并 Three.js/Plotly 展示 | 已实现 | 增加 no-data/dry cell 处理；基准对照 |
| Cell budget | 全模型预算、package budget、误差 | 只用 SPDIS 估算单元六面流量 | 部分实现 | 解析 listing/budget；输出 percent discrepancy 和 package summary |
| 流向显示 | 可视化流速/比流量方向 | Three.js 箭头已实现 | 部分实现 | 与 MF6 specific discharge 坐标方向核对 |
| 等值线 | 层面水头等值线 | Plotly contour 已实现 | 部分实现 | 规则网格化、inactive mask、色标和导出 |
| 剖面分析 | 任意剖面或行/列剖面 | 支持 row/col 结果图；独立 Streamlit 原型可读 OBJ Excel | 部分实现 | 与模型网格统一；支持任意线剖面 |
| MODPATH 粒子追踪 | 粒子释放、方向、路径结果 | 后端部分实现；前端事件未转发；路径硬编码 | 存在明显错误 | 修复触发链路；配置 mpath7；基准路径测试 |
| OBJ 导出 | 可导出当前模型几何和结果 | 后端从 points 推断 cell size 导出 OBJ | 部分实现 | 使用真实 delr/delc；记录坐标轴约定；测试导出 |
| 输入验证 | 所有 API schema/范围/单位检查 | 多数 API 只捕获异常 | 部分实现 | Pydantic/dataclass 或等效 schema；错误可定位到字段 |
| 自动化测试 | 单元、API、数值回归 | 已有 MF6 executable、workspace、Project Schema/API、隔离和最小稳定流 benchmark 测试 | 部分实现 | 扩展到网格、package 写入、API schema、更多标准模型 |
| 标准模型基准 | 官方或可重复标准模型 | 已有单层稳定流最小 benchmark | 部分实现 | 建立多 package benchmark suite，固定容差 |

## 最重要的差距

1. UI 和 FloPy package 不一致：DRN/GHB/RCH/EVT/MODPATH 是最明显断点。
2. 已有项目级 schema，但还没有正式 geology/flow/run schema，仍无法保证保存/打开后复现同一 MF6 输入文件。
3. 没有数值验收，不能判定结果是否收敛、守恒、可复核。
4. 网格索引在前端和后端各算一遍，存在 row/col 偏差风险。
5. MODPATH 路径、run manifest 和运行目录清理策略仍需后续完善。
