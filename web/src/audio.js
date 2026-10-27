import { reactive } from 'vue'

export const audioState = reactive({
  messageId: '',
  playing: false,
  paused: false,
  index: 0,
  total: 0,
})

let queue = []
let current = null
let currentResolve = null
let activeId = ''
let token = 0
let pumping = false

function stopCurrent() {
  if (!current) return
  current.onended = null
  current.onerror = null
  try {
    current.pause()
  } catch {
    
  }
  current = null
  if (currentResolve) {
    const resolve = currentResolve
    currentResolve = null
    resolve()
  }
}

export function stopAudio() {
  token += 1
  queue = []
  activeId = ''
  pumping = false
  stopCurrent()
  audioState.messageId = ''
  audioState.playing = false
  audioState.paused = false
  audioState.index = 0
  audioState.total = 0
}

export function beginQueue(messageId) {
  stopAudio()
  activeId = messageId
  audioState.messageId = messageId
}

export function enqueueClip(messageId, clip) {
  if (!clip?.url || messageId !== activeId) return
  queue.push(clip)
  audioState.total += 1
  if (!pumping) pump()
}

async function pump() {
  if (pumping) return
  pumping = true
  const my = token
  try {
    while (my === token && queue.length) {
      const clip = queue.shift()
      audioState.index += 1
      await playOne(clip)
    }
  } finally {
    if (my === token) {
      pumping = false
      if (!queue.length) {
        audioState.playing = false
        audioState.paused = false
        audioState.messageId = ''
        activeId = ''
      }
    }
  }
}

function playOne(clip) {
  return new Promise((resolve) => {
    const audio = new Audio(clip.url)
    current = audio
    currentResolve = resolve
    const done = () => {
      if (current === audio) current = null
      if (currentResolve === resolve) currentResolve = null
      resolve()
    }
    audio.onended = done
    audio.onerror = done
    audio
      .play()
      .then(() => {
        audioState.playing = true
        audioState.paused = false
      })
      .catch(done)
  })
}

export function pauseAudio() {
  if (!current || !audioState.playing) return
  current.pause()
  audioState.playing = false
  audioState.paused = true
}

export function resumeAudio() {
  if (!current || audioState.playing) return
  current
    .play()
    .then(() => {
      audioState.playing = true
      audioState.paused = false
    })
    .catch(() => {})
}

export function playClipList(messageId, clips) {
  if (audioState.messageId === messageId && current) {
    if (audioState.playing) {
      pauseAudio()
    } else {
      resumeAudio()
    }
    return
  }
  beginQueue(messageId)
  clips.forEach((clip) => enqueueClip(messageId, clip))
}

export function isPlaying(messageId) {
  return audioState.messageId === messageId && audioState.playing
}

export function isPaused(messageId) {
  return audioState.messageId === messageId && audioState.paused
}
