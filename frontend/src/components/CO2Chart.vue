<script setup lang="ts">
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import type { HistoryEntry, MinuteEntry, HourlyEntry, DailyEntry } from '../types'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

type AnyHistoryEntry = HistoryEntry | MinuteEntry | HourlyEntry | DailyEntry

const props = defineProps<{
  history: AnyHistoryEntry[]
  resolution?: 'raw' | '5min' | '10min' | '15min' | 'hourly' | 'daily'
}>()

// Helper to get timestamp from any entry type
function getTimestamp(entry: AnyHistoryEntry): string {
  if ('date' in entry) return entry.date
  return entry.timestamp
}

// Helper to get CO2 value from any entry type
function getCO2(entry: AnyHistoryEntry): number {
  if ('co2_avg' in entry) return entry.co2_avg
  return entry.co2_ppm
}

// Helper to get temperature from any entry type
function getTemperature(entry: AnyHistoryEntry): number | null {
  if ('temp_avg' in entry) return entry.temp_avg
  return entry.temperature_celsius
}

const chartData = computed(() => {
  const resolution = props.resolution || 'raw'
  const sorted = [...props.history].sort(
    (a, b) => new Date(getTimestamp(a)).getTime() - new Date(getTimestamp(b)).getTime()
  )

  return {
    labels: sorted.map(h => {
      const ts = getTimestamp(h)
      const date = new Date(ts)

      if (resolution === 'daily') {
        return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })
      } else if (resolution === 'hourly') {
        return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) +
               ' ' + date.toLocaleTimeString('de-DE', { hour: '2-digit' }) + 'h'
      } else if (resolution === '5min' || resolution === '10min' || resolution === '15min') {
        return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) +
               ' ' + date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
      }
      return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
    }),
    datasets: [
      {
        label: resolution === 'raw' ? 'CO2 (ppm)' : 'CO2 Avg (ppm)',
        data: sorted.map(h => getCO2(h)),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.3,
        yAxisID: 'y'
      },
      {
        label: resolution === 'raw' ? 'Temperature (°C)' : 'Temp Avg (°C)',
        data: sorted.map(h => getTemperature(h)),
        borderColor: 'rgb(249, 115, 22)',
        backgroundColor: 'rgba(249, 115, 22, 0.1)',
        fill: false,
        tension: 0.3,
        yAxisID: 'y1'
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index' as const,
    intersect: false
  },
  plugins: {
    legend: {
      labels: {
        color: 'rgb(156, 163, 175)'
      }
    },
    tooltip: {
      backgroundColor: 'rgba(17, 24, 39, 0.9)',
      titleColor: 'rgb(243, 244, 246)',
      bodyColor: 'rgb(156, 163, 175)',
      borderColor: 'rgb(75, 85, 99)',
      borderWidth: 1
    }
  },
  scales: {
    x: {
      grid: {
        color: 'rgba(75, 85, 99, 0.3)'
      },
      ticks: {
        color: 'rgb(156, 163, 175)',
        maxTicksLimit: 12
      }
    },
    y: {
      type: 'linear' as const,
      display: true,
      position: 'left' as const,
      min: 400,
      grid: {
        color: 'rgba(75, 85, 99, 0.3)'
      },
      ticks: {
        color: 'rgb(59, 130, 246)'
      },
      title: {
        display: true,
        text: 'CO2 (ppm)',
        color: 'rgb(59, 130, 246)'
      }
    },
    y1: {
      type: 'linear' as const,
      display: true,
      position: 'right' as const,
      grid: {
        drawOnChartArea: false
      },
      ticks: {
        color: 'rgb(249, 115, 22)'
      },
      title: {
        display: true,
        text: 'Temperature (°C)',
        color: 'rgb(249, 115, 22)'
      }
    }
  }
}
</script>

<template>
  <div class="h-80">
    <Line :data="chartData" :options="chartOptions" />
  </div>
</template>
