<script setup lang="ts">
import { useCO2Data } from './composables/useCO2Data'
import CO2Chart from './components/CO2Chart.vue'
import AlarmSettings from './components/AlarmSettings.vue'
import AppFooter from './components/AppFooter.vue'
import type { TimeRange, Resolution } from './types'

const {
  currentReading,
  history,
  historyResolution,
  selectedTimeRange,
  setTimeRange,
  selectedResolution,
  setResolution,
  summary,
  hourlyPattern,
  weeklyPattern,
  dayNight,
  workWeekend,
  device,
  connected,
  co2Status,
  co2Percentage,
  loading
} = useCO2Data()

const timeRanges: { value: TimeRange; label: string }[] = [
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: '90d', label: '90d' },
  { value: '1y', label: '1y' },
  { value: 'all', label: 'All' }
]

const resolutions: { value: Resolution; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'raw', label: 'Raw' },
  { value: '5min', label: '5min' },
  { value: '10min', label: '10min' },
  { value: '15min', label: '15min' },
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' }
]

function formatTime(timestamp: string | null): string {
  if (!timestamp) return '--:--'
  return new Date(timestamp).toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function formatHour(hour: number): string {
  return `${hour.toString().padStart(2, '0')}:00`
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
    <!-- Header -->
    <header class="border-b border-gray-700 bg-gray-900/50 backdrop-blur sticky top-0 z-10">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <h1 class="text-xl font-bold text-white">CO2 Monitor</h1>
            <p class="text-sm text-gray-400">TFA Dostmann AirControl Mini</p>
          </div>
        </div>
        <div class="flex items-center gap-4">
          <span v-if="loading" class="text-gray-400 text-sm">Loading...</span>
          <AlarmSettings />
          <span class="flex items-center gap-2 text-sm">
            <span
              class="w-2 h-2 rounded-full"
              :class="connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'"
            ></span>
            <span :class="connected ? 'text-green-400' : 'text-red-400'">
              {{ connected ? 'Connected' : 'Disconnected' }}
            </span>
          </span>
        </div>
      </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-8 pb-16">
      <!-- Current Reading Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <!-- CO2 Card -->
        <div
          class="col-span-1 md:col-span-2 rounded-2xl p-6 border transition-colors"
          :class="[co2Status.bg, 'border-gray-700']"
        >
          <div class="flex items-start justify-between mb-4">
            <div>
              <p class="text-gray-400 text-sm font-medium uppercase tracking-wide">CO2 Level</p>
              <div class="flex items-baseline gap-2 mt-1">
                <span class="text-5xl font-bold text-white">
                  {{ currentReading.co2_ppm ?? '---' }}
                </span>
                <span class="text-2xl text-gray-400">ppm</span>
              </div>
            </div>
            <span
              class="px-3 py-1 rounded-full text-sm font-medium"
              :class="{
                'bg-green-500/20 text-green-400': co2Status.color === 'green',
                'bg-yellow-500/20 text-yellow-400': co2Status.color === 'yellow',
                'bg-orange-500/20 text-orange-400': co2Status.color === 'orange',
                'bg-red-500/20 text-red-400': co2Status.color === 'red',
                'bg-gray-500/20 text-gray-400': co2Status.color === 'gray'
              }"
            >
              {{ co2Status.label }}
            </span>
          </div>

          <div class="h-3 bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-500"
              :class="{
                'bg-green-500': co2Status.color === 'green',
                'bg-yellow-500': co2Status.color === 'yellow',
                'bg-orange-500': co2Status.color === 'orange',
                'bg-red-500': co2Status.color === 'red',
                'bg-gray-500': co2Status.color === 'gray'
              }"
              :style="{ width: `${co2Percentage}%` }"
            ></div>
          </div>
          <div class="flex justify-between text-xs text-gray-500 mt-1">
            <span>400 ppm (outdoor)</span>
            <span>2000 ppm</span>
          </div>

          <p class="text-gray-500 text-sm mt-4">
            Last updated: {{ formatTime(currentReading.timestamp) }}
          </p>
        </div>

        <!-- Temperature Card -->
        <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700">
          <p class="text-gray-400 text-sm font-medium uppercase tracking-wide">Temperature</p>
          <div class="flex items-baseline gap-2 mt-1">
            <span class="text-5xl font-bold text-white">
              {{ currentReading.temperature_celsius?.toFixed(1) ?? '--.-' }}
            </span>
            <span class="text-2xl text-gray-400">°C</span>
          </div>
          <div class="mt-6 flex items-center gap-2 text-orange-400">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707" />
            </svg>
            <span class="text-sm">Indoor temperature</span>
          </div>
        </div>
      </div>

      <!-- Time Range & Resolution Selector -->
      <div class="flex flex-wrap items-center gap-4 mb-4">
        <div class="flex flex-wrap gap-2">
          <span class="text-gray-500 text-sm self-center mr-1">Range:</span>
          <button
            v-for="range in timeRanges"
            :key="range.value"
            @click="setTimeRange(range.value)"
            class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            :class="selectedTimeRange === range.value
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
          >
            {{ range.label }}
          </button>
        </div>
        <div class="flex flex-wrap gap-2">
          <span class="text-gray-500 text-sm self-center mr-1">Resolution:</span>
          <button
            v-for="res in resolutions"
            :key="res.value"
            @click="setResolution(res.value)"
            class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            :class="selectedResolution === res.value
              ? 'bg-green-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700'"
          >
            {{ res.label }}
          </button>
        </div>
      </div>

      <!-- Chart -->
      <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700 mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-white">History</h2>
          <span class="text-sm text-gray-500">
            Resolution: {{ historyResolution }}
          </span>
        </div>
        <CO2Chart :history="history" :resolution="historyResolution" />
      </div>

      <!-- Pattern Analysis -->
      <h2 class="text-xl font-bold text-white mb-4">Pattern Analysis</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <!-- Day vs Night -->
        <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700">
          <h3 class="text-lg font-semibold text-white mb-4">Day vs Night</h3>
          <div class="grid grid-cols-2 gap-4">
            <div class="text-center p-4 bg-yellow-900/20 rounded-xl">
              <div class="text-yellow-400 text-sm mb-2">Day ({{ dayNight?.day.hours }})</div>
              <div class="text-3xl font-bold text-white">
                {{ dayNight?.day.co2_avg ?? '---' }}
              </div>
              <div class="text-gray-500 text-sm">ppm avg</div>
            </div>
            <div class="text-center p-4 bg-indigo-900/20 rounded-xl">
              <div class="text-indigo-400 text-sm mb-2">Night ({{ dayNight?.night.hours }})</div>
              <div class="text-3xl font-bold text-white">
                {{ dayNight?.night.co2_avg ?? '---' }}
              </div>
              <div class="text-gray-500 text-sm">ppm avg</div>
            </div>
          </div>
        </div>

        <!-- Workday vs Weekend -->
        <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700">
          <h3 class="text-lg font-semibold text-white mb-4">Workday vs Weekend</h3>
          <div class="grid grid-cols-2 gap-4">
            <div class="text-center p-4 bg-blue-900/20 rounded-xl">
              <div class="text-blue-400 text-sm mb-2">Workday</div>
              <div class="text-3xl font-bold text-white">
                {{ workWeekend?.workday.co2_avg ?? '---' }}
              </div>
              <div class="text-gray-500 text-xs">{{ workWeekend?.workday.description }}</div>
            </div>
            <div class="text-center p-4 bg-green-900/20 rounded-xl">
              <div class="text-green-400 text-sm mb-2">Weekend</div>
              <div class="text-3xl font-bold text-white">
                {{ workWeekend?.weekend.co2_avg ?? '---' }}
              </div>
              <div class="text-gray-500 text-xs">{{ workWeekend?.weekend.description }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Hourly Pattern -->
      <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700 mb-8">
        <h3 class="text-lg font-semibold text-white mb-4">Average by Hour of Day</h3>
        <div class="flex gap-1 h-32 items-end">
          <div
            v-for="h in hourlyPattern"
            :key="h.hour"
            class="flex-1 bg-blue-600/50 hover:bg-blue-500/50 rounded-t transition-colors relative group"
            :style="{ height: h.co2_avg ? `${Math.max(10, (h.co2_avg - 400) / 16)}%` : '10%' }"
          >
            <div class="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-gray-900 px-2 py-1 rounded text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
              {{ formatHour(h.hour) }}: {{ h.co2_avg ?? '---' }} ppm
            </div>
          </div>
        </div>
        <div class="flex justify-between text-xs text-gray-500 mt-2">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>23:00</span>
        </div>
      </div>

      <!-- Weekly Pattern -->
      <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700 mb-8">
        <h3 class="text-lg font-semibold text-white mb-4">Average by Day of Week</h3>
        <div class="grid grid-cols-7 gap-2">
          <div
            v-for="d in weeklyPattern"
            :key="d.day"
            class="text-center p-3 rounded-xl"
            :class="d.day_num >= 5 ? 'bg-green-900/20' : 'bg-blue-900/20'"
          >
            <div class="text-sm font-medium" :class="d.day_num >= 5 ? 'text-green-400' : 'text-blue-400'">
              {{ d.day }}
            </div>
            <div class="text-xl font-bold text-white mt-1">
              {{ d.co2_avg ?? '---' }}
            </div>
            <div class="text-xs text-gray-500">ppm</div>
          </div>
        </div>
      </div>

      <!-- Statistics Summary -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700">
          <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-4">Last 24 Hours</h3>
          <div class="space-y-2">
            <div class="flex justify-between">
              <span class="text-gray-500">CO2 Avg</span>
              <span class="text-white font-medium">{{ summary?.last_24h.co2.avg ?? '---' }} ppm</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">CO2 Max</span>
              <span class="text-white font-medium">{{ summary?.last_24h.co2.max ?? '---' }} ppm</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Measurements</span>
              <span class="text-white font-medium">{{ summary?.last_24h.count ?? '---' }}</span>
            </div>
          </div>
        </div>

        <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700">
          <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-4">Last 7 Days</h3>
          <div class="space-y-2">
            <div class="flex justify-between">
              <span class="text-gray-500">CO2 Avg</span>
              <span class="text-white font-medium">{{ summary?.last_7d.co2.avg ?? '---' }} ppm</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">CO2 Max</span>
              <span class="text-white font-medium">{{ summary?.last_7d.co2.max ?? '---' }} ppm</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Measurements</span>
              <span class="text-white font-medium">{{ summary?.last_7d.count ?? '---' }}</span>
            </div>
          </div>
        </div>

        <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700">
          <h3 class="text-sm font-medium text-gray-400 uppercase tracking-wide mb-4">Last 30 Days</h3>
          <div class="space-y-2">
            <div class="flex justify-between">
              <span class="text-gray-500">CO2 Avg</span>
              <span class="text-white font-medium">{{ summary?.last_30d.co2.avg ?? '---' }} ppm</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">CO2 Max</span>
              <span class="text-white font-medium">{{ summary?.last_30d.co2.max ?? '---' }} ppm</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Measurements</span>
              <span class="text-white font-medium">{{ summary?.last_30d.count ?? '---' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Device Info -->
      <div class="rounded-2xl bg-gray-800/50 p-6 border border-gray-700">
        <h2 class="text-lg font-semibold text-white mb-4">Device Information</h2>
        <div class="flex items-center gap-4">
          <div
            class="w-3 h-3 rounded-full"
            :class="device?.connected ? 'bg-green-500' : 'bg-red-500'"
          ></div>
          <div>
            <p class="text-white font-medium">
              {{ device?.devices[0]?.product ?? 'Unknown Device' }}
            </p>
            <p class="text-gray-500 text-sm">
              VID: {{ device?.devices[0]?.vendor_id ?? '----' }} |
              PID: {{ device?.devices[0]?.product_id ?? '----' }}
            </p>
          </div>
        </div>
        <p class="text-gray-500 text-sm mt-4">
          Total measurements: {{ summary?.total_measurements ?? 0 }}
        </p>
      </div>
    </main>

    <AppFooter />
  </div>
</template>
