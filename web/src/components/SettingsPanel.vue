<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({
  settings: { type: Object, required: true },
  characters: { type: Array, default: () => [] },
  voiceCharacters: { type: Array, default: () => [] },
  personas: { type: Object, default: () => ({}) },
  version: { type: String, default: '0.1.2' },
})

const emit = defineEmits(['close', 'save-settings', 'save-persona', 'settings-updated'])

const tab = ref('model')
const tabHistory = ref(['model'])
const savedHint = ref('')
const activeCharacter = ref(props.characters[0]?.id || '')

function selectTab(next) {
  if (next === tab.value) return
  tabHistory.value.push(next)
  tab.value = next
  if (next === 'tts') {
    refreshTtsStatus()
    if (!ttsModels.value.length && props.settings.tts.base_url) loadTtsModels()
  }
}

function goBack() {
  if (tabHistory.value.length <= 1) return
  tabHistory.value.pop()
  tab.value = tabHistory.value[tabHistory.value.length - 1]
}

const model = reactive({
  fake: props.settings.model.fake,
  base_url: props.settings.model.base_url,
  api_key: '',
  model: props.settings.model.model,
  history_limit: props.settings.model.history_limit,
})

const tts = reactive({
  provider: props.settings.tts.provider || 'openai-compatible',
  base_url: props.settings.tts.base_url || '',
  api_key: '',
  model: props.settings.tts.model || '',
  voice: props.settings.tts.voice || '',
  speed: props.settings.tts.speed ?? 1.0,
  mode: props.settings.tts.mode || 'text',
})

const ttsModels = ref([])
const ttsLoading = ref(false)
const ttsStatus = ref('')
const ttsStatusText = ref('')
const ttsError = ref('')
const ttsPreviewing = ref(false)

const characterModels = reactive({ ...(props.settings.tts.character_models || {}) })
const voiceCharacter = ref(props.voiceCharacters[0]?.id || '')
const voiceModel = ref('')
const voiceSaving = ref(false)

const voiceCharacterInfo = computed(
  () => props.characters.find((item) => item.id === voiceCharacter.value) || null,
)

const voiceList = computed(() => {
  const rows = [...props.voiceCharacters]
  const seen = new Set(rows.map((item) => item.id))
  for (const character of props.characters) {
    if (characterModels[character.id] && !seen.has(character.id)) {
      rows.push(character)
      seen.add(character.id)
    }
  }
  return rows
})

watch(
  () => props.settings.tts.character_models,
  (value) => {
    Object.keys(characterModels).forEach((key) => delete characterModels[key])
    Object.assign(characterModels, value || {})
  },
  { deep: true },
)

watch(
  voiceCharacter,
  (id) => {
    voiceModel.value = characterModels[id] || ''
  },
  { immediate: true },
)

async function refreshTtsStatus() {
  ttsStatusText.value = '检测中…'
  try {
    const status = await api.ttsStatus()
    if (status.reachable) {
      ttsStatus.value = 'ok'
      ttsStatusText.value = status.latency_ms
        ? `服务可达（${status.latency_ms} ms）`
        : '服务可达'
    } else {
      ttsStatus.value = 'error'
      ttsStatusText.value = status.detail || '服务不可达'
    }
  } catch (e) {
    ttsStatus.value = 'error'
    ttsStatusText.value = String(e)
  }
}

async function loadTtsModels() {
  ttsLoading.value = true
  ttsError.value = ''
  try {
    const data = await api.ttsModels()
    ttsModels.value = data.models || []
  } catch (e) {
    ttsError.value = String(e)
  } finally {
    ttsLoading.value = false
  }
}

async function saveCharacterVoice() {
  if (!voiceCharacter.value) return
  voiceSaving.value = true
  ttsError.value = ''
  try {
    const updated = await api.setCharacterVoice(voiceCharacter.value, voiceModel.value)
    characterModels[voiceCharacter.value] = voiceModel.value
    emit('settings-updated', updated)
    flash('角色语音已保存')
  } catch (e) {
    ttsError.value = String(e)
  } finally {
    voiceSaving.value = false
  }
}

async function previewCharacterVoice() {
  ttsPreviewing.value = true
  ttsError.value = ''
  try {
    const name = voiceCharacterInfo.value?.name || '角色'
    const blob = await api.ttsPreview(
      voiceCharacter.value,
      `你好，我是${name}。`,
      voiceModel.value,
    )
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onended = () => URL.revokeObjectURL(url)
    audio.onerror = () => URL.revokeObjectURL(url)
    await audio.play()
  } catch (e) {
    ttsError.value = String(e)
  } finally {
    ttsPreviewing.value = false
  }
}

