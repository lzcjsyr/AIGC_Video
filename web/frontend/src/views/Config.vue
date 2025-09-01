<template>
  <div class="config-container">
    <el-card>
      <template #header>
        <h2>系统配置</h2>
      </template>

      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="API密钥配置" name="api">
          <div class="config-section">
            <el-alert
              title="API密钥配置"
              description="请配置相应的API密钥以使用对应的服务商"
              type="info"
              :closable="false"
              show-icon
            />

            <el-form :model="apiConfig" label-width="150px" style="margin-top: 20px;">
              <el-form-item label="OpenRouter API">
                <el-input
                  v-model="apiConfig.openrouter_key"
                  placeholder="请输入OpenRouter API Key"
                  show-password
                  :suffix-icon="apiStatus.openrouter ? 'check' : 'close'"
                  :class="{ 'input-valid': apiStatus.openrouter, 'input-invalid': !apiStatus.openrouter }"
                />
                <div class="config-hint">用于GPT、Claude、Gemini等大语言模型</div>
              </el-form-item>

              <el-form-item label="硅基流动 API">
                <el-input
                  v-model="apiConfig.siliconflow_key"
                  placeholder="请输入SiliconFlow API Key"
                  show-password
                  :suffix-icon="apiStatus.siliconflow ? 'check' : 'close'"
                  :class="{ 'input-valid': apiStatus.siliconflow, 'input-invalid': !apiStatus.siliconflow }"
                />
                <div class="config-hint">用于GLM、Kimi等国产大模型</div>
              </el-form-item>

              <el-form-item label="AIHubMix API">
                <el-input
                  v-model="apiConfig.aihubmix_key"
                  placeholder="请输入AIHubMix API Key"
                  show-password
                  :suffix-icon="apiStatus.aihubmix ? 'check' : 'close'"
                  :class="{ 'input-valid': apiStatus.aihubmix, 'input-invalid': !apiStatus.aihubmix }"
                />
                <div class="config-hint">用于GPT-5等最新模型</div>
              </el-form-item>

              <el-form-item label="豆包图像 API">
                <el-input
                  v-model="apiConfig.seedream_key"
                  placeholder="请输入Seedream API Key"
                  show-password
                  :suffix-icon="apiStatus.seedream ? 'check' : 'close'"
                  :class="{ 'input-valid': apiStatus.seedream, 'input-invalid': !apiStatus.seedream }"
                />
                <div class="config-hint">用于豆包Seedream 3.0图像生成</div>
              </el-form-item>

              <el-form-item label="字节TTS AppID">
                <el-input
                  v-model="apiConfig.bytedance_appid"
                  placeholder="请输入字节跳动TTS AppID"
                  :suffix-icon="apiStatus.bytedance ? 'check' : 'close'"
                  :class="{ 'input-valid': apiStatus.bytedance, 'input-invalid': !apiStatus.bytedance }"
                />
              </el-form-item>

              <el-form-item label="字节TTS Token">
                <el-input
                  v-model="apiConfig.bytedance_token"
                  placeholder="请输入字节跳动TTS Access Token"
                  show-password
                  :suffix-icon="apiStatus.bytedance ? 'check' : 'close'"
                  :class="{ 'input-valid': apiStatus.bytedance, 'input-invalid': !apiStatus.bytedance }"
                />
                <div class="config-hint">用于字节跳动语音合成大模型</div>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveApiConfig" :loading="saving">
                  保存配置
                </el-button>
                <el-button @click="testApiKeys" :loading="testing">
                  测试连接
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane label="模型配置" name="models">
          <div class="config-section">
            <el-alert
              title="推荐模型配置"
              description="以下是各服务商推荐的模型列表"
              type="info"
              :closable="false"
              show-icon
            />

            <div class="model-categories">
              <div class="model-category" v-for="(models, category) in recommendedModels" :key="category">
                <h3>{{ getCategoryName(category) }}</h3>
                <div class="model-list">
                  <div v-for="(modelList, provider) in models" :key="provider" class="provider-group">
                    <h4>{{ getProviderName(provider) }}</h4>
                    <el-tag
                      v-for="model in modelList"
                      :key="model"
                      size="large"
                      class="model-tag"
                      effect="plain"
                    >
                      {{ model }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="系统设置" name="system">
          <div class="config-section">
            <el-alert
              title="系统参数设置"
              description="配置系统默认参数和处理限制"
              type="info"
              :closable="false"
              show-icon
            />

            <el-form :model="systemConfig" label-width="150px" style="margin-top: 20px;">
              <el-form-item label="默认目标字数">
                <el-slider
                  v-model="systemConfig.default_target_length"
                  :min="500"
                  :max="3000"
                  :step="100"
                  show-input
                />
              </el-form-item>

              <el-form-item label="默认分段数">
                <el-slider
                  v-model="systemConfig.default_num_segments"
                  :min="5"
                  :max="20"
                  show-input
                />
              </el-form-item>

              <el-form-item label="默认图像尺寸">
                <el-select v-model="systemConfig.default_image_size" placeholder="选择默认图像尺寸">
                  <el-option label="1280x720 (16:9)" value="1280x720"></el-option>
                  <el-option label="1024x1024 (1:1)" value="1024x1024"></el-option>
                  <el-option label="720x1280 (9:16)" value="720x1280"></el-option>
                  <el-option label="1152x864 (4:3)" value="1152x864"></el-option>
                  <el-option label="864x1152 (3:4)" value="864x1152"></el-option>
                </el-select>
              </el-form-item>

              <el-form-item label="语音速度">
                <el-slider
                  v-model="systemConfig.speech_speed"
                  :min="200"
                  :max="350"
                  :step="10"
                  show-input
                />
                <div class="config-hint">每分钟字数，影响语音时长估算</div>
              </el-form-item>

              <el-form-item label="启用字幕">
                <el-switch v-model="systemConfig.default_subtitles"></el-switch>
              </el-form-item>

              <el-form-item>
                <el-button type="primary" @click="saveSystemConfig" :loading="saving">
                  保存系统设置
                </el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('api')
const saving = ref(false)
const testing = ref(false)

const apiConfig = reactive({
  openrouter_key: '',
  siliconflow_key: '',
  aihubmix_key: '',
  seedream_key: '',
  bytedance_appid: '',
  bytedance_token: ''
})

const apiStatus = reactive({
  openrouter: false,
  siliconflow: false,
  aihubmix: false,
  seedream: false,
  bytedance: false
})

const systemConfig = reactive({
  default_target_length: 1000,
  default_num_segments: 10,
  default_image_size: '1280x720',
  speech_speed: 250,
  default_subtitles: true
})

const recommendedModels = ref({})

onMounted(() => {
  loadConfig()
  loadRecommendedModels()
})

const loadConfig = async () => {
  try {
    const response = await axios.get('/api/config')
    const config = response.data
    
    // 更新API配置状态
    Object.assign(apiStatus, config.api_status)
    
    // 更新系统配置
    if (config.system_config) {
      Object.assign(systemConfig, config.system_config)
    }
  } catch (error) {
    console.error('Load config error:', error)
    ElMessage.error('加载配置失败!')
  }
}

const loadRecommendedModels = async () => {
  try {
    const response = await axios.get('/api/config/models')
    recommendedModels.value = response.data
  } catch (error) {
    console.error('Load models error:', error)
  }
}

const saveApiConfig = async () => {
  saving.value = true
  try {
    await axios.post('/api/config/api', apiConfig)
    ElMessage.success('API配置保存成功!')
    await loadConfig() // 重新加载配置状态
  } catch (error) {
    console.error('Save API config error:', error)
    ElMessage.error('保存API配置失败!')
  } finally {
    saving.value = false
  }
}

const testApiKeys = async () => {
  testing.value = true
  try {
    const response = await axios.post('/api/config/test', apiConfig)
    const results = response.data
    
    let successCount = 0
    Object.entries(results).forEach(([key, success]) => {
      if (success) successCount++
    })
    
    ElMessage.success(`API测试完成! ${successCount}/${Object.keys(results).length} 个服务可用`)
    Object.assign(apiStatus, results)
  } catch (error) {
    console.error('Test API keys error:', error)
    ElMessage.error('API测试失败!')
  } finally {
    testing.value = false
  }
}

const saveSystemConfig = async () => {
  saving.value = true
  try {
    await axios.post('/api/config/system', systemConfig)
    ElMessage.success('系统配置保存成功!')
  } catch (error) {
    console.error('Save system config error:', error)
    ElMessage.error('保存系统配置失败!')
  } finally {
    saving.value = false
  }
}

const getCategoryName = (category) => {
  const names = {
    llm: '大语言模型',
    image: '图像生成模型',
    tts: '语音合成模型'
  }
  return names[category] || category
}

const getProviderName = (provider) => {
  const names = {
    openrouter: 'OpenRouter',
    siliconflow: '硅基流动',
    aihubmix: 'AIHubMix',
    doubao: '豆包',
    bytedance: '字节跳动'
  }
  return names[provider] || provider
}
</script>

<style scoped>
.config-container {
  max-width: 900px;
  margin: 0 auto;
}

.config-section {
  padding: 20px 0;
}

.config-hint {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.input-valid {
  border-color: #67c23a;
}

.input-invalid {
  border-color: #f56c6c;
}

.model-categories {
  margin-top: 20px;
}

.model-category {
  margin-bottom: 30px;
}

.model-category h3 {
  color: #333;
  margin-bottom: 15px;
  font-size: 18px;
}

.provider-group {
  margin-bottom: 20px;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 6px;
}

.provider-group h4 {
  color: #666;
  margin: 0 0 10px 0;
  font-size: 14px;
}

.model-tag {
  margin-right: 10px;
  margin-bottom: 8px;
}
</style>