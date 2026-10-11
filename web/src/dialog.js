// 弹层的键盘规矩：打开时把焦点放进去，Tab 在里面循环，Esc 关闭，关上后把焦点还给原来的位置。
import { nextTick, onBeforeUnmount, onMounted, watch } from 'vue'

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
const stack = []

export const dialogOpen = () => stack.length > 0

export function trapFocus(container, onClose) {
  let previous = null
  let attached = null

  const keydown = (event) => {
    if (stack[stack.length - 1] !== attached) return
    if (event.key === 'Escape') {
      event.stopPropagation()
      event.preventDefault()
      onClose?.()
      return
    }
    if (event.key !== 'Tab') return
    const items = [...attached.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null)
    if (!items.length) return
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    } else if (!attached.contains(document.activeElement)) {
      event.preventDefault()
      first.focus()
    }
  }

  function attach(el) {
    if (!el || attached === el) return
    detach()
    attached = el
    previous = document.activeElement
    stack.push(el)
    window.addEventListener('keydown', keydown, true)
    nextTick(() => {
      const target = el.querySelector('[autofocus]') || el.querySelector(FOCUSABLE) || el
      if (!el.contains(document.activeElement)) target.focus?.({ preventScroll: true })
    })
  }

  function detach() {
    if (!attached) return
    const index = stack.indexOf(attached)
    if (index >= 0) stack.splice(index, 1)
    window.removeEventListener('keydown', keydown, true)
    attached = null
    if (previous && document.contains(previous)) previous.focus?.({ preventScroll: true })
    previous = null
  }

  onMounted(() => {
    watch(container, (el) => (el ? attach(el) : detach()), { immediate: true, flush: 'post' })
  })
  onBeforeUnmount(detach)
}