onMounted(refreshTtsStatus)

const prompts = reactive({ ...props.personas })

watch(
  () => props.personas,
  (value) => {
    Object.assign(prompts, value)
  },
)

const activePrompt = computed({
  get: () => prompts[activeCharacter.value] || '',
  set: (value) => {
    prompts[activeCharacter.value] = value
  },
})

const activeCharacterInfo = computed(
  () => props.characters.find((item) => item.id === activeCharacter.value) || null,
)

function flash(message) {
  savedHint.value = message
  window.setTimeout(() => {
    if (savedHint.value === message) savedHint.value = ''
  }, 1800)
}

function saveModelAndTts() {
  emit('save-settings', {
    model: {
      fake: model.fake,
      base_url: model.base_url,
      api_key: model.api_key || null,
      model: model.model,
      history_limit: Number(model.history_limit) || 30,
    },
    tts: {
      provider: tts.provider,
      base_url: tts.base_url,
      api_key: tts.api_key || null,
      model: tts.model,
      voice: tts.voice,
      speed: Number(tts.speed) || 1.0,
      mode: tts.mode,
    },
  })
  model.api_key = ''
  tts.api_key = ''
  flash('已保存')
}

function savePersona() {
  if (!activeCharacter.value) return
  emit('save-persona', activeCharacter.value, activePrompt.value)
  flash('提示词已保存')
}
</script>

