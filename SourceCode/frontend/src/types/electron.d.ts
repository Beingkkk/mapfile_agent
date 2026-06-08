export interface ElectronFile {
  name: string;
  content_base64: string;
}

export interface SaveExportResult {
  success: boolean;
  saved: string[];
  errors?: Array<{ name: string; error: string }>;
  directory?: string;
  error?: string;
}

export interface ElectronAPI {
  openFile: (options?: { filters?: Array<{ name: string; extensions: string[] }> }) => Promise<{ canceled: boolean; filePaths: string[] }>;
  saveDirectory: () => Promise<{ canceled: boolean; filePaths: string[] }>;
  writeFile: (filePath: string, content: string) => Promise<{ success: boolean; error?: string }>;
  saveExportFiles: (files: ElectronFile[]) => Promise<SaveExportResult>;
  platform: string;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
