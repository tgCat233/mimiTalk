<script setup>
defineProps({
  themes: { type: Array, default: () => [] },
  current: { type: String, default: '' },
})

defineEmits(['pick', 'close'])
</script>

<template>
  <div class="p3-sticker-mask" @click.self="$emit('close')">
    <div class="p3-sticker-panel">
      <div class="p3-sticker-head">
        <strong>气泡主题</strong>
        <button type="button" @click="$emit('close')">×</button>
      </div>
      <div class="p3-bubble-grid">
        <button
          v-for="theme in themes"
          :key="theme.id"
          type="button"
          :class="{ active: theme.id === current }"
          @click="$emit('pick', theme.id)"
        >
          <img :src="theme.right.url" alt="" />
          <span>{{ theme.name }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
