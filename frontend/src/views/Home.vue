<template>
  <div class="service-console">
    <div class="service-console__bg" aria-hidden="true" />

    <main class="service-console__container">
      <section class="hero-card">
        <div class="hero-card__eyebrow">PlotPilot Local Runtime</div>
        <div class="hero-card__header">
          <div class="hero-copy">
            <h1 class="hero-card__title">本地服务控制台</h1>
            <p class="hero-card__subtitle">
              桌面壳只负责守护本地运行环境。你可以在这里查看服务状态、执行启动/停止/重启，
              再通过浏览器进入实际业务界面。
            </p>
          </div>

          <div class="hero-card__actions">
            <n-button secondary strong @click="refreshDashboard" :loading="loading">
              立即刷新
            </n-button>
            <n-button
              strong
              :type="autoRefreshEnabled ? 'success' : 'default'"
              @click="toggleAutoRefresh"
            >
              {{ autoRefreshEnabled ? '自动巡检中' : '开启自动巡检' }}
            </n-button>
            <n-button
              type="primary"
              strong
              :disabled="!webPortalUrl"
              @click="openWebPortal"
            >
              打开浏览器入口
            </n-button>
          </div>
        </div>

        <div v-if="hasServiceIssue" class="alert-strip">
          <div class="alert-strip__dot" />
          <div>
            <strong>发现本地服务异常</strong>
            <p>至少有一个关键服务不可用。可直接在下方执行启动或重启。</p>
          </div>
        </div>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="hero-stat__label">运行服务</span>
            <strong class="hero-stat__value">{{ runningCount }}/2</strong>
          </div>
          <div class="hero-stat">
            <span class="hero-stat__label">浏览器入口</span>
            <strong class="hero-stat__value">{{ webPortalUrl || '等待服务' }}</strong>
          </div>
          <div class="hero-stat">
            <span class="hero-stat__label">上次巡检</span>
            <strong class="hero-stat__value">{{ lastRefreshText }}</strong>
          </div>
          <div class="hero-stat">
            <span class="hero-stat__label">巡检模式</span>
            <strong class="hero-stat__value">{{ autoRefreshEnabled ? '每 8 秒自动轮询' : '手动刷新' }}</strong>
          </div>
        </div>
      </section>

      <section class="grid-section">
        <article
          v-for="service in serviceCards"
          :key="service.id"
          class="service-card"
          :class="{
            'service-card--down': service.visualState === 'stopped' || service.visualState === 'failed',
            'service-card--transition': service.isTransitioning,
          }"
        >
          <div class="service-card__top">
            <div>
              <div class="service-card__label-row">
                <h2 class="service-card__title">{{ service.label }}</h2>
                <n-tag
                  size="small"
                  round
                  :type="service.badgeType"
                  :bordered="false"
                >
                  {{ service.badgeLabel }}
                </n-tag>
              </div>
              <p class="service-card__desc">{{ service.statusDetail }}</p>
              <div class="service-state-row">
                <span class="service-state-row__label">{{ "\u72b6\u6001\u673a\u9636\u6bb5" }}</span>
                <strong>{{ service.stateHeadline }}</strong>
              </div>
            </div>
            <div class="service-indicator" :class="service.indicatorClass" />
          </div>

          <div class="service-meta">
            <div class="service-meta__item">
              <span class="service-meta__label">访问地址</span>
              <span class="service-meta__value">{{ service.url || '未就绪' }}</span>
            </div>
            <div class="service-meta__item">
              <span class="service-meta__label">监听端口</span>
              <span class="service-meta__value">{{ service.port ?? '—' }}</span>
            </div>
            <div class="service-meta__item">
              <span class="service-meta__label">建议动作</span>
              <span class="service-meta__value">{{ service.recommendation }}</span>
            </div>
            <div class="service-meta__item">
              <span class="service-meta__label">依赖关系</span>
              <span class="service-meta__value">{{ service.id === 'frontend' ? '依赖后端 HTTP 服务' : '核心本地 API 进程' }}</span>
            </div>
          </div>

          <div class="service-card__actions">
            <n-button
              type="success"
              secondary
              :loading="activeAction?.serviceId === service.id && activeAction?.action === 'start'"
              :disabled="!service.canStart"
              @click="runServiceAction('start', service.id)"
            >
              启动
            </n-button>
            <n-button
              type="warning"
              secondary
              :loading="activeAction?.serviceId === service.id && activeAction?.action === 'stop'"
              :disabled="!service.canStop"
              @click="runServiceAction('stop', service.id)"
            >
              停止
            </n-button>
            <n-button
              type="primary"
              secondary
              :loading="activeAction?.serviceId === service.id && activeAction?.action === 'restart'"
              :disabled="!service.canRestart"
              @click="runServiceAction('restart', service.id)"
            >
              重启
            </n-button>
            <n-button
              quaternary
              :disabled="!service.url"
              @click="service.url && servicesApi.openUrl(service.url)"
            >
              打开地址
            </n-button>
          </div>
        </article>
      </section>

      <section class="details-grid">
        <article class="info-card">
          <div class="section-headline">
            <h3 class="info-card__title">运行环境</h3>
            <n-tag size="small" :bordered="false" type="info">桌面壳侧</n-tag>
          </div>
          <div class="env-grid">
            <div class="env-item">
              <span class="env-item__label">Python 可用</span>
              <strong class="env-item__value">{{ environmentInfo?.python_available ? '是' : '否 / 未知' }}</strong>
            </div>
            <div class="env-item">
              <span class="env-item__label">内嵌 Python 包</span>
              <strong class="env-item__value">{{ environmentInfo?.has_embedded_python ? '已提供' : '未检测到' }}</strong>
            </div>
            <div class="env-item env-item--wide">
              <span class="env-item__label">项目根目录</span>
              <strong class="env-item__value env-item__value--path">{{ environmentInfo?.project_root || '未获取到' }}</strong>
            </div>
          </div>
        </article>

        <article class="info-card">
          <div class="section-headline">
            <h3 class="info-card__title">日志筛选面板</h3>
            <div class="log-panel-actions">
              <n-button
                text
                :type="logAutoTailEnabled ? 'success' : 'default'"
                @click="toggleLogAutoTail"
              >
                {{ logAutoTailEnabled ? '日志追尾中' : '开启日志追尾' }}
              </n-button>
              <n-button text type="primary" @click="refreshDashboard">
                刷新日志
              </n-button>
            </div>
          </div>

          <div class="log-toolbar">
            <n-input
              v-model:value="logSearch"
              clearable
              placeholder="搜索日志关键词"
              class="log-toolbar__search"
            />
            <div class="log-toolbar__toggles">
              <n-button
                size="small"
                secondary
                :type="logLevelFilter === 'all' ? 'primary' : 'default'"
                @click="logLevelFilter = 'all'"
              >
                全部
              </n-button>
              <n-button
                size="small"
                secondary
                :type="logLevelFilter === 'error' ? 'error' : 'default'"
                @click="logLevelFilter = 'error'"
              >
                仅错误
              </n-button>
              <n-button
                size="small"
                secondary
                :type="logLevelFilter === 'warning' ? 'warning' : 'default'"
                @click="logLevelFilter = 'warning'"
              >
                仅警告
              </n-button>
              <n-button size="small" quaternary @click="clearLogFilters">
                清空筛选
              </n-button>
            </div>
          </div>

          <div class="log-badges">
            <n-tag size="small" :bordered="false" type="default">总计 {{ runtimeLogs?.line_count ?? 0 }}</n-tag>
            <n-tag size="small" :bordered="false" type="error">ERROR {{ logStats.error }}</n-tag>
            <n-tag size="small" :bordered="false" type="warning">WARNING {{ logStats.warning }}</n-tag>
            <n-tag size="small" :bordered="false" type="info">INFO {{ logStats.info }}</n-tag>
            <n-tag size="small" :bordered="false" type="success">显示 {{ filteredLogEntries.length }}</n-tag>
          </div>

          <div class="log-summary">
            <span>日志路径：{{ runtimeLogs?.path || '未获取到' }}</span>
            <span>筛选状态：{{ logFilterSummary }}</span>
            <span>追尾状态：{{ logAutoTailEnabled ? '自动刷新并滚动到底部' : '手动查看' }}</span>
          </div>

          <div ref="logViewerRef" class="log-viewer">
            <div v-if="filteredLogEntries.length" class="log-lines">
              <div
                v-for="entry in filteredLogEntries"
                :key="entry.id"
                class="log-line"
                :class="`log-line--${entry.level}`"
              >
                <span class="log-line__badge">{{ entry.levelLabel }}</span>
                <code class="log-line__text">{{ entry.text }}</code>
              </div>
            </div>
            <div v-else class="log-empty">
              当前筛选条件下没有匹配日志。
            </div>
          </div>
        </article>
      </section>

      <section class="details-grid">
        <article class="info-card">
          <div class="section-headline">
            <h3 class="info-card__title">后端健康信息</h3>
            <n-tag size="small" :bordered="false" :type="healthPayload ? 'success' : 'default'">
              {{ healthPayload ? '已获取' : '暂无数据' }}
            </n-tag>
          </div>
          <pre class="health-preview">{{ healthPreview }}</pre>
        </article>
        <article class="info-card">
          <div class="section-headline">
            <h3 class="info-card__title">日志说明</h3>
            <n-tag size="small" :bordered="false" type="warning">高亮与筛选</n-tag>
          </div>
          <ul class="info-list">
            <li>这里读取的是本地真实日志文件，不是模拟数据。</li>
            <li>支持按关键词搜索，也支持只看 ERROR 或 WARNING。</li>
            <li>日志颜色遵循语义级别，便于快速扫出异常。</li>
            <li>默认展示最后 200 行，适合定位最近崩溃、超时与重启问题。</li>
          </ul>
        </article>
      </section>

      <section class="details-grid details-grid--bottom">
        <article class="info-card">
          <div class="section-headline">
            <h3 class="info-card__title">最近操作记录</h3>
            <n-tag size="small" :bordered="false" type="default">{{ actionLogs.length }} 条</n-tag>
          </div>
          <div v-if="actionLogs.length" class="timeline-list">
            <div v-for="log in actionLogs" :key="log.id" class="timeline-item">
              <div class="timeline-item__marker" :class="`timeline-item__marker--${log.level}`" />
              <div class="timeline-item__content">
                <div class="timeline-item__top">
                  <strong>{{ log.title }}</strong>
                  <span>{{ log.time }}</span>
                </div>
                <p>{{ log.message }}</p>
              </div>
            </div>
          </div>
          <div v-else class="empty-inline">暂无操作记录。</div>
        </article>

        <article class="info-card">
          <div class="section-headline">
            <h3 class="info-card__title">建议运维流程</h3>
            <n-tag size="small" :bordered="false" type="success">推荐</n-tag>
          </div>
          <ul class="info-list">
            <li>先看 ERROR / WARNING 数量，再决定是否重启服务。</li>
            <li>遇到启动失败时，先搜索端口、traceback、exception 等关键词。</li>
            <li>若浏览器入口失效，优先筛选 ERROR，并配合后端健康信息一起看。</li>
            <li>业务页面仍在浏览器中访问，桌面端只承担本地运维职责。</li>
          </ul>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import {
  servicesApi,
  type EnvironmentInfo,
  type ManagedServiceStatus,
  type RuntimeLogSnapshot,
  type ServiceAction,
  type ServiceId,
  type ServiceOverview,
} from '../api/services'

interface ActionLogItem {
  id: number
  title: string
  message: string
  time: string
  level: 'info' | 'success' | 'warning' | 'error'
}

type LogLevelFilter = 'all' | 'error' | 'warning'
type ParsedLogLevel = 'error' | 'warning' | 'info' | 'plain'
type ServiceVisualState = 'running' | 'stopped' | 'starting' | 'stopping' | 'restarting' | 'failed' | 'recovering'
type ServiceTransitionPhase = 'idle' | 'starting' | 'stopping' | 'restarting'
type ServiceBadgeType = 'default' | 'primary' | 'info' | 'success' | 'warning' | 'error'

interface ServiceTransitionSnapshot {
  phase: ServiceTransitionPhase
  lastAction: ServiceAction | null
  lastOutcome: 'success' | 'error' | null
  message: string
  changedAt: number | null
}

interface ParsedLogEntry {
  id: number
  text: string
  level: ParsedLogLevel
  levelLabel: string
}

interface ServiceCardViewModel extends ManagedServiceStatus {
  visualState: ServiceVisualState
  badgeType: ServiceBadgeType
  badgeLabel: string
  stateHeadline: string
  statusDetail: string
  recommendation: string
  indicatorClass: string[]
  isTransitioning: boolean
  canStart: boolean
  canStop: boolean
  canRestart: boolean
}

