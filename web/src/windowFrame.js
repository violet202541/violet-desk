// 自绘标题区的拖动：按下交给系统移动循环（保留贴边分屏）；两次按下间隔很短视为双击，切换最大化。
import { api } from './api.js'

let lastDown = 0

export function windowAction(action, edge) {
  api.window(action, edge).catch(() => {})
}

export function startDrag(event) {
  if (event.button !== 0 || event.target.closest('button, a, input')) return
  const now = Date.now()
  if (now - lastDown < 320) {
    lastDown = 0
    windowAction('toggle')
    return
  }
  lastDown = now
  windowAction('begin', 'caption')
}
