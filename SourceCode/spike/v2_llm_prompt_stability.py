"""V2 Spike: LLM Prompt 输出稳定性验证

目标：验证简化版 PromptBuilder 能否让 Claude 稳定输出正确格式的结构化 JSON，
      以及当输出异常时，宽容解析层能否优雅降级并转化为用户友好的提示。

设计重点（借鉴 GISTaskAgent 的 diagnosis.py 模式）：
    - 多层解析策略：直接解析 → 去除代码块 → 平衡花括号提取 → json5 宽容解析
    - 错误分类 + 友好回退：不是抛异常，而是返回结构化错误信息
    - 统计稳定性指标

环境要求：
    - anthropic SDK (已安装: 0.104.1)
    - json5 (已安装)
    - config/config.json 中有 API key
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic
import json5

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)["llm"]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """LLM输出解析结果 —— 成功或失败都封装在此，不抛异常。"""

    success: bool
    data: Optional[dict] = None
    error_type: Optional[str] = None
    error_detail: Optional[str] = None
    user_friendly_message: Optional[str] = None
    raw_preview: str = ""
    parse_strategy: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class TrialResult:
    """单次试验结果。"""

    trial: int
    parse_ok: bool
    action: Optional[str] = None
    paths: List[str] = field(default_factory=list)
    values: List[Any] = field(default_factory=list)
    parse_result: Optional[ParseResult] = None
    latency_ms: float = 0.0


@dataclass
class TestCaseResult:
    """一个测试用例（多次试验）的汇总结果。"""

    case_id: int
    question: str
    expected_action: str
    trials: List[TrialResult] = field(default_factory=list)
    parse_success_rate: float = 0.0
    action_accuracy: float = 0.0
    path_format_rate: float = 0.0
    value_type_reasonable: float = 0.0


# ---------------------------------------------------------------------------
# LLM Client (Simplified)
# ---------------------------------------------------------------------------

class LLMClient:
    """简化版 LLM 客户端，只保留核心调用逻辑。"""

    def __init__(self, cfg: dict) -> None:
        self._client = anthropic.Anthropic(
            base_url=cfg["base_url"],
            api_key=cfg["auth_key"],
        )
        self._model = cfg["model_name"]

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
        """单次调用，返回原始文本（已处理 ThinkingBlock）。"""
        response = self._client.messages.create(
            model=self._model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=temperature,
            max_tokens=2048,
        )
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text  # type: ignore[union-attr]
        raise RuntimeError("No text content in LLM response")


# ---------------------------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一个 MapServer 配置助手。用户正在交互式编辑 Mapfile 配置。

## 回复格式（严格 JSON）
你必须用 JSON 格式回复，不要包含任何其他内容（不要 Markdown 代码块标记、不要解释性文字）：
{
  "action": "answer" | "update" | "question",
  "content": "回答内容（当 action=answer 时必填）",
  "params_update": [
    {"path": "参数扁平路径，如 layers.0.name", "value": "新值", "reason": "修改原因"}
  ]
}

## 规则
1. action 选择：
   - "answer"：用户问的是知识性问题，不需要修改配置
   - "update"：用户要求修改配置，需要在 params_update 中给出具体变更
   - "question"：信息不足，需要反问用户（如缺少数据源路径、坐标系等关键信息）

2. 参数路径格式：
   - 使用点号分隔，数组用数字索引
   - 示例：layers.0.name, layers.0.connectiontype, web.metadata.wms_title

3. 值的类型必须正确：
   - 字符串：用引号，如 "highways"
   - 数字：不用引号，如 4326
   - 布尔：用 true / false
   - 数组：用 [ ]，如投影 ["init=epsg:4326"]，颜色 [255, 0, 0]
   - Extent：[minx, miny, maxx, maxy]

4. 只修改你确定的参数。不确定的不要包含在 params_update 中。

5. 如果要添加新图层/类/样式，在 params_update 中使用正确的数组索引。
   如添加第一个图层：path="layers.0"，value 为完整对象（包含 __type__: "layer"）。"""


