# MapGuide 需求规格文档 (Spec)

> **效力**：需求真相源。所有功能实现必须以本文档为准。
> **版本**：v1.0.0（SDD 采纳基线）
> **日期**：2026-06-07
> **对应原型**：`Document/UX/ui-prototype-interactive-v2.html`

---

## 1. 产品概述

MapGuide 是一款面向 GIS 技术人员和开发者的 Windows 桌面应用，提供可视化的 MapServer Mapfile 配置编辑环境，并集成 LLM 问答助手辅助配置决策。

**核心价值**：降低 Mapfile 配置门槛，将参数填写从「记忆文档」变为「可视编辑 + 即时问答」。

---

## 2. 用户画像

| 角色 | 技能水平 | 核心痛点 | 使用场景 |
|------|----------|----------|----------|
| **GIS 技术人员** | 熟悉 GIS 概念，不精通 Mapfile 语法 | 参数多、语法严格、文档分散 | 发布 PostGIS 表为 WMS/WFS |
| **后端开发者** | 有开发经验，偶尔接触地图服务 | 需要快速生成可用的 Mapfile | 项目中集成地图服务 |
| **学习者** | 刚接触 MapServer | 不理解参数含义和关联关系 | 学习 Mapfile 配置 |

---

## 3. 功能需求

### 3.1 Must Have（核心 MVP）

#### F-M1：配置树编辑（ConfigTree）
- **F-M1.1** 显示 MAP 根节点及嵌套结构（MAP → WEB/METADATA → LAYER → CLASS → STYLE/LABEL）
- **F-M1.2** 每个属性叶子提供对应 `value_type` 的编辑控件（string/enum/integer/float/boolean/color/array）
- **F-M1.3** 支持添加/删除 LAYER、CLASS、STYLE、LABEL 对象节点
- **F-M1.4** 支持添加自定义属性（key + type + desc），标记为 ✎ 自定义
- **F-M1.5** 必填性标识：`*` 必填 / `D` 默认值 / `○` 可选 / `→` 推导 / `✎` 自定义
- **F-M1.6** 显示模式切换：「全部」/「仅必填」
- **F-M1.7** 服务类型选择栏：勾选 WMS/WFS/WCS + MapCache，METADATA 字段按服务类型过滤显示
- **F-M1.8** 图例说明栏：解释标记含义

#### F-M2：问答助手（QAPanel）
- **F-M2.1** 用户可自由提问（不选中任何属性）
- **F-M2.2** 用户可选中属性/对象节点后提问（注入 `focus_param`）
- **F-M2.3** 显示当前关注点路径
- **F-M2.4** 显示问答轮数计数器，切换关注点时重置
- **F-M2.5** LLM 回复中的代码块带复制按钮
- **F-M2.6** 快捷提问按钮：校验错误旁的 `?` 自动发送求助

#### F-M3：校验系统
- **F-M3.1** 字段失焦自动触发 L1-L3 校验（别名解析 + 类型检查 + 语义检查）
- **F-M3.2** 「校验全部」按钮触发四层完整校验（含 L4 mappyfile 语法）
- **F-M3.3** 校验错误在字段上标红显示，对象节点显示状态图标
- **F-M3.4** 导出前自动校验，不通过则阻断

#### F-M4：导入/导出
- **F-M4.1** 导入 `.map` 文件 → 解析为配置树，未知字段标为自定义
- **F-M4.2** 导出 `.map`（一份文件包含所有勾选服务）
- **F-M4.3** 导出 `mapcache.xml`（当勾选 MapCache 时）
- **F-M4.4** 导出确认弹窗显示服务类型摘要

#### F-M5：LLM 集成
- **F-M5.1** 单 Prompt 架构，L0-L5 上下文组装
- **F-M5.2** LLM 返回 JSON 格式：`{thought, action, params_update, question}`
- **F-M5.3** 四层容错解析：`direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback`
- **F-M5.4** `params_update` 通过扁平路径应用到配置树
- **F-M5.5** 每次 LLM 更新后触发完整校验

### 3.2 Should Have（增强体验）

- **F-S1** 配置树搜索过滤
- **F-S2** 响应式布局（≤900px 收起 QAPanel，≤600px 底部输入条）
- **F-S3** 导出历史记录（本次会话内）
- **F-S4** 常用配置模板（快速创建 PostGIS/WMS 配置）

### 3.3 Could Have（未来扩展）

- **F-C1** 支持更多数据源（Oracle Spatial、SQL Server）
- **F-C2** 地图预览（集成 MapServer CGI 或 WMS 渲染）
- **F-C3** 配置 diff / 版本快照
- **F-C4** 支持其他 LLM 提供商（OpenAI、本地模型）

### 3.4 Won't Have（明确不做）

- **F-W1** 多用户协作
- **F-W2** 云端保存/同步
- **F-W3** 移动端适配
- **F-W4** MapScript（Python/PHP）代码生成

