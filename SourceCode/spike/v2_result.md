# V2 验证结论：LLM Prompt 输出稳定性

> 验证时间: 2026-06-06 21:43:20
> 模型: M3
> 测试用例: 10 个 × 3 次 = 30 次调用

---

## 一、核心指标

| 指标 | 数值 | 通过标准 | 状态 |
|------|------|----------|------|
| JSON 可解析率 | 28/30 = 93.3% | ≥ 90% | ✅ 通过 |
| action 正确率 | 22/28 = 78.6% (在可解析中) | ≥ 80% | ⚠️ 接近 |

## 二、按用例统计

| # | 问题 | 期望 | 可解析 | action 对 | 路径格式 | 值合理 |
|---|------|------|--------|-----------|----------|--------|
| 1 | 这个配置能发布 WMS 吗？... | answer | 100% | 100% | 100% | 100% |
| 2 | 把第一个图层的名称改成 highways... | update | 100% | 100% | 100% | 100% |
| 3 | 我想用 PostGIS 作为数据源... | update | 67% | 0% | 67% | 67% |
| 4 | 图层的颜色怎么设置？... | answer | 67% | 67% | 67% | 67% |
| 5 | 帮我添加一个叫 rivers 的图层... | update | 100% | 0% | 100% | 100% |
| 6 | WMS 的服务标题在哪里设置？... | answer | 100% | 100% | 100% | 100% |
| 7 | 这个配置有什么明显问题吗？... | answer | 100% | 100% | 100% | 100% |
| 8 | 帮我创建一个完整的 Mapfile... | question | 100% | 67% | 100% | 100% |
| 9 | 把图层的投影改成 EPSG:4326... | update | 100% | 100% | 100% | 100% |
| 10 | 把地图状态改成关闭... | update | 100% | 100% | 100% | 100% |

## 三、解析策略分布

| 策略 | 次数 | 说明 |
|------|------|------|
| direct_json | 21 | 直接 JSON 解析（最理想） |
| strip_codeblock | 7 | 去除 Markdown 代码块后解析 |
| all_failed | 2 | 全部失败，回退 |

## 四、错误类型分布

| 错误类型 | 次数 | 说明 |
|----------|------|------|
| json_parse | 2 | JSON 解析失败 |

## 五、延迟统计

| 指标 | 数值 |
|------|------|
| 平均延迟 | 19042 ms |
| 最大延迟 | 46309 ms |
| 总调用次数 | 30 |

## 六、详细原始记录

### Case 1: 这个配置能发布 WMS 吗？

- **Trial 1**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=20073ms
- **Trial 2**: ✅ action=`answer` paths=[] values=[] strategy=`strip_codeblock` latency=38685ms
- **Trial 3**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=19886ms

### Case 2: 把第一个图层的名称改成 highways

- **Trial 1**: ✅ action=`update` paths=['layers.0.name'] values=['highways'] strategy=`direct_json` latency=3886ms
- **Trial 2**: ✅ action=`update` paths=['layers.0.name'] values=['highways'] strategy=`direct_json` latency=4683ms
- **Trial 3**: ✅ action=`update` paths=['layers.0.name'] values=['highways'] strategy=`direct_json` latency=7104ms

### Case 3: 我想用 PostGIS 作为数据源

- **Trial 1**: ✅ action=`question` paths=[] values=[] strategy=`direct_json` latency=21472ms
- **Trial 2**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=20015ms
- **Trial 3**: ❌ json_parse: 助手返回的格式无法识别，已转为普通问答模式。 strategy=`all_failed` latency=19458ms
  - raw_preview: `{   "action": "question",   "content": "当前 roads 图层已经配置了 PostGIS 连接方式（connectiontype=POSTGIS），但缺少 DATA 参数（用于指定要查询的表名或 SQ...`

### Case 4: 图层的颜色怎么设置？

- **Trial 1**: ✅ action=`answer` paths=[] values=[] strategy=`strip_codeblock` latency=28848ms
- **Trial 2**: ✅ action=`answer` paths=[] values=[] strategy=`strip_codeblock` latency=20342ms
- **Trial 3**: ❌ json_parse: 助手返回的格式无法识别，已转为普通问答模式。 strategy=`all_failed` latency=17809ms
  - raw_preview: `{   "action": "answer",   "content": "在 MapServer 中，图层颜色的设置主要通过 CLASS 下的 STYLE 块来控制。根据要素类型（几何形状），可设置的颜色属性有所不同：\n\n1. **填...`

### Case 5: 帮我添加一个叫 rivers 的图层

- **Trial 1**: ✅ action=`question` paths=[] values=[] strategy=`direct_json` latency=12518ms
- **Trial 2**: ✅ action=`question` paths=[] values=[] strategy=`strip_codeblock` latency=18700ms
- **Trial 3**: ✅ action=`question` paths=[] values=[] strategy=`direct_json` latency=16576ms

### Case 6: WMS 的服务标题在哪里设置？

- **Trial 1**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=8816ms
- **Trial 2**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=11152ms
- **Trial 3**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=12099ms

### Case 7: 这个配置有什么明显问题吗？

- **Trial 1**: ✅ action=`answer` paths=[] values=[] strategy=`strip_codeblock` latency=36603ms
- **Trial 2**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=34726ms
- **Trial 3**: ✅ action=`answer` paths=[] values=[] strategy=`direct_json` latency=46309ms

### Case 8: 帮我创建一个完整的 Mapfile

- **Trial 1**: ✅ action=`answer` paths=[] values=[] strategy=`strip_codeblock` latency=40196ms
- **Trial 2**: ✅ action=`question` paths=[] values=[] strategy=`direct_json` latency=25268ms
- **Trial 3**: ✅ action=`question` paths=[] values=[] strategy=`strip_codeblock` latency=38654ms

### Case 9: 把图层的投影改成 EPSG:4326

- **Trial 1**: ✅ action=`update` paths=['layers.0.projection'] values=[['init=epsg:4326']] strategy=`direct_json` latency=12950ms
- **Trial 2**: ✅ action=`update` paths=['layers.0.projection'] values=[['init=epsg:4326']] strategy=`direct_json` latency=8998ms
- **Trial 3**: ✅ action=`update` paths=['layers.0.projection'] values=['init=epsg:4326'] strategy=`direct_json` latency=6219ms

### Case 10: 把地图状态改成关闭

- **Trial 1**: ✅ action=`update` paths=['status'] values=[False] strategy=`direct_json` latency=9429ms
- **Trial 2**: ✅ action=`update` paths=['status'] values=['OFF'] strategy=`direct_json` latency=4100ms
- **Trial 3**: ✅ action=`update` paths=['status'] values=['OFF'] strategy=`direct_json` latency=5685ms


## 七、Go / No-go 判定

| 条件 | 状态 | 说明 |
|------|------|------|
| JSON 可解析率 93.3% | ⚠️ Go with caution | 需增加 few-shot 或调整 prompt 结构 |

### 宽容解析层效果

- 直接解析成功: 21/30 (70.0%)
- 需要宽容解析: 9/30
- 宽容解析成功挽救: 7/9

**结论**: 宽容解析层有效减少了因格式微偏差导致的失败。

## 八、对生产代码的建议

1. **保留多层解析策略**: direct → strip_codeblock → brace_extract → json5 → fallback
2. **错误分类 + 友好回退**: 每种错误类型映射到用户友好的提示语
3. **日志记录原始输出**: 便于排查和迭代 prompt
4. **action 校验**: 无效的 action 值应安全回退为 answer 模式
5. **params_update 类型防御**: 确保是数组，每个元素有 path/value/reason