const AUTO_REFRESH_INTERVAL = 8000
const SERVICE_STATE_STICKY_MS = 10000

const message = useMessage()
const loading = ref(false)
const autoRefreshEnabled = ref(true)
const overview = ref<ServiceOverview | null>(null)
const healthPayload = ref<Record<string, unknown> | null>(null)
const environmentInfo = ref<EnvironmentInfo | null>(null)
const runtimeLogs = ref<RuntimeLogSnapshot | null>(null)
const lastRefreshAt = ref<Date | null>(null)
const pollTimer = ref<number | null>(null)
const logTailTimer = ref<number | null>(null)
const actionLogs = ref<ActionLogItem[]>([])
const activeAction = ref<{ serviceId: ServiceId; action: ServiceAction } | null>(null)
const logSearch = ref('')
const logLevelFilter = ref<LogLevelFilter>('all')
const logAutoTailEnabled = ref(true)
const logViewerRef = ref<HTMLElement | null>(null)
const serviceTransitions = ref<Record<ServiceId, ServiceTransitionSnapshot>>({
  backend: { phase: 'idle', lastAction: null, lastOutcome: null, message: '', changedAt: null },
  frontend: { phase: 'idle', lastAction: null, lastOutcome: null, message: '', changedAt: null },
})

const serviceCards = computed<ServiceCardViewModel[]>(() => {
  if (!overview.value) return []
  return [overview.value.backend, overview.value.frontend].map(buildServiceCardViewModel)
})