<template>
  <div class="settings-mask">
    <section class="settings-panel">
      <header class="settings-head">
        <button
          class="settings-back"
          type="button"
          title="返回上一页"
          :disabled="tabHistory.length <= 1"
          @click="goBack"
        >
          ←
        </button>
        <h2>设置</h2>
        <span class="settings-saved">{{ savedHint }}</span>
        <button
          class="settings-close"
          type="button"
          title="关闭设置"
          aria-label="关闭设置"
          @click="$emit('close')"
        >
          ×
        </button>
      </header>

      <nav class="settings-tabs">
        <button type="button" :class="{ active: tab === 'model' }" @click="selectTab('model')">
          模型
        </button>
        <button type="button" :class="{ active: tab === 'tts' }" @click="selectTab('tts')">
          语音
        </button>
        <button type="button" :class="{ active: tab === 'persona' }" @click="selectTab('persona')">
          角色提示词
        </button>
        <button type="button" :class="{ active: tab === 'about' }" @click="selectTab('about')">
          关于
        </button>
      </nav>

      <div class="settings-body">
        <div v-if="tab === 'model'" class="settings-form">
          <div class="settings-row">
            <span class="settings-label">回复模式</span>
            <div class="settings-segment">
              <button
                type="button"
                :class="{ active: model.fake }"
                @click="model.fake = true"
              >
                示例回复
              </button>
              <button
                type="button"
                :class="{ active: !model.fake }"
                @click="model.fake = false"
              >
                AI 回复
              </button>
            </div>
          </div>
          <p v-if="!settings.model.has_key && !model.api_key" class="settings-hint">
            未填写 API Key，将自动使用示例回复。
          </p>

          <label class="settings-field">
            <span>接口地址（Base URL）</span>
            <input v-model="model.base_url" type="text" placeholder="https://api.example.com/v1" />
          </label>
          <label class="settings-field">
            <span>API Key</span>
            <input
              v-model="model.api_key"
              type="password"
              :placeholder="settings.model.has_key ? '已设置，留空不修改' : 'sk-...'"
            />
          </label>
          <label class="settings-field">
            <span>模型名称</span>
            <input v-model="model.model" type="text" placeholder="模型名" />
          </label>
          <label class="settings-field">
            <span>历史消息条数（上限 27100 ≈ 1M 上下文）</span>
            <input v-model.number="model.history_limit" type="number" min="1" max="27100" />
          </label>
        </div>

        <div v-else-if="tab === 'tts'" class="settings-form">
          <p class="settings-hint">
            仅接入外部 TTS API；本地部署、权重微调不在本项目范围。
          </p>
          <label class="settings-field">
            <span>接口地址（Base URL）</span>
            <input v-model="tts.base_url" type="text" placeholder="http://127.0.0.1:7860/v1" />
          </label>
          <label class="settings-field">
            <span>API Key</span>
            <input
              v-model="tts.api_key"
              type="password"
              :placeholder="settings.tts.has_key ? '已设置，留空不修改' : 'Bearer Key'"
            />
          </label>

          <div class="settings-row">
            <span class="settings-label">服务状态</span>
            <span class="settings-status" :class="ttsStatus">{{ ttsStatusText || '未检测' }}</span>
            <button class="settings-link" type="button" @click="refreshTtsStatus">检测</button>
          </div>
          <div class="settings-row">
            <span class="settings-label">音色模型</span>
            <button class="settings-link" type="button" :disabled="ttsLoading" @click="loadTtsModels">
              {{ ttsLoading ? '读取中…' : '刷新模型列表' }}
            </button>
          </div>

          <label class="settings-field">
            <span>角色</span>
            <select v-model="voiceCharacter">
              <option v-for="character in characters" :key="character.id" :value="character.id">
                {{ character.name }}
              </option>
            </select>
          </label>
          <label class="settings-field">
            <span>模型</span>
            <select v-model="voiceModel">
              <option value="">（未配置）</option>
              <option v-for="item in ttsModels" :key="item.id" :value="item.id">
                {{ item.id }}
              </option>
            </select>
          </label>

          <div class="settings-row">
            <button
              class="settings-primary"
              type="button"
              :disabled="voiceSaving"
              @click="saveCharacterVoice"
            >
              {{ voiceSaving ? '保存中…' : '保存该角色语音' }}
            </button>
            <button
              class="settings-link"
              type="button"
              :disabled="ttsPreviewing"
              @click="previewCharacterVoice"
            >
              {{ ttsPreviewing ? '合成中…' : '试听该角色' }}
            </button>
          </div>

          <div class="settings-voice-map">
            <div v-for="character in voiceList" :key="character.id" class="settings-voice-item">
              <span>{{ character.name }}</span>
              <span :class="{ muted: !characterModels[character.id] }">
                {{ characterModels[character.id] || '未配置' }}
              </span>
            </div>
          </div>

          <label class="settings-field">
            <span>语速（0.5–2.0，全部角色）</span>
            <input v-model.number="tts.speed" type="number" min="0.5" max="2" step="0.1" />
          </label>

          <div class="settings-row">
            <span class="settings-label">回复模式</span>
            <div class="settings-segment">
              <button type="button" :class="{ active: tts.mode === 'text' }" @click="tts.mode = 'text'">
                文字
              </button>
              <button type="button" :class="{ active: tts.mode === 'voice' }" @click="tts.mode = 'voice'">
                语音
              </button>
            </div>
          </div>

          <p v-if="ttsError" class="settings-status error">{{ ttsError }}</p>
          <p class="settings-hint">
            每个角色单独匹配一个模型，点“保存该角色语音”立即写入 config/p3.toml；地址或 Key 改动后请用底部“保存设置”。
          </p>
        </div>

        <div v-else-if="tab === 'persona'" class="settings-form">
          <div class="settings-character-list">
            <button
              v-for="character in characters"
              :key="character.id"
              type="button"
              :class="{ active: character.id === activeCharacter }"
              @click="activeCharacter = character.id"
            >
              <img :src="character.avatar" alt="" />
              <span>{{ character.name }}</span>
            </button>
          </div>
          <label class="settings-field">
            <span>系统提示词（system prompt）</span>
            <textarea v-model="activePrompt" rows="8" placeholder="角色人设与说话方式"></textarea>
          </label>
          <button class="settings-primary" type="button" @click="savePersona">
            保存提示词
          </button>
          <p class="settings-hint">
            当前角色：{{ activeCharacterInfo?.name }}。保存后下一条消息生效。
          </p>
        </div>

        <div v-else class="settings-form">
          <dl class="settings-about">
            <dt>版本</dt><dd>P3 v{{ version }}</dd>
            <dt>配置文件</dt><dd>config/p3.toml</dd>
            <dt>角色卡</dt><dd>config/personas/</dd>
            <dt>数据目录</dt><dd>data/</dd>
          </dl>
          <p class="settings-hint">
            插件与高级设置（参考 NapCat / AstrBot 的能力）留待 S5 与后续预研。
          </p>
        </div>
      </div>

      <footer v-if="tab === 'model' || tab === 'tts'" class="settings-foot">
        <button class="settings-primary" type="button" @click="saveModelAndTts">
          保存设置
        </button>
      </footer>
    </section>
  </div>
</template>
