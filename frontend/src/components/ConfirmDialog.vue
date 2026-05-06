<template>
  <Teleport to="body">
    <div v-if="visible" class="confirm-overlay" @click.self="onCancel">
      <div class="confirm-dialog">
        <div class="confirm-title">{{ title }}</div>
        <div class="confirm-message">{{ message }}</div>
        <div class="confirm-actions">
          <button class="btn-cancel" @click="onCancel">取消</button>
          <button class="btn-confirm" :class="{ danger: isDanger }" @click="onConfirm">{{ confirmText }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '确定要执行此操作吗？' },
  confirmText: { type: String, default: '确定' },
  isDanger: { type: Boolean, default: true },
})

const visible = ref(false)
let _resolve = null

function show() {
  visible.value = true
  return new Promise((resolve) => { _resolve = resolve })
}

function onConfirm() {
  visible.value = false
  if (_resolve) _resolve(true)
}

function onCancel() {
  visible.value = false
  if (_resolve) _resolve(false)
}

defineExpose({ show })
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.confirm-dialog {
  background: var(--c-card);
  border-radius: 8px;
  padding: 24px;
  min-width: 320px;
  max-width: 420px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
}
.confirm-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}
.confirm-message {
  font-size: 14px;
  color: var(--c-text-2);
  margin-bottom: 20px;
  line-height: 1.5;
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.btn-cancel, .btn-confirm {
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid #ddd;
  cursor: pointer;
  font-size: 14px;
}
.btn-cancel {
  background: var(--c-card);
  color: var(--c-text);
}
.btn-cancel:hover {
  background: var(--c-hover);
}
.btn-confirm {
  background: var(--c-primary, #1677ff);
  color: #fff;
  border-color: var(--c-primary, #1677ff);
}
.btn-confirm.danger {
  background: var(--c-red, #ff4d4f);
  border-color: var(--c-red, #ff4d4f);
}
.btn-cancel:focus, .btn-cancel:focus-visible,
.btn-confirm:focus, .btn-confirm:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 2px;
}
.btn-confirm:hover {
  opacity: 0.85;
}
</style>
