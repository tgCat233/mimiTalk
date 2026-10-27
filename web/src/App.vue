<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api } from './api'
import { stopAudio } from './audio'
import AvatarPicker from './components/AvatarPicker.vue'
import BubblePicker from './components/BubblePicker.vue'
import ChatPanel from './components/ChatPanel.vue'
import MessageContextMenu from './components/MessageContextMenu.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import SideList from './components/SideList.vue'
import StickerPicker from './components/StickerPicker.vue'

const conversations = ref([])
const messages = ref([])
const stickerCategories = ref([])
const avatars = ref({ heroes: {}, groups: {} })
const characters = ref([])
const heroCharacters = computed(() =>
  characters.value.filter((character) => character.kind !== 'group'),
)
const voiceCharacters = computed(() =>
  characters.value
    .filter((character) => character.tts)
    .sort((a, b) => a.tts_rank - b.tts_rank),
)
const showStickers = ref(false)
const showSettings = ref(false)
const showAdminPicker = ref(false)
const showBubblePicker = ref(false)
const settingsData = ref(null)
const voiceMode = computed(() => settingsData.value?.tts?.mode === 'voice')
const personas = ref({})
const appearance = ref({ bubbles: [], bubbleDefault: '9000', admins: [] })
const scale = ref(1)

function updateScale() {
  const padding = 18
  const width = window.innerWidth - padding * 2
  const height = window.innerHeight - padding * 2
  scale.value = Math.min(width / 1680, height / 906)
}


function applyUiScale() {
  const dpr = window.devicePixelRatio || 1
  const value = Math.min(4, Math.max(0.25, 1 / dpr))
  document.documentElement.style.setProperty('--p3-ui-scale', String(value))
}


let lastDpr = 1

function handleResize() {
  const dpr = window.devicePixelRatio
  if (Math.abs(dpr - lastDpr) > 0.001) {
    lastDpr = dpr
    applyUiScale()
    
    window.scrollTo(0, 0)
    return
  }
  updateScale()
  applyUiScale()
}

let pollTimer = null

async function pollMessages() {
  if (streaming.value || !activeId.value) return
  if (messages.value.some((item) => item.status !== 'sent')) return
  try {
    const latest = await api.messages(activeId.value)
    const changed =
      latest.length !== messages.value.length ||
      latest[latest.length - 1]?.id !== messages.value[messages.value.length - 1]?.id
    if (changed) messages.value = latest
  } catch {
    
  }
}

onMounted(() => {
  updateScale()
  applyUiScale()
  lastDpr = window.devicePixelRatio
  window.addEventListener('resize', handleResize)
  pollTimer = window.setInterval(pollMessages, 1000)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (pollTimer) window.clearInterval(pollTimer)
})
const activeId = ref('')
const error = ref('')
const streaming = ref(false)
const messageMenu = ref(null)
const replyTarget = ref(null)

watch(streaming, (value) => {
  if (value) messageMenu.value = null
})

let controller = null

const activeConversation = computed(
  () => conversations.value.find((item) => item.id === activeId.value) || null,
)

const adminAvatar = computed(
  () =>
    activeConversation.value?.settings?.admin_avatar ||
    appearance.value.admins[0]?.url ||
    '/static/assets/avatars/admin.png',
)

const bubbleThemeId = computed(
  () =>
    activeConversation.value?.settings?.bubble_theme ||
    appearance.value.bubbleDefault,
)

const currentBubbleTheme = computed(
  () =>
    appearance.value.bubbles.find((theme) => theme.id === bubbleThemeId.value) ||
    appearance.value.bubbles[0] ||
    null,
)

const peerAvatar = computed(() => {
  const conversation = activeConversation.value
  if (!conversation) return ''
  const hero = avatars.value.heroes?.[conversation.title]
  if (hero?.url) return hero.url
  const group = avatars.value.groups?.[conversation.title]
  return group?.url || group?.members?.[0] || ''
})

const mentionCandidates = computed(() => {
  const conversation = activeConversation.value
  if (!conversation) return []
  if (conversation.kind === 'group') {
    const ids = avatars.value.groups?.[conversation.title]?.member_ids || []
    const byId = new Map(
      characters.value.map((item) => [String(item.id), item]),
    )
    return ids.map((id) => byId.get(String(id))).filter(Boolean)
  }
  const current = characters.value.find(
    (item) => String(item.id) === String(conversation.contact_id),
  )
  return current ? [current] : []
})

