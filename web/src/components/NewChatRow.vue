<script setup>
const props = defineProps({
  character: { type: Object, required: true },
})

const emit = defineEmits(['pick', 'favorite'])

function pick() {
  if (props.character.conversation_id) return
  emit('pick', props.character)
}
</script>

<template>
  <div class="new-chat-row">
    <button
      class="new-chat-row-main"
      type="button"
      :disabled="!!character.conversation_id"
      @click="pick"
    >
      <img v-if="character.avatar" :src="character.avatar" alt="" />
      <span v-else class="avatar">{{ character.name.slice(0, 1) }}</span>
      <span class="new-chat-row-name">{{ character.name }}</span>
      <small v-if="character.conversation_id">已有会话</small>
    </button>
    <button
      class="new-chat-star"
      type="button"
      :class="{ filled: character.favorite }"
      :title="character.favorite ? '取消收藏' : '收藏'"
      :aria-label="character.favorite ? '取消收藏' : '收藏'"
      @click.stop="$emit('favorite', character)"
    >
      {{ character.favorite ? '★' : '☆' }}
    </button>
  </div>
</template>
