/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_EDITOR_TOKEN?: string;
  readonly VITE_ADMIN_TOKEN?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
