<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toastStore.toasts"
          :key="toast.id"
          class="toast-item"
          :class="'toast-' + toast.type"
          @click="toastStore.remove(toast.id)"
        >
          <span class="toast-icon">{{ icons[toast.type] }}</span>
          <span class="toast-message">{{ toast.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToastStore } from '../stores/toast'

const toastStore = useToastStore()

const icons = {
  success: '✓',
  error: '✕',
  warning: '!',
  info: 'i',
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-radius: var(--r-md, 10px);
  font-size: 13px;
  font-weight: 500;
  font-family: var(--f-ui, system-ui, sans-serif);
  box-shadow: var(--shadow-md, 0 4px 24px rgba(0,0,0,0.45));
  pointer-events: auto;
  cursor: pointer;
  max-width: 360px;
  backdrop-filter: blur(8px);
  background: var(--c-card);
  border: 1px solid var(--c-border);
  color: var(--c-text);
}

.toast-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.toast-success {
  background: rgba(20, 29, 47, 0.97);
  color: var(--c-text);
  border: 1px solid rgba(0, 212, 138, 0.35);
}
.toast-success .toast-icon {
  background: var(--c-green);
  color: #0c1222;
}

.toast-error {
  background: rgba(20, 29, 47, 0.97);
  color: var(--c-text);
  border: 1px solid rgba(255, 71, 87, 0.35);
}
.toast-error .toast-icon {
  background: var(--c-red);
  color: #0c1222;
}

.toast-warning {
  background: rgba(20, 29, 47, 0.97);
  color: var(--c-text);
  border: 1px solid rgba(240, 165, 0, 0.35);
}
.toast-warning .toast-icon {
  background: var(--c-orange);
  color: #0c1222;
}

.toast-info {
  background: rgba(20, 29, 47, 0.97);
  color: var(--c-text);
  border: 1px solid rgba(45, 122, 237, 0.35);
}
.toast-info .toast-icon {
  background: var(--c-primary);
  color: #0c1222;
}

.toast-enter-active {
  transition: all 0.3s ease;
}
.toast-leave-active {
  transition: all 0.2s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px) scale(0.95);
}

.toast-move {
  transition: transform 0.2s ease;
}
</style>
