"""
V1: mappyfile validate() 行为摸底

目标：摸清 mappyfile.validate(mf, version=8.4) 的接受边界，
形成隐式要求清单，指导 to_mappyfile_dict() 的实现。

覆盖维度（10个）：
1. 基本类型   2. 颜色   3. 投影   4. Enum大小写
5. 嵌套对象   6. 数组字段   7. METADATA   8. 缺字段
9. Extent   10. 自定义字段

运行方式：
    cd SourceCode
    "/c/Users/PC/.conda/envs/gis-agent/python" spike/v1_mappyfile_validate.py
"""

import mappyfile
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TestResult:
    description: str
    category: str                    # 所属维度
    passed: Optional[bool] = None    # validate 是否通过
    dumps_ok: bool = False           # dumps() 是否成功
    errors: list = field(default_factory=list)
    exception: Optional[str] = None
    dumps_output: str = ""
    note: str = ""


RESULTS: list[TestResult] = []


def run_test(description: str, category: str, mf: dict, expect_validate_pass: Optional[bool] = None):
    """
    运行单个测试用例。
    expect_validate_pass: True=期望通过, False=期望失败, None=只观察不断言
    """
    result = TestResult(description=description, category=category)

    # --- 1. dumps() 测试 ---
    try:
        dumps_output = mappyfile.dumps(mf)
        result.dumps_ok = True
        result.dumps_output = dumps_output[:200].replace("\n", " ")
    except Exception as e:
        result.dumps_ok = False
        result.exception = f"dumps: {type(e).__name__}: {e}"

    # --- 2. validate() 测试 ---
    try:
        errors = mappyfile.validate(mf, version=8.4)
        result.passed = len(errors) == 0
        result.errors = [str(e) for e in errors[:3]]  # 最多保留3条
    except Exception as e:
        result.passed = False
        result.exception = f"validate: {type(e).__name__}: {e}"

    # --- 3. 与期望对比 ---
    status = "?"
    if expect_validate_pass is not None:
        if result.passed == expect_validate_pass:
            status = "✓"
        else:
            status = "✗"
            result.note = f"期望 validate={'通过' if expect_validate_pass else '失败'}，实际={'通过' if result.passed else '失败'}"
    else:
        status = "✓" if result.passed else "○"  # ○ 表示"观察到失败，但未必是坏事"

    icon = "💥" if result.exception else status
    print(f"{icon} [{category}] {description}")
    if result.exception:
        print(f"    异常: {result.exception}")
    if result.errors:
        print(f"    错误: {result.errors}")
    if result.dumps_output:
        print(f"    dumps: {result.dumps_output}...")
    if result.note:
        print(f"    注意: {result.note}")

    RESULTS.append(result)
    return result


# ============================================================
# 测试用例定义
# ============================================================

print("=" * 70)
print("mappyfile validate() 行为摸底 — 开始运行")
print(f"mappyfile 版本: {mappyfile.__version__}")
print("=" * 70)

# --------------------------------------------------
# 维度 1: 基本类型 (string, int, float, boolean)
# --------------------------------------------------
print("\n【维度 1】基本类型")

run_test(
    "name 字符串", "基本类型",
    {"__type__": "map", "name": "test"}, True)

run_test(
    "size 整数", "基本类型",
    {"__type__": "map", "name": "test", "size": [800, 600]}, True)

run_test(
    "resolution float", "基本类型",
    {"__type__": "map", "name": "test", "resolution": 72.0}, True)

run_test(
    "status 布尔 true", "基本类型",
    {"__type__": "map", "name": "test", "status": True}, True)

run_test(
    "status 布尔 false", "基本类型",
    {"__type__": "map", "name": "test", "status": False}, True)

run_test(
    "status 字符串 'ON' (Mapfile 语法)", "基本类型",
    {"__type__": "map", "name": "test", "status": "ON"}, None)

run_test(
    "status 字符串 'OFF'", "基本类型",
    {"__type__": "map", "name": "test", "status": "OFF"}, None)

run_test(
    "size 字符串 '800 600'", "基本类型",
    {"__type__": "map", "name": "test", "size": "800 600"}, None)