def build_user_prompt(question: str, context: str) -> str:
    return f"""## 当前配置
{context}

## 用户问题
{question}

请根据当前配置和用户问题，按上述格式回复 JSON。"""


# ---------------------------------------------------------------------------
# LLM Output Parser —— 核心：宽容解析 + 友好回退
# ---------------------------------------------------------------------------

class LLMOutputParser:
    """解析 LLM 结构化 JSON 输出，多层容错，优雅降级。

    借鉴 GISTaskAgent diagnosis.py 的 _extract_json_block + json5 模式，
    增加更细粒度的错误分类和用户友好回退。
    """

    # 用户友好的错误消息模板
    _FRIENDLY_MESSAGES = {
        "json_parse": "助手返回的格式无法识别，已转为普通问答模式。",
        "schema_missing": "助手返回的数据不完整，缺少必要字段。已记录此问题。",
        "schema_invalid": "助手返回了意外的操作类型，已按最保守方式处理。",
        "empty_response": "助手没有返回有效内容，请重试。",
        "unknown": "遇到未知问题，已切换为安全模式。",
    }

    # JSON Schema 要求
    _REQUIRED_FIELDS = ("action",)
    _VALID_ACTIONS = {"answer", "update", "question"}

    def parse(self, raw: str) -> ParseResult:
        """主入口：尝试多层解析策略，全部失败时返回友好回退。"""
        if not raw or not raw.strip():
            return self._make_fallback(
                raw, "empty_response", "LLM 返回了空内容", strategy="empty_check"
            )

        # 策略1: 直接解析（最精确）
        result = self._try_direct(raw)
        if result:
            return self._validate_schema(result, raw, "direct_json")

        # 策略2: 去除 Markdown 代码块标记后解析
        result = self._try_strip_code_block(raw)
        if result:
            return self._validate_schema(result, raw, "strip_codeblock")

        # 策略3: 从平衡花括号中提取 JSON
        result = self._try_brace_extraction(raw)
        if result:
            return self._validate_schema(result, raw, "brace_extract")

        # 策略4: json5 宽容解析（bare keys, single quotes, trailing commas）
        result = self._try_json5(raw)
        if result:
            return self._validate_schema(result, raw, "json5_tolerant")

        # 策略5: 全部失败 → 友好回退
        return self._make_fallback(
            raw,
            "json_parse",
            "所有解析策略均失败（direct/strip_codeblock/brace_extract/json5）",
            strategy="all_failed",
        )

    # ---- 解析策略 ----------------------------------------------------------

    def _try_direct(self, raw: str) -> Optional[dict]:
        try:
            return json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            return None

    def _try_strip_code_block(self, raw: str) -> Optional[dict]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

    def _try_brace_extraction(self, raw: str) -> Optional[dict]:
        """从文本中找到第一个平衡的花括号对。"""
        start = raw.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i, ch in enumerate(raw[start:], start=start):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not in_string:
                in_string = True
            elif ch == '"' and in_string:
                in_string = False
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[start : i + 1])
                        except (json.JSONDecodeError, ValueError):
                            return None
        return None

    def _try_json5(self, raw: str) -> Optional[dict]:
        """使用 json5 做宽容解析。"""
        # 先尝试提取最可能的 JSON 块
        extracted = self._extract_json_block(raw)
        try:
            return json5.loads(extracted)
        except (ValueError, TypeError):
            return None

    def _extract_json_block(self, raw: str) -> str:
        """提取 JSON 内容：优先代码块，再平衡花括号。"""
        code_match = re.search(
            r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", raw, flags=re.IGNORECASE
        )
        if code_match:
            return code_match.group(1).strip()

        start = raw.find("{")
        if start == -1:
            return raw.strip()

        depth = 0
        in_string = False
        escape = False
        for i, ch in enumerate(raw[start:], start=start):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not in_string:
                in_string = True
            elif ch == '"' and in_string:
                in_string = False
            elif not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return raw[start : i + 1]
        return raw[start:].strip()

    # ---- 校验 -------------------------------------------------------------

    def _validate_schema(self, parsed: dict, raw: str, strategy: str) -> ParseResult:
        """校验解析出的 dict 是否符合我们的 schema。"""
        preview = raw[:300].replace("\n", " ")

        # 检查必填字段
        for field in self._REQUIRED_FIELDS:
            if field not in parsed:
                return self._make_fallback(
                    raw,
                    "schema_missing",
                    f"缺少必填字段: {field}",
                    strategy=f"{strategy}_missing_{field}",
                )

        # 检查 action 合法性
        action = parsed.get("action")
        if action not in self._VALID_ACTIONS:
            return self._make_fallback(
                raw,
                "schema_invalid",
                f"无效的 action: {action!r}（期望: answer/update/question）",
                strategy=f"{strategy}_invalid_action",
            )

        # 检查 params_update 类型
        params_update = parsed.get("params_update", [])
        if params_update is not None and not isinstance(params_update, list):
            return self._make_fallback(
                raw,
                "schema_invalid",
                f"params_update 必须是数组，当前类型: {type(params_update).__name__}",
                strategy=f"{strategy}_invalid_params_type",
            )

        return ParseResult(
            success=True,
            data=parsed,
            raw_preview=preview,
            parse_strategy=strategy,
        )

    def _make_fallback(
        self,
        raw: str,
        error_type: str,
        error_detail: str,
        strategy: str,
    ) -> ParseResult:
        """构建友好回退结果。"""
        preview = raw[:300].replace("\n", " ") if raw else "(empty)"
        friendly = self._FRIENDLY_MESSAGES.get(
            error_type, self._FRIENDLY_MESSAGES["unknown"]
        )
        return ParseResult(
            success=False,
            error_type=error_type,
            error_detail=error_detail,
            user_friendly_message=friendly,
            raw_preview=preview,
            parse_strategy=strategy,
        )


