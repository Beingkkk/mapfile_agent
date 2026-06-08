# Proposal-0009: Electron 打包配置 + 导出文件保存 + 服务类型切换 UI

> **类型**: Type-B（设计变更 — 新增配置与交互）
> **状态**: ACTIVE
> **日期**: 2026-06-08
> **对应 Plan**: `plan-platform` Phase 5
> **影响范围**:
> - 根目录 `package.json` — Electron 项目配置
> - `electron/main.js` — 主进程完善（dev/prod 路径、进程管理、窗口状态）
> - `electron/preload.js` — IPC 桥接完善（saveFiles）
> - `frontend/src/services/ws.ts` — export_result 处理，调用 Electron 保存文件
> - `frontend/src/components/ConfigTreePanel.vue` — 服务类型切换 UI

---

## 目标

完成 Phase 5 三大功能块：

1. **Electron 打包配置**：根目录 `package.json` 整合 frontend + electron，配置 `electron-builder` 打包
2. **导出文件保存**：后端 export 返回文件后，前端通过 Electron dialog 让用户选择保存目录并写入文件
3. **服务类型切换 UI**：在 ConfigTreePanel 顶部添加 WMS/WFS/WCS + MapCache 复选框，发送 `set_service_types` WS 消息

**核心复杂度**：
- Electron 开发/生产环境路径区分（dev 用 gis-agent Python，prod 用 PyInstaller exe）
- Electron 安全 IPC 设计（preload 桥接 + contextIsolation）
- 前端服务类型切换与后端 `set_service_types` 消息联动

**原则**：
- TDD 纪律：RED → GREEN → REFACTOR
- Electron 开发环境复用现有 gis-agent conda 环境
- 生产环境依赖 PyInstaller 打包的后端 exe

---

## 变更内容

### [ADDED] 根目录 `package.json`

Electron 项目根配置：
- `dependencies`: `electron`, `electron-builder`
- `scripts`: `electron:dev`, `electron:build`
- `build` 配置：`files`（frontend/dist, electron, backend/dist），`extraResources`（PyInstaller exe）
- `main`: `electron/main.js`

### [MODIFIED] `electron/main.js`

完善内容：
- **开发环境**：使用 `C:\Users\PC\.conda\envs\gis-agent\python.exe` 启动 backend（通过 `PYTHON_PATH` env 或默认路径）
- **生产环境**：使用 `resources/backend/MapGuideBackend.exe`（PyInstaller 输出）
- **进程清理**：`window-all-closed` 时 kill Python 子进程，`before-quit` 发送 SIGTERM
- **窗口状态**：使用 `electron-store` 持久化窗口大小/位置（可选，先不做）
- **导出保存 IPC**：`ipcMain.handle('save:exportFiles', ...)` 打开 dialog 保存多个文件
- **健康检查**：Python 进程启动后等待端口 8765 就绪再加载窗口

### [MODIFIED] `electron/preload.js`

新增：
- `saveExportFiles: (files) => ipcRenderer.invoke('save:exportFiles', files)` — 保存导出文件
- `platform: process.platform` — 暴露平台信息

### [MODIFIED] `frontend/src/services/ws.ts`

`export_result` 处理：
- 开发环境（无 Electron）：console.log 文件名
- Electron 环境：调用 `window.electronAPI.saveExportFiles(files)` 打开保存对话框
- 检测 Electron：`typeof window !== 'undefined' && (window as any).electronAPI`

### [MODIFIED] `frontend/src/components/ConfigTreePanel.vue`

在 toolbar 上方添加服务类型切换栏：
- 三个 checkbox：WMS / WFS / WCS
- 一个 checkbox：MapCache（启用时显示 WMTS/TMS）
- 切换时发送 `set_service_types` WS 消息
- 同步 `sessionStore.service_types` 和 `sessionStore.mapcache_enabled`

---

## 测试策略

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|---------|
| DC-041 | 手动验证 | `npm run electron:dev` 启动成功，`electron:build` 配置无报错 |
| DC-042 | 手动验证 | dev 模式启动 Python 后端、prod 模式加载 exe、进程退出清理 |
| DC-043 | 手动验证 | preload 暴露的 API 在 renderer 中可访问 |
| DC-044 | 手动验证 | export 后弹出保存对话框、文件正确写入 |
| DC-045 | `session.spec.ts` | 服务类型状态变更、applyTreeState 同步 mapcache_enabled |

---

## 验收标准

- [ ] 根目录 `package.json` 包含 electron + electron-builder 配置
- [ ] `npm run electron:dev` 能启动 Electron 窗口并加载前端
- [ ] Electron 开发模式正确启动 Python 后端（gis-agent 环境）
- [ ] Electron 生产模式正确加载 PyInstaller 打包的 exe
- [ ] app 退出时 Python 子进程被清理
- [ ] 导出文件时弹出保存对话框，文件正确写入磁盘
- [ ] 服务类型切换 UI 正常显示，发送正确的 WS 消息
- [ ] 全部现有测试零回归

---

## 依赖

- proposal-0004（ConfigSession + ConfigTree）
- proposal-0007（ExportService + main.py WS 路由）
- proposal-0008（MapCacheGenerator + CustomPropModal）
- Electron 已安装（`npm install electron electron-builder`）

---

*Approved by: SDD 流程 — plan-platform Phase 5 既定任务*
