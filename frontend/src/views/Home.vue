<template>
  <div class="service-console">
    <div class="service-console__bg" aria-hidden="true" />

    <main class="service-console__container">
      <section class="hero-card">
        <div class="hero-card__eyebrow">PlotPilot Service Console</div>
        <div class="hero-card__header">
          <div>
            <h1 class="hero-card__title">把桌面端改成服务控制台</h1>
            <p class="hero-card__subtitle">
              桌面应用只负责管理本地服务：查看状态、重启异常服务、打开浏览器入口。
              实际业务界面继续通过浏览器访问，减少“壳已打开但服务已崩”的不可操作状态。
            </p>
          </div>
          <div class="hero-card__actions">
            <n-button secondary strong @click="refreshOverview" :loading="loading">
              刷新状态
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
            <span class="hero-stat__label">异常恢复方式</span>
            <strong class="hero-stat__value">一键重启本地服务</strong>
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
          </div>

          <div class="service-card__actions">
            <n-button
              type="primary"
              secondary
              :loading="restartingServiceId === service.id"
              @click="handleRestart(service.id)"
            >
              重启{{ service.label }}
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
          <h3 class="info-card__title">推荐运行方式</h3>
          <ul class="info-list">
            <li>桌面端只做本地守护与配置，不再承担完整业务 UI。</li>
            <li>后端异常时，先在这里查看状态，再一键重启。</li>
            <li>前端业务继续通过默认浏览器访问，便于调试和恢复。</li>
          </ul>
        </article>

        <article class="info-card">
          <h3 class="info-card__title">当前健康信息</h3>
          <pre class="health-preview">{{ healthPreview }}</pre>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { servicesApi, type ManagedServiceStatus, type ServiceOverview } from '../api/services'

const message = useMessage()
const loading = ref(false)
const restartingServiceId = ref<string | null>(null)
const overview = ref<ServiceOverview | null>(null)
const healthPayload = ref<Record<string, unknown> | null>(null)

const serviceCards = computed<ManagedServiceStatus[]>(() => {
  if (!overview.value) return []
  return [overview.value.backend, overview.value.frontend]
})

const runningCount = computed(() => serviceCards.value.filter(item => item.running).length)

const webPortalUrl = computed(() => overview.value?.frontend.url || overview.value?.backend.url?.replace(/\/health$/, '') || '')

const healthPreview = computed(() => {
  if (!healthPayload.value) return '暂无健康数据，请先刷新服务状态。'
  return JSON.stringify(healthPayload.value, null, 2)
})

async function refreshOverview() {
  loading.value = true
  try {
    overview.value = await servicesApi.getOverview()
    healthPayload.value = await servicesApi.getHealthPayload()
  } catch (error) {
    console.error(error)
    message.error('获取服务状态失败')
  } finally {
    loading.value = false
  }
}

async function handleRestart(serviceId: 'backend' | 'frontend') {
  restartingServiceId.value = serviceId
  try {
    const result = await servicesApi.restart(serviceId)
    message.success(`${result.message}：${result.url || '端口已恢复'}`)
    await refreshOverview()
  } catch (error) {
    console.error(error)
    message.error(error instanceof Error ? error.message : '重启失败')
  } finally {
    restartingServiceId.value = null
  }
}

async function openWebPortal() {
  if (!webPortalUrl.value) {
    message.warning('浏览器入口尚未就绪')
    return
  }
  await servicesApi.openUrl(webPortalUrl.value)
}

onMounted(() => {
  void refreshOverview()
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
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.hero-card,
.service-card,
.info-card {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(18px);
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
  gap: 8px;
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

.hero-card__title {
  margin: 0 0 12px;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.05;
  color: var(--app-text-primary);
}

.hero-card__subtitle {
  max-width: 760px;
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

.hero-stats {
  margin-top: 24px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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

.service-card__label-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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

.service-meta__item {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.service-meta__label {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.service-meta__value {
  color: var(--app-text-primary);
  font-weight: 600;
  word-break: break-all;
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

.info-list {
  margin: 16px 0 0;
  padding-left: 20px;
  color: var(--app-text-secondary);
  line-height: 1.85;
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
  min-height: 220px;
}

@media (max-width: 1024px) {
  .grid-section,
  .details-grid,
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

  .service-meta {
    grid-template-columns: 1fr;
  }
}
</style>
