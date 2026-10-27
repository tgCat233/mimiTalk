<script setup>
import { nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import Composer from './Composer.vue'
import VoiceBubble from './VoiceBubble.vue'

const props = defineProps({
  conversation: { type: Object, default: null },
  messages: { type: Array, default: () => [] },
  streaming: { type: Boolean, default: false },
  peerAvatar: { type: String, default: '' },
  adminAvatar: { type: String, default: '/static/assets/avatars/admin.png' },
  replyTarget: { type: Object, default: null },
  mentionCandidates: { type: Array, default: () => [] },
})

function avatarFor(message) {
  return message.role === 'user' ? props.adminAvatar : props.peerAvatar
}

const emit = defineEmits([
  'send',
  'image',
  'open-stickers',
  'stop',
  'retry',
  'message-menu',
  'cancel-reply',
])

const scrollRef = ref(null)
const trackRef = ref(null)
const scrollThumb = reactive({ top: 0, height: 0 })
const canScroll = ref(false)

function scrollToBottom() {
  nextTick(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    updateScrollbar()
  })
}

function updateScrollbar() {
  const el = scrollRef.value
  if (!el) return
  const maxScroll = el.scrollHeight - el.clientHeight
  canScroll.value = maxScroll > 1
  if (!canScroll.value) {
    scrollThumb.top = 0
    scrollThumb.height = 0
    return
  }
  const height = Math.max((el.clientHeight / el.scrollHeight) * 100, 8)
  const maxTop = 100 - height
  scrollThumb.height = height
  scrollThumb.top = (el.scrollTop / maxScroll) * maxTop
}

let dragging = false
let dragStartY = 0
let dragStartTop = 0

function onThumbDown(event) {
  dragging = true
  dragStartY = event.clientY
  dragStartTop = scrollThumb.top
  window.addEventListener('pointermove', onThumbMove)
  window.addEventListener('pointerup', onThumbUp)
  event.preventDefault()
}

function onThumbMove(event) {
  if (!dragging || !trackRef.value || !scrollRef.value) return
  const trackHeight = trackRef.value.getBoundingClientRect().height || 1
  const delta = ((event.clientY - dragStartY) / trackHeight) * 100
  const maxTop = 100 - scrollThumb.height
  const top = Math.min(Math.max(dragStartTop + delta, 0), maxTop)
  const ratio = maxTop > 0 ? top / maxTop : 0
  scrollRef.value.scrollTop = ratio * (scrollRef.value.scrollHeight - scrollRef.value.clientHeight)
}

function onThumbUp() {
  dragging = false
  window.removeEventListener('pointermove', onThumbMove)
  window.removeEventListener('pointerup', onThumbUp)
}

onMounted(() => {
  scrollRef.value?.addEventListener('scroll', updateScrollbar)
  updateScrollbar()
})

onUnmounted(() => {
  scrollRef.value?.removeEventListener('scroll', updateScrollbar)
  window.removeEventListener('pointermove', onThumbMove)
  window.removeEventListener('pointerup', onThumbUp)
})

watch(() => props.messages, () => { scrollToBottom(); updateScrollbar() }, { deep: true })
watch(() => props.conversation?.id, () => { scrollToBottom(); updateScrollbar() })

function imageSrc(message) {
  return message.meta?.url || (message.file_id ? `/api/uploads/${message.file_id}` : '')
}

function rowClass(message) {
  return {
    right: message.role === 'user',
    left: message.role !== 'user',
    'admin-message': message.role === 'user',
    'media-row': message.type === 'image',
    'sticker-row': message.type === 'sticker',
  }
}