# ---------------------------------------------------------------------------
# Value Type Reasonableness Checker
# ---------------------------------------------------------------------------

def check_value_reasonable(value: Any) -> tuple[bool, str]:
    """检查值类型是否合理（粗略启发式）。"""
    if value is None:
        return True, "null"
    if isinstance(value, bool):
        return True, "boolean"
    if isinstance(value, (int, float)):
        return True, "number"
    if isinstance(value, str):
        return True, "string"
    if isinstance(value, list):
        if len(value) == 3 and all(isinstance(v, int) for v in value):
            return True, "color_rgb"
        if (
            len(value) == 4
            and all(isinstance(v, (int, float)) for v in value)
        ):
            return True, "extent"
        if all(isinstance(v, str) for v in value):
            return True, "string_array"
        return True, "array"
    if isinstance(value, dict):
        return True, "object"
    return False, f"unknown_type_{type(value).__name__}"


# ---------------------------------------------------------------------------
# Test Runner
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "id": 1,
        "question": "这个配置能发布 WMS 吗？",
        "expected_action": "answer",
        "notes": "纯知识问答，无配置修改",
    },
    {
        "id": 2,
        "question": "把第一个图层的名称改成 highways",
        "expected_action": "update",
        "notes": "路径格式: layers.0.name",
    },
    {
        "id": 3,
        "question": "我想用 PostGIS 作为数据源",
        "expected_action": "update",
        "notes": "多字段关联: connectiontype + connection",
    },
    {
        "id": 4,
        "question": "图层的颜色怎么设置？",
        "expected_action": "answer",
        "notes": "知识性问题，LLM应教用户参数路径",
    },
    {
        "id": 5,
        "question": "帮我添加一个叫 rivers 的图层",
        "expected_action": "update",
        "notes": "添加数组元素",
    },
    {
        "id": 6,
        "question": "WMS 的服务标题在哪里设置？",
        "expected_action": "answer",
        "notes": "METADATA 路径知识",
    },
    {
        "id": 7,
        "question": "这个配置有什么明显问题吗？",
        "expected_action": "answer",
        "notes": "基于上下文的分析",
    },
    {
        "id": 8,
        "question": "帮我创建一个完整的 Mapfile",
        "expected_action": "question",
        "notes": "空/不完整上下文，应反问",
    },
    {
        "id": 9,
        "question": "把图层的投影改成 EPSG:4326",
        "expected_action": "update",
        "notes": "PROJECTION 值格式应为数组",
    },
    {
        "id": 10,
        "question": "把地图状态改成关闭",
        "expected_action": "update",
        "notes": "布尔/enum 值转换: 关闭 -> OFF",
    },
]

