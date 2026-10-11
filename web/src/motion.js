// 动效小工具：功能之间的「寄送」——办完的委托飞进邮戳簿，封好的回信飞进信箱，夹进信里的歌飞向书桌。
// 全部用 Web Animations，尊重系统的「减少动态效果」和设置里的「光影与动效」开关。
import { store } from './store.js'

const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)')

export function calm() {
  return reducedQuery.matches || store.settings?.ambient === false
}

const GLYPHS = {
  // A tiny sealed envelope.
  letter: `<svg viewBox="0 0 34 24" width="34" height="24"><rect x="1" y="1" width="32" height="22" rx="2.5" fill="var(--sheet-raised)" stroke="var(--rule-strong)"/><path d="M1.8 2.2 17 13.5 32.2 2.2" fill="none" stroke="var(--rule-strong)"/><circle cx="17" cy="13" r="4.6" fill="var(--wax-a)"/><circle cx="17" cy="13" r="2.4" fill="none" stroke="var(--wax-text)" stroke-width=".8" opacity=".7"/></svg>`,
  // A postmark ring with 已送达.
  stamp: `<svg viewBox="0 0 40 40" width="34" height="34"><circle cx="20" cy="20" r="17" fill="var(--sheet-raised)" stroke="var(--violet-ink)" stroke-width="1.6"/><circle cx="20" cy="20" r="12.5" fill="none" stroke="var(--violet-ink)" stroke-width=".8" stroke-dasharray="2 2"/><path d="M13 20.5l4.5 4.5 9-10" fill="none" stroke="var(--violet-ink)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  note: `<svg viewBox="0 0 24 24" width="26" height="26"><circle cx="12" cy="12" r="11" fill="var(--sheet-raised)" stroke="var(--rule-strong)"/><path d="M10 16.5V7.5l6-1.5v9" fill="none" stroke="var(--violet-ink)" stroke-width="1.6" stroke-linecap="round"/><circle cx="8.6" cy="16.6" r="1.8" fill="var(--violet-ink)"/><circle cx="14.6" cy="15.1" r="1.8" fill="var(--violet-ink)"/></svg>`,
}

function centre(el) {
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
}

// Fly a little glyph from `from` (an element or {x, y}) to the sidebar bookmark `nav` (or any element), along an arc.
export function flyTo(from, nav, kind = 'letter') {
  const target = typeof nav === 'string' ? document.querySelector(`.sidebar [data-nav="${nav}"]`) : nav
  if (!target) return
  const start = from instanceof Element ? centre(from) : from
  const end = centre(target)
  if (calm() || !start) {
    receive(target)
    return
  }
  const node = document.createElement('div')
  node.className = 'flyer'
  node.innerHTML = GLYPHS[kind] || GLYPHS.letter
  node.style.cssText = `position:fixed;left:0;top:0;z-index:300;pointer-events:none;filter:drop-shadow(0 6px 8px rgba(40,20,60,.28));will-change:transform`
  document.body.appendChild(node)
  const dx = end.x - start.x
  const dy = end.y - start.y
  const lift = Math.min(160, 60 + Math.abs(dx) * 0.18)
  const frames = []
  for (let i = 0; i <= 12; i++) {
    const t = i / 12
    // Quadratic arc: up first, then down into the bookmark.
    const x = start.x + dx * t
    const y = start.y + dy * t - lift * 4 * t * (1 - t)
    const turn = -18 + 36 * t
    const scale = 1 + 0.25 * Math.sin(Math.PI * t) - 0.45 * t * t
    frames.push({ transform: `translate(${x - 17}px, ${y - 12}px) rotate(${turn}deg) scale(${scale})`, opacity: t > 0.92 ? 0 : 1 })
  }
  const anim = node.animate(frames, { duration: 900, easing: 'cubic-bezier(.45,.05,.4,1)' })
  anim.onfinish = () => {
    node.remove()
    receive(target)
  }
}

// The bookmark that catches something gives a small bounce and a gold glint.
export function receive(target) {
  target.classList.remove('caught')
  void target.offsetWidth
  target.classList.add('caught')
  setTimeout(() => target.classList.remove('caught'), 900)
}

// A burst of tiny ink petals from a point (completing the day's last commission, sealing a week…).
export function petals(from, count = 14) {
  if (calm()) return
  const { x, y } = from instanceof Element ? centre(from) : from
  const colours = ['var(--violet-ink)', 'var(--gold)', 'var(--wax-a)', 'var(--danger)']
  for (let i = 0; i < count; i++) {
    const p = document.createElement('span')
    const size = 5 + Math.random() * 6
    p.style.cssText = `position:fixed;left:${x}px;top:${y}px;width:${size}px;height:${size * 1.6}px;z-index:300;pointer-events:none;border-radius:50% 50% 50% 0;background:${colours[i % colours.length]};opacity:.85`
    document.body.appendChild(p)
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5
    const reach = 50 + Math.random() * 70
    const tx = Math.cos(angle) * reach
    const ty = Math.sin(angle) * reach * 0.7 - 30
    p.animate(
      [
        { transform: 'translate(-50%,-50%) rotate(0deg) scale(.4)', opacity: 0 },
        { transform: `translate(calc(-50% + ${tx * 0.7}px), calc(-50% + ${ty * 0.7}px)) rotate(${120 + i * 20}deg) scale(1)`, opacity: 0.9, offset: 0.35 },
        { transform: `translate(calc(-50% + ${tx}px), calc(-50% + ${ty + 70}px)) rotate(${260 + i * 30}deg) scale(.7)`, opacity: 0 },
      ],
      { duration: 1300 + Math.random() * 500, easing: 'cubic-bezier(.2,.7,.3,1)' },
    ).onfinish = () => p.remove()
  }
}

// Type text into a textarea a few characters at a time, as if the typewriter were writing it.
export function typeInto(el, text, onStep) {
  return new Promise((resolve) => {
    const startAt = el.selectionStart ?? el.value.length
    const before = el.value.slice(0, startAt)
    const after = el.value.slice(el.selectionEnd ?? startAt)
    if (calm()) {
      el.value = before + text + after
      onStep?.(el.value, true)
      el.selectionStart = el.selectionEnd = startAt + text.length
      resolve()
      return
    }
    let i = 0
    const step = () => {
      i = Math.min(text.length, i + 1 + Math.floor(Math.random() * 2))
      el.value = before + text.slice(0, i) + after
      el.selectionStart = el.selectionEnd = startAt + i
      onStep?.(el.value, i >= text.length)
      if (i < text.length) setTimeout(step, 28 + Math.random() * 40)
      else resolve()
    }
    step()
  })
}
