#Requires -Version 5.1
<#
.SYNOPSIS
    MapGuide v0.1.0 Electron 一键打包脚本
.DESCRIPTION
    1. 构建前端（Vite，跳过有兼容性问题的 vue-tsc）
    2. PyInstaller 打包 Python 后端为独立 exe（MapGuideBackend.exe）
    3. electron-builder 生成安装包与便携版
    4. 生成 README.txt 说明文件

    打包产物输出到项目根目录 dist/ 下，不提交 git。
.NOTES
    运行前请确保：
      - Node.js + npm 已安装
      - Python 3.11+（gis-agent conda 环境）已安装且 PyInstaller 可用
      - 图标文件 SourceCode/electron/icon.png 存在
#>

# 设置控制台输出编码，避免中文乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"

# ─── 路径常量 ──────────────────────────────────────────
$ProjectRoot    = Resolve-Path (Join-Path $PSScriptRoot "..")
$SourceCodeDir  = Join-Path $ProjectRoot "SourceCode"
$FrontendDir    = Join-Path $SourceCodeDir "frontend"
$BackendDir     = Join-Path $SourceCodeDir "backend"
$ElectronDir    = Join-Path $SourceCodeDir "electron"
$DistDir        = Join-Path $ProjectRoot "dist"
$PyInstallerOut = Join-Path $BackendDir "dist"
$BuildDir       = Join-Path $ElectronDir "build"

# 默认 Python 路径（gis-agent conda 环境）
$DefaultPythonPath = "C:\Users\PC\.conda\envs\gis-agent\python.exe"

# ─── 工具函数 ──────────────────────────────────────────
function Write-Step($msg) {
    Write-Host "`n>>> $msg" -ForegroundColor Cyan
}

function Write-Info($msg) {
    Write-Host "    $msg" -ForegroundColor DarkGray
}

function Write-Ok($msg) {
    Write-Host "    $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    $msg" -ForegroundColor Yellow
}

function Write-ErrorMsg($msg) {
    Write-Host "    $msg" -ForegroundColor Red
}

# ─── 0. 前置检查 ───────────────────────────────────────
Write-Step "Step 0/5: 前置检查"

# 检查图标
$IconPath = Join-Path $ElectronDir "icon.png"
if (-not (Test-Path $IconPath)) {
    throw "图标文件不存在: $IconPath`n请确认 icon.png 已放置在 SourceCode/electron/ 下。"
}
Write-Ok "图标检查通过: $IconPath"

# 检查 npm
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
    throw "npm 未找到，请确保 Node.js 已安装并加入 PATH"
}
Write-Ok "npm 检查通过: $($npm.Source)"

# 检查 Python（优先环境变量，其次默认路径）
$PythonPath = if ($env:PYTHON_PATH) { $env:PYTHON_PATH } else { $DefaultPythonPath }
if (-not (Test-Path $PythonPath)) {
    # 尝试从 PATH 查找
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $PythonPath = $pythonCmd.Source
    } else {
        throw "Python 未找到: $PythonPath`n请设置 PYTHON_PATH 环境变量或确保 gis-agent conda 环境存在。"
    }
}
Write-Ok "Python 检查通过: $PythonPath"

# 检查 PyInstaller
Write-Info "检查 PyInstaller..."
& $PythonPath -m PyInstaller --version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Info "PyInstaller 未安装，正在安装..."
    & $PythonPath -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 安装失败" }
}
Write-Ok "PyInstaller 检查通过"

# 检查 backend/core/ 模块路径（PyInstaller 会用到）
$BackendCoreDir = Join-Path $BackendDir "core"
if (-not (Test-Path $BackendCoreDir)) {
    throw "backend/core/ 目录不存在: $BackendCoreDir"
}
Write-Ok "backend/core/ 检查通过"

# ─── 1. 前端构建 ───────────────────────────────────────
Write-Step "Step 1/5: 构建前端 (Vite)"
Set-Location $FrontendDir

# 安装依赖（如未安装）
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Warn "node_modules 不存在，正在安装 npm 依赖..."
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
}

# 构建渲染进程（dist/）
# 跳过 vue-tsc（Node v24 兼容性问题），直接使用 vite build
Write-Info "构建 Vite 渲染进程..."
npx vite build
if ($LASTEXITCODE -ne 0) { throw "Vite build 失败" }
Write-Ok "Vite build 完成"

# 验证前端构建产物
$IndexHtmlPath = Join-Path $FrontendDir "dist" "index.html"
if (-not (Test-Path $IndexHtmlPath)) {
    throw "前端构建产物不存在: $IndexHtmlPath"
}
Write-Ok "前端构建产物确认: dist/index.html"

# 切回 SourceCode 目录进行后续操作
Set-Location $SourceCodeDir

# ─── 2. PyInstaller 打包 Python 后端 ───────────────────
Write-Step "Step 2/5: PyInstaller 打包 Python 后端"

# 清理旧的 PyInstaller 输出
if (Test-Path $PyInstallerOut) {
    Remove-Item -Recurse -Force $PyInstallerOut
    Write-Info "清理旧 backend/dist/ 目录"
}

# 确保 data/ 目录存在（PyInstaller spec 中引用了它）
$DataDir = Join-Path $SourceCodeDir "data"
if (-not (Test-Path $DataDir)) {
    throw "data/ 目录不存在: $DataDir`n这是 PyInstaller 打包必需的数据目录。"
}