function applyBubbleTheme(theme) {
  if (!theme) return
  const root = document.documentElement
  const k = 0.0574
  for (const side of ['left', 'right']) {
    const variant = theme[side]
    if (!variant) continue
    root.style.setProperty(
      `--momotalk-selected-bubble-${side}`,
      `url(${variant.url})`,
    )
    const slice = variant.slice
    if (slice) {
      root.style.setProperty(
        `--momotalk-selected-bubble-slice-${side}`,
        `${slice.top} ${slice.right} ${slice.bottom} ${slice.left}`,
      )
      root.style.setProperty(
        `--momotalk-selected-bubble-edge-${side}`,
        `${(slice.top * k).toFixed(2)}cqw ${(slice.right * k).toFixed(2)}cqw ${(slice.bottom * k).toFixed(2)}cqw ${(slice.left * k).toFixed(2)}cqw`,
      )
    }
    root.style.setProperty(
      `--momotalk-selected-text-${side}`,
      variant.text_color || '#303b4b',
    )
  }
}

watch(currentBubbleTheme, applyBubbleTheme, { immediate: true })

function replaceConversation(updated) {
  const index = conversations.value.findIndex((item) => item.id === updated.id)
  if (index >= 0) conversations.value[index] = updated
}

async function saveAdminAvatar(url) {
  if (!activeId.value) return
  const previous = activeConversation.value?.settings?.admin_avatar || ''
  try {
    replaceConversation(
      await api.saveConversationSettings(activeId.value, { admin_avatar: url }),
    )
    if (previous.startsWith('/api/uploads/')) {
      await api.deleteUpload(previous.split('/').pop()).catch(() => {})
    }
  } catch (e) {
    error.value = String(e)
  }
}

async function pickAdmin(url) {
  showAdminPicker.value = false
  await saveAdminAvatar(url)
}

async function uploadCustomAvatar(blob) {
  showAdminPicker.value = false
  if (!activeId.value) return
  try {
    const file = new File([blob], `avatar-${Date.now()}.png`, { type: 'image/png' })
    const uploaded = await api.uploadImage(file)
    await saveAdminAvatar(uploaded.url)
  } catch (e) {
    error.value = String(e)
  }
}

async function pickBubble(themeId) {
  showBubblePicker.value = false
  if (!activeId.value) return
  try {
    replaceConversation(
      await api.saveConversationSettings(activeId.value, { bubble_theme: themeId }),
    )
  } catch (e) {
    error.value = String(e)
  }
}

async function refreshConversations() {
  conversations.value = await api.conversations()
}

async function refresh() {
  try {
    await refreshConversations()
    if (!activeId.value && conversations.value.length) {
      await select(conversations.value[0].id)
    }
  } catch (e) {
    error.value = String(e)
  }
}

async function select(id) {
  stopAudio()
  messageMenu.value = null
  replyTarget.value = null
  activeId.value = id
  try {
    messages.value = await api.messages(id)
  } catch (e) {
    error.value = String(e)
    messages.value = []
  }
}

async function loadCharacters() {
  characters.value = await api.characters()
}

async function create(characterId) {
  try {
    const created = await api.createConversation(characterId)
    await Promise.all([refreshConversations(), loadCharacters()])
    await select(created.id)
  } catch (e) {
    error.value = String(e)
  }
}

async function toggleFavorite(characterId, favorite) {
  try {
    await api.setFavorite(characterId, favorite)
    await loadCharacters()
  } catch (e) {
    error.value = String(e)
  }
}

async function requestReply({ recallNotice = false } = {}) {
  if (!activeId.value || streaming.value) return
  stopAudio()
  messageMenu.value = null
  streaming.value = true
  const wantsVoice = voiceMode.value

  const draft = reactive({
    id: `local-${Date.now()}`,
    role: 'assistant',
    type: wantsVoice ? 'voice' : 'text',
    content: '',
    status: 'streaming',
    error_text: '',
    meta: wantsVoice ? { voice_pending: true } : {},
  })
  messages.value.push(draft)

  let collected = ''
  controller = new AbortController()
  try {
    await api.streamReply(activeId.value, {
      signal: controller.signal,
      recallNotice,
      onEvent(event, data) {
        if (event === 'delta') {
          collected += data.text
          if (!wantsVoice) draft.content += data.text
        } else if (event === 'end') {
          Object.assign(draft, data.message)
          if (wantsVoice) {
            draft.type = 'voice'
            draft.meta = { ...(draft.meta || {}), voice_pending: true }
          }
          draft.status = 'sent'
        } else if (event === 'error') {
          draft.status = 'error'
          draft.error_text = data.detail
        }
      },
    })
    if (draft.status === 'streaming') {
      draft.content = collected
      draft.status = 'sent'
    }
    await refreshConversations()
  } catch (e) {
    draft.status = 'error'
    draft.error_text = e.name === 'AbortError' ? '已中断' : String(e)
  } finally {
    streaming.value = false
    controller = null
  }

  if (wantsVoice && draft.status === 'sent' && draft.content && draft.id) {
    synthesizeVoice(draft)
  }
}

