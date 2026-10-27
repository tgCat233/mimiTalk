<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  disabled: { type: Boolean, default: true },
  streaming: { type: Boolean, default: false },
  speaker: { type: String, default: '角色' },
  mentionCandidates: { type: Array, default: () => [] },
})

const emit = defineEmits(['send', 'image', 'open-stickers', 'stop'])

const inputRef = ref(null)
const fileInput = ref(null)
const pickerOpen = ref(false)
const pickerQuery = ref('')
const pickerIndex = ref(0)
const pickerStyle = ref({})
let activeMention = null
let composing = false

const placeholder = computed(() => {
  if (props.disabled) return '先选择一个会话'
  if (props.streaming) return '正在生成回复…'
  return '输入对话内容'
})

const suggestions = computed(() => {
  const query = pickerQuery.value.trim().toLowerCase()
  return [...props.mentionCandidates]
    .filter((item) => !query || String(item.name).toLowerCase().includes(query))
    .sort((a, b) => {
      const aq = String(a.name).toLowerCase().startsWith(query) ? 0 : 1
      const bq = String(b.name).toLowerCase().startsWith(query) ? 0 : 1
      return aq - bq || String(a.name).localeCompare(String(b.name), 'zh-CN')
    })
})

function closePicker() {
  pickerOpen.value = false
  pickerQuery.value = ''
  pickerIndex.value = 0
  activeMention = null
}

function updatePickerPosition() {
  const el = inputRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  pickerStyle.value = {
    left: `${Math.max(8, rect.left)}px`,
    bottom: `${Math.max(8, window.innerHeight - rect.top + 6)}px`,
  }
}

function getCaretInfo() {
  const selection = window.getSelection()
  if (!selection || !selection.rangeCount) return null
  const range = selection.getRangeAt(0)
  if (!range.collapsed) return null
  const node = range.startContainer
  if (node.nodeType !== Node.TEXT_NODE) return null
  if (!inputRef.value?.contains(node)) return null
  const text = node.textContent || ''
  const before = text.slice(0, range.startOffset)
  const at = before.lastIndexOf('@')
  if (at < 0) return null
  const prev = at > 0 ? before[at - 1] : ''
  if (prev && /[A-Za-z0-9_]/.test(prev)) return null
  const query = before.slice(at + 1)
  if (/\s/.test(query)) return null
  return { node, start: at, end: range.startOffset, query }
}

function insertMention(candidate, info) {
  if (!candidate || !info) return
  const range = document.createRange()
  range.setStart(info.node, info.start)
  range.setEnd(info.node, info.end)
  range.deleteContents()
  const token = document.createElement('span')
  token.className = 'mention-token'
  token.contentEditable = 'false'
  token.dataset.id = String(candidate.id)
  token.dataset.name = String(candidate.name)
  token.textContent = `@${candidate.name}`
  range.insertNode(token)
  const space = document.createTextNode(' ')
  token.after(space)
  const caret = document.createRange()
  caret.setStart(space, 1)
  caret.collapse(true)
  const selection = window.getSelection()
  selection.removeAllRanges()
  selection.addRange(caret)
  closePicker()
  inputRef.value?.focus()
}

function updateMentionState() {
  if (composing) return
  const info = getCaretInfo()
  if (!info) {
    closePicker()
    return
  }
  activeMention = info
  const exact = props.mentionCandidates.find(
    (item) => String(item.name) === info.query,
  )
  if (info.query && exact) {
    insertMention(exact, info)
    return
  }
  pickerQuery.value = info.query
  pickerIndex.value = 0
  pickerOpen.value = true
  updatePickerPosition()
}

function normalizeEmpty() {
  const el = inputRef.value
  if (!el) return
  if (el.querySelector('.mention-token')) return
  if ((el.innerText || '').trim()) return
  el.innerHTML = ''
}

function onInput() {
  if (composing) return
  updateMentionState()
  normalizeEmpty()
}

function onCaretMove() {
  if (composing) return
  updateMentionState()
}

function onCompositionStart() {
  composing = true
  closePicker()
}

function onCompositionEnd() {
  composing = false
  updateMentionState()
  normalizeEmpty()
}

function chooseMention(candidate) {
  if (!candidate || !activeMention) return
  insertMention(candidate, activeMention)
}

function movePicker(delta) {
  if (!suggestions.value.length) return
  const count = suggestions.value.length
  pickerIndex.value = (pickerIndex.value + delta + count) % count
  nextTick(() => {
    document
      .querySelector('.mention-picker-item.active')
      ?.scrollIntoView({ block: 'nearest' })
  })
}

function insertLineBreak() {
  document.execCommand('insertLineBreak')
}

function onKeydown(event) {
  if (event.isComposing || composing) return
  if (pickerOpen.value && suggestions.value.length) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      movePicker(1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      movePicker(-1)
      return
    }
    if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault()
      chooseMention(suggestions.value[pickerIndex.value])
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      closePicker()
      return
    }
  }
  if (event.key === 'Enter') {
    if (event.shiftKey) {
      event.preventDefault()
      insertLineBreak()
      return
    }
    event.preventDefault()
    submit()
  }
}

