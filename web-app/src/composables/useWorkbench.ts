import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { bookApi, jobApi } from '../api/book'

export interface UseWorkbenchOptions {
  slug: string
  chatAreaRef?: { fetchMessages?: () => Promise<void> } | null
}

export function useWorkbench(options: UseWorkbenchOptions) {
  const { slug, chatAreaRef } = options
  const router = useRouter()
  const message = useMessage()

  // State
  const bookTitle = ref('')
  const chapters = ref<any[]>([])
  const rightPanel = ref<'bible' | 'knowledge'>('knowledge')
  const biblePanelKey = ref(0)
  const pageLoading = ref(true)
  const showPlanModal = ref(false)
  const planMode = ref<'initial' | 'revise'>('initial')
  const planDryRun = ref(false)
  const bookMeta = ref<{ has_bible?: boolean; has_outline?: boolean }>({})
  const showTaskModal = ref(false)
  const taskProgress = ref(0)
  const taskMessage = ref('')
  const currentJobId = ref<string | null>(null)
  let taskTimer: number | null = null

  // Computed
  const hasStructure = computed<boolean>(
    () => !!(bookMeta.value.has_bible && bookMeta.value.has_outline)
  )

  const currentChapterId = computed(() => {
    // This will be provided by the route in the component
    return null
  })

  // Methods
  const setRightPanel = (panel: 'bible' | 'knowledge') => {
    rightPanel.value = panel
  }

  const onMessagesUpdated = () => {
    // Messages have been updated in ChatArea, trigger any parent-side updates if needed
  }

  const loadDesk = async () => {
    const res = await bookApi.getDesk(slug)
    bookTitle.value = res.book?.title || slug
    chapters.value = res.chapters || []
    bookMeta.value = {
      has_bible: res.book?.has_bible,
      has_outline: res.book?.has_outline,
    }
  }

  const openPlanModal = () => {
    planMode.value = hasStructure.value ? 'revise' : 'initial'
    planDryRun.value = false
    showPlanModal.value = true
  }

  const confirmPlan = async () => {
    showPlanModal.value = false
    try {
      const res = await jobApi.startPlan(slug, planDryRun.value, planMode.value)
      startPolling(res.job_id)
    } catch (error: any) {
      message.error(error.response?.data?.detail || '启动失败')
    }
  }

  const startWrite = async () => {
    try {
      const res = await jobApi.startWrite(slug, 1)
      startPolling(res.job_id)
    } catch (error: any) {
      message.error(error.response?.data?.detail || '启动失败')
    }
  }

  const startPolling = (jobId: string) => {
    currentJobId.value = jobId
    showTaskModal.value = true
    taskProgress.value = 6
    taskMessage.value = '任务启动中…'
    let bump = 6

    taskTimer = window.setInterval(async () => {
      bump = Math.min(93, bump + 2 + Math.random() * 6)
      taskProgress.value = Math.floor(bump)
      try {
        const status = await jobApi.getStatus(jobId)
        taskMessage.value = status.message || status.phase || '执行中…'

        if (status.status === 'done') {
          taskProgress.value = 100
          stopPolling()
          message.success('任务完成')
          await loadDesk()
          await chatAreaRef?.fetchMessages?.()
          biblePanelKey.value += 1
        } else if (status.status === 'cancelled') {
          taskProgress.value = 100
          stopPolling()
          message.info('任务已终止')
          await loadDesk()
        } else if (status.status === 'error') {
          stopPolling()
          message.error(status.error || '任务失败')
        }
      } catch {
        stopPolling()
      }
    }, 1000)
  }

  const cancelRunningTask = async () => {
    const jid = currentJobId.value
    if (!jid) return
    try {
      await jobApi.cancelJob(jid)
      taskMessage.value = '正在终止…'
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '终止失败')
    }
  }

  const stopPolling = () => {
    if (taskTimer) {
      clearInterval(taskTimer)
      taskTimer = null
    }
    currentJobId.value = null
    showTaskModal.value = false
  }

  const goHome = () => {
    router.push('/')
  }

  const goToChapter = (id: number) => {
    router.push(`/book/${slug}/chapter/${id}`)
  }

  // Cleanup on unmount
  onUnmounted(() => {
    stopPolling()
  })

  return {
    // State
    bookTitle,
    chapters,
    rightPanel,
    biblePanelKey,
    pageLoading,
    showPlanModal,
    planMode,
    planDryRun,
    bookMeta,
    showTaskModal,
    taskProgress,
    taskMessage,
    currentJobId,

    // Computed
    hasStructure,
    currentChapterId,

    // Methods
    setRightPanel,
    onMessagesUpdated,
    loadDesk,
    openPlanModal,
    confirmPlan,
    startWrite,
    startPolling,
    cancelRunningTask,
    stopPolling,
    goHome,
    goToChapter,
  }
}