async function synthesizeVoice(message) {
  try {
    const result = await api.ttsSynthesize({
      message_id: message.id,
      text: message.content,
      index: 0,
    })
    const target = messages.value.find((item) => item.id === message.id) || message
    Object.assign(target, result.message)
  } catch (e) {
    const target = messages.value.find((item) => item.id === message.id) || message
    target.type = 'text'
    target.meta = { ...(target.meta || {}), voice_pending: false }
    error.value = `语音生成失败：${e.message || e}`
  }
}

function stopReply() {
  controller?.abort()
}

async function retry() {
  const index = messages.value.findIndex((item) => item.status === 'error')
  if (index >= 0) messages.value.splice(index, 1)
  await requestReply()
}

async function removeConversation(id) {
  try {
    await api.deleteConversation(id)
    if (activeId.value === id) {
      activeId.value = ''
      messages.value = []
    }
    await Promise.all([refreshConversations(), loadCharacters()])
    if (!activeId.value && conversations.value.length) {
      await select(conversations.value[0].id)
    }
  } catch (e) {
    error.value = String(e)
  }
}

function replyName(message) {
  return message.role === 'user'
    ? '管理员'
    : activeConversation.value?.title || '角色'
}

function replyText(message) {
  if (message.type === 'image') return '[图片]'
  if (message.type === 'sticker') return '[表情]'
  if (message.type === 'voice') return '[语音]'
  return message.content || ''
}

function openMessageMenu(payload) {
  messageMenu.value = payload
}

function startReply(message) {
  messageMenu.value = null
  replyTarget.value = {
    id: message.id,
    name: replyName(message),
    text: replyText(message),
  }
}

function cancelReply() {
  replyTarget.value = null
}

async function deleteMessage(message) {
  messageMenu.value = null
  if (!activeId.value) return
  try {
    await api.deleteMessage(activeId.value, message.id)
    if (replyTarget.value?.id === message.id) replyTarget.value = null
    messages.value = await api.messages(activeId.value)
    await refreshConversations()
  } catch (e) {
    error.value = String(e)
  }
}

async function recallMessage(message) {
  messageMenu.value = null
  if (!activeId.value) return
  try {
    const result = await api.recallMessage(activeId.value, message.id)
    if (replyTarget.value?.id === message.id) replyTarget.value = null
    messages.value = await api.messages(activeId.value)
    await refreshConversations()
    if (result.will_reply && activeConversation.value?.kind !== 'group') {
      await requestReply({ recallNotice: true })
    }
  } catch (e) {
    error.value = String(e)
  }
}

async function sendText({ text, mentions = [] }) {
  if (!activeId.value) return
  const isGroup = activeConversation.value?.kind === 'group'
  try {
    const payload = {
      role: 'user',
      type: 'text',
      content: text,
    }
    if (mentions.length) payload.meta = { mentions }
    if (replyTarget.value) payload.reply_to_id = replyTarget.value.id
    const message = await api.sendMessage(activeId.value, payload)
    replyTarget.value = null
    messages.value.push(message)
    await refreshConversations()
    if (!isGroup) await requestReply()
  } catch (e) {
    error.value = String(e)
  }
}

async function sendImage(file) {
  if (!activeId.value) return
  try {
    const uploaded = await api.uploadImage(file)
    const payload = {
      role: 'user',
      type: 'image',
      file_id: uploaded.file_id,
      meta: { url: uploaded.url },
    }
    if (replyTarget.value) payload.reply_to_id = replyTarget.value.id
    const message = await api.sendMessage(activeId.value, payload)
    replyTarget.value = null
    messages.value.push(message)
    await refreshConversations()
  } catch (e) {
    error.value = String(e)
  }
}

async function openSettings() {
  try {
    const [settings, personaMap] = await Promise.all([
      api.settings(),
      api.personas(),
    ])
    settingsData.value = settings
    personas.value = personaMap
    showSettings.value = true
  } catch (e) {
    error.value = String(e)
  }
}

async function saveSettings(payload) {
  try {
    settingsData.value = await api.saveSettings(payload)
  } catch (e) {
    error.value = String(e)
  }
}

function applySettings(payload) {
  settingsData.value = payload
}

async function savePersona(characterId, systemPrompt) {
  try {
    await api.savePersona(characterId, systemPrompt)
    personas.value[characterId] = systemPrompt
  } catch (e) {
    error.value = String(e)
  }
}

