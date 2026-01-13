<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAlarmSettings } from '../composables/useAlarmSettings'

const { settings, loading, error, saveSettings } = useAlarmSettings()

const showSettings = ref(false)
const localSettings = ref({
  enabled: settings.value.enabled,
  threshold: settings.value.threshold,
  cooldown_minutes: settings.value.cooldown_minutes
})

// Sync local settings with loaded settings
watch(() => settings.value, (newSettings) => {
  localSettings.value = { ...newSettings }
}, { deep: true })

async function handleSave() {
  const success = await saveSettings(localSettings.value)
  if (success) {
    showSettings.value = false
  }
}

function handleCancel() {
  localSettings.value = { ...settings.value }
  showSettings.value = false
}
</script>

<template>
  <div>
    <!-- Settings Button -->
    <button
      @click="showSettings = true"
      class="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white transition-colors"
      :disabled="loading"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
      <span>Alarm</span>
      <span v-if="settings.enabled" class="w-2 h-2 rounded-full bg-green-500"></span>
    </button>

    <!-- Settings Modal -->
    <div
      v-if="showSettings"
      class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      @click.self="handleCancel"
    >
      <div class="bg-gray-800 rounded-2xl border border-gray-700 p-6 max-w-md w-full shadow-2xl">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-xl font-bold text-white">CO2 Alarm Settings</h2>
          <button
            @click="handleCancel"
            class="text-gray-400 hover:text-white transition-colors"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div v-if="error" class="mb-4 p-3 bg-red-500/10 border border-red-500 rounded-lg text-red-400 text-sm">
          {{ error }}
        </div>

        <div class="space-y-6">
          <!-- Enable/Disable -->
          <div class="flex items-center justify-between">
            <div>
              <label class="text-white font-medium">Enable Alarm</label>
              <p class="text-sm text-gray-400">Get notifications when CO2 is high</p>
            </div>
            <button
              @click="localSettings.enabled = !localSettings.enabled"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
              :class="localSettings.enabled ? 'bg-blue-600' : 'bg-gray-600'"
            >
              <span
                class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                :class="localSettings.enabled ? 'translate-x-6' : 'translate-x-1'"
              />
            </button>
          </div>

          <!-- Threshold -->
          <div>
            <label class="block text-white font-medium mb-2">
              Threshold (ppm)
            </label>
            <input
              v-model.number="localSettings.threshold"
              type="number"
              min="400"
              max="5000"
              step="50"
              class="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              :disabled="!localSettings.enabled"
            />
            <p class="mt-2 text-sm text-gray-400">
              Notify when CO2 exceeds this level
            </p>
          </div>

          <!-- Cooldown -->
          <div>
            <label class="block text-white font-medium mb-2">
              Cooldown (minutes)
            </label>
            <input
              v-model.number="localSettings.cooldown_minutes"
              type="number"
              min="5"
              max="120"
              step="5"
              class="w-full px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              :disabled="!localSettings.enabled"
            />
            <p class="mt-2 text-sm text-gray-400">
              Wait this long before sending another notification
            </p>
          </div>
        </div>

        <div class="flex gap-3 mt-8">
          <button
            @click="handleCancel"
            class="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            @click="handleSave"
            class="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
            :disabled="loading"
          >
            {{ loading ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