function noticeText(message) {
  return (
    message.meta?.display_text ||
    String(message.content || '').replace(/^<|>$/g, '')
  )
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function messageSegments(message) {
  const content = String(message.content || '')
  const mentions = Array.isArray(message.meta?.mentions)
    ? message.meta.mentions
    : []
  const names = [...new Set(mentions.map((item) => item?.name).filter(Boolean))]
    .sort((a, b) => b.length - a.length)
  if (!names.length) return [{ text: content }]
  const pattern = new RegExp(`@(${names.map(escapeRegExp).join('|')})`, 'g')
  const segments = []
  let last = 0
  let match
  while ((match = pattern.exec(content)) !== null) {
    if (match.index > last) {
      segments.push({ text: content.slice(last, match.index) })
    }
    segments.push({ text: match[0], mention: true })
    last = match.index + match[0].length
  }
  if (last < content.length) {
    segments.push({ text: content.slice(last) })
  }
  return segments
}

function openMenu(event, message) {
  if (props.streaming) return
  if (message.type === 'recall' || message.type === 'system') return
  if (message.status === 'streaming' || String(message.id).startsWith('local-')) return
  emit('message-menu', { message, x: event.clientX, y: event.clientY })
}
</script>

<template>
  <section
    class="momotalk-chat has-background"
    :style="{ '--chat-background': 'url(/static/assets/backgrounds/Momotalk_04.png)' }"
  >
    <header class="chat-header">
      <div class="contact-heading">
        <span class="contact-name">{{ conversation?.title || '未选择会话' }}</span>
      </div>
    </header>

    <div v-show="canScroll" ref="trackRef" class="p3-scrollbar" aria-hidden="true">
      <div
        class="p3-scrollbar-thumb"
        :style="{ top: `${scrollThumb.top}%`, height: `${scrollThumb.height}%` }"
        @pointerdown="onThumbDown"
      ></div>
    </div>

    <div ref="scrollRef" class="chat-scroll">
      <template v-if="conversation">
        <template v-for="message in messages" :key="message.id">
          <div v-if="message.type === 'recall'" class="chat-notice">
            {{ noticeText(message) }}
          </div>
          <div v-else class="chat-row" :class="rowClass(message)">
            <div class="message-avatar avatar-frame" aria-hidden="true">
              <span
                v-if="avatarFor(message)"
                class="avatar has-image"
                :style="{ backgroundImage: `url(${avatarFor(message)})` }"
              ></span>
              <span v-else class="avatar">?</span>
            </div>
            <div
              class="message-stack"
              @contextmenu.prevent="openMenu($event, message)"
            >
              <span
                v-if="message.role !== 'user' && conversation?.kind === 'group'"
                class="message-speaker"
              >
                {{ message.role === 'assistant' ? '角色' : '系统' }}
              </span>

              <div
                v-if="message.meta?.quote"
                class="quote-block"
                :class="{ deleted: message.meta.quote.deleted }"
              >
                <span class="quote-name">{{ message.meta.quote.name }}</span>
                <span class="quote-text">
                  {{ message.meta.quote.deleted ? '原消息已删除' : message.meta.quote.text }}
                </span>
              </div>

              <img
              v-if="message.type === 'image'"
              class="chat-image"
              :src="imageSrc(message)"
              alt="图片消息"
            />

            <div v-else-if="message.type === 'sticker'" class="sticker-frame">
              <img
                class="chat-sticker"
                :src="message.meta?.url"
                :alt="message.meta?.name || '贴纸'"
              />
            </div>

            <div
              v-else
              class="bubble"
              :class="{
                'bubble-error': message.status === 'error',
                'bubble-voice': message.type === 'voice',
              }"
            >
              <div
                v-if="message.type === 'voice' && message.meta?.voice_pending"
                class="voice-pending"
              >
                <span class="voice-wave" aria-hidden="true">
                  <i v-for="n in 5" :key="n"></i>
                </span>
                <span class="voice-duration">语音生成中…</span>
              </div>
              <VoiceBubble
                v-else-if="message.type === 'voice' && message.meta?.voice?.clips?.length"
                :message="message"
              />
              <div v-else class="bubble-text">
                <template v-if="message.content">
                  <template
                    v-for="(segment, index) in messageSegments(message)"
                    :key="index"
                  >
                    <span v-if="segment.mention" class="bubble-mention">
                      {{ segment.text }}
                    </span>
                    <template v-else>{{ segment.text }}</template>
                  </template>
                </template>
                <template v-else-if="message.status === 'streaming'">正在输入…</template>
                <template v-else>（生成失败）</template>
              </div>
              <p v-if="message.status === 'error'" class="bubble-error-text">
                {{ message.error_text }}
              </p>
              <button
                v-if="message.status === 'error'"
                class="bubble-retry"
                type="button"
                @click="$emit('retry')"
              >
                重试
              </button>
            </div>
          </div>
        </div>
        </template>
        <p v-if="!messages.length" class="empty-state chat-empty">还没有消息</p>
      </template>
      <p v-else class="empty-state chat-empty">选择左侧会话开始</p>
    </div>

    <div v-if="replyTarget" class="composer-quote">
      <div class="composer-quote-text">
        <span class="composer-quote-name">{{ replyTarget.name }}</span>
        <span class="composer-quote-body">{{ replyTarget.text }}</span>
      </div>
      <button
        class="composer-quote-cancel"
        type="button"
        aria-label="取消回复"
        @click="$emit('cancel-reply')"
      >
        ×
      </button>
    </div>

    <Composer
      :key="conversation?.id || 'none'"
      :disabled="!conversation"
      :streaming="streaming"
      speaker="管理员"
      :mention-candidates="mentionCandidates"
      @send="$emit('send', $event)"
      @image="$emit('image', $event)"
      @open-stickers="$emit('open-stickers')"
      @stop="$emit('stop')"
    />
  </section>
</template>