async function openStickers() {
  if (!stickerCategories.value.length) {
    try {
      stickerCategories.value = (await api.stickers()).categories
    } catch (e) {
      error.value = String(e)
      return
    }
  }
  showStickers.value = true
}

async function sendSticker(sticker) {
  if (!activeId.value) return
  showStickers.value = false
  try {
    const payload = {
      role: 'user',
      type: 'sticker',
      asset_id: sticker.id,
      meta: { url: sticker.url, name: sticker.name },
    }
    if (replyTarget.value) payload.reply_to_id = replyTarget.value.id
    const message = await api.sendMessage(activeId.value, payload)
    replyTarget.value = null
    messages.value.push(message)
    await refreshConversations()
  } catch (e) {
    error.value = String(e)
  }
}

onMounted(async () => {
  try {
    avatars.value = await api.avatars()
    appearance.value = await api.appearance()
  } catch {
    
  }
  try {
    settingsData.value = await api.settings()
  } catch {
    
  }
  try {
    await loadCharacters()
  } catch (e) {
    error.value = String(e)
  }
  await refresh()
})
</script>

<template>
  <div class="p3-stage">
    <div class="p3-canvas" :style="{ zoom: scale }">
    <div class="phone-stack">
      <div class="phone-preview" data-ui="momotalk">
        <div class="momotalk-panel">
          <aside class="momotalk-rail" aria-label="管理员工具">
            <button
              class="rail-profile"
              type="button"
              title="切换管理员头像"
              :disabled="!activeConversation"
              @click="showAdminPicker = true"
            >
              <span
                class="avatar has-image"
                :style="{ backgroundImage: `url(${adminAvatar})` }"
              ></span>
            </button>
            <button
              class="rail-bubble"
              type="button"
              title="切换气泡主题"
              :disabled="!activeConversation"
              @click="showBubblePicker = true"
            >
              <img :src="currentBubbleTheme?.right?.url || '/static/assets/misc/9000_1.png'" alt="" />
            </button>
            <button
              class="rail-action rail-settings"
              type="button"
              title="设置"
              aria-label="设置"
              @click="openSettings"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="12" r="3"></circle>
                <path
                  d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.55 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.55-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"
                ></path>
              </svg>
            </button>
            <button
              class="rail-action rail-out"
              type="button"
              title="退出（待接入）"
              disabled
            >
              ↪
            </button>
          </aside>
          <aside class="momotalk-side">
            <SideList
              :conversations="conversations"
              :active-id="activeId"
              :avatars="avatars"
              :characters="characters"
              @select="select"
              @create="create"
              @remove="removeConversation"
              @favorite="toggleFavorite"
            />
          </aside>
          <ChatPanel
            :conversation="activeConversation"
            :messages="messages"
            :streaming="streaming"
            :peer-avatar="peerAvatar"
            :admin-avatar="adminAvatar"
            :reply-target="replyTarget"
            :mention-candidates="mentionCandidates"
            @send="sendText"
            @image="sendImage"
            @open-stickers="openStickers"
            @stop="stopReply"
            @retry="retry"
            @message-menu="openMessageMenu"
            @cancel-reply="cancelReply"
          />
        </div>
      </div>
    </div>
    </div>

    <StickerPicker
      v-if="showStickers"
      :categories="stickerCategories"
      @pick="sendSticker"
      @close="showStickers = false"
    />

    <AvatarPicker
      v-if="showAdminPicker"
      :avatars="appearance.admins"
      :current="adminAvatar"
      @pick="pickAdmin"
      @custom="uploadCustomAvatar"
      @close="showAdminPicker = false"
    />

    <BubblePicker
      v-if="showBubblePicker"
      :themes="appearance.bubbles"
      :current="bubbleThemeId"
      @pick="pickBubble"
      @close="showBubblePicker = false"
    />

    <SettingsPanel
      v-if="showSettings && settingsData"
      :settings="settingsData"
      :characters="heroCharacters"
      :voice-characters="voiceCharacters"
      :personas="personas"
      @close="showSettings = false"
      @save-settings="saveSettings"
      @save-persona="savePersona"
      @settings-updated="applySettings"
    />

    <MessageContextMenu
      v-if="messageMenu"
      :message="messageMenu.message"
      :x="messageMenu.x"
      :y="messageMenu.y"
      @reply="startReply(messageMenu.message)"
      @recall="recallMessage(messageMenu.message)"
      @delete="deleteMessage(messageMenu.message)"
      @close="messageMenu = null"
    />

    <p v-if="error" class="p3-error">{{ error }}</p>
  </div>
</template>
