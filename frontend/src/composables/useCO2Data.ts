import { ref, computed, onMounted, onUnmounted } from 'vue'
import type {
  Reading, HistoryEntry, HistoryResponse, Resolution,
  Statistics, DeviceInfo, HourlyPattern, WeeklyPattern,
  DayNightComparison, WorkWeekendComparison, Summary, TimeRange
} from '../types'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8080' : ''

export function useCO2Data() {
  // Current reading
  const currentReading = ref<Reading>({
    co2_ppm: null,
    temperature_celsius: null,
    timestamp: null
  })

  // History data
  const historyResponse = ref<HistoryResponse | null>(null)
  const selectedTimeRange = ref<TimeRange>('24h')
  const selectedResolution = ref<Resolution>('auto')

  // Statistics
  const statistics = ref<Statistics | null>(null)
  const summary = ref<Summary | null>(null)

  // Patterns
  const hourlyPattern = ref<HourlyPattern[]>([])
  const weeklyPattern = ref<WeeklyPattern[]>([])
  const dayNight = ref<DayNightComparison | null>(null)
  const workWeekend = ref<WorkWeekendComparison | null>(null)

  // Device and connection
  const device = ref<DeviceInfo | null>(null)
  const connected = ref(false)
  const error = ref<string | null>(null)
  const loading = ref(false)

  let ws: WebSocket | null = null

  // Computed properties
  const co2Status = computed(() => {
    const ppm = currentReading.value.co2_ppm
    if (ppm === null) return { label: 'Unknown', color: 'gray', bg: 'bg-gray-700' }
    if (ppm < 800) return { label: 'Good', color: 'green', bg: 'bg-green-900/50' }
    if (ppm < 1000) return { label: 'OK', color: 'yellow', bg: 'bg-yellow-900/50' }
    if (ppm < 1500) return { label: 'Poor', color: 'orange', bg: 'bg-orange-900/50' }
    return { label: 'Bad', color: 'red', bg: 'bg-red-900/50' }
  })

  const co2Percentage = computed(() => {
    const ppm = currentReading.value.co2_ppm
    if (ppm === null) return 0
    return Math.min(100, Math.max(0, ((ppm - 400) / 1600) * 100))
  })

  // Helper to get history data as the appropriate type
  const history = computed(() => {
    if (!historyResponse.value) return []
    return historyResponse.value.data as HistoryEntry[]
  })

  const historyResolution = computed(() => {
    return historyResponse.value?.resolution || 'raw'
  })

  // Time range to API params
  function timeRangeToParams(range: TimeRange): { hours?: number; days?: number } {
    switch (range) {
      case '24h': return { hours: 24 }
      case '7d': return { days: 7 }
      case '30d': return { days: 30 }
      case '90d': return { days: 90 }
      case '1y': return { days: 365 }
      case 'all': return { days: 3650 } // ~10 years
      default: return { hours: 24 }
    }
  }

  // API calls
  async function fetchHistory(range?: TimeRange, resolution?: Resolution) {
    const r = range || selectedTimeRange.value
    const res_value = resolution || selectedResolution.value
    const params = timeRangeToParams(r)
    const queryParams = new URLSearchParams()

    if (params.hours) queryParams.set('hours', params.hours.toString())
    if (params.days) queryParams.set('days', params.days.toString())
    queryParams.set('resolution', res_value)

    try {
      loading.value = true
      const res = await fetch(`${API_BASE}/api/history?${queryParams}`)
      historyResponse.value = await res.json()
    } catch (e) {
      console.error('Failed to fetch history:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStatistics(hours: number = 24) {
    try {
      const res = await fetch(`${API_BASE}/api/statistics?hours=${hours}`)
      statistics.value = await res.json()
    } catch (e) {
      console.error('Failed to fetch statistics:', e)
    }
  }

  async function fetchSummary() {
    try {
      const res = await fetch(`${API_BASE}/api/stats/summary`)
      summary.value = await res.json()
    } catch (e) {
      console.error('Failed to fetch summary:', e)
    }
  }

  async function fetchPatterns() {
    try {
      const [hourlyRes, weeklyRes, dayNightRes, workWeekendRes] = await Promise.all([
        fetch(`${API_BASE}/api/patterns/hourly`),
        fetch(`${API_BASE}/api/patterns/weekly`),
        fetch(`${API_BASE}/api/patterns/day-night`),
        fetch(`${API_BASE}/api/patterns/work-weekend`)
      ])

      hourlyPattern.value = await hourlyRes.json()
      weeklyPattern.value = await weeklyRes.json()
      dayNight.value = await dayNightRes.json()
      workWeekend.value = await workWeekendRes.json()
    } catch (e) {
      console.error('Failed to fetch patterns:', e)
    }
  }

  async function fetchDevice() {
    try {
      const res = await fetch(`${API_BASE}/api/device`)
      device.value = await res.json()
    } catch (e) {
      console.error('Failed to fetch device info:', e)
    }
  }

  function setTimeRange(range: TimeRange) {
    selectedTimeRange.value = range
    fetchHistory(range)
  }

  function setResolution(resolution: Resolution) {
    selectedResolution.value = resolution
    fetchHistory(undefined, resolution)
  }

  // WebSocket
  function connectWebSocket() {
    const wsUrl = import.meta.env.DEV
      ? 'ws://localhost:8080/ws'
      : `ws://${window.location.host}/ws`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
      error.value = null
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        currentReading.value = data
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onclose = () => {
      connected.value = false
      setTimeout(connectWebSocket, 3000)
    }

    ws.onerror = () => {
      error.value = 'WebSocket connection error'
    }
  }

  function disconnect() {
    if (ws) {
      ws.close()
      ws = null
    }
  }

  // Lifecycle
  onMounted(() => {
    connectWebSocket()
    fetchHistory()
    fetchStatistics()
    fetchSummary()
    fetchPatterns()
    fetchDevice()

    // Refresh data periodically
    const historyInterval = setInterval(() => {
      fetchHistory()
      fetchStatistics()
    }, 60000)

    const patternsInterval = setInterval(() => {
      fetchPatterns()
      fetchSummary()
    }, 300000) // Every 5 minutes

    onUnmounted(() => {
      clearInterval(historyInterval)
      clearInterval(patternsInterval)
      disconnect()
    })
  })

  return {
    // Current
    currentReading,
    co2Status,
    co2Percentage,

    // History
    history,
    historyResponse,
    historyResolution,
    selectedTimeRange,
    setTimeRange,
    selectedResolution,
    setResolution,

    // Statistics
    statistics,
    summary,

    // Patterns
    hourlyPattern,
    weeklyPattern,
    dayNight,
    workWeekend,

    // Device
    device,
    connected,
    error,
    loading,

    // Methods
    fetchHistory,
    fetchStatistics,
    fetchPatterns,
    fetchSummary
  }
}
