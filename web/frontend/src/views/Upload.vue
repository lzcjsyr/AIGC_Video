<template>
  <div class="upload-container">
    <el-card class="upload-card">
      <template #header>
        <div class="card-header">
          <h2>文件上传</h2>
          <p>支持 PDF、EPUB、MOBI 等格式文档</p>
        </div>
      </template>

      <el-upload
        class="upload-dragger"
        drag
        :action="uploadAction"
        :before-upload="beforeUpload"
        :on-success="handleSuccess"
        :on-error="handleError"
        :file-list="fileList"
        accept=".pdf,.epub,.mobi,.docx,.doc"
        :limit="1"
        :on-exceed="handleExceed"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 PDF、EPUB、MOBI、DOCX、DOC 格式，文件大小不超过 50MB
          </div>
        </template>
      </el-upload>

      <div class="form-section" v-if="uploadedFile">
        <el-divider>处理参数配置</el-divider>
        
        <el-form :model="form" label-width="120px" label-position="left">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="目标字数">
                <el-slider
                  v-model="form.target_length"
                  :min="500"
                  :max="3000"
                  :step="100"
                  show-input
                  :input-size="'small'"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="分段数">
                <el-slider
                  v-model="form.num_segments"
                  :min="5"
                  :max="20"
                  show-input
                  :input-size="'small'"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="LLM模型">
                <el-select v-model="form.llm_model" placeholder="请选择LLM模型">
                  <el-option label="Gemini 2.5 Pro" value="google/gemini-2.5-pro"></el-option>
                  <el-option label="Claude Sonnet 4" value="anthropic/claude-sonnet-4"></el-option>
                  <el-option label="GLM-4.5" value="zai-org/GLM-4.5"></el-option>
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="图像尺寸">
                <el-select v-model="form.image_size" placeholder="请选择图像尺寸">
                  <el-option label="1280x720 (16:9)" value="1280x720"></el-option>
                  <el-option label="1024x1024 (1:1)" value="1024x1024"></el-option>
                  <el-option label="720x1280 (9:16)" value="720x1280"></el-option>
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="语音选择">
                <el-select v-model="form.voice" placeholder="请选择语音">
                  <el-option label="男声-元伯小书" value="zh_male_yuanboxiaoshu_moon_bigtts"></el-option>
                  <el-option label="女声-温柔" value="zh_female_wenrou_moon_bigtts"></el-option>
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="图像风格">
                <el-select v-model="form.image_style" placeholder="请选择图像风格">
                  <el-option label="电影级" value="cinematic"></el-option>
                  <el-option label="纪录片" value="documentary"></el-option>
                  <el-option label="艺术性" value="artistic"></el-option>
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="启用字幕">
            <el-switch v-model="form.enable_subtitles"></el-switch>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="startProcess" :loading="processing" size="large">
              开始制作视频
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const uploadAction = '/api/files/upload'
const fileList = ref([])
const uploadedFile = ref(null)
const processing = ref(false)

const form = reactive({
  target_length: 1000,
  num_segments: 10,
  llm_model: 'google/gemini-2.5-pro',
  image_size: '1280x720',
  voice: 'zh_male_yuanboxiaoshu_moon_bigtts',
  image_style: 'cinematic',
  enable_subtitles: true
})

const beforeUpload = (file) => {
  const isValidFormat = ['pdf', 'epub', 'mobi', 'docx', 'doc'].includes(
    file.name.split('.').pop().toLowerCase()
  )
  const isLt50M = file.size / 1024 / 1024 < 50

  if (!isValidFormat) {
    ElMessage.error('只支持 PDF、EPUB、MOBI、DOCX、DOC 格式文件!')
    return false
  }
  if (!isLt50M) {
    ElMessage.error('文件大小不能超过 50MB!')
    return false
  }
  return true
}

const handleSuccess = (response, file) => {
  ElMessage.success('文件上传成功!')
  uploadedFile.value = response.data
}

const handleError = (error) => {
  console.error('Upload error:', error)
  ElMessage.error('文件上传失败!')
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个文件，请先删除已上传的文件!')
}

const startProcess = async () => {
  if (!uploadedFile.value) {
    ElMessage.error('请先上传文件!')
    return
  }

  processing.value = true
  
  try {
    const response = await axios.post('/api/tasks/start', {
      file_path: uploadedFile.value.path,
      ...form
    })
    
    ElMessage.success('任务已启动!')
    router.push(`/process/${response.data.task_id}`)
  } catch (error) {
    console.error('Start task error:', error)
    ElMessage.error('启动任务失败!')
  } finally {
    processing.value = false
  }
}
</script>

<style scoped>
.upload-container {
  max-width: 800px;
  margin: 0 auto;
}

.upload-card {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.card-header h2 {
  margin: 0 0 8px 0;
  color: #333;
}

.card-header p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.upload-dragger {
  width: 100%;
}

.form-section {
  margin-top: 30px;
}

.el-divider {
  margin: 30px 0 20px 0;
}
</style>