const runningCount = computed(() => serviceCards.value.filter(item => item.running).length)
const hasServiceIssue = computed(() =>
  serviceCards.value.some(item => ['stopped', 'failed'].includes(item.visualState)),
)

const webPortalUrl = computed(() => {
  return overview.value?.frontend.url || overview.value?.backend.url?.replace(/\/health$/, '') || ''
})

const healthPreview = computed(() => {
  if (!healthPayload.value) return '暂无健康数据，请先刷新服务状态。'
  return JSON.stringify(healthPayload.value, null, 2)
})

const parsedLogEntries = computed<ParsedLogEntry[]>(() => {
  const lines = runtimeLogs.value?.lines ?? []
  return lines.map((text, index) => {
    const upper = text.toUpperCase()
    let level: ParsedLogLevel = 'plain'
    let levelLabel = 'LOG'

    if (upper.includes('ERROR') || upper.includes('CRITICAL') || upper.includes('TRACEBACK')) {
      level = 'error'
      levelLabel = 'ERROR'
    } else if (upper.includes('WARNING') || upper.includes('WARN')) {
      level = 'warning'
      levelLabel = 'WARN'
    } else if (upper.includes('INFO')) {
      level = 'info'
      levelLabel = 'INFO'
    }

    return {
      id: index,
      text,
      level,
      levelLabel,
    }
  })
})

const filteredLogEntries = computed(() => {
  const keyword = logSearch.value.trim().toLowerCase()
  return parsedLogEntries.value.filter(entry => {
    if (logLevelFilter.value === 'error' && entry.level !== 'error') return false
    if (logLevelFilter.value === 'warning' && entry.level !== 'warning') return false
    if (keyword && !entry.text.toLowerCase().includes(keyword)) return false
    return true
  })
})

const logStats = computed(() => {
  const stats = { error: 0, warning: 0, info: 0 }
  for (const entry of parsedLogEntries.value) {
    if (entry.level === 'error') stats.error += 1
    else if (entry.level === 'warning') stats.warning += 1
    else if (entry.level === 'info') stats.info += 1
  }
  return stats
})

const logFilterSummary = computed(() => {
  const parts: string[] = []
  if (logLevelFilter.value === 'all') parts.push('全部级别')
  if (logLevelFilter.value === 'error') parts.push('仅 ERROR')
  if (logLevelFilter.value === 'warning') parts.push('仅 WARNING')
  if (logSearch.value.trim()) parts.push(`关键词：${logSearch.value.trim()}`)
  return parts.join(' / ')
})

const lastRefreshText = computed(() => {
  if (!lastRefreshAt.value) return '尚未巡检'
  return lastRefreshAt.value.toLocaleTimeString('zh-CN', { hour12: false })
})

function pushLog(level: ActionLogItem['level'], title: string, messageText: string) {
  actionLogs.value.unshift({
    id: Date.now() + Math.floor(Math.random() * 1000),
    title,
    message: messageText,
    time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    level,
  })
  actionLogs.value = actionLogs.value.slice(0, 10)
}

function clearLogFilters() {
  logSearch.value = ''
  logLevelFilter.value = 'all'
}

function getServiceTransition(serviceId: ServiceId): ServiceTransitionSnapshot {
  return serviceTransitions.value[serviceId]
}