CONTEXT = """MAP 名称: test_map
状态: STATUS ON
范围: EXTENT -180 -90 180 90
投影: PROJECTION "init=epsg:3857" END
背景色: IMAGECOLOR 255 255 255

图层列表:
- LAYER[0]: name="roads", type=POLYGON, connectiontype=POSTGIS, connection="host=localhost dbname=gis user=postgres"
  - CLASS[0]: name="default"
    - STYLE[0]: color=[200, 200, 200], outlinecolor=[0, 0, 0]

WEB 配置:
- metadata: wms_title="My Test Map", wms_enable_request="*"
"""


def run_single_trial(
    client: LLMClient,
    parser: LLMOutputParser,
    question: str,
    trial_num: int,
) -> TrialResult:
    """跑一次试验。"""
    user_prompt = build_user_prompt(question, CONTEXT)

    start = time.perf_counter()
    try:
        raw = client.chat(SYSTEM_PROMPT, user_prompt, temperature=0.1)
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return TrialResult(
            trial=trial_num,
            parse_ok=False,
            parse_result=ParseResult(
                success=False,
                error_type="api_error",
                error_detail=str(e),
                user_friendly_message=f"API 调用失败: {e}",
                raw_preview="",
                parse_strategy="api_call",
            ),
            latency_ms=latency,
        )

    latency = (time.perf_counter() - start) * 1000
    parse_result = parser.parse(raw)

    if parse_result.success:
        data = parse_result.data or {}
        action = data.get("action")
        updates = data.get("params_update", []) or []
        paths = [u.get("path", "") for u in updates if isinstance(u, dict)]
        values = [u.get("value") for u in updates if isinstance(u, dict)]
        return TrialResult(
            trial=trial_num,
            parse_ok=True,
            action=action,
            paths=paths,
            values=values,
            parse_result=parse_result,
            latency_ms=latency,
        )
    else:
        return TrialResult(
            trial=trial_num,
            parse_ok=False,
            parse_result=parse_result,
            latency_ms=latency,
        )


def check_path_format(paths: List[str]) -> float:
    """检查路径格式是否正确（点号+数字索引）。"""
    if not paths:
        return 1.0  # 无路径 = 无错误
    ok = 0
    for p in paths:
        # 允许空字符串（缺失path字段）
        if not p:
            continue
        # 检查基本格式：字母/数字/点/下划线
        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\.[0-9]+)*$", p):
            ok += 1
    return ok / len(paths)


def check_values_reasonable(values: List[Any]) -> float:
    """检查值类型合理性。"""
    if not values:
        return 1.0
    ok = sum(1 for v in values if check_value_reasonable(v)[0])
    return ok / len(values)


