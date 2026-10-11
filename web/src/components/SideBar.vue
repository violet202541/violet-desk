<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { store, activeJobs, saveSettings, isDark, go, MUSIC_VIEWS } from '../store.js'
import { desk } from '../desk.js'
import { player } from '../player.js'
import { unread, urgentCount } from '../geese.js'
import Icon from './Icon.vue'
import flower from '../assets/violet-flower.png'
import { startDrag } from '../windowFrame.js'

// A logo dropped into assets/ (logo.png / logo.webp) replaces the watercolour violet.
const custom = Object.values(import.meta.glob('../assets/logo.{png,webp}', { eager: true, import: 'default' }))[0]
const logo = custom || flower

const NAV = [
  { id: 'desk', label: '书桌', hint: '今日：来信、回信与今天的委托', icon: 'desk', key: '1' },
  { id: 'commissions', label: '委托', hint: '待办事项', icon: 'commission', key: '2' },
  { id: 'calendar', label: '邮戳簿', hint: '日历：约定、纪念日与每一天', icon: 'stamp', key: '3' },
  { id: 'mailbox', label: '信箱', hint: '来信与回信（日记）', icon: 'letter', key: '4' },
  { id: 'geese', label: '鸿雁', hint: '学校的通知：沿驿路取信，按名片拣信', icon: 'goose', key: '5' },
  { id: 'music', label: '音乐', hint: '寻歌、歌单、书信匣、信札（收藏与我的歌单）与寄信室', icon: 'music', key: '6' },
]

function isOn(id) {
  if (id === 'music') return MUSIC_VIEWS.includes(store.view)
  if (id === 'desk') return store.view === 'desk' || store.view === 'write'
  return store.view === id
}

const quota = computed(() => {
  const q = store.quota || {}
  if (q.free === undefined && q.paid === undefined) return ''
  return (q.free || 0) + (q.paid || 0)
})
const progress = computed(() => {
  const jobs = activeJobs.value
  if (!jobs.length) return 0
  return jobs.reduce((sum, j) => sum + (j.state === 'downloading' || j.state === 'finishing' ? j.pct : 0), 0) / jobs.length
})
const dueCount = computed(() => desk.today?.commissions?.length || 0)
const mailWaiting = computed(
  () => (store.letters.today && !store.letters.today.opened) || Boolean(desk.today?.arrivals?.length),
)

// One ribbon glides between the bookmarks instead of each bookmark owning its own.
const marks = ref(null)
const glide = ref(null)
let lastTop = null
function place() {
  const list = marks.value
  const ribbon = glide.value
  if (!list || !ribbon) return
  const on = list.querySelector('.mark.on')
  if (!on) {
    ribbon.style.transform = `translate(-104%, ${lastTop ?? 0}px)`
    return
  }
  const top = on.offsetTop
  ribbon.style.height = `${on.offsetHeight}px`
  ribbon.style.transform = `translate(0, ${top}px)`
  if (lastTop !== null && lastTop !== top && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    ribbon.classList.remove('moving')
    void ribbon.offsetWidth
    ribbon.classList.add('moving')
  }
  lastTop = top
}
watch(() => store.view, () => nextTick(place))
let observer = null
onMounted(() => {
  nextTick(place)
  observer = new ResizeObserver(() => {
    lastTop = null
    place()
  })
  observer.observe(marks.value)
})
onBeforeUnmount(() => observer?.disconnect())

function toggleTheme() {
  saveSettings({ theme: isDark() ? 'light' : 'dark' })
}
</script>

