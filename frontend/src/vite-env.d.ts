/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL, e.g. http://127.0.0.1:8083 */
  readonly VITE_API_BASE_URL?: string
  /**
   * Local MVP API credential, sent as X-API-Key.
   *
   * Vite inlines this into the bundle, so keep it empty for production builds.
   * Set it only for local development against a backend with
   * AUTH_REQUIRED=true.
   */
  readonly VITE_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