def run_all_tests(trials_per_case: int = 3) -> List[TestCaseResult]:
    """运行全部测试用例。"""
    cfg = load_config()
    client = LLMClient(cfg)
    parser = LLMOutputParser()

    results: List[TestCaseResult] = []

    for case in TEST_CASES:
        case_id = case["id"]
        question = case["question"]
        expected_action = case["expected_action"]
        notes = case.get("notes", "")

        print(f"\n{'='*60}")
        print(f"[Case {case_id}] {question}")
        print(f"    期望: {expected_action} | {notes}")
        print(f"{'='*60}")

        trials: List[TrialResult] = []
        parse_ok_count = 0
        action_correct_count = 0
        path_ok_total = 0.0
        value_ok_total = 0.0

        for t in range(1, trials_per_case + 1):
            print(f"  Trial {t}/{trials_per_case} ...", end=" ", flush=True)
            trial = run_single_trial(client, parser, question, t)
            trials.append(trial)

            if trial.parse_ok:
                parse_ok_count += 1
                if trial.action == expected_action:
                    action_correct_count += 1
                path_rate = check_path_format(trial.paths)
                value_rate = check_values_reasonable(trial.values)
                path_ok_total += path_rate
                value_ok_total += value_rate
                print(
                    f"✓ action={trial.action} paths={trial.paths} "
                    f"latency={trial.latency_ms:.0f}ms strategy={trial.parse_result.parse_strategy if trial.parse_result else '?'}")
            else:
                pr = trial.parse_result
                print(
                    f"✗ {pr.error_type}: {pr.user_friendly_message} "
                    f"strategy={pr.parse_strategy} latency={trial.latency_ms:.0f}ms"
                )

            # 避免过快请求
            if t < trials_per_case:
                time.sleep(0.5)

        total = trials_per_case
        result = TestCaseResult(
            case_id=case_id,
            question=question,
            expected_action=expected_action,
            trials=trials,
            parse_success_rate=parse_ok_count / total,
            action_accuracy=action_correct_count / total if parse_ok_count > 0 else 0.0,
            path_format_rate=path_ok_total / total if parse_ok_count > 0 else 0.0,
            value_type_reasonable=value_ok_total / total if parse_ok_count > 0 else 0.0,
        )
        results.append(result)

        # 用例间延迟，避免rate limit
        if case_id < len(TEST_CASES):
            time.sleep(1.0)

    return results


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

class ResultEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, ParseResult):
            return o.to_dict()
        if isinstance(o, (TrialResult, TestCaseResult)):
            return asdict(o)
        return super().default(o)


def generate_json_report(results: List[TestCaseResult], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2, cls=ResultEncoder)
    print(f"\n📄 JSON 报告已保存: {path}")


