const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  openFile: () => ipcRenderer.invoke('dialog:openFile'),
  saveDirectory: () => ipcRenderer.invoke('dialog:saveDirectory'),
  writeFile: (path, content) => ipcRenderer.invoke('file:write', path, content),
});