function setServiceTransition(serviceId: ServiceId, patch: Partial<ServiceTransitionSnapshot>) {
  serviceTransitions.value[serviceId] = {
    ...serviceTransitions.value[serviceId],
    ...patch,
    changedAt: Date.now(),
  }
}

function isRecentTransition(snapshot: ServiceTransitionSnapshot) {
  return !!snapshot.changedAt && Date.now() - snapshot.changedAt < SERVICE_STATE_STICKY_MS
}

function buildServiceCardViewModel(service: ManagedServiceStatus): ServiceCardViewModel {
  const transition = getServiceTransition(service.id)
  const isTransitioning = transition.phase !== 'idle'
  const recent = isRecentTransition(transition)

  let visualState: ServiceVisualState = service.running ? 'running' : 'stopped'
  let badgeType: ServiceBadgeType = service.running ? 'success' : 'error'
  let badgeLabel = service.running ? '\u8fd0\u884c\u4e2d' : '\u4e0d\u53ef\u7528'
  let stateHeadline = service.running ? '\u7a33\u5b9a\u8fd0\u884c' : '\u7b49\u5f85\u542f\u52a8'
  let statusDetail = service.detail
  let recommendation = service.running ? '\u53ef\u76f4\u63a5\u6253\u5f00\u6216\u91cd\u542f' : '\u5efa\u8bae\u5148\u542f\u52a8\u6216\u91cd\u542f'

  if (transition.phase === 'starting') {
    visualState = 'starting'
    badgeType = 'warning'
    badgeLabel = '\u542f\u52a8\u4e2d'
    stateHeadline = '\u8fdb\u7a0b\u62c9\u8d77\u4e2d'
    statusDetail = '\u5df2\u53d1\u8d77\u542f\u52a8\u8bf7\u6c42\uff0c\u6b63\u5728\u7b49\u5f85\u672c\u5730\u670d\u52a1\u5c31\u7eea\u5e76\u8fd4\u56de\u8bbf\u95ee\u5730\u5740\u3002'
    recommendation = '\u8bf7\u7b49\u5f85\u542f\u52a8\u5b8c\u6210\uff0c\u671f\u95f4\u4e0d\u8981\u91cd\u590d\u70b9\u51fb\u542f\u52a8\u3002'
  } else if (transition.phase === 'stopping') {
    visualState = 'stopping'
    badgeType = 'warning'
    badgeLabel = '\u505c\u6b62\u4e2d'
    stateHeadline = '\u6b63\u5728\u91ca\u653e\u7aef\u53e3'
    statusDetail = '\u5df2\u53d1\u8d77\u505c\u6b62\u8bf7\u6c42\uff0c\u6b63\u5728\u7ec8\u6b62\u672c\u5730\u8fdb\u7a0b\u5e76\u56de\u6536\u76d1\u542c\u7aef\u53e3\u3002'
    recommendation = '\u8bf7\u7b49\u5f85\u505c\u6b62\u5b8c\u6210\uff0c\u4e4b\u540e\u53ef\u91cd\u65b0\u542f\u52a8\u670d\u52a1\u3002'
  } else if (transition.phase === 'restarting') {
    visualState = 'restarting'
    badgeType = 'info'
    badgeLabel = '\u91cd\u542f\u4e2d'
    stateHeadline = '\u505c\u6b62\u540e\u91cd\u65b0\u62c9\u8d77'
    statusDetail = '\u670d\u52a1\u6b63\u5728\u6267\u884c\u91cd\u542f\u6d41\u7a0b\uff1a\u5148\u505c\u6b62\u65e7\u8fdb\u7a0b\uff0c\u518d\u542f\u52a8\u65b0\u8fdb\u7a0b\u3002'
    recommendation = '\u91cd\u542f\u671f\u95f4\u6d4f\u89c8\u5668\u5165\u53e3\u53ef\u80fd\u77ed\u6682\u4e0d\u53ef\u7528\uff0c\u8bf7\u7a0d\u5019\u3002'
  } else if (recent && transition.lastOutcome === 'error') {
    visualState = 'failed'
    badgeType = 'error'
    badgeLabel = '\u64cd\u4f5c\u5931\u8d25'
    stateHeadline = '\u9700\u8981\u4eba\u5de5\u5904\u7406'
    statusDetail = transition.message || '\u6700\u8fd1\u4e00\u6b21\u670d\u52a1\u64cd\u4f5c\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u65e5\u5fd7\u9762\u677f\u5b9a\u4f4d\u539f\u56e0\u3002'
    recommendation = '\u5efa\u8bae\u5148\u67e5\u770b ERROR \u65e5\u5fd7\uff0c\u518d\u51b3\u5b9a\u91cd\u8bd5\u542f\u52a8\u8fd8\u662f\u91cd\u542f\u3002'
  } else if (recent && transition.lastOutcome === 'success' && transition.lastAction) {
    visualState = 'recovering'
    badgeType = service.running ? 'success' : 'default'
    badgeLabel = transition.lastAction === 'start' ? '\u5df2\u542f\u52a8' : transition.lastAction === 'stop' ? '\u5df2\u505c\u6b62' : '\u5df2\u91cd\u542f'
    stateHeadline = transition.lastAction === 'start' ? '\u521a\u5b8c\u6210\u542f\u52a8' : transition.lastAction === 'stop' ? '\u521a\u5b8c\u6210\u505c\u6b62' : '\u521a\u5b8c\u6210\u91cd\u542f'
    statusDetail = transition.message || service.detail
    recommendation = service.running ? '\u5efa\u8bae\u89c2\u5bdf\u51e0\u79d2\u5e76\u5173\u6ce8\u65e5\u5fd7\u662f\u5426\u7ee7\u7eed\u62a5\u9519\u3002' : '\u5f53\u524d\u53ef\u4fdd\u6301\u505c\u6b62\u72b6\u6001\uff0c\u6216\u6309\u9700\u91cd\u65b0\u542f\u52a8\u3002'
  }

  return {
    ...service,
    visualState,
    badgeType,
    badgeLabel,
    stateHeadline,
    statusDetail,
    recommendation,
    indicatorClass: [
      `service-indicator--${visualState}`,
      ...(isTransitioning ? ['service-indicator--pulse'] : []),
    ],
    isTransitioning,
    canStart: !isTransitioning && !service.running,
    canStop: !isTransitioning && service.running,
    canRestart: !isTransitioning,
  }
}

