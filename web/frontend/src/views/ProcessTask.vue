<template>
  <div class="process-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>视频制作进度</h2>
          <el-button @click="$router.go(-1)">
            <el-icon><arrow-left /></el-icon>
            返回
          </el-button>
        </div>
      </template>

      <div class="progress-overview">
        <el-steps :active="currentStepIndex" :process-status="stepStatus" finish-status="success">
          <el-step title="智能缩写" description="分析文档生成脚本"></el-step>
          <el-step title="关键词提取" description="提取画面关键词"></el-step>
          <el-step title="AI图像生成" description="生成配套图片"></el-step>
          <el-step title="语音合成" description="生成语音解说"></el-step>
          <el-step title="视频合成" description="合成最终视频"></el-step>
        </el-steps>
      </div>

      <div class="current-task" v-if="currentTask">
        <el-alert
          :title="currentTask.title"
          :description="currentTask.description"
          :type="currentTask.type"
          :closable="false"
          show-icon
        >
          <template #default>
            <div class="task-details">
              <div class="task-progress" v-if="currentTask.progress !== undefined">
                <el-progress
                  :percentage="currentTask.progress"
                  :status="currentTask.progress === 100 ? 'success' : null"
                />
              </div>
              <div class="task-logs" v-if="taskLogs.length > 0">
                <el-scrollbar height="200px">
                  <div class="log-list">
                    <div
                      v-for="(log, index) in taskLogs"
                      :key="index"
                      class="log-item"
                      :class="log.level"
                    >
                      <span class="log-time">{{ formatTime(log.timestamp) }}</span>
                      <span class="log-message">{{ log.message }}</span>
                    </div>
                  </div>
                </el-scrollbar>
              </div>
            </div>
          </template>
        </el-alert>
      </div>

      <div class="task-result" v-if="taskCompleted">
        <el-result
          icon="success"
          title="视频制作完成！"
          sub-title="您的视频已成功生成，可以预览和下载。"
        >
          <template #extra>
            <el-button type="primary" @click="previewVideo" v-if="finalVideoPath">
              <el-icon><video-play /></el-icon>
              预览视频
            </el-button>
            <el-button @click="downloadVideo" v-if="finalVideoPath">
              <el-icon><download /></el-icon>
              下载视频
            </el-button>
            <el-button @click="$router.push('/projects')">
              返回项目列表
            </el-button>
          </template>
        </el-result>
      </div>

      <div class="task-error" v-if="taskError">
        <el-result
          icon="error"
          title="任务执行失败"
          :sub-title="taskError.message"
        >
          <template #extra>
            <el-button type="primary" @click="retryTask">重试</el-button>
            <el-button @click="$router.push('/projects')">返回项目列表</el-button>
          </template>
        </el-result>
      </div>
    </el-card>

    <!-- 视频预览对话框 -->
    <el-dialog v-model="previewDialogVisible" title="视频预览" width="80%" center>
      <div class="video-preview">
        <video
          v-if="finalVideoPath"
          :src="getVideoUrl()"
          controls
          width="100%"
          height="auto"
          preload="metadata"
        >
          您的浏览器不支持视频播放
        </video>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, VideoPlay, Download } from '@element-plus/icons-vue'
import axios from 'axios'

const route = useRoute()
const taskId = route.params.projectId

const currentStepIndex = ref(0)
const stepStatus = ref('process')
const currentTask = ref(null)
const taskLogs = ref([])
const taskCompleted = ref(false)
const taskError = ref(null)
const finalVideoPath = ref(null)
const previewDialogVisible = ref(false)

let pollInterval = null

const stepNames = {
  1: '智能缩写',
  2: '关键词提取',
  3: 'AI图像生成', 
  4: '语音合成',
  5: '视频合成'
}

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

const startPolling = () => {
  // 立即执行一次
  pollTaskStatus()
  
  // 每2秒轮询一次
  pollInterval = setInterval(pollTaskStatus, 2000)
}

