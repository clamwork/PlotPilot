import { apiAxios, resolveHttpUrl } from './config'

export type ServiceId = 'backend' | 'frontend'
export type ServiceAction = 'start' | 'stop' | 'restart'

export interface ManagedServiceStatus {
  id: ServiceId
  label: string
  running: boolean
  port?: number | null
  url?: string | null
  detail: string
}

export interface ServiceOverview {
  backend: ManagedServiceStatus
  frontend: ManagedServiceStatus
}

export interface ServiceActionResult {
  service_id: string
  running: boolean
  port?: number | null
  url?: string | null
  message: string
}

export interface EnvironmentInfo {
  python_available: boolean
  has_embedded_python: boolean
  project_root: string
}

export interface RuntimeLogSnapshot {
  path: string
  exists: boolean
  line_count: number
  lines: string[]
}

function isTauriRuntime(): boolean {
  if (typeof window === 'undefined') return false
  const w = window as Window & {
    __TAURI__?: unknown
    __TAURI_INTERNALS__?: unknown
  }
  return !!(w.__TAURI__ || w.__TAURI_INTERNALS__)
}

async function invokeTauri<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core')
  return invoke<T>(command, args)
}

async function getBrowserOverview(): Promise<ServiceOverview> {
  let running = false
  let detail = '本地 Web 入口可直接通过浏览器访问。'

  try {
    const res = await fetch(resolveHttpUrl('/health'), {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    })
    running = res.ok
    if (!res.ok) detail = `健康检查失败，HTTP ${res.status}。`
  } catch {
    detail = '当前无法连通本地服务，请确认后端是否已启动。'
  }

  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  return {
    backend: {
      id: 'backend',
      label: 'Backend API',
      running,
      url: running ? `${origin}/health` : undefined,
      detail: running
        ? 'FastAPI 服务可用。'
        : '浏览器模式下无法直接拉起后端，请先手动启动服务。',
    },
    frontend: {
      id: 'frontend',
      label: 'Web Portal',
      running,
      url: origin,
      detail,
    },
  }
}

export const servicesApi = {
  isTauriRuntime,

  async getOverview(): Promise<ServiceOverview> {
    if (isTauriRuntime()) {
      return invokeTauri<ServiceOverview>('get_service_overview')
    }
    return getBrowserOverview()
  },

  async runAction(action: ServiceAction, serviceId: ServiceId): Promise<ServiceActionResult> {
    if (!isTauriRuntime()) {
      throw new Error('浏览器模式下不支持直接控制本地服务')
    }

    if (action === 'start') {
      return invokeTauri<ServiceActionResult>('start_service', { serviceId })
    }
    if (action === 'stop') {
      return invokeTauri<ServiceActionResult>('stop_service', { serviceId })
    }
    return invokeTauri<ServiceActionResult>('restart_service', { serviceId })
  },

  async openUrl(url: string): Promise<void> {
    if (isTauriRuntime()) {
      await invokeTauri('open_in_browser', { url })
      return
    }
    window.open(url, '_blank', 'noopener,noreferrer')
  },

  async getHealthPayload(): Promise<Record<string, unknown> | null> {
    try {
      const response = await apiAxios.get('/health')
      return response as unknown as Record<string, unknown>
    } catch {
      return null
    }
  },

  async getEnvironmentInfo(): Promise<EnvironmentInfo | null> {
    if (!isTauriRuntime()) {
      return null
    }
    try {
      return await invokeTauri<EnvironmentInfo>('check_environment')
    } catch {
      return null
    }
  },

  async getRuntimeLogs(lines = 200): Promise<RuntimeLogSnapshot | null> {
    if (!isTauriRuntime()) {
      return null
    }
    try {
      return await invokeTauri<RuntimeLogSnapshot>('get_runtime_logs', { lines })
    } catch {
      return null
    }
  },
}
