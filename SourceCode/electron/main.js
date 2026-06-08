const { app, BrowserWindow, ipcMain, dialog, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const net = require('net');

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const BACKEND_PORT = 8765;
const BACKEND_HOST = '127.0.0.1';
const IS_DEV = !app.isPackaged;

// Development: use gis-agent conda environment Python
const DEFAULT_PYTHON_PATH = 'C:\\Users\\PC\\.conda\\envs\\gis-agent\\python.exe';

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────

let mainWindow = null;
let pythonProcess = null;
let isQuitting = false;

// ─────────────────────────────────────────────────────────────────────────────
// Window
// ─────────────────────────────────────────────────────────────────────────────

function createWindow() {
  const iconPath = path.join(__dirname, 'icon.png');
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    title: 'MapGuide',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    // Frameless window: custom title bar via HTML/CSS
    frame: false,
    titleBarStyle: 'hidden',
    // Transparent background until content loads (prevents white flash)
    backgroundColor: '#1a1a2e',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false, // Required for preload to access ipcRenderer
    },
  });

  // Remove native application menu (File, Edit, etc.)
  Menu.setApplicationMenu(null);

  // Load URL or file depending on environment
  if (IS_DEV) {
    mainWindow.loadURL('http://127.0.0.1:18001');
    mainWindow.webContents.openDevTools();
  } else {
    const indexPath = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Python Backend
// ─────────────────────────────────────────────────────────────────────────────

function getPythonExecutablePath() {
  if (IS_DEV) {
    return process.env.PYTHON_PATH || DEFAULT_PYTHON_PATH;
  }
  // Production: PyInstaller bundled exe
  return path.join(process.resourcesPath, 'backend', 'MapGuideBackend.exe');
}

function getBackendWorkingDirectory() {
  if (IS_DEV) {
    return path.join(__dirname, '..');
  }
  // Production: exe handles its own paths via __file__
  return path.dirname(getPythonExecutablePath());
}

function startPythonBackend() {
  const pythonPath = getPythonExecutablePath();

  if (!fs.existsSync(pythonPath)) {
    console.error(`[Electron] Backend executable not found: ${pythonPath}`);
    dialog.showErrorBox(
      'Backend Not Found',
      `Could not find backend executable:\n${pythonPath}\n\n` +
        (IS_DEV
          ? 'Please set PYTHON_PATH environment variable or ensure gis-agent conda environment exists.'
          : 'The application may not be installed correctly.')
    );
    return;
  }

  const cwd = getBackendWorkingDirectory();
  const args = IS_DEV
    ? ['-m', 'uvicorn', 'backend.main:app', '--port', String(BACKEND_PORT), '--host', BACKEND_HOST]
    : [];

  console.log(`[Electron] Starting backend: ${pythonPath} ${args.join(' ')}`);

  pythonProcess = spawn(pythonPath, args, {
    cwd,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.on('error', (err) => {
    console.error('[Electron] Failed to start backend:', err.message);
    dialog.showErrorBox('Backend Error', `Failed to start Python backend:\n${err.message}`);
  });

  pythonProcess.on('exit', (code) => {
    if (!isQuitting) {
      console.error(`[Electron] Backend exited unexpectedly with code ${code}`);
    }
    pythonProcess = null;
  });
}

function stopPythonBackend() {
  if (pythonProcess) {
    isQuitting = true;
    console.log('[Electron] Stopping backend...');
    // SIGTERM on Windows sends to the process group
    pythonProcess.kill('SIGTERM');
    // Force kill after 3s if still running
    setTimeout(() => {
      if (pythonProcess && !pythonProcess.killed) {
        pythonProcess.kill('SIGKILL');
      }
    }, 3000);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Health Check
// ─────────────────────────────────────────────────────────────────────────────

function waitForBackend(timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    const interval = setInterval(() => {
      const socket = new net.Socket();
      socket.setTimeout(500);
      socket.once('connect', () => {
        clearInterval(interval);
        socket.destroy();
        resolve();
      });
      socket.once('error', () => {
        socket.destroy();
      });
      socket.connect(BACKEND_PORT, BACKEND_HOST);

      if (Date.now() - startTime > timeoutMs) {
        clearInterval(interval);
        reject(new Error(`Backend did not respond on port ${BACKEND_PORT} within ${timeoutMs}ms`));
      }
    }, 500);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// IPC
// ─────────────────────────────────────────────────────────────────────────────

function setupIPC() {
  // Open file dialog for importing .map files
  ipcMain.handle('dialog:openFile', async (_event, options = {}) => {
    const result = await dialog.showOpenDialog(mainWindow, {
      filters: options.filters || [{ name: 'Mapfile', extensions: ['map'] }],
      properties: ['openFile'],
    });
    return result;
  });

  // Open directory dialog for selecting save location
  ipcMain.handle('dialog:saveDirectory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    });
    return result;
  });

  // Save export files to disk
  ipcMain.handle('save:exportFiles', async (_event, files) => {
    // files: [{ name: 'mapfile.map', content_base64: '...' }, ...]
    const { filePaths } = await dialog.showOpenDialog(mainWindow, {
      title: '选择导出目录',
      properties: ['openDirectory', 'createDirectory'],
      buttonLabel: '保存到此处',
    });

    if (!filePaths || filePaths.length === 0) {
      return { success: false, saved: [], error: 'No directory selected' };
    }

    const saveDir = filePaths[0];
    const saved = [];
    const errors = [];

    for (const file of files) {
      try {
        const filePath = path.join(saveDir, file.name);
        const content = Buffer.from(file.content_base64, 'base64');
        fs.writeFileSync(filePath, content);
        saved.push(file.name);
      } catch (err) {
        errors.push({ name: file.name, error: err.message });
      }
    }

    return {
      success: errors.length === 0,
      saved,
      errors: errors.length > 0 ? errors : undefined,
      directory: saveDir,
    };
  });

  // Write a single file (used by legacy IPC)
  ipcMain.handle('file:write', async (_event, filePath, content) => {
    try {
      fs.writeFileSync(filePath, content, 'utf-8');
      return { success: true };
    } catch (err) {
      return { success: false, error: err.message };
    }
  });

  // ── Window controls (frameless) ──
  ipcMain.handle('window:minimize', () => {
    if (mainWindow) mainWindow.minimize();
  });

  ipcMain.handle('window:maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });

  ipcMain.handle('window:close', () => {
    if (mainWindow) mainWindow.close();
  });

  ipcMain.handle('window:isMaximized', () => {
    return mainWindow ? mainWindow.isMaximized() : false;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// App Lifecycle
// ─────────────────────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startPythonBackend();

  try {
    await waitForBackend();
    console.log('[Electron] Backend is ready');
    createWindow();
  } catch (err) {
    console.error('[Electron] Backend health check failed:', err.message);
    dialog.showErrorBox(
      'Backend Startup Failed',
      `The Python backend did not start correctly:\n${err.message}\n\n` +
        'Please check that port 8765 is not in use by another process.'
    );
    createWindow(); // Still open window so user can see error
  }

  setupIPC();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopPythonBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonBackend();
});
