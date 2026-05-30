/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ANTHROPIC_LIVE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