function onPaste(event) {
  event.preventDefault()
  const text = event.clipboardData?.getData('text/plain') || ''
  if (!text) return
  document.execCommand('insertText', false, text)
  onInput()
}

function readContent() {
  const mentions = []
  const seen = new Set()
  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent || ''
    if (node.nodeType !== Node.ELEMENT_NODE) return ''
    if (node.classList?.contains('mention-token')) {
      const id = node.dataset.id
      const name = node.dataset.name
      if (id && name && !seen.has(id)) {
        seen.add(id)
        mentions.push({ id, name })
      }
      return node.textContent || ''
    }
    if (node.tagName === 'BR') return '\n'
    return Array.from(node.childNodes).map(walk).join('')
  }
  if (!inputRef.value) return { text: '', mentions }
  return { text: walk(inputRef.value).trim(), mentions }
}

function submit() {
  if (props.disabled || props.streaming) return
  const { text, mentions } = readContent()
  if (!text) return
  emit('send', { text, mentions })
  if (inputRef.value) inputRef.value.innerHTML = ''
  closePicker()
  inputRef.value?.focus()
}

function onFileChange(event) {
  const file = event.target.files?.[0]
  if (file) emit('image', file)
  event.target.value = ''
}

function pickImage() {
  fileInput.value?.click()
}

function onDocumentPointerDown(event) {
  if (!pickerOpen.value) return
  const target = event.target
  if (inputRef.value?.contains(target)) return
  if (target.closest?.('.mention-picker')) return
  closePicker()
}

onMounted(() => document.addEventListener('pointerdown', onDocumentPointerDown))
onUnmounted(() =>
  document.removeEventListener('pointerdown', onDocumentPointerDown),
)
</script>

<template>
  <form class="momotalk-composer" @submit.prevent="submit">
    <span class="composer-speaker-label" :title="speaker">
      {{ speaker }}<span class="composer-chevron" aria-hidden="true">▾</span>
    </span>

    <div
      ref="inputRef"
      class="composer-input"
      role="textbox"
      aria-multiline="true"
      :data-placeholder="placeholder"
      :contenteditable="disabled || streaming ? 'false' : 'true'"
      @input="onInput"
      @keydown="onKeydown"
      @click="onCaretMove"
      @paste="onPaste"
      @compositionstart="onCompositionStart"
      @compositionend="onCompositionEnd"
    ></div>

    <input
      ref="fileInput"
      type="file"
      accept="image/png,image/jpeg"
      hidden
      @change="onFileChange"
    />

    <button
      class="composer-save-button composer-image-button"
      type="button"
      title="发送图片"
      aria-label="发送图片"
      :disabled="disabled || streaming"
      @click="pickImage"
    >
      <span class="composer-image-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="4" y="5" width="16" height="14" rx="2"></rect>
          <circle cx="9" cy="10" r="1.5"></circle>
          <path d="m5.5 17 4.2-4.2 3.1 3.1 2.1-2.1 3.6 3.2"></path>
        </svg>
      </span>
    </button>

    <button
      class="composer-save-button composer-sticker-button"
      type="button"
      title="选择表情"
      aria-label="选择表情"
      :disabled="disabled || streaming"
      @click="$emit('open-stickers')"
    >
      <span class="composer-sticker-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="8.5"></circle>
          <path d="M8.5 10h.01" stroke-width="2.4"></path>
          <path d="M15.5 10h.01" stroke-width="2.4"></path>
          <path d="M8.2 13.6c.9 1.5 2.2 2.3 3.8 2.3s2.9-.8 3.8-2.3"></path>
        </svg>
      </span>
    </button>

    <button
      v-if="streaming"
      class="composer-save-button composer-stop-button"
      type="button"
      title="停止生成"
      aria-label="停止生成"
      @click="$emit('stop')"
    >
      <span aria-hidden="true">■</span>
    </button>
    <button
      v-else
      class="composer-save-button composer-send-button"
      type="submit"
      title="发送"
      aria-label="发送"
      :disabled="disabled"
    >
      <span aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 12 20 4l-5 16-3.5-6.5L4 12z"></path>
          <path d="m11.5 13.5 8.5-9.5"></path>
        </svg>
      </span>
    </button>
  </form>

  <Teleport to="body">
    <div
      v-if="pickerOpen && suggestions.length"
      class="mention-picker"
      :style="pickerStyle"
      @mousedown.prevent
    >
      <button
        v-for="(candidate, index) in suggestions"
        :key="candidate.id"
        class="mention-picker-item"
        :class="{ active: index === pickerIndex }"
        type="button"
        @mousedown.prevent
        @click="chooseMention(candidate)"
      >
        <img v-if="candidate.avatar" :src="candidate.avatar" alt="" />
        <span>{{ candidate.name }}</span>
      </button>
    </div>
  </Teleport>
</template>
