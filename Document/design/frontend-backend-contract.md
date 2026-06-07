---
title: 前端-后端契约
description: WebSocket 通信约束、消息类型定义、前后端数据交换格式
---

## 12. 前端-后端契约

### 通信约束

**前后端统一使用 WebSocket 通信，禁止 HTTP 与 WebSocket 混合交互。**

- 前端 ↔ 后端：仅通过一条 WebSocket 长连接（`ws://localhost:8765/ws`）进行所有数据交换
- 后端 → LLM 厂商：通过 HTTP API（Anthropic Claude）
- 前端获取静态资源（如 Vue 打包后的 JS/CSS）：通过 Electron 本地文件协议（`file://`），不走网络请求
- 后端 FastAPI 仅暴露 WebSocket 路由 `/ws` 给前端，不暴露任何 HTTP REST API 供前端调用

> 设计理由：单一通信通道降低架构复杂度，避免维护两套协议的消息格式；WebSocket 的双工特性天然适合实时配置同步 + 问答推送的场景。

### 12.1 WebSocket 消息类型

```typescript
// ── 前端 → 后端 ──

interface InitSession {
  type: "init_session";
  intent?: string;                 // 用户初始意图，可选
}

interface TreeUpdate {
  type: "tree_update";
  updates: Array<{ path: string; value: any }>;
}

interface TreeAddNode {
  type: "tree_add_node";
  parent_path: string;             // 父节点 path
  object_type: "LAYER" | "CLASS" | "STYLE" | "LABEL";
}

interface TreeRemoveNode {
  type: "tree_remove_node";
  path: string;
}

interface TreeAddCustomProp {
  type: "tree_add_custom_prop";
  parent_path: string;
  key: string;
  value: any;
  prop_type: string;
  desc?: string;
}

interface FocusChange {
  type: "focus_change";
  path: string | null;
}

interface Question {
  type: "question";
  text: string;
}

interface ValidateRequest {
  type: "validate";
}

interface ExportRequest {
  type: "export";
}

interface SetServiceTypesRequest {
  type: "set_service_types";
  services: Array<"wms" | "wfs" | "wcs">;     // 勾选的服务类型
  mapcache_enabled: boolean;                    // 是否启用 MapCache(WMTS/TMS)
}

interface ResetSession {
  type: "reset_session";
}

interface ImportMapfile {
  type: "import_mapfile";
  content: string;                   // Mapfile 文本内容（UTF-8）
}


// ── 后端 → 前端 ──

interface SetServiceTypes {
  type: "set_service_types";
  services: Array<"wms" | "wfs" | "wcs">;     // 勾选的服务类型
  mapcache_enabled: boolean;                    // 是否启用 MapCache(WMTS/TMS)
}

// ── 后端 → 前端 ──

interface TreeState {
  type: "tree_state";
  params_snapshot: any;
  validation_state: "idle" | "checking" | "pass" | "fail";
  validation_errors: Array<{ path: string; message: string }>;
  can_export: boolean;
  focus_param?: string;
  service_types: Array<"wms" | "wfs" | "wcs">;  // 当前勾选的服务类型
  mapcache_enabled: boolean;
}

interface FocusState {
  type: "focus_state";
  focus_param?: string;
}

interface QAResult {
  type: "qa_result";
  bot_message: string;
  params_update: Array<{ path: string; value: any; previous_value?: any }>;
  validation_state: "idle" | "checking" | "pass" | "fail";
  validation_errors: Array<{ path: string; message: string }>;
  can_export: boolean;
  focus_param?: string;
}

interface ValidationResult {
  type: "validation_result";
  validation_state: "idle" | "checking" | "pass" | "fail";
  validation_errors: Array<{ path: string; message: string }>;
  can_export: boolean;
}

interface ExportResult {
  type: "export_result";
  success: boolean;
  files: Array<{ name: string; content_base64: string }>;
  error?: string;
}

interface ImportResult {
  type: "import_result";
  success: boolean;
  error?: string;                    // 失败时提供详细错误信息
}

interface ErrorMessage {
  type: "error";
  message: string;
}
```

---
