// Type declarations for Vite import.meta.env
// Add VITE_ environment variables here as needed.

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
