const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Dialogs
  openFile: (options) => ipcRenderer.invoke('dialog:openFile', options),
  saveDirectory: () => ipcRenderer.invoke('dialog:saveDirectory'),

  // File operations
  writeFile: (filePath, content) => ipcRenderer.invoke('file:write', filePath, content),
  saveExportFiles: (files) => ipcRenderer.invoke('save:exportFiles', files),

  // Platform info
  platform: process.platform,
});
