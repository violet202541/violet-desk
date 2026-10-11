<script setup>
// 「夹进信札」的小菜单：在哪首歌上点，就在哪儿弹出。列出所有信札（缎带颜色 + 名字），最下面可以扎一束新的。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { shelf, RIBBONS, addToBundle } from '../shelf.js'
import Icon from './Icon.vue'

const box = ref(null)
const pos = ref({ left: 0, top: 0 })
const menu = computed(() => shelf.menu)
const ids = computed(() => (menu.value?.tracks || []).map((t) => t.id))
const label = computed(() => {
  const tracks = menu.value?.tracks || []
  return tracks.length === 1 ? `「${tracks[0].title}」` : `${tracks.length} 首歌`
})

// A bundle already holding every song in hand is marked, not offered again.
function holds(bundle) {
  return ids.value.length > 0 && ids.value.every((id) => (shelf.memberships[id] || []).includes(bundle.id))
}

function place() {
  const m = menu.value
  const el = box.value
  if (!m || !el) return
  const w = el.offsetWidth
  const h = el.offsetHeight
  let left = Math.min(Math.max(12, m.x - w / 2), innerWidth - w - 12)
  let top = m.y
  // Near the bottom (the player bar), open upwards instead.
  if (top + h > innerHeight - 12) top = Math.max(12, m.top - h)
  pos.value = { left, top }
}

watch(menu, async (m) => {
  if (!m) return
  await nextTick()
  place()
})
watch(() => shelf.bundles.length, () => nextTick(place))

// Read what is in hand before the menu closes: closing it empties the computed list.
async function pick(bundle) {
  const m = menu.value
  const trackIds = ids.value
  shelf.menu = null
  await addToBundle(bundle, { trackIds }, m.from)
}

function tieNew() {
  const m = menu.value
  const trackIds = ids.value
  shelf.menu = null
  shelf.editing = { trackIds, covers: m.tracks.filter((t) => t.has_cover).map((t) => t.id).slice(0, 3) }
}

const close = () => (shelf.menu = null)
function outside(event) {
  if (menu.value && box.value && !box.value.contains(event.target) && !menu.value.from?.contains(event.target)) close()
}
function key(event) {
  if (menu.value && event.key === 'Escape') {
    event.stopPropagation()
    close()
  }
}
onMounted(() => {
  document.addEventListener('mousedown', outside, true)
  document.addEventListener('keydown', key, true)
  window.addEventListener('resize', close)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', outside, true)
  document.removeEventListener('keydown', key, true)
  window.removeEventListener('resize', close)
})
</script>

<template>
  <Transition name="pop">
    <div v-if="menu" ref="box" class="bundle-menu sheet" role="menu" :aria-label="`把${label}夹进信札`"
      :style="{ left: pos.left + 'px', top: pos.top + 'px' }">
      <p class="head">把<span class="title-text">{{ label }}</span>夹进……</p>
      <div class="items">
        <button v-for="b in shelf.bundles" :key="b.id" class="item" role="menuitem" :disabled="holds(b)"
          :style="{ '--ribbon': (RIBBONS[b.ribbon] || RIBBONS.violet).hue }" @click="pick(b)">
          <span class="knot" />
          <span class="name ellipsis">{{ b.name }}</span>
          <span v-if="holds(b)" class="already">已在其中</span>
          <span v-else class="n mono">{{ b.count }}</span>
        </button>
        <p v-if="shelf.loaded && !shelf.bundles.length" class="empty faint">还没有信札。扎第一束吧。</p>
      </div>
      <button class="item new" role="menuitem" @click="tieNew"><Icon name="plus" :size="14" />扎一束新的信札</button>
    </div>
  </Transition>
</template>

<style scoped>
.bundle-menu {
  position: fixed;
  z-index: 90;
  width: 250px;
  padding: 10px 6px 6px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lift);
}
.head {
  margin: 0 8px 6px;
  font-size: 12.5px;
  color: var(--ink-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.head .title-text {
  color: var(--ink);
}
.items {
  max-height: 260px;
  overflow-y: auto;
}
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  border-radius: var(--radius);
  font-size: 14px;
  color: var(--ink);
  text-align: left;
}
.item:hover:not(:disabled),
.item:focus-visible {
  background: var(--violet-wash);
}
.item:disabled {
  color: var(--ink-faint);
  cursor: default;
}
/* A little bow in the bundle's ribbon colour. */
.knot {
  flex: none;
  width: 18px;
  height: 12px;
  background: var(--ribbon);
  clip-path: path('M9 6 C 6 0, 0 0, 0 3 C 0 7, 6 7, 9 6 Z M9 6 C 12 0, 18 0, 18 3 C 18 7, 12 7, 9 6 Z M8 6 L 5 12 L 9 7 L 13 12 L 10 6 Z');
}
.name {
  flex: 1;
  min-width: 0;
}
.n {
  font-size: 11.5px;
  color: var(--ink-faint);
}
.already {
  font-size: 11.5px;
  color: var(--emerald);
}
.empty {
  margin: 4px 10px 8px;
  font-size: 12.5px;
}
.new {
  margin-top: 4px;
  border-top: 1px dashed var(--rule-strong);
  border-radius: 0 0 var(--radius) var(--radius);
  color: var(--violet-ink);
  font-size: 13.5px;
}
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.18s var(--ease), transform 0.22s var(--ease);
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
</style>
