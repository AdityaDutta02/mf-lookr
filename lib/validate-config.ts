// Validates terminal-ai.config.json at import time
import config from '../terminal-ai.config.json' assert { type: 'json' }

const REQUIRED_KEYS = ['app_name', 'framework', 'health_check_path', 'category', 'tier'] as const

for (const key of REQUIRED_KEYS) {
  if (!config[key as keyof typeof config]) {
    throw new Error(`terminal-ai.config.json is missing required key: "${key}"`)
  }
}

export default config
