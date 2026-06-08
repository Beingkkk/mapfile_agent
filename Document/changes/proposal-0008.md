# Proposal-0008: MapCache 生成器 + 自定义属性前端组件

> **类型**: Type-B（设计变更 — 新增组件）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Plan**: `plan-platform` Phase 4
> **影响范围**:
> - `backend/mapcache/generator.py` — MapCacheGenerator
> - `backend/mapcache/validator.py` — MapCacheValidator
> - `backend/mapcache/templates/mapcache.xml.j2` — Jinja2 模板
> - `backend/core/export_service.py` — MapCache 集成
> - `frontend/src/components/CustomPropModal.vue` — 自定义属性模态框
> - `tests/unit/test_mapcache_generator.py` — 生成器测试
> - `tests/unit/test_mapcache_validator.py` — 校验器测试

---

## 目标

完成 Phase 4 两大功能块：

1. **MapCache 生成与校验**：根据 session 中 `cache` 节点数据生成 `mapcache.xml`，并进行基础 XML 结构校验
2. **自定义属性前端交互**：通过模态框添加自定义属性（_custom），后端已支持

**核心复杂度**：
- MapCache XML 结构与 session params 的映射关系
- Jinja2 模板渲染 + XML 基本格式校验（无需安装 MapCache）
- 自定义属性模态框的 Vue 组件

**原则**：
- TDD 纪律：RED → GREEN → REFACTOR
- MapCache XML 不依赖 MapCache 安装
- 自定义属性存储在 `_custom` 中，to_mappyfile_dict 自动展开

---

## 变更内容

### [ADDED] `backend/mapcache/generator.py`

**MapCacheGenerator**:
- `__init__(templates_dir)` — 加载 Jinja2 模板
- `generate(session)` → `str` — 从 session.params 中提取 cache 数据，渲染 XML
- 支持的 cache 字段：type, base, expires, wmts_enabled, tms_enabled, grid, format, metatile, minzoom, maxzoom
- 默认值：`type="disk"`, `base="/tmp/mapcache"`, `format="PNG"`

### [ADDED] `backend/mapcache/templates/mapcache.xml.j2`

基础 MapCache XML 模板：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mapcache>
  <source name="{{ source_name }}" type="wms">
    <http>
      <url>{{ wms_url }}</url>
    </http>
    <getmap>
      <params>
        <map>{{ mapfile_path }}</map>
        <layers>{{ layers }}</layers>
      </params>
    </getmap>
  </source>
  <cache name="{{ cache_name }}" type="{{ cache_type }}">
    <base>{{ cache_base }}</base>
  </cache>
  <tileset name="{{ tileset_name }}">
    <source>{{ source_name }}</source>
    <cache>{{ cache_name }}</cache>
    <grid>{{ grid }}</grid>
    <format>{{ format }}</format>
    <metatile>{{ metatile }}</metatile>
    <expires>{{ expires }}</expires>
  </tileset>
  {% if wmts_enabled %}
  <service type="wmts" enabled="true" />
  {% endif %}
  {% if tms_enabled %}
  <service type="tms" enabled="true" />
  {% endif %}
</mapcache>
```

### [ADDED] `backend/mapcache/validator.py`

**MapCacheValidator**:
- `validate(xml_text)` → `ValidationResult`（list of error dicts）
- 检查：XML 可解析、必填节点存在（source, cache, tileset）、service type 有效
- 不依赖外部 MapCache 安装

### [MODIFIED] `backend/core/export_service.py`

取消 TODO，集成 MapCacheGenerator：
- `ExportService.__init__` 接受可选的 `mapcache_generator`
- `export()` 当 `session.mapcache_enabled` 为 True 时调用 generator
- 返回结果包含 `"mapcache.xml"`

### [ADDED] `frontend/src/components/CustomPropModal.vue`

模态框组件：
- key 输入（参数名）
- type 选择（string / integer / float / boolean / color / array）
- desc 输入（描述）
- value 输入（根据 type 显示不同控件）
- 提交发送 `tree_add_custom_prop` WS 消息

### [MODIFIED] `frontend/src/components/ObjectCard.vue`

在 MAP / WEB / LAYER / CLASS / METADATA 节点上添加“+ 自定义属性”按钮，点击打开 CustomPropModal。

---

## 测试策略

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|---------|
| DC-038 | `test_mapcache_generator.py` | 默认参数生成、完整参数生成、无 cache 节点返回空、类型和 base 覆盖 |
| DC-039 | `test_mapcache_validator.py` | 有效 XML 通过、无效 XML 报错、缺少必填节点报错、service type 校验 |
| DC-040 | `test_export_service.py` | MapCache 启用时包含 xml 文件、MapCache 禁用时只有 map 文件 |
| — | 前端（手动验证） | CustomPropModal 打开/关闭、提交发送 WS 消息、后端 tree 更新 |

---

## 验收标准

- [ ] MapCacheGenerator 从 session.params.cache 生成有效 XML
- [ ] MapCacheValidator 验证 XML 结构，无需外部依赖
- [ ] ExportService 在 mapcache_enabled=True 时返回 mapcache.xml
- [ ] pytest 新增测试全部通过
- [ ] CustomPropModal 前端组件可添加自定义属性
- [ ] 全部现有测试零回归

---

## 依赖

- proposal-0004（ConfigSession + ConfigTree）
- proposal-0007（ExportService + main.py WS 路由）
- Jinja2（已安装）

---

*Approved by: SDD 流程 — plan-platform Phase 4 既定任务*
