import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])
  let _id = 0

  function show(message, type = 'info', duration = 3000) {
    const id = ++_id
    toasts.value.push({ id, message, type })
    if (duration > 0) {
      setTimeout(() => remove(id), duration)
    }
    return id
  }

  function remove(id) {
    const idx = toasts.value.findIndex(t => t.id === id)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  function success(message, duration) { return show(message, 'success', duration) }
  function error(message, duration) { return show(message, 'error', duration ?? 5000) }
  function warning(message, duration) { return show(message, 'warning', duration) }
  function info(message, duration) { return show(message, 'info', duration) }

  return { toasts, show, remove, success, error, warning, info }
})
