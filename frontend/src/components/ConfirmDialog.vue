<template>
  <Teleport to="body">
    <Transition name="dialog">
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
    </Transition>
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
  background: rgba(6, 10, 20, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.confirm-dialog {
  background: var(--c-card);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md, 10px);
  padding: 24px;
  min-width: 320px;
  max-width: 420px;
  box-shadow: var(--shadow-md, 0 4px 24px rgba(0,0,0,0.45));
}
.confirm-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--c-text);
  margin-bottom: 12px;
  font-family: var(--f-ui);
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
  border-radius: var(--r-sm, 8px);
  border: 1px solid var(--c-border);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--f-ui, system-ui, sans-serif);
  transition: all 0.15s ease;
}
.btn-cancel {
  background: var(--c-surface);
  color: var(--c-text);
}
.btn-cancel:hover {
  background: var(--c-card);
  border-color: var(--c-text-2);
}
.btn-confirm {
  background: var(--c-primary);
  color: var(--c-text);
  border-color: var(--c-primary);
}
.btn-confirm.danger {
  background: var(--c-red);
  border-color: var(--c-red);
}
.btn-cancel:focus, .btn-cancel:focus-visible,
.btn-confirm:focus, .btn-confirm:focus-visible {
  outline: 2px solid var(--c-accent);
  outline-offset: 2px;
}
.btn-confirm:hover {
  opacity: 0.85;
}

.dialog-enter-active { transition: all 0.2s ease; }
.dialog-leave-active { transition: all 0.15s ease; }
.dialog-enter-from { opacity: 0; }
.dialog-enter-from .confirm-dialog { transform: scale(0.95); }
.dialog-leave-to { opacity: 0; }
.dialog-leave-to .confirm-dialog { transform: scale(0.95); }
</style>
