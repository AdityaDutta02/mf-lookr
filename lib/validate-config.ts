// Next.js resolves JSON imports directly (resolveJsonModule). The `assert
// { type: 'json' }` import-attribute syntax can crash the standalone server at
// runtime depending on the module loader, so we import plainly.
import config from '../terminal-ai.config.json'

const REQUIRED_KEYS = ['app_name', 'framework', 'health_check_path', 'category', 'tier'] as const

for (const key of REQUIRED_KEYS) {
  if (!config[key as keyof typeof config]) {
    throw new Error(`terminal-ai.config.json is missing required key: "${key}"`)
  }
}

export default config
