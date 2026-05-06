<template>
  <span class="ocr-btn-group">
    <button class="btn btn-ghost btn-sm ocr-btn" :disabled="loading" @click="$emit('pick')" title="从图片识别文字">
      {{ loading ? '⏳ 识别中...' : '📷 图片识别' }}
    </button>
    <button class="btn btn-ghost btn-sm ocr-btn" :disabled="loading" @click="$emit('paste')" title="从剪贴板粘贴图片识别">
      📋 粘贴图片
    </button>
    <span v-if="error" class="ocr-error">{{ error }}</span>
  </span>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
defineEmits(['pick', 'paste'])
</script>

<style scoped>
.ocr-btn-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 8px;
}
.ocr-btn {
  padding: 2px 8px;
  font-size: 11px;
  white-space: nowrap;
}
.ocr-error {
  font-size: 11px;
  color: var(--c-red);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