def generate_markdown_report(results: List[TestCaseResult], path: Path) -> None:
    total_trials = sum(len(r.trials) for r in results)
    parse_ok_total = sum(1 for r in results for t in r.trials if t.parse_ok)
    action_ok_total = sum(
        1 for r in results for t in r.trials
        if t.parse_ok and t.action == r.expected_action
    )

    # 解析策略统计
    strategy_counts: Dict[str, int] = {}
    error_type_counts: Dict[str, int] = {}
    for r in results:
        for t in r.trials:
            if t.parse_result:
                s = t.parse_result.parse_strategy
                strategy_counts[s] = strategy_counts.get(s, 0) + 1
                if not t.parse_ok and t.parse_result.error_type:
                    e = t.parse_result.error_type
                    error_type_counts[e] = error_type_counts.get(e, 0) + 1

    # 延迟统计
    latencies = [t.latency_ms for r in results for t in r.trials]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0

    lines = [
        "# V2 验证结论：LLM Prompt 输出稳定性",
        "",
        f"> 验证时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 模型: {load_config()['model_name']}",
        f"> 测试用例: {len(results)} 个 × 3 次 = {total_trials} 次调用",
        "",
        "---",
        "",
        "## 一、核心指标",
        "",
        f"| 指标 | 数值 | 通过标准 | 状态 |",
        f"|------|------|----------|------|",
        f"| JSON 可解析率 | {parse_ok_total}/{total_trials} = {parse_ok_total/total_trials*100:.1f}% | ≥ 90% | {'✅ 通过' if parse_ok_total/total_trials >= 0.9 else '⚠️ 接近' if parse_ok_total/total_trials >= 0.7 else '❌ 未通过'} |",
        f"| action 正确率 | {action_ok_total}/{parse_ok_total} = {action_ok_total/parse_ok_total*100:.1f}% (在可解析中) | ≥ 80% | {'✅ 通过' if parse_ok_total > 0 and action_ok_total/parse_ok_total >= 0.8 else '⚠️ 接近' if parse_ok_total > 0 and action_ok_total/parse_ok_total >= 0.7 else '❌ 未通过'} |",
    ]

    # 按用例统计
    lines.extend([
        "",
        "## 二、按用例统计",
        "",
        "| # | 问题 | 期望 | 可解析 | action 对 | 路径格式 | 值合理 |",
        "|---|------|------|--------|-----------|----------|--------|",
    ])
    for r in results:
        ps = f"{r.parse_success_rate*100:.0f}%"
        aa = f"{r.action_accuracy*100:.0f}%" if r.parse_success_rate > 0 else "N/A"
        pf = f"{r.path_format_rate*100:.0f}%" if r.parse_success_rate > 0 else "N/A"
        vr = f"{r.value_type_reasonable*100:.0f}%" if r.parse_success_rate > 0 else "N/A"
        lines.append(
            f"| {r.case_id} | {r.question[:30]}... | {r.expected_action} | {ps} | {aa} | {pf} | {vr} |"
        )

    # 解析策略统计
    lines.extend([
        "",
        "## 三、解析策略分布",
        "",
        "| 策略 | 次数 | 说明 |",
        "|------|------|------|",
    ])
    for s, c in sorted(strategy_counts.items(), key=lambda x: -x[1]):
        desc = {
            "direct_json": "直接 JSON 解析（最理想）",
            "strip_codeblock": "去除 Markdown 代码块后解析",
            "brace_extract": "从平衡花括号提取",
            "json5_tolerant": "json5 宽容解析",
            "all_failed": "全部失败，回退",
            "empty_check": "空内容",
            "api_call": "API 调用",
        }.get(s, s)
        lines.append(f"| {s} | {c} | {desc} |")

    # 错误类型统计
    if error_type_counts:
        lines.extend([
            "",
            "## 四、错误类型分布",
            "",
            "| 错误类型 | 次数 | 说明 |",
            "|----------|------|------|",
        ])
        for e, c in sorted(error_type_counts.items(), key=lambda x: -x[1]):
            desc = {
                "json_parse": "JSON 解析失败",
                "schema_missing": "缺少必填字段",
                "schema_invalid": "字段值无效",
                "api_error": "API 调用异常",
                "empty_response": "空响应",
            }.get(e, e)
            lines.append(f"| {e} | {c} | {desc} |")

    # 延迟统计
    lines.extend([
        "",
        "## 五、延迟统计",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 平均延迟 | {avg_latency:.0f} ms |",
        f"| 最大延迟 | {max_latency:.0f} ms |",
        f"| 总调用次数 | {total_trials} |",
    ])

    # 详细原始记录
    lines.extend([
        "",
        "## 六、详细原始记录",
        "",
    ])
    for r in results:
        lines.append(f"### Case {r.case_id}: {r.question}")
        lines.append("")
        for t in r.trials:
            pr = t.parse_result
            if t.parse_ok:
                lines.append(
                    f"- **Trial {t.trial}**: ✅ action=`{t.action}` paths={t.paths} "
                    f"values={t.values} strategy=`{pr.parse_strategy}` latency={t.latency_ms:.0f}ms"
                )
            else:
                lines.append(
                    f"- **Trial {t.trial}**: ❌ {pr.error_type}: {pr.user_friendly_message} "
                    f"strategy=`{pr.parse_strategy}` latency={t.latency_ms:.0f}ms"
                )
                lines.append(f"  - raw_preview: `{pr.raw_preview[:120]}...`")
        lines.append("")

    # 结论
    parse_rate = parse_ok_total / total_trials if total_trials > 0 else 0
    action_rate = action_ok_total / parse_ok_total if parse_ok_total > 0 else 0

    lines.extend([
        "",
        "## 七、Go / No-go 判定",
        "",
        f"| 条件 | 状态 | 说明 |",
        f"|------|------|------|",
    ])

    if parse_rate >= 0.9 and action_rate >= 0.8:
        verdict = "✅ Go"
        detail = "prompt 设计可行，进入微调阶段"
    elif parse_rate >= 0.7:
        verdict = "⚠️ Go with caution"
        detail = "需增加 few-shot 或调整 prompt 结构"
    else:
        verdict = "❌ No-go"
        detail = "prompt 框架需重新设计"

    lines.append(f"| JSON 可解析率 {parse_rate*100:.1f}% | {verdict} | {detail} |")
    lines.append("")

    # 宽容解析层效果
    direct_count = strategy_counts.get("direct_json", 0)
    fallback_needed = total_trials - direct_count
    fallback_succeeded = sum(
        1 for r in results for t in r.trials
        if t.parse_ok and t.parse_result and t.parse_result.parse_strategy != "direct_json"
    )
    lines.extend([
        "### 宽容解析层效果",
        "",
        f"- 直接解析成功: {direct_count}/{total_trials} ({direct_count/total_trials*100:.1f}%)",
        f"- 需要宽容解析: {fallback_needed}/{total_trials}",
        f"- 宽容解析成功挽救: {fallback_succeeded}/{fallback_needed}",
        "",
        "**结论**: " + (
            "宽容解析层有效减少了因格式微偏差导致的失败。"
            if fallback_succeeded > 0 else
            "LLM 输出格式足够规范，宽容解析层未触发。"
        ),
        "",
        "## 八、对生产代码的建议",
        "",
        "1. **保留多层解析策略**: direct → strip_codeblock → brace_extract → json5 → fallback",
        "2. **错误分类 + 友好回退**: 每种错误类型映射到用户友好的提示语",
        "3. **日志记录原始输出**: 便于排查和迭代 prompt",
        "4. **action 校验**: 无效的 action 值应安全回退为 answer 模式",
        "5. **params_update 类型防御**: 确保是数组，每个元素有 path/value/reason",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"📄 Markdown 报告已保存: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 70)
    print("V2 Spike: LLM Prompt 输出稳定性验证")
    print("=" * 70)
    print(f"Config: {CONFIG_PATH}")
    print(f"Model:  {load_config()['model_name']}")
    print(f"Cases:  {len(TEST_CASES)} × 3 trials = {len(TEST_CASES) * 3} API calls")
    print("=" * 70)

    results = run_all_tests(trials_per_case=3)

    # 汇总
    total_trials = sum(len(r.trials) for r in results)
    parse_ok = sum(1 for r in results for t in r.trials if t.parse_ok)
    action_ok = sum(
        1 for r in results for t in r.trials
        if t.parse_ok and t.action == r.expected_action
    )

    print("\n" + "=" * 70)
    print("汇总结果")
    print("=" * 70)
    print(f"总调用次数:     {total_trials}")
    print(f"JSON 可解析:    {parse_ok} ({parse_ok/total_trials*100:.1f}%)")
    print(f"action 正确:    {action_ok} (在可解析中 {action_ok/parse_ok*100:.1f}%)")
    print("=" * 70)

    # 生成报告
    spike_dir = Path(__file__).parent
    generate_json_report(results, spike_dir / "v2_result.json")
    generate_markdown_report(results, spike_dir / "v2_result.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