# --------------------------------------------------
# 维度 2: 颜色 (RGB 数组 vs 字符串 vs hex)
# --------------------------------------------------
print("\n【维度 2】颜色")

run_test(
    "imagecolor RGB 数组 [255,0,0]", "颜色",
    {"__type__": "map", "name": "test", "imagecolor": [255, 0, 0]}, True)

run_test(
    "imagecolor RGB 数组 [0,0,255]", "颜色",
    {"__type__": "map", "name": "test", "imagecolor": [0, 0, 255]}, True)

run_test(
    "imagecolor 字符串 '255 0 0'", "颜色",
    {"__type__": "map", "name": "test", "imagecolor": "255 0 0"}, None)

run_test(
    "imagecolor hex '#FF0000'", "颜色",
    {"__type__": "map", "name": "test", "imagecolor": "#FF0000"}, None)

run_test(
    "style color RGB 数组", "颜色",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "styles": [{"__type__": "style", "color": [255, 0, 0]}]}]}]}, True)

run_test(
    "style color 字符串 '255 0 0'", "颜色",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "styles": [{"__type__": "style", "color": "255 0 0"}]}]}]}, None)

run_test(
    "outlinecolor RGB 数组", "颜色",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "styles": [{"__type__": "style", "outlinecolor": [0, 0, 0]}]}]}]}, True)

# --------------------------------------------------
# 维度 3: 投影 (数组 vs 字符串)
# --------------------------------------------------
print("\n【维度 3】投影")

run_test(
    "projection 数组 ['init=epsg:3857']", "投影",
    {"__type__": "map", "name": "test", "projection": ["init=epsg:3857"]}, True)

run_test(
    "projection 数组多元素 ['proj=merc', 'datum=WGS84']", "投影",
    {"__type__": "map", "name": "test", "projection": ["proj=merc", "datum=WGS84"]}, True)

run_test(
    "projection 字符串 'init=epsg:3857'", "投影",
    {"__type__": "map", "name": "test", "projection": "init=epsg:3857"}, None)

run_test(
    "LAYER 层 projection 数组", "投影",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "projection": ["init=epsg:4326"]}]}, True)

# --------------------------------------------------
# 维度 4: Enum 值大小写
# --------------------------------------------------
print("\n【维度 4】Enum 大小写")

run_test(
    "connectiontype POSTGIS 大写", "Enum",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "connectiontype": "POSTGIS", "connection": "host=localhost"}]}, True)

run_test(
    "connectiontype postgis 小写", "Enum",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "connectiontype": "postgis", "connection": "host=localhost"}]}, None)

run_test(
    "type POLYGON 大写", "Enum",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON"}]}, True)

run_test(
    "type polygon 小写", "Enum",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "polygon"}]}, None)

run_test(
    "type POINT 大写", "Enum",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POINT"}]}, True)

run_test(
    "type LINE 大写", "Enum",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "LINE"}]}, True)

# --------------------------------------------------
# 维度 5: 嵌套对象结构 (LAYER / CLASS / STYLE / LABEL)
# --------------------------------------------------
print("\n【维度 5】嵌套对象")

run_test(
    "最小 MAP (只有 name)", "嵌套对象",
    {"__type__": "map", "name": "test"}, True)

run_test(
    "LAYER 最小结构", "嵌套对象",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON"}]}, True)

run_test(
    "LAYER 缺 type", "嵌套对象",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1"}]}, False)

run_test(
    "CLASS 嵌套", "嵌套对象",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class", "name": "c1"}]}]}, True)

run_test(
    "STYLE 嵌套", "嵌套对象",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "styles": [{"__type__": "style", "color": [255, 0, 0]}]}]}]}, True)

run_test(
    "LABEL 嵌套 (sibling to STYLE)", "嵌套对象",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "labels": [{"__type__": "label", "text": "[name]"}]}]}]}, True)

run_test(
    "CLASS + STYLE + LABEL 完整链", "嵌套对象",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class", "name": "c1",
                              "styles": [{"__type__": "style", "color": [255, 0, 0]}],
                              "labels": [{"__type__": "label", "text": "[name]"}]}]}]}, True)

