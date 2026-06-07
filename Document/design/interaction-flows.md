---
title: 交互流程
description: 6 个核心交互场景的数据流：编辑参数、切换关注点、提问、手动校验、导出、导入
---

## 11. 核心交互逻辑

### 11.1 交互一：用户编辑参数

```
前端：用户在某字段失焦
  │
  ▼
WS: tree_update { updates: [{ path, value }] }
  │
  ▼
后端：ConfigTree.update_value(path, value)（遍历 updates 逐个应用）
  │
  ▼
后端：ValidationPipeline.validate_field(path, full=False)
  ├── 别名解析（如 "红色" → [255,0,0]）
  ├── 类型校验
  └── 语义校验
  │
  ▼
WS: tree_state {
      params_snapshot,
      validation_state,
      validation_errors,
      focus_param
    }
  │
  ▼
前端：更新树显示、错误标记、导出按钮状态
```

### 11.2 交互二：用户切换关注点

```
前端：用户点击树中某节点/属性
  │
  ▼
WS: focus_change { path }
  │
  ▼
后端：session.set_focus(path)
  ├── 如果 focus_param 改变：清空历史 messages（保留 intent）
  └── 更新 session.focus_param
  │
  ▼
WS: focus_state { focus_param }
  │
  ▼
前端：右侧面板显示关注点信息
```

### 11.3 交互三：用户提问

```
前端：用户在输入框输入问题并发送
  │
  ▼
WS: question { text, focus_param? }
  │
  ▼
后端：QAService.answer(session, text)
  ├── history.add_message("user", text)
  ├── PromptBuilder.render(...)  ← 组装 L0-L5
  ├── LLMClient.chat(prompt)
  ├── LLMOutput.parse(raw_json)
  ├── 如果有 params_update：UpdateResolver.resolve + ConfigTree.update_value
  ├── ValidationPipeline.validate_tree(tree)
  └── history.add_message("bot", answer)
  │
  ▼
WS: qa_result {
      bot_message,
      params_update,
      validation_state,
      validation_errors,
      can_export,
      focus_param
    }
  │
  ▼
前端：追加对话、更新树（如果 LLM 改了参数）、显示校验结果
```

### 11.4 交互四：手动校验

```
前端：点击「校验全部」
  │
  ▼
WS: validate {}
  │
  ▼
后端：ValidationPipeline.validate_tree(tree)
  ├── 遍历所有叶子字段：alias + type + semantic
  └── mappyfile.validate(version=8.4)
  │
  ▼
WS: validation_result { validation_state, validation_errors, can_export }
  │
  ▼
前端：显示全局错误面板，更新导出按钮
```

### 11.5 交互五：导出

```
前端：点击「导出」
  │
  ▼
后端：先执行 validate_tree（与手动校验相同逻辑）
  │
  ▼
如果通过：ExportService.export(session)
  ├── mappyfile.dumps(tree.to_mappyfile_dict())
  └── 可选 mapcache.xml
  │
  ▼
WS: export_result { files: [{name, content_base64}] }
  │
  ▼
前端：弹出保存对话框
```

### 11.6 交互六：导入 Mapfile

```
前端：点击「📂 导入 Mapfile」
  │
  ▼
Electron dialog.showOpenDialog({ filters: [{ name: 'Mapfile', extensions: ['map'] }] })
  │
  ▼
Electron 主进程读取文件内容 → IPC → 渲染进程
  │
  ▼
WS: import_mapfile { content }
  │
  ▼
后端：ConfigSession.from_mapfile_content(session_id, content, mapper)
  ├── mappyfile.loads(content) → dict
  ├── 失败 → WS: import_result { success: false, error }
  └── 成功 → 新建 session（销毁旧 session）
  │
  ▼
后端：ConfigTree._build_tree(parsed_dict) — 未知字段自动标 custom=True
  │
  ▼
后端：ValidationPipeline.validate_tree(tree) — 四层完整校验
  │
  ▼
WS: import_result { success: true }
WS: tree_state { params_snapshot, validation_state, errors, can_export }
  │
  ▼
前端：完全刷新配置树，清空问答历史，轮数归零
```

**关键实现点**：
- 文件读取由 Electron 主进程完成，通过 IPC/preload 传给渲染进程，再经 WS 发送给后端
- 解析失败时返回 `import_result { success: false }`，当前会话不受影响
- 解析成功时返回 `import_result { success: true }`，紧接着返回 `tree_state`（与重置后的初始状态一致）
- `_build_tree()` 对 schema 未定义字段统一标记 `custom=True`，不额外维护白名单

---