<template>
  <nav class="sidebar" aria-label="主导航">
    <div v-if="store.frame.frameless" class="drag" @pointerdown="startDrag" />
    <button class="logo" :class="{ custom }" title="Violet · 回到书桌" @click="go('desk')">
      <img :src="logo" alt="Violet" draggable="false" />
    </button>
    <ul ref="marks" class="marks">
      <li class="glide" aria-hidden="true"><span ref="glide" class="ribbon" @animationend="$event.target.classList.remove('moving')" /></li>
      <li v-for="item in NAV" :key="item.id">
        <button class="mark" :class="{ on: isOn(item.id) }" :data-nav="item.id" :title="`${item.hint}　Alt+${item.key}`"
          :aria-label="`${item.label}：${item.hint}`" :aria-current="isOn(item.id) ? 'page' : undefined" @click="go(item.id)">
          <span class="glyph">
            <Icon :name="item.icon" :size="21" />
            <span v-if="item.id === 'music' && player.playing" class="eq" aria-hidden="true"><i /><i /><i /></span>
          </span>
          <span class="label">{{ item.label }}</span>
          <span v-if="item.id === 'commissions' && dueCount" class="badge mono" :title="`今天有 ${dueCount} 份委托`">{{ dueCount }}</span>
          <span v-if="item.id === 'mailbox' && mailWaiting" class="dot" title="有还没拆的信" />
          <span v-if="item.id === 'geese' && unread" class="badge mono" :class="{ hot: urgentCount }"
            :title="`信绳上有 ${unread} 封没拆${urgentCount ? `，其中 ${urgentCount} 封急件` : ''}`">{{ unread }}</span>
          <template v-if="item.id === 'music' && activeJobs.length">
            <span class="badge mono">{{ activeJobs.length }}</span>
            <svg class="ring" viewBox="0 0 36 36" aria-hidden="true">
              <circle cx="18" cy="18" r="16" pathLength="100" :style="{ strokeDashoffset: 100 - progress }" />
            </svg>
          </template>
        </button>
      </li>
    </ul>
    <div class="foot">
      <div v-if="quota !== '' && MUSIC_VIEWS.includes(store.view)" class="quota" title="ChKSz 剩余额度">
        <span class="mono">{{ quota }}</span>
        <span class="caption">余额</span>
      </div>
      <div v-if="!store.connected" class="offline" title="与本地服务的连接中断，正在重连">重连中</div>
      <button class="icon-btn" :title="isDark() ? '换成信笺（浅色）' : '点亮烛光（深色）'" @click="toggleTheme">
        <Icon :name="isDark() ? 'sun' : 'candle'" :size="19" />
      </button>
      <button class="icon-btn" :class="{ on: store.view === 'settings' }" title="设置：钥匙、目录、灯光与备份　Alt+7"
        aria-label="设置" @click="go('settings')">
        <Icon name="sliders" :size="19" />
      </button>
    </div>
  </nav>
</template>

