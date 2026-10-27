<script setup>
import { ref } from 'vue'
import AvatarCrop from './AvatarCrop.vue'

defineProps({
  avatars: { type: Array, default: () => [] },
  current: { type: String, default: '' },
})

const emit = defineEmits(['pick', 'custom', 'close'])

const fileInput = ref(null)
const cropSrc = ref('')

function pickFile() {
  fileInput.value?.click()
}

function onFileChange(event) {
  const file = event.target.files?.[0]
  if (file) {
    cropSrc.value = URL.createObjectURL(file)
  }
  event.target.value = ''
}

function onConfirm(blob) {
  URL.revokeObjectURL(cropSrc.value)
  cropSrc.value = ''
  emit('custom', blob)
}

function onCancel() {
  URL.revokeObjectURL(cropSrc.value)
  cropSrc.value = ''
}
</script>

<template>
  <div class="p3-sticker-mask" @click.self="$emit('close')">
    <div class="p3-sticker-panel">
      <div class="p3-sticker-head">
        <strong>管理员头像</strong>
        <button type="button" @click="$emit('close')">×</button>
      </div>

      <div class="p3-avatar-grid">
        <button
          v-for="avatar in avatars"
          :key="avatar.id"
          type="button"
          :class="{ active: avatar.url === current }"
          @click="$emit('pick', avatar.url)"
        >
          <img :src="avatar.url" alt="" />
        </button>

        <button class="p3-avatar-add" type="button" title="上传自定义头像" @click="pickFile">
          +
        </button>
      </div>

      <input
        ref="fileInput"
        type="file"
        accept="image/png,image/jpeg"
        hidden
        @change="onFileChange"
      />
    </div>

    <AvatarCrop v-if="cropSrc" :src="cropSrc" @cancel="onCancel" @confirm="onConfirm" />
  </div>
</template>
