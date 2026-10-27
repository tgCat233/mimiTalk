<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  categories: { type: Array, default: () => [] },
})

const emit = defineEmits(['pick', 'close'])

const activeIndex = ref(0)
const currentStickers = computed(
  () => props.categories[activeIndex.value]?.stickers || [],
)
</script>

<template>
  <div class="p3-sticker-mask" @click.self="$emit('close')">
    <div class="p3-sticker-panel">
      <div class="p3-sticker-head">
        <strong>贴纸</strong>
        <button type="button" @click="$emit('close')">×</button>
      </div>
      <div class="p3-sticker-tabs">
        <button
          v-for="(category, index) in categories"
          :key="category.id"
          type="button"
          :class="{ active: index === activeIndex }"
          @click="activeIndex = index"
        >
          {{ category.name }}
        </button>
      </div>
      <div class="p3-sticker-grid">
        <img
          v-for="sticker in currentStickers"
          :key="sticker.url"
          :src="sticker.url"
          :alt="sticker.name"
          :title="sticker.name"
          loading="lazy"
          @click="$emit('pick', sticker)"
        />
      </div>
    </div>
  </div>
</template>