const pollTaskStatus = async () => {
  try {
    const response = await axios.get(`/api/tasks/${taskId}/status`)
    const status = response.data
    
    updateTaskStatus(status)
    
    // 如果任务完成或失败，停止轮询
    if (status.status === 'completed' || status.status === 'failed') {
      if (pollInterval) {
        clearInterval(pollInterval)
        pollInterval = null
      }
    }
  } catch (error) {
    console.error('Poll task status error:', error)
    // 继续轮询，可能是临时网络问题
  }
}

const updateTaskStatus = (status) => {
  // 更新当前步骤
  currentStepIndex.value = Math.max(0, status.current_step - 1)
  
  // 更新步骤状态
  if (status.status === 'completed') {
    stepStatus.value = 'finish'
    taskCompleted.value = true
    finalVideoPath.value = status.final_video_path
    currentTask.value = null
  } else if (status.status === 'failed') {
    stepStatus.value = 'error'
    taskError.value = {
      message: status.error_message || '任务执行过程中发生未知错误'
    }
    currentTask.value = null
  } else {
    // 运行中
    stepStatus.value = 'process'
    currentTask.value = {
      title: `正在执行: ${stepNames[status.current_step] || '处理中'}`,
      description: status.current_task || '任务正在进行中...',
      type: 'info',
      progress: status.progress || 0
    }
  }
  
  // 更新日志
  if (status.logs && status.logs.length > 0) {
    taskLogs.value = status.logs.map(log => ({
      timestamp: log.timestamp,
      message: log.message,
      level: log.level || 'info'
    }))
  }
}

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString('zh-CN')
}

const previewVideo = () => {
  previewDialogVisible.value = true
}

const downloadVideo = async () => {
  try {
    const response = await axios.get(`/api/files/download/${encodeURIComponent(finalVideoPath.value)}`, {
      responseType: 'blob'
    })
    
    const blob = new Blob([response.data])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `video_${Date.now()}.mp4`
    link.click()
    window.URL.revokeObjectURL(url)
    
    ElMessage.success('视频下载开始!')
  } catch (error) {
    console.error('Download video error:', error)
    ElMessage.error('视频下载失败!')
  }
}

const getVideoUrl = () => {
  if (!finalVideoPath.value) return ''
  return `/api/files/stream/${encodeURIComponent(finalVideoPath.value)}`
}

const retryTask = async () => {
  try {
    taskError.value = null
    taskCompleted.value = false
    currentStepIndex.value = 0
    stepStatus.value = 'process'
    
    await axios.post(`/api/tasks/${taskId}/retry`)
    ElMessage.success('任务已重新启动!')
    
    startPolling()
  } catch (error) {
    console.error('Retry task error:', error)
    ElMessage.error('重试任务失败!')
  }
}
</script>

<style scoped>
.process-container {
  max-width: 1000px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  color: #333;
}

.progress-overview {
  margin: 30px 0;
}

.current-task {
  margin: 30px 0;
}

.task-details {
  margin-top: 15px;
}

.task-progress {
  margin-bottom: 15px;
}

.task-logs {
  margin-top: 15px;
}

.log-list {
  padding: 10px;
  background: #f8f9fa;
  border-radius: 4px;
}

.log-item {
  display: flex;
  margin-bottom: 8px;
  font-size: 13px;
  font-family: monospace;
}

.log-time {
  color: #999;
  margin-right: 10px;
  min-width: 80px;
}

.log-message {
  color: #333;
}

.log-item.error .log-message {
  color: #f56c6c;
}

.log-item.warning .log-message {
  color: #e6a23c;
}

.log-item.success .log-message {
  color: #67c23a;
}

.task-result,
.task-error {
  margin: 40px 0;
}

.video-preview {
  text-align: center;
}

.video-preview video {
  max-width: 100%;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style>