# --------------------------------------------------
# 维度 6: 数组字段 (单元素能否省略列表)
# --------------------------------------------------
print("\n【维度 6】数组字段")

run_test(
    "layers 是列表", "数组字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON"}]}, True)

run_test(
    "layers 单元素非列表 (直接 dict)", "数组字段",
    {"__type__": "map", "name": "test",
     "layers": {"__type__": "layer", "name": "l1", "type": "POLYGON"}}, None)

run_test(
    "classes 是列表", "数组字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class", "name": "c1"}]}]}, True)

run_test(
    "classes 单元素非列表", "数组字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": {"__type__": "class", "name": "c1"}}]}, None)

run_test(
    "styles 是列表", "数组字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "styles": [{"__type__": "style", "color": [255, 0, 0]}]}]}]}, True)

run_test(
    "styles 单元素非列表", "数组字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "styles": {"__type__": "style", "color": [255, 0, 0]}}]}]}, None)

# --------------------------------------------------
# 维度 7: METADATA
# --------------------------------------------------
print("\n【维度 7】METADATA")

run_test(
    "WEB.metadata 键值对", "METADATA",
    {"__type__": "map", "name": "test",
     "web": {"__type__": "web", "metadata": {"wms_title": "My Map"}}}, True)

run_test(
    "LAYER.metadata 键值对", "METADATA",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "metadata": {"wms_title": "Layer Title"}}]}, True)

run_test(
    "空 metadata {}", "METADATA",
    {"__type__": "map", "name": "test",
     "web": {"__type__": "web", "metadata": {}}}, True)

run_test(
    "metadata 值是整数", "METADATA",
    {"__type__": "map", "name": "test",
     "web": {"__type__": "web", "metadata": {"wms_max_width": 4096}}}, None)

run_test(
    "metadata 含自定义属性", "METADATA",
    {"__type__": "map", "name": "test",
     "web": {"__type__": "web", "metadata": {"my_custom_key": "value"}}}, None)

# --------------------------------------------------
# 维度 8: 缺字段 (hard-required vs optional)
# --------------------------------------------------
print("\n【维度 8】缺字段")

run_test(
    "MAP 缺 name", "缺字段",
    {"__type__": "map"}, False)

run_test(
    "LAYER 缺 name", "缺字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "type": "POLYGON"}]}, False)

run_test(
    "LAYER 缺 type", "缺字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1"}]}, False)

run_test(
    "STYLE 缺必填 (空 style)", "缺字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "styles": [{"__type__": "style"}]}]}]}, None)

run_test(
    "CLASS 缺 name (可选?)", "缺字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class"}]}]}, True)

run_test(
    "LABEL 缺 text", "缺字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "classes": [{"__type__": "class",
                              "labels": [{"__type__": "label"}]}]}]}, None)

# --------------------------------------------------
# 维度 9: Extent
# --------------------------------------------------
print("\n【维度 9】Extent")

run_test(
    "extent 数组 [-180,-90,180,90]", "Extent",
    {"__type__": "map", "name": "test", "extent": [-180, -90, 180, 90]}, True)

run_test(
    "extent 字符串 '-180 -90 180 90'", "Extent",
    {"__type__": "map", "name": "test", "extent": "-180 -90 180 90"}, None)

run_test(
    "extent 数组 3 元素", "Extent",
    {"__type__": "map", "name": "test", "extent": [-180, -90, 180]}, False)

run_test(
    "extent 数组 5 元素", "Extent",
    {"__type__": "map", "name": "test", "extent": [-180, -90, 180, 90, 0]}, False)

# --------------------------------------------------
# 维度 10: 自定义字段 / 扩展属性
# --------------------------------------------------
print("\n【维度 10】自定义字段")

run_test(
    "MAP 加未知字段", "自定义字段",
    {"__type__": "map", "name": "test", "my_unknown_field": "hello"}, None)

