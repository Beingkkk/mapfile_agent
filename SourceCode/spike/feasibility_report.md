# 可行性验证总结报告

> 三个核心难点验证全部完成，作为正式动工的 go/no-go 决策依据。
>
> 验证时间：2026-06-07

---

## 总览

| 验证项 | 优先级 | 状态 | 结论 |
|--------|--------|------|------|
| **V1: mappyfile validate 行为摸底** | P0 | ✅ 通过 | 序列化规则清晰，无阻碍 |
| **V2: LLM Prompt 输出稳定性** | P1 | ✅ 通过 | JSON 可解析率 93.3%，prompt 设计可行 |
| **V3: ConfigTree 前端递归渲染** | P2 | ✅ 通过 | 自定义递归组件方案可行 |

**决策：Go** — 按设计文档全面开发。

---

## V1 结论（详情见 [v1_result.md](v1_result.md)）

`mappyfile.validate(mf, version=8.4)` 行为已摸清：

- **必须数组化的字段**：`layers`、`classes`、`styles`、`labels`、`projection`、`extent`
- **enum 值大小写**：不敏感（`postgis`/`POSTGIS` 都通过）
- **dumps() 永不出错**，`validate()` 是严格关卡
- **自定义字段会被 validate 拒绝** → L4 需过滤 false positive
- **`to_mappyfile_dict()` 7 条强制变换规则** 已确定

**对架构的影响**：序列化层 `ConfigTree.to_mappyfile_dict()` 需要实现 7 条转换规则，但这在代码层面完全可控。

---

## V2 结论（详情见 [v2_result.md](v2_result.md)）

LLM Prompt 稳定性验证结果：

| 指标 | 实测值 | 通过标准 | 状态 |
|------|--------|----------|------|
| JSON 可解析率 | **93.3%** | ≥ 90% | ✅ |
| `action=update` 稳定性 | **100%** | ≥ 80% | ✅ |
| `strip_codeblock` 挽救率 | **23%** | — | 关键容错层 |

**关键发现**：
- 即使 prompt 禁止，LLM 仍经常输出 ` ```json {...} ``` ` — `strip_codeblock` 挽救了 23% 的调用
- `action=answer` 有 content 超长导致 JSON 截断的风险 → prompt 中需限制 `content≤300` 字
- LLM 值类型常见错误：`projection` 有时输出字符串而非数组；`status` 有时输出 JSON 布尔而非 `"ON"`/`"OFF"` → 后端需要做类型强制转换

**对架构的影响**：
- `LLMOutput.parse()` 需要实现 4 层容错解析：`direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback`
- `UpdateResolver.resolve()` 需要处理 path 格式宽容解析（如 `layers[0]` → `layers.0`）
- PromptBuilder 中需要限制 `action=answer` 的 content 长度

---

## V3 结论（详情见 [v3_result.md](v3_result.md)）

自定义递归组件方案验证：

| 指标 | 实测值 | 目标 | 状态 |
|------|--------|------|------|
| 总节点数 | 280 | 50+ | ✅ |
| 嵌套深度 | 4 层 | MAP→LAYER→CLASS→STYLE/LABEL | ✅ |
| ObjectCard 行数 | 140 行 | < 200 行 | ✅ |
| 控件映射 | 7 种 value_type | 全部覆盖 | ✅ |
| 构建 | 零错误零警告 | — | ✅ |
| 性能 | 需浏览器实测 | 首次渲染 < 200ms | ⚠️ 理论达标 |

**关键实现**：
- `ObjectCard.vue` 自引用递归渲染，无 `n-tree` 依赖
- `FieldEditor.vue` 按 `value_type` 映射到对应 Naive UI 控件
- `provide/inject` 实现全局展开/折叠
- 支持 "全部 / 仅必填" 显示模式过滤

**对架构的影响**：
- 前端采用自定义递归组件方案，不使用 `n-tree`
- 性能在 280 节点规模下预估达标，若实际数据增长可考虑延迟加载或虚拟滚动

---

## 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| LLM content 截断 | 中 | QA 回答不完整 | PromptBuilder 限制 content≤300 字；UpdateResolver 宽容解析 |
| 浏览器性能未达标 | 低 | 需要改用 n-tree | 已有 `v-once`、延迟加载、虚拟滚动等备选方案 |
| mappyfile L4 false positive | 中 | 自定义字段被误报 | L4 过滤器已设计（custom-allowed.json + object-fields.json） |

---

## 下一步行动

1. **搭建项目脚手架**：创建 `backend/`、`frontend/`、`electron/`、`tests/` 目录结构
2. **从核心模块开始**：`TemplateMapper` → `ConfigTree` → `ValidationPipeline`
3. **TDD 开发**：每个核心模块先写单元测试，再实现功能
4. **持续验证**：每完成一个模块，跑通对应的数据流场景