async function scrollLogToBottom() {
  await nextTick()
  if (logViewerRef.value) {
    logViewerRef.value.scrollTop = logViewerRef.value.scrollHeight
  }
}

async function refreshDashboard(showToast = false) {
  loading.value = true
  try {
    const [logData, overviewData, healthData, envData] = await Promise.all([
      servicesApi.getRuntimeLogs(200),
      servicesApi.getOverview(),
      servicesApi.getHealthPayload(),
      servicesApi.getEnvironmentInfo(),
    ])
    runtimeLogs.value = logData
    overview.value = overviewData
    healthPayload.value = healthData
    environmentInfo.value = envData
    lastRefreshAt.value = new Date()

    if (logAutoTailEnabled.value) {
      void scrollLogToBottom()
    }

    if (showToast) {
      message.success('服务状态已刷新')
    }
  } catch (error) {
    console.error(error)
    pushLog('error', '刷新失败', '获取服务状态失败，请稍后重试。')
    message.error('获取服务状态失败')
  } finally {
    loading.value = false
  }
}

async function runServiceAction(action: ServiceAction, serviceId: ServiceId) {
  activeAction.value = { action, serviceId }
  setServiceTransition(serviceId, {
    phase: action === 'start' ? 'starting' : action === 'stop' ? 'stopping' : 'restarting',
    lastAction: action,
    lastOutcome: null,
    message: '',
  })
  try {
    const result = await servicesApi.runAction(action, serviceId)
    const actionLabel = action === 'start' ? '启动' : action === 'stop' ? '停止' : '重启'
    setServiceTransition(serviceId, {
      phase: 'idle',
      lastAction: action,
      lastOutcome: 'success',
      message: result.message,
    })
    pushLog('success', `${actionLabel} ${serviceId}`, `${result.message}${result.url ? `：${result.url}` : ''}`)
    message.success(result.message)
    await refreshDashboard()
  } catch (error) {
    console.error(error)
    const text = error instanceof Error ? error.message : '服务控制失败'
    setServiceTransition(serviceId, {
      phase: 'idle',
      lastAction: action,
      lastOutcome: 'error',
      message: text,
    })
    pushLog('error', `${serviceId} 操作失败`, text)
    message.error(text)
  } finally {
    activeAction.value = null
  }
}

async function openWebPortal() {
  if (!webPortalUrl.value) {
    message.warning('浏览器入口尚未就绪')
    return
  }
  await servicesApi.openUrl(webPortalUrl.value)
  pushLog('info', '打开浏览器入口', `已请求打开 ${webPortalUrl.value}`)
}