---

## 4. 非功能需求

### 4.1 性能

| 指标 | 目标 | 验证方式 |
|------|------|----------|
| 配置树渲染 | 280 节点、4 层嵌套 < 100ms | V3 spike 已验证 |
| 字段失焦校验 | < 200ms | 单元测试 |
| LLM 响应 | < 30s（含 3 次重试） | 集成测试 |
| 完整树校验 | < 2s | 单元测试 |
| 导出 | < 1s | 单元测试 |

### 4.2 可靠性

- LLM 输出解析失败率 ≤ 10%（V2 验证：7%）
- mappyfile `dumps()` 永不抛异常（V1 验证：62/62 通过）
- WebSocket 断线后前端保留树状态，提示用户重连

### 4.3 可维护性

- 模板资源（`data/templates/*.json`）可独立修改，无需改代码
- 新增对象类型：修改 `object-fields.json` + `phase-map.json`
- 新增必填规则：修改 `required.json`
- 新增别名：修改 `aliases.json`

### 4.4 安全

- LLM API key 仅存于后端 `config.json`（gitignored）
- 前端不接触任何 API key
- Electron preload 限制 IPC 暴露面

---

## 5. 验收标准

### 5.1 端到端场景验收

#### AC-1：从零配置 PostGIS → WMS + WFS

**前置**：打开应用，默认显示 MAP 根节点

**步骤**：
1. 勾选 WMS + WFS 服务类型
2. 填写 MAP.name = "city_buildings"
3. 添加 LAYER[0]，connectiontype = postgis
4. 填写 connection 和 data
5. 填写 WEB.METADATA.ows_title
6. 点击「校验全部」→ 通过
7. 点击「导出」→ 生成 `.map`

**预期**：导出文件包含 WMS + WFS 配置，mappyfile 验证通过

#### AC-2：校验错误 → LLM 求助 → 修复

**前置**：已有 LAYER[0].CLASS[0].STYLE[0].color = "蓝色"

**步骤**：
1. 失焦触发校验 → color 标红
2. 点击 color 旁 `?` 按钮
3. LLM 回复解释 RGB 数组格式
4. 用户修改为 `[0, 0, 255]`
5. 失焦 → 校验通过

**预期**：错误清除，状态恢复 idle/pass

#### AC-3：导入已有 Mapfile

**前置**：有一个有效的 `.map` 文件

**步骤**：
1. 点击「导入」→ 选择文件
2. 后端解析 → 构建配置树
3. 未知字段标为自定义
4. 自动四层校验 → 结果显示

**预期**：配置树完整显示文件内容，自定义属性有 ✎ 标记

### 5.2 单元测试验收

| 模块 | 覆盖率目标 | 关键用例 |
|------|-----------|----------|
| TemplateMapper | ≥ 90% | 字段查询、别名解析、必填判断 |
| ConfigTree | ≥ 85% | 构建树、更新值、序列化、路径查找 |
| ValidationPipeline | ≥ 90% | L1-L4 各层校验、false positive 过滤 |
| LLMOutput | ≥ 90% | 四层解析策略、降级处理 |
| UpdateResolver | ≥ 90% | 路径解析、格式转换 |

---

## 6. 风险与假设

### 6.1 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| mappyfile L4 假阳性过滤不完整 | 导出被误阻断 | V1 已摸清边界，需充分测试 |
| LLM 长文本回答截断 | 用户体验差 | prompt 限制 content ≤ 300 字 |
| 真实数据规模 > 280 节点 | 前端卡顿 | 预留虚拟滚动方案 |
| Electron + Python 子进程通信 | 打包复杂 | PyInstaller + electron-builder 标准方案 |

### 6.2 假设

- 用户有基本的 GIS 概念（图层、坐标系、服务类型）
- 用户有可用的 LLM API key（Anthropic）
- 目标环境为 Windows 10/11
- PostGIS 数据源已存在（应用不创建数据库）

---

## 7. 术语表

| 术语 | 说明 |
|------|------|
| **Mapfile** | MapServer 的配置文件，定义地图、图层、样式等 |
| **MapCache** | MapServer 的瓦片缓存系统，生成 `mapcache.xml` |
| **ConfigTree** | 前端可视化配置树，用户直接编辑参数 |
| **扁平路径** | `layers.0.name` 格式的稳定路径标识 |
| **阶段（Phase）** | 参数分类标签：datasource(蓝) / style(橙) / service(绿) / cache(紫) |
| **L1-L4 校验** | 别名解析 → 类型检查 → 语义检查 → mappyfile 语法 |
| **focus_param** | 用户当前关注的参数/对象路径，注入 LLM Prompt |

---

*本文档为 SDD 采纳基线 v1.0.0。所有功能实现以此为准，变更需通过 `/sdd-propose` 流程。*
