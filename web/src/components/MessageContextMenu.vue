<script setup>
import { computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
  x: { type: Number, required: true },
  y: { type: Number, required: true },
})

const emit = defineEmits(['reply', 'recall', 'delete', 'close'])

const canRecall = computed(() => {
  if (props.message.role !== 'user') return false
  const created = Number(props.message.created_at || 0)
  return created > 0 && Date.now() - created <= 120000
})

const style = computed(() => ({
  left: `${Math.max(8, Math.min(props.x, window.innerWidth - 132))}px`,
  top: `${Math.max(8, Math.min(props.y, window.innerHeight - 148))}px`,
}))

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div
    class="message-menu-backdrop"
    @click="$emit('close')"
    @contextmenu.prevent="$emit('close')"
  ></div>
  <div class="message-menu" :style="style" role="menu" @click.stop>
    <button type="button" @click="$emit('reply')">回复</button>
    <button v-if="canRecall" type="button" @click="$emit('recall')">撤回</button>
    <button type="button" class="danger" @click="$emit('delete')">删除</button>
  </div>
</template>