function stopPolling() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function stopLogTailPolling() {
  if (logTailTimer.value !== null) {
    window.clearInterval(logTailTimer.value)
    logTailTimer.value = null
  }
}

function startPolling() {
  stopPolling()
  if (!autoRefreshEnabled.value) return
  pollTimer.value = window.setInterval(() => {
    void refreshDashboard()
  }, AUTO_REFRESH_INTERVAL)
}

function startLogTailPolling() {
  stopLogTailPolling()
  if (!logAutoTailEnabled.value) return
  logTailTimer.value = window.setInterval(() => {
    void refreshDashboard()
  }, 3000)
}

function toggleAutoRefresh() {
  autoRefreshEnabled.value = !autoRefreshEnabled.value
  if (autoRefreshEnabled.value) {
    startPolling()
    pushLog('info', '自动巡检已开启', `控制台将每 ${AUTO_REFRESH_INTERVAL / 1000} 秒刷新一次状态。`)
  } else {
    stopPolling()
    pushLog('warning', '自动巡检已关闭', '当前改为手动刷新模式。')
  }
}

function toggleLogAutoTail() {
  logAutoTailEnabled.value = !logAutoTailEnabled.value
  if (logAutoTailEnabled.value) {
    startLogTailPolling()
    void scrollLogToBottom()
    pushLog('info', '日志追尾已开启', '日志面板将每 3 秒自动刷新并滚动到底部。')
  } else {
    stopLogTailPolling()
    pushLog('warning', '日志追尾已关闭', '日志面板改为手动刷新模式。')
  }
}

onMounted(() => {
  void refreshDashboard()
  startPolling()
  startLogTailPolling()
  pushLog('info', '控制台已启动', '本地服务控制台已就绪。')
})

onBeforeUnmount(() => {
  stopPolling()
  stopLogTailPolling()
})
</script>

<style scoped>
.service-console {
  position: relative;
  min-height: 100vh;
  padding: 32px;
  background: var(--app-page-bg);
  overflow: hidden;
}

.service-console__bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 35%),
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.14), transparent 28%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.02), transparent 55%);
  pointer-events: none;
}

.service-console__container {
  position: relative;
  z-index: 1;
  max-width: 1320px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.hero-card,
.service-card,
.info-card {
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08);
}

.hero-card {
  border-radius: 28px;
  padding: 32px;
}

.hero-card__eyebrow {
  display: inline-flex;
  align-items: center;
  margin-bottom: 18px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  color: var(--color-brand);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-card__header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.hero-copy {
  max-width: 760px;
}

.hero-card__title {
  margin: 0 0 12px;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.05;
  color: var(--app-text-primary);
}

.hero-card__subtitle {
  margin: 0;
  color: var(--app-text-secondary);
  font-size: 16px;
  line-height: 1.75;
}

.hero-card__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.alert-strip {
  margin-top: 20px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
}

.alert-strip p {
  margin: 4px 0 0;
  color: var(--app-text-secondary);
}

.alert-strip__dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: #ef4444;
  margin-top: 4px;
}