# 运行 PyInstaller（在 electron/build 目录下执行，因为 spec 中的路径是相对的）
# --distpath ../../backend/dist  强制输出到 backend/dist/（electron-builder extraResources 需要）
# --workpath ../../backend/build 将临时构建文件也放在 backend/ 下
Write-Info "运行 PyInstaller（spec: electron/build/pyinstaller.spec）..."
Set-Location $BuildDir
& $PythonPath -m PyInstaller pyinstaller.spec --clean --noconfirm `
    --distpath ../../backend/dist `
    --workpath ../../backend/build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }
Set-Location $SourceCodeDir

# 验证输出
$BackendExe = Join-Path $PyInstallerOut "MapGuideBackend.exe"
if (-not (Test-Path $BackendExe)) {
    throw "PyInstaller 输出不存在: $BackendExe`n请检查 spec 文件配置。"
}
Write-Ok "PyInstaller 打包完成: backend/dist/MapGuideBackend.exe"

# ─── 3. Electron Builder 打包 ──────────────────────────
Write-Step "Step 3/5: Electron Builder 打包 (nsis + portable)"

# 确保 backend/dist 存在（electron-builder extraResources 需要）
if (-not (Test-Path $PyInstallerOut)) {
    throw "backend/dist/ 目录不存在，无法继续 Electron 打包"
}

Write-Info "开始 Electron Builder 打包..."
npx electron-builder
if ($LASTEXITCODE -ne 0) { throw "electron-builder 打包失败" }

# 探测输出目录
$BuildOutput = Get-ChildItem -Path $DistDir -Directory |
    Where-Object { $_.Name -notmatch '^\.' } |
    Select-Object -First 1
if (-not $BuildOutput) {
    throw "未找到 electron-builder 输出目录，请检查 $DistDir"
}
$BuildOutputPath = $BuildOutput.FullName
Write-Ok "打包输出目录: $($BuildOutput.Name)"

# ─── 4. 生成说明文件 ───────────────────────────────────
Write-Step "Step 4/5: 生成说明文件"
$ReadmePath = Join-Path $BuildOutputPath "README.txt"
$ReadmeContent = @"
================================================================================
  MapGuide v0.1.0
================================================================================

启动方式
--------
双击 MapGuide Setup.exe 安装，或运行便携版目录中的 MapGuide.exe。

目录说明
--------
- resources/app.asar       前端资源（Electron 渲染进程）
- resources/backend/
  |-- MapGuideBackend.exe  Python 后端（含 Python 运行时 + 依赖 + data/）
- resources/config/        外置配置文件（用户可编辑）
  |-- config.json          API 密钥等敏感配置
  |-- config.json.template 配置模板

环境依赖
--------
- Windows 10/11 x64
- 无需额外安装 Python（后端已内置于 exe）

技术栈
------
- 前端: Vue 3 + Naive UI + Vite
- 后端: FastAPI + uvicorn + mappyfile（PyInstaller 打包）
- 通信: WebSocket (ws://localhost:18080/ws)

注意事项
--------
- config.json 包含 API 密钥等敏感信息，请勿泄露
- config/ 是外置资源，安装后可直接编辑 resources/config/config.json
- 首次启动时后端服务需要几秒钟初始化时间
- 后端端口 18080 若被占用，程序将无法正常工作
================================================================================
"@
$ReadmeContent | Set-Content -Path $ReadmePath -Encoding UTF8 -NoNewline
Write-Ok "README.txt 已生成"

# ─── 5. 完成汇总 ───────────────────────────────────────
Write-Step "Step 5/5: 打包完成汇总"

$NsisExe = Get-ChildItem -Path $DistDir -Filter "*.exe" -File | Where-Object { $_.Name -like "*Setup*" } | Select-Object -First 1
$PortableDir = Get-ChildItem -Path $DistDir -Directory | Where-Object { $_.Name -like "*win-unpacked*" -or $_.Name -like "*win-ia32-unpacked*" } | Select-Object -First 1

Write-Host "`n    ╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "    ║  ✅ MapGuide v0.1.0 打包完成                       ║" -ForegroundColor Green
Write-Host "    ╠══════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "    ║  输出目录: $($BuildOutput.Name)" -ForegroundColor Green
if ($NsisExe) {
    Write-Host "    ║  安装包  : $($NsisExe.Name)" -ForegroundColor Green
}
if ($PortableDir) {
    Write-Host "    ║  便携版  : $($PortableDir.Name)/ (文件夹)" -ForegroundColor Green
}
Write-Host "    ║  完整路径: $BuildOutputPath" -ForegroundColor Green
Write-Host "    ╚══════════════════════════════════════════════════════╝" -ForegroundColor Green

Write-Host "`n📦 如需分发给用户，可将以下文件打包:" -ForegroundColor Cyan
if ($PortableDir) {
    Write-Host "   - $($PortableDir.FullName)/ (便携版可直接使用整个文件夹)" -ForegroundColor White
}
if ($NsisExe) {
    Write-Host "   - $($NsisExe.FullName) (NSIS 安装包)" -ForegroundColor White
}

# 切回原目录
Set-Location $ProjectRoot
