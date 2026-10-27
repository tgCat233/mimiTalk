<script setup>
import { computed } from 'vue'
import { audioState, isPlaying, playClipList } from '../audio'

const props = defineProps({
  message: { type: Object, required: true },
})

const clips = computed(() => props.message.meta?.voice?.clips || [])
const duration = computed(() =>
  clips.value.reduce((sum, clip) => sum + (Number(clip.duration) || 0), 0),
)
const active = computed(() => audioState.messageId === props.message.id)
const playing = computed(() => isPlaying(props.message.id))

function toggle() {
  playClipList(props.message.id, clips.value)
}
</script>

<template>
  <div
    class="voice-bubble"
    :class="{ active, playing }"
    role="button"
    tabindex="0"
    :aria-label="playing ? '暂停语音' : '播放语音'"
    @click="toggle"
    @keydown.enter.prevent="toggle"
    @keydown.space.prevent="toggle"
  >
    <span class="voice-icon" aria-hidden="true">
      <svg
        v-if="!playing"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M8 5.5 18 12 8 18.5Z"></path>
      </svg>
      <svg
        v-else
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      >
        <path d="M9 6v12"></path>
        <path d="M15 6v12"></path>
      </svg>
    </span>
    <span class="voice-wave" aria-hidden="true">
      <i v-for="n in 5" :key="n"></i>
    </span>
    <span class="voice-duration">
      {{ duration ? `${Math.round(duration)}″` : '语音' }}
    </span>
  </div>
</template>
