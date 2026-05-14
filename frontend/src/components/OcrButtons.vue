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
  font-family: var(--f-ui);
  color: var(--c-text-2);
  background: var(--c-surface);
  border: 1px solid var(--c-border-s);
  border-radius: var(--r-sm);
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
.ocr-btn:hover:not(:disabled) {
  color: var(--c-accent);
  border-color: var(--c-accent);
  background: rgba(240, 165, 0, 0.08);
}
.ocr-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