run_test(
    "LAYER 加未知字段", "自定义字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "my_custom": "value"}]}, None)

run_test(
    "_custom 嵌套对象", "自定义字段",
    {"__type__": "map", "name": "test", "_custom": {"foo": "bar"}}, None)

# --------------------------------------------------
# 额外：边缘/特殊字段
# --------------------------------------------------
print("\n【额外】特殊字段")

run_test(
    "units METERS", "特殊字段",
    {"__type__": "map", "name": "test", "units": "METERS"}, None)

run_test(
    "shapepath 字符串", "特殊字段",
    {"__type__": "map", "name": "test", "shapepath": "/data/shapes"}, None)

run_test(
    "template 字符串", "特殊字段",
    {"__type__": "map", "name": "test",
     "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON",
                 "template": "template.html"}]}, None)

run_test(
    "dump true (布尔)", "特殊字段",
    {"__type__": "map", "name": "test", "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON", "dump": True}]}, None)

run_test(
    "dump 'true' (字符串)", "特殊字段",
    {"__type__": "map", "name": "test", "layers": [{"__type__": "layer", "name": "l1", "type": "POLYGON", "dump": "true"}]}, None)

run_test(
    "debug 整数", "特殊字段",
    {"__type__": "map", "name": "test", "debug": 5}, None)

# ============================================================
# 汇总报告
# ============================================================

print("\n" + "=" * 70)
print("汇总报告")
print("=" * 70)

# 按维度分组统计
from collections import defaultdict
by_category = defaultdict(list)
for r in RESULTS:
    by_category[r.category].append(r)

print("\n按维度统计：")
for cat, items in sorted(by_category.items()):
    passed = sum(1 for r in items if r.passed)
    failed = sum(1 for r in items if r.passed == False)
    exc = sum(1 for r in items if r.exception)
    print(f"  {cat:12s}: {len(items):2d} 项 | 通过 {passed:2d} | 失败 {failed:2d} | 异常 {exc:2d}")

print("\n关键发现：")

# 1. 必须数组化的字段
array_required = []
for r in RESULTS:
    if "投影" in r.category and r.passed == False and "字符串" in r.description:
        array_required.append("projection")
    if "Extent" in r.category and r.passed == False and "字符串" in r.description:
        array_required.append("extent")
    if "数组字段" in r.category and r.passed == False and "非列表" in r.description:
        if "layers" in r.description:
            array_required.append("layers")
        elif "classes" in r.description:
            array_required.append("classes")
        elif "styles" in r.description:
            array_required.append("styles")

# 2. 枚举严格大小写
case_sensitive = []
for r in RESULTS:
    if r.category == "Enum" and r.passed == False:
        case_sensitive.append(r.description)

# 3. dumps 异常的情况
dumps_exceptions = [r for r in RESULTS if not r.dumps_ok]

# 4. validate 检测不到的
cannot_detect = [r for r in RESULTS
                 if r.passed and r.category in ("缺字段", "自定义字段", "METADATA")]

print(f"\n  [发现 1] 必须数组化的字段: {list(set(array_required)) or '（待确认）'}")
print(f"  [发现 2] Enum 大小写敏感: {len(case_sensitive)} 个失败用例")
for c in case_sensitive:
    print(f"           - {c}")
print(f"  [发现 3] dumps() 异常: {len(dumps_exceptions)} 个")
for r in dumps_exceptions:
    print(f"           - {r.description}: {r.exception}")
print(f"  [发现 4] validate 通过但可能有问题: {len(cannot_detect)} 个")
for r in cannot_detect:
    print(f"           - {r.description}")

# 输出到文件
report = {
    "mappyfile_version": mappyfile.__version__,
    "total_tests": len(RESULTS),
    "by_category": {
        cat: {
            "total": len(items),
            "passed": sum(1 for r in items if r.passed),
            "failed": sum(1 for r in items if r.passed == False),
            "exceptions": sum(1 for r in items if r.exception),
        }
        for cat, items in sorted(by_category.items())
    },
    "key_findings": {
        "array_required_fields": list(set(array_required)),
        "case_sensitive_enums": case_sensitive,
        "dumps_exceptions": [{"desc": r.description, "exc": r.exception} for r in dumps_exceptions],
        "validate_passed_but_suspicious": [r.description for r in cannot_detect],
    },
}

with open("SourceCode/spike/v1_result.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n详细结果已写入: SourceCode/spike/v1_result.json")
print("=" * 70)
