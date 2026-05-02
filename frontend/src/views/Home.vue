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
          :class="{ 'service-card--down': !service.running }"
        >
          <div class="service-card__top">
            <div>
              <div class="service-card__label-row">
                <h2 class="service-card__title">{{ service.label }}</h2>
                <n-tag
                  size="small"
                  round
                  :type="service.running ? 'success' : 'error'"
                  :bordered="false"
                >
                  {{ service.running ? '运行中' : '不可用' }}
                </n-tag>
              </div>
              <p class="service-card__desc">{{ service.detail }}</p>
            </div>
            <div class="service-indicator" :class="{ 'service-indicator--down': !service.running }" />
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
              <span class="service-meta__value">{{ service.running ? '可直接打开或重启' : '建议先启动或重启' }}</span>
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
              :disabled="service.running"
              @click="runServiceAction('start', service.id)"
            >
              启动
            </n-button>
            <n-button
              type="warning"
              secondary
              :loading="activeAction?.serviceId === service.id && activeAction?.action === 'stop'"
              :disabled="!service.running"
              @click="runServiceAction('stop', service.id)"
            >
              停止
            </n-button>
            <n-button
              type="primary"
              secondary
              :loading="activeAction?.serviceId === service.id && activeAction?.action === 'restart'"
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
            <h3 class="info-card__title">真实运行日志</h3>
            <n-button text type="primary" @click="refreshDashboard">
              刷新日志
            </n-button>
          </div>
          <div class="log-summary">
            <span>日志路径：{{ runtimeLogs?.path || '未获取到' }}</span>
            <span>总行数：{{ runtimeLogs?.line_count ?? 0 }}</span>
          </div>
          <pre class="health-preview">{{ runtimeLogText }}</pre>
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
            <n-tag size="small" :bordered="false" type="warning">实时 tail</n-tag>
          </div>
          <ul class="info-list">
            <li>这里读取的是本地真实日志文件，不是模拟数据。</li>
            <li>发布版优先读取 AppData 下的 <code>data/logs/aitext.log</code>。</li>
            <li>开发模式回退读取仓库内的 <code>logs/aitext.log</code>。</li>
            <li>默认展示最后 200 行，便于快速定位最近崩溃或重启问题。</li>
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
            <li>先观察状态灯与健康信息，再决定执行启动、停止或重启。</li>
            <li>如果浏览器入口失效，优先重启 Backend API，再重新打开入口。</li>
            <li>开启自动巡检后，控制台会持续轮询并展示最新状态。</li>
            <li>业务页面仍在浏览器中访问，桌面端只承担本地运维职责。</li>
          </ul>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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

const AUTO_REFRESH_INTERVAL = 8000

const message = useMessage()
const loading = ref(false)
const autoRefreshEnabled = ref(true)
const overview = ref<ServiceOverview | null>(null)
const healthPayload = ref<Record<string, unknown> | null>(null)
const environmentInfo = ref<EnvironmentInfo | null>(null)
const runtimeLogs = ref<RuntimeLogSnapshot | null>(null)
const lastRefreshAt = ref<Date | null>(null)
const pollTimer = ref<number | null>(null)
const actionLogs = ref<ActionLogItem[]>([])
const activeAction = ref<{ serviceId: ServiceId; action: ServiceAction } | null>(null)

const serviceCards = computed<ManagedServiceStatus[]>(() => {
  if (!overview.value) return []
  return [overview.value.backend, overview.value.frontend]
})

const runningCount = computed(() => serviceCards.value.filter(item => item.running).length)
const hasServiceIssue = computed(() => serviceCards.value.some(item => !item.running))

const webPortalUrl = computed(() => {
  return overview.value?.frontend.url || overview.value?.backend.url?.replace(/\/health$/, '') || ''
})

const healthPreview = computed(() => {
  if (!healthPayload.value) return '暂无健康数据，请先刷新服务状态。'
  return JSON.stringify(healthPayload.value, null, 2)
})

const runtimeLogText = computed(() => {
  if (!runtimeLogs.value) return '尚未读取日志。'
  if (!runtimeLogs.value.exists) return '当前日志文件尚未生成。'
  if (!runtimeLogs.value.lines.length) return '日志文件存在，但暂无内容。'
  return runtimeLogs.value.lines.join('\n')
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
  try {
    const result = await servicesApi.runAction(action, serviceId)
    const actionLabel = action === 'start' ? '启动' : action === 'stop' ? '停止' : '重启'
    pushLog('success', `${actionLabel} ${serviceId}`, `${result.message}${result.url ? `：${result.url}` : ''}`)
    message.success(result.message)
    await refreshDashboard()
  } catch (error) {
    console.error(error)
    const text = error instanceof Error ? error.message : '服务控制失败'
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

function startPolling() {
  stopPolling()
  if (!autoRefreshEnabled.value) return
  pollTimer.value = window.setInterval(() => {
    void refreshDashboard()
  }, AUTO_REFRESH_INTERVAL)
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

onMounted(() => {
  void refreshDashboard()
  startPolling()
  pushLog('info', '控制台已启动', '本地服务控制台已就绪。')
})

onBeforeUnmount(() => {
  stopPolling()
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

.health-preview {
  margin: 16px 0 0;
  padding: 18px;
  border-radius: 18px;
  background: #0f172a;
  color: #dbeafe;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.65;
  overflow: auto;
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