.hero-stats {
  margin-top: 24px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.hero-stat {
  padding: 18px 20px;
  border-radius: 20px;
  background: rgba(248, 250, 252, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.16);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hero-stat__label {
  color: var(--app-text-muted);
  font-size: 13px;
}

.hero-stat__value {
  color: var(--app-text-primary);
  font-size: 18px;
  word-break: break-all;
}

.grid-section,
.details-grid {
  display: grid;
  gap: 20px;
}

.grid-section {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.details-grid {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
}

.details-grid--bottom {
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
}

.service-card {
  border-radius: 24px;
  padding: 24px;
}

.service-card--down {
  border-color: rgba(239, 68, 68, 0.22);
}

.service-card--transition {
  border-color: rgba(59, 130, 246, 0.26);
  box-shadow: 0 20px 50px rgba(37, 99, 235, 0.12);
}

.service-card__top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.service-card__label-row,
.section-headline {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.service-card__label-row {
  margin-bottom: 10px;
}

.service-card__title,
.info-card__title {
  margin: 0;
  color: var(--app-text-primary);
}

.service-card__title {
  font-size: 22px;
}

.service-card__desc {
  margin: 0;
  color: var(--app-text-secondary);
  line-height: 1.7;
}

.service-state-row {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  color: var(--app-text-secondary);
  font-size: 13px;
}

.service-state-row__label {
  color: var(--app-text-muted);
}

.service-indicator {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 8px rgba(34, 197, 94, 0.14);
  margin-top: 8px;
}

.service-indicator--down {
  background: #ef4444;
  box-shadow: 0 0 0 8px rgba(239, 68, 68, 0.12);
}

.service-indicator--running,
.service-indicator--recovering {
  background: #22c55e;
  box-shadow: 0 0 0 8px rgba(34, 197, 94, 0.14);
}

.service-indicator--starting,
.service-indicator--stopping {
  background: #f59e0b;
  box-shadow: 0 0 0 8px rgba(245, 158, 11, 0.14);
}

.service-indicator--restarting {
  background: #3b82f6;
  box-shadow: 0 0 0 8px rgba(59, 130, 246, 0.14);
}

.service-indicator--stopped,
.service-indicator--failed {
  background: #ef4444;
  box-shadow: 0 0 0 8px rgba(239, 68, 68, 0.12);
}

.service-indicator--pulse {
  animation: servicePulse 1.4s ease-in-out infinite;
}

.service-meta {
  margin: 22px 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.service-meta__item,
.env-item {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.service-meta__label,
.env-item__label {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.service-meta__value,
.env-item__value {
  color: var(--app-text-primary);
  font-weight: 600;
  word-break: break-all;
}

.env-item__value--path {
  font-size: 13px;
}

.service-card__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.log-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.info-card {
  border-radius: 24px;
  padding: 24px;
}

.env-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.env-item--wide {
  grid-column: 1 / -1;
}

.log-toolbar {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.log-toolbar__search {
  max-width: 360px;
}

.log-toolbar__toggles,
.log-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.log-badges {
  margin-top: 14px;
}

.info-list {
  margin: 16px 0 0;
  padding-left: 20px;
  color: var(--app-text-secondary);
  line-height: 1.85;
}

.log-summary {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--app-text-muted);
  font-size: 13px;
}

.log-viewer,
.health-preview {
  margin-top: 16px;
  border-radius: 18px;
  background: #0f172a;
  overflow: auto;
}

.log-viewer {
  min-height: 320px;
  max-height: 520px;
  padding: 14px;
}

.log-lines {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-line {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(15, 23, 42, 0.45);
}

.log-line--error {
  border-color: rgba(248, 113, 113, 0.35);
  background: rgba(127, 29, 29, 0.28);
}

.log-line--warning {
  border-color: rgba(251, 191, 36, 0.28);
  background: rgba(120, 53, 15, 0.28);
}

.log-line--info {
  border-color: rgba(96, 165, 250, 0.22);
  background: rgba(30, 64, 175, 0.18);
}

.log-line__badge {
  min-width: 54px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  color: #e2e8f0;
  font-size: 11px;
  font-weight: 700;
  text-align: center;
  letter-spacing: 0.04em;
}

.log-line__text {
  color: #dbeafe;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  flex: 1;
}

.log-empty {
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.7;
}

.health-preview {
  padding: 18px;
  color: #dbeafe;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.65;
  min-height: 260px;
}

.timeline-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.timeline-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.timeline-item__marker {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  margin-top: 7px;
  flex-shrink: 0;
}

.timeline-item__marker--info { background: #3b82f6; }
.timeline-item__marker--success { background: #22c55e; }
.timeline-item__marker--warning { background: #f59e0b; }
.timeline-item__marker--error { background: #ef4444; }

.timeline-item__content {
  flex: 1;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.timeline-item__top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: var(--app-text-primary);
}

.timeline-item__top span,
.timeline-item__content p,
.empty-inline {
  color: var(--app-text-secondary);
}

@keyframes servicePulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.18);
    opacity: 0.72;
  }
}

.timeline-item__content p {
  margin: 0;
  line-height: 1.7;
}

.empty-inline {
  margin-top: 16px;
}

@media (max-width: 1100px) {
  .grid-section,
  .details-grid,
  .details-grid--bottom,
  .hero-stats {
    grid-template-columns: 1fr;
  }

  .hero-card__header {
    flex-direction: column;
  }
}

@media (max-width: 768px) {
  .service-console {
    padding: 16px;
  }

  .hero-card,
  .service-card,
  .info-card {
    border-radius: 22px;
    padding: 20px;
  }

  .service-meta,
  .env-grid {
    grid-template-columns: 1fr;
  }

  .env-item--wide {
    grid-column: auto;
  }

  .timeline-item__top {
    flex-direction: column;
  }
}
</style>
