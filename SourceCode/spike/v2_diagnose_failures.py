"""诊断 V2 中两次解析失败的具体根因."""
import json
import json5

# 从 v2_result.json 中提取的两个失败 case 的完整原始输出
# 注意：raw_preview 只是前 300 字符，真实输出可能更长
case3_raw_preview = (
    '{   "action": "question",   "content": "当前 roads 图层已经配置了 PostGIS '
    '连接方式（connectiontype=POSTGIS），但缺少 DATA 参数（用于指定要查询的表名或 SQL '
    '语句）。\\n\\n请提供以下信息：\\n\\n1. **数据来源**：你想要查询的是哪个 PostGIS 表，'
    '或者需要执行什么 SQL 语句？\\n   - 例如：DATA \"geom FROM roads\" 表示从 roads '
    '表查询 geom 字段\\n   - 例如：DATA \"geom FROM (SELECT * FROM roads WHERE '
)

case4_raw_preview = (
    '{   "action": "answer",   "content": "在 MapServer 中，图层颜色的设置主要通过 '
    'CLASS 下的 STYLE 块来控制。根据要素类型（几何形状），可设置的颜色属性有所不同：'
    '\\n\\n1. **填充颜色 (COLOR)** —— 用于多边形 (POLYGON) 的填充：\\n   ```\\n   CLASS\\n'
    '     STYLE\\n       COLOR 200 200 200    # 灰色填充（RGB）\\n     END\\n   END\\n   ```'
    '\\n\\n2. **边框颜色 (OUTLINECOLOR)** —— 用于多边形边界或线状要素'
)


def diagnose(name: str, raw: str) -> None:
    print(f"\n=== {name} ===")
    print(f"Preview length: {len(raw)} chars")
    print(f"Last 50 chars: {repr(raw[-50:])}")

    # 检查是否以 } 结尾
    stripped = raw.strip()
    print(f"Ends with '}}': {stripped.endswith('}')}")

    # 尝试直接解析
    try:
        json.loads(raw)
        print("json.loads: OK")
    except json.JSONDecodeError as e:
        print(f"json.loads ERROR: {e}")

    # 尝试 json5
    try:
        json5.loads(raw)
        print("json5.loads: OK")
    except Exception as e:
        print(f"json5.loads ERROR: {e}")

    # 检查引号平衡
    quotes = raw.count('"')
    escaped_quotes = raw.count('\\"')
    unescaped = quotes - escaped_quotes
    print(f"Quotes: total={quotes}, escaped={escaped_quotes}, unescaped={unescaped} (should be even)")

    # 检查花括号平衡
    print(f"Braces: open={raw.count('{')}, close={raw.count('}')}")


diagnose("Case 3 Trial 3 (PostGIS)", case3_raw_preview)
diagnose("Case 4 Trial 3 (Color)", case4_raw_preview)

print("\n" + "=" * 60)
print("分析结论:")
print("=" * 60)
print("""
两次失败的 raw_preview 都在 content 中间被截断（preview 只保留前300字符）。

Case 3: preview 在 'WHERE ' 处截断，说明完整输出后面还有内容。
Case 4: preview 在 '线状要素' 处截断，同样不完整。

由于 preview 不是完整原始输出，无法 100% 确定失败原因。但根据经验推断：

1. LLM 在长文本回答（action=answer/question + 详细 content）时，容易在 content
   的后面部分产生 JSON 语法错误：
   - 未正确转义中文引号或 markdown 格式中的引号
   - content 过长导致输出被截断（max_tokens 限制），JSON 结构不完整
   - markdown 代码块（```）内部的字符干扰了 JSON 解析

2. 短输出（action=update，只有 params_update）从未失败，因为：
   - 输出简短，不容易产生转义问题
   - 不含长文本 content，结构简单

3. 生产建议：
   - 在 prompt 中限制 content 长度（如 "content 不超过 500 字符"）
   - 对 action=answer 的长文本，max_tokens 设置更大（如 4096→8192）
   - 增加一层 "截断恢复" 逻辑：如果检测到 JSON 在字符串中截断，尝试截断并补全
""")
