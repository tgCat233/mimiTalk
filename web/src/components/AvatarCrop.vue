<script setup>
import { reactive, ref } from 'vue'

const props = defineProps({
  src: { type: String, required: true },
})

const emit = defineEmits(['cancel', 'confirm'])

const imgRef = ref(null)
const box = reactive({ x: 0, y: 0, size: 0 })
const rect = reactive({ width: 0, height: 0, naturalWidth: 1, naturalHeight: 1 })

function init() {
  const img = imgRef.value
  if (!img) return
  const bounds = img.getBoundingClientRect()
  rect.width = bounds.width
  rect.height = bounds.height
  rect.naturalWidth = img.naturalWidth
  rect.naturalHeight = img.naturalHeight
  box.size = Math.min(bounds.width, bounds.height) * 0.6
  box.x = (bounds.width - box.size) / 2
  box.y = (bounds.height - box.size) / 2
}

let mode = ''
let start = null

function onDown(event, nextMode) {
  mode = nextMode
  start = { x: event.clientX, y: event.clientY, bx: box.x, by: box.y, bs: box.size }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
  event.preventDefault()
}

function onMove(event) {
  if (!mode) return
  const dx = event.clientX - start.x
  const dy = event.clientY - start.y
  if (mode === 'drag') {
    box.x = Math.min(Math.max(start.bx + dx, 0), rect.width - box.size)
    box.y = Math.min(Math.max(start.by + dy, 0), rect.height - box.size)
    return
  }
  const limit = Math.min(rect.width, rect.height)
  const next = Math.min(Math.max(start.bs + Math.max(dx, dy), 40), limit)
  box.size = next
  box.x = Math.min(box.x, rect.width - box.size)
  box.y = Math.min(box.y, rect.height - box.size)
}

function onUp() {
  mode = ''
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onUp)
}

function confirm() {
  const img = imgRef.value
  if (!img || !box.size) return
  const scaleX = rect.naturalWidth / rect.width
  const scaleY = rect.naturalHeight / rect.height
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256
  canvas
    .getContext('2d')
    .drawImage(
      img,
      box.x * scaleX,
      box.y * scaleY,
      box.size * scaleX,
      box.size * scaleY,
      0,
      0,
      256,
      256,
    )
  canvas.toBlob((blob) => {
    if (blob) emit('confirm', blob)
  }, 'image/png')
}
</script>

<template>
  <div class="p3-crop-mask">
    <div class="p3-crop-panel">
      <div class="p3-crop-stage">
        <img ref="imgRef" :src="props.src" alt="" @load="init" />
        <div
          class="p3-crop-box"
          :style="{
            left: `${box.x}px`,
            top: `${box.y}px`,
            width: `${box.size}px`,
            height: `${box.size}px`,
          }"
          @pointerdown="onDown($event, 'drag')"
        >
          <span class="p3-crop-handle" @pointerdown.stop="onDown($event, 'resize')"></span>
        </div>
      </div>
      <div class="p3-crop-actions">
        <button type="button" @click="$emit('cancel')">取消</button>
        <button class="primary" type="button" @click="confirm">确定</button>
      </div>
    </div>
  </div>
</template>
