const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Dialogs
  openFile: (options) => ipcRenderer.invoke('dialog:openFile', options),
  saveDirectory: () => ipcRenderer.invoke('dialog:saveDirectory'),

  // File operations
  readFile: (filePath) => ipcRenderer.invoke('file:read', filePath),
  writeFile: (filePath, content) => ipcRenderer.invoke('file:write', filePath, content),
  saveExportFiles: (files) => ipcRenderer.invoke('save:exportFiles', files),

  // Window controls (frameless)
  minimizeWindow: () => ipcRenderer.invoke('window:minimize'),
  maximizeWindow: () => ipcRenderer.invoke('window:maximize'),
  closeWindow: () => ipcRenderer.invoke('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),

  // Platform info
  platform: process.platform,
});