<style scoped>
.sidebar {
  position: relative;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: var(--sidebar);
  min-height: 0;
  padding: calc(var(--titlebar) * 0.5 + 16px) 0 12px;
  background: var(--paper-deep);
  border-right: 1px solid var(--rule);
  box-shadow: inset -12px 0 18px -16px rgba(60, 40, 20, 0.25);
}
.drag {
  position: absolute;
  inset: 0 0 auto 0;
  height: var(--titlebar);
}
.logo {
  position: relative;
  align-self: center;
  flex: none;
  margin-bottom: 14px;
  transition: transform 0.5s var(--ease);
  filter: drop-shadow(0 4px 6px rgba(60, 30, 80, 0.22));
}
.logo img {
  display: block;
  width: 52px;
  height: 52px;
}
.logo.custom img {
  border-radius: 14px;
}
.logo:hover {
  transform: rotate(-8deg) scale(1.05);
}
.marks {
  list-style: none;
  margin: 0;
  padding: 0 0 8px;
  display: grid;
  align-content: start;
  gap: 2px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: none;
}
.marks::-webkit-scrollbar {
  display: none;
}
.mark {
  position: relative;
  display: grid;
  justify-items: center;
  gap: 2px;
  width: 100%;
  padding: 11px 0 12px;
  isolation: isolate;
  color: var(--ink-faint);
  transition: color 0.25s var(--ease);
}
.mark:hover {
  color: var(--ink);
}
.mark.on {
  color: var(--wax-text);
}
/* The bookmark ribbon spans the whole width, ends in a swallowtail, and glides from bookmark to bookmark. */
.glide {
  position: absolute;
  inset: 0 0 auto 0;
  height: 0;
  pointer-events: none;
}
.ribbon {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 64px;
  background: radial-gradient(130% 120% at 20% 10%, var(--wax-a), var(--wax-b));
  clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 88%, 0 100%);
  transform: translate(-104%, 0);
  transition: transform 0.55s cubic-bezier(0.3, 1.25, 0.45, 1), height 0.4s var(--ease);
  box-shadow: 0 6px 12px -8px rgba(40, 20, 60, 0.6);
}
/* While it travels the tail flutters like silk. */
.ribbon.moving {
  animation: flutter 0.6s ease-out;
}
@keyframes flutter {
  0% {
    clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 88%, 0 100%);
  }
  30% {
    clip-path: polygon(0 4%, 100% 0, 96% 94%, 46% 78%, 4% 100%);
  }
  60% {
    clip-path: polygon(0 0, 100% 3%, 100% 100%, 54% 94%, 0 96%);
  }
  100% {
    clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 88%, 0 100%);
  }
}
.marks {
  position: relative;
}
.mark {
  z-index: 1;
}
.glyph {
  position: relative;
  display: grid;
  place-items: center;
  transition: transform 0.35s var(--ease);
}
.mark:hover .glyph {
  transform: translateY(-2px) rotate(-4deg);
}
/* Something just landed in this bookmark (a delivered commission, a sealed letter…). */
.mark.caught .glyph {
  animation: catch 0.8s cubic-bezier(0.3, 1.6, 0.5, 1);
}
.mark.caught::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 40%;
  width: 46px;
  height: 46px;
  margin: -23px 0 0 -23px;
  border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--gold) 45%, transparent), transparent 70%);
  animation: glint 0.9s ease-out forwards;
  pointer-events: none;
}
@keyframes catch {
  0% {
    transform: scale(1);
  }
  30% {
    transform: scale(1.32) rotate(-8deg);
  }
  60% {
    transform: scale(0.92) rotate(4deg);
  }
  100% {
    transform: none;
  }
}
@keyframes glint {
  from {
    transform: scale(0.4);
    opacity: 1;
  }
  to {
    transform: scale(1.6);
    opacity: 0;
  }
}
/* A tiny equaliser while a song plays. */
.eq {
  position: absolute;
  right: -11px;
  bottom: 0;
  display: flex;
  align-items: flex-end;
  gap: 1.5px;
  height: 10px;
}
.eq i {
  width: 2px;
  height: 100%;
  border-radius: 1px;
  background: currentColor;
  transform-origin: bottom;
  animation: eq 0.9s ease-in-out infinite alternate;
}
.eq i:nth-child(2) {
  animation-delay: -0.3s;
  animation-duration: 0.7s;
}
.eq i:nth-child(3) {
  animation-delay: -0.6s;
  animation-duration: 1.1s;
}
@keyframes eq {
  from {
    transform: scaleY(0.25);
  }
  to {
    transform: scaleY(1);
  }
}
@media (prefers-reduced-motion: reduce) {
  .eq i,
  .ribbon.moving,
  .mark.caught .glyph,
  .mark.caught::after {
    animation: none;
  }
}
.label {
  font-family: var(--font-title);
  font-size: 13px;
  letter-spacing: 0.12em;
  padding-left: 0.12em;
}
.badge {
  position: absolute;
  top: 5px;
  right: 18px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 9px;
  background: var(--gold);
  color: #fff;
  font-size: 11px;
  line-height: 18px;
}
.badge.hot {
  background: var(--danger);
}
.mark.on .badge {
  background: var(--wax-text);
  color: var(--wax-b);
}
.dot {
  position: absolute;
  top: 9px;
  right: 25px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #c06b62, #8f2f28);
  box-shadow: 0 0 0 2px var(--paper-deep);
}
.ring {
  position: absolute;
  top: 3px;
  left: calc(50% - 18px);
  width: 36px;
  height: 36px;
  transform: rotate(-90deg);
  fill: none;
  stroke: var(--gold);
  stroke-width: 1.6;
  stroke-dasharray: 100;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.5s var(--ease);
  pointer-events: none;
}
.foot {
  flex: none;
  display: grid;
  justify-items: center;
  gap: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--rule);
  margin: 0 14px;
}
.icon-btn.on {
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.quota {
  display: grid;
  justify-items: center;
  line-height: 1.2;
  color: var(--ink-soft);
  font-size: 13px;
  margin-bottom: 4px;
}
.caption {
  font-size: 11px;
  color: var(--ink-faint);
  letter-spacing: 0.2em;
}
.offline {
  font-size: 11px;
  color: var(--danger);
}
@media (max-height: 700px) {
  .logo img {
    width: 42px;
    height: 42px;
  }
  .mark {
    padding: 8px 0 9px;
  }
}
</style>
