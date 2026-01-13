import { ref } from 'vue'

export interface AlarmSettings {
  enabled: boolean
  threshold: number
  cooldown_minutes: number
}

const API_BASE = import.meta.env.DEV ? 'http://localhost:8080' : ''

export function useAlarmSettings() {
  const settings = ref<AlarmSettings>({
    enabled: false,
    threshold: 1000,
    cooldown_minutes: 30
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadSettings() {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/settings/alarm`)
      if (!response.ok) {
        throw new Error('Failed to load alarm settings')
      }
      settings.value = await response.json()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to load alarm settings:', err)
    } finally {
      loading.value = false
    }
  }

  async function saveSettings(newSettings: AlarmSettings) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/api/settings/alarm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newSettings)
      })

      if (!response.ok) {
        throw new Error('Failed to save alarm settings')
      }

      const result = await response.json()
      settings.value = result.settings
      return true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to save alarm settings:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  // Load settings on initialization
  loadSettings()

  return {
    settings,
    loading,
    error,
    loadSettings,
    saveSettings
  }
}
