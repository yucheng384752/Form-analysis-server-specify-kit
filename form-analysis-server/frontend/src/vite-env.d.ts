/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_MAX_FILE_SIZE: string
  readonly VITE_API_KEY?: string
  readonly VITE_API_KEY_HEADER?: string
  // 可以添加更多環境變數
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}