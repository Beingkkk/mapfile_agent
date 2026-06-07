const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Development: load Vite dev server
  // Production: load built index.html
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../frontend/dist/index.html'));
  }
}

function startPythonBackend() {
  // TODO: PyInstaller exe in production, Python script in development
  const pythonPath = process.env.PYTHON_PATH || 'python';
  pythonProcess = spawn(pythonPath, ['-m', 'uvicorn', 'backend.main:app', '--port', '8765'], {
    cwd: path.join(__dirname, '..'),
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python] ${data}`);
  });
}

function setupIPC() {
  ipcMain.handle('dialog:openFile', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      filters: [{ name: 'Mapfile', extensions: ['map'] }],
    });
    return result;
  });

  ipcMain.handle('dialog:saveDirectory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    });
    return result;
  });

  ipcMain.handle('file:write', async (event, filePath, content) => {
    const fs = require('fs');
    fs.writeFileSync(filePath, content, 'utf-8');
    return true;
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();
  setupIPC();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});
