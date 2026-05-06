/**
 * OCR 图片识别 composable
 * 提供图片选择、粘贴、识别等通用逻辑
 */
import { ref } from 'vue'
import { ocrImage } from '@/services/api'

export function useOcr() {
  const ocrLoading = ref(false)
  const ocrError = ref('')

  /**
   * 将 File 对象转为 base64
   */
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = reject
      reader.readAsDataURL(file)
    })
  }

  /**
   * 从文件选择器选图并识别，结果追加到目标 ref
   * @param {Ref<string>} targetRef - 要填充的 v-model ref
   * @param {string} prompt - 可选的识别提示词
   * @param {'replace'|'append'} mode - 替换还是追加
   */
  async function pickAndRecognize(targetRef, prompt = '', mode = 'append') {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.multiple = true
    input.onchange = async () => {
      if (!input.files?.length) return
      await recognizeFiles(Array.from(input.files), targetRef, prompt, mode)
    }
    input.click()
  }

  /**
   * 识别多个文件
   */
  async function recognizeFiles(files, targetRef, prompt = '', mode = 'append') {
    ocrLoading.value = true
    ocrError.value = ''
    const results = []
    try {
      for (const file of files) {
        if (!file.type.startsWith('image/')) continue
        const base64 = await fileToBase64(file)
        const res = await ocrImage(base64, prompt)
        if (res.ok) {
          results.push(res.text)
        } else {
          ocrError.value = res.error
          break
        }
      }
      if (results.length > 0) {
        const text = results.join('\n')
        if (mode === 'replace' || !targetRef.value) {
          targetRef.value = text
        } else {
          targetRef.value = targetRef.value.trimEnd() + '\n' + text
        }
      }
    } catch (e) {
      ocrError.value = e.message || '识别失败'
    } finally {
      ocrLoading.value = false
    }
  }

  /**
   * 从剪贴板粘贴图片并识别
   */
  async function pasteAndRecognize(targetRef, prompt = '', mode = 'append') {
    ocrLoading.value = true
    ocrError.value = ''
    try {
      const items = await navigator.clipboard.read()
      const imageFiles = []
      for (const item of items) {
        const imageType = item.types.find(t => t.startsWith('image/'))
        if (imageType) {
          const blob = await item.getType(imageType)
          imageFiles.push(new File([blob], 'clipboard.png', { type: imageType }))
        }
      }
      if (imageFiles.length === 0) {
        ocrError.value = '剪贴板中没有图片'
        ocrLoading.value = false
        return
      }
      await recognizeFiles(imageFiles, targetRef, prompt, mode)
    } catch (e) {
      // 剪贴板权限被拒绝等
      if (e.name === 'NotAllowedError') {
        ocrError.value = '剪贴板访问被拒绝，请使用文件选择'
      } else {
        ocrError.value = e.message || '粘贴失败'
      }
      ocrLoading.value = false
    }
  }

  return {
    ocrLoading,
    ocrError,
    pickAndRecognize,
    pasteAndRecognize,
    recognizeFiles,
  }
}
