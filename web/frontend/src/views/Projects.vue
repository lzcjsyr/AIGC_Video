<template>
  <div class="projects-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>项目管理</h2>
          <el-button type="primary" @click="refreshProjects">
            <el-icon><refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="projects.length === 0" class="empty-container">
        <el-empty description="暂无项目">
          <el-button type="primary" @click="$router.push('/upload')">
            开始创建项目
          </el-button>
        </el-empty>
      </div>

      <div v-else>
        <el-table :data="projects" style="width: 100%">
          <el-table-column prop="name" label="项目名称" min-width="200">
            <template #default="scope">
              <div class="project-name">
                <el-icon><video-camera /></el-icon>
                {{ scope.row.name }}
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="progress" label="进度" width="200">
            <template #default="scope">
              <el-progress
                :percentage="getProgressPercentage(scope.row.current_step)"
                :status="scope.row.current_step === 5 ? 'success' : null"
              />
              <div class="step-info">
                步骤 {{ scope.row.current_step_display }}/5
                <span class="step-name">({{ getStepName(scope.row.current_step_display) }})</span>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column prop="modified_time" label="最后修改" width="180">
            <template #default="scope">
              {{ formatTime(scope.row.modified_time) }}
            </template>
          </el-table-column>
          
          <el-table-column label="操作" width="200">
            <template #default="scope">
              <el-button-group>
                <el-button 
                  size="small" 
                  @click="viewProject(scope.row)"
                  :disabled="scope.row.current_step < 1"
                >
                  查看
                </el-button>
                <el-button 
                  size="small" 
                  type="primary" 
                  @click="continueProject(scope.row)"
                  :disabled="scope.row.current_step === 5"
                >
                  继续
                </el-button>
                <el-button 
                  size="small" 
                  type="danger" 
                  @click="deleteProject(scope.row)"
                >
                  删除
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- 重新执行步骤对话框 -->
    <el-dialog
      v-model="rerunDialogVisible"
      title="选择重新执行的步骤"
      width="600px"
    >
      <div class="rerun-steps">
        <el-radio-group v-model="selectedRerunStep">
          <div v-for="step in availableRerunSteps" :key="step.value" class="step-item">
            <el-radio :value="step.value">
              <div class="step-content">
                <div class="step-title">{{ step.label }}</div>
                <div class="step-desc">{{ step.description }}</div>
              </div>
            </el-radio>
          </div>
        </el-radio-group>
      </div>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="rerunDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmRerun">确定重新执行</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoCamera } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const loading = ref(true)
const projects = ref([])
const rerunDialogVisible = ref(false)
const selectedProject = ref(null)
const selectedRerunStep = ref(null)
const availableRerunSteps = ref([])

const stepNames = {
  1: '智能缩写',
  2: '关键词提取', 
  3: 'AI图像生成',
  4: '语音合成',
  5: '视频合成'
}

const rerunStepOptions = [
  { value: 1, label: '步骤1：智能缩写', description: '重新生成脚本内容' },
  { value: 2, label: '步骤2：关键词提取', description: '重新提取画面关键词' },
  { value: 3, label: '步骤3：AI图像生成', description: '重新生成所有图片' },
  { value: 4, label: '步骤4：语音合成', description: '重新生成语音文件' },
  { value: 5, label: '步骤5：视频合成', description: '重新合成最终视频' }
]

onMounted(() => {
  fetchProjects()
})

const fetchProjects = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/projects')
    projects.value = response.data
  } catch (error) {
    console.error('Fetch projects error:', error)
    ElMessage.error('获取项目列表失败!')
  } finally {
    loading.value = false
  }
}

const refreshProjects = () => {
  fetchProjects()
}

const getProgressPercentage = (step) => {
  return step * 20
}

const getStepName = (step) => {
  return stepNames[step] || '未知'
}

const formatTime = (timeStr) => {
  return new Date(timeStr).toLocaleString('zh-CN')
}

const viewProject = (project) => {
  // 查看项目详情，可以跳转到结果页面
  if (project.has_final_video) {
    // 如果有最终视频，显示预览
    ElMessage.info('项目预览功能开发中...')
  } else {
    ElMessage.warning('项目尚未完成，无法预览')
  }
}

const continueProject = (project) => {
  if (project.current_step === 5) {
    ElMessage.info('项目已完成!')
    return
  }
  
  selectedProject.value = project
  // 获取可以重新执行的步骤
  availableRerunSteps.value = rerunStepOptions.filter(step => 
    step.value <= project.current_step + 1
  )
  selectedRerunStep.value = project.current_step + 1
  rerunDialogVisible.value = true
}

const confirmRerun = async () => {
  if (!selectedRerunStep.value) {
    ElMessage.warning('请选择要重新执行的步骤!')
    return
  }

  try {
    const response = await axios.post('/api/tasks/rerun', {
      project_path: selectedProject.value.path,
      from_step: selectedRerunStep.value
    })
    
    ElMessage.success('任务已启动!')
    rerunDialogVisible.value = false
    router.push(`/process/${response.data.task_id}`)
  } catch (error) {
    console.error('Rerun task error:', error)
    ElMessage.error('启动任务失败!')
  }
}

const deleteProject = async (project) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除项目 "${project.name}" 吗？此操作不可撤销。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await axios.delete(`/api/projects/${encodeURIComponent(project.name)}`)
    ElMessage.success('项目删除成功!')
    fetchProjects()
  } catch (error) {
    if (error === 'cancel') {
      return
    }
    console.error('Delete project error:', error)
    ElMessage.error('删除项目失败!')
  }
}
</script>

<style scoped>
.projects-container {
  max-width: 1200px;
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

.loading-container,
.empty-container {
  padding: 40px;
  text-align: center;
}

.project-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-info {
  margin-top: 5px;
  font-size: 12px;
  color: #666;
}

.step-name {
  color: #999;
}

.rerun-steps {
  padding: 20px 0;
}

.step-item {
  margin-bottom: 20px;
  padding: 15px;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  transition: all 0.3s;
}

.step-item:hover {
  border-color: #409eff;
  background-color: #f0f9ff;
}

.step-content {
  margin-left: 20px;
}

.step-title {
  font-weight: 500;
  color: #333;
  margin-bottom: 5px;
}

.step-desc {
  font-size: 13px;
  color: #666;
}
</style>