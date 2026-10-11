<script setup>
import { computed } from 'vue'
import { sendLetters, songKey } from '../store.js'
import Icon from './Icon.vue'
import TrackTable from './TrackTable.vue'

const props = defineProps({
  view: { type: Object, required: true },
  showPlatform: { type: Boolean, default: true },
  more: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
})
const emit = defineEmits(['more'])

const visible = computed(() => {
  const q = props.view.filter.trim().toLowerCase()
  if (!q) return props.view.songs
  return props.view.songs.filter((s) => `${s.name} ${s.artist} ${s.album}`.toLowerCase().includes(q))
})
const selectedSongs = computed(() => props.view.songs.filter((s) => props.view.selected.has(songKey(s))))
const hiddenSelected = computed(() => {
  const shown = new Set(visible.value.map(songKey))
  return selectedSongs.value.filter((s) => !shown.has(songKey(s))).length
})
const allVisibleSelected = computed(
  () => visible.value.length > 0 && visible.value.every((s) => props.view.selected.has(songKey(s))),
)

function selectVisible() {
  if (allVisibleSelected.value) visible.value.forEach((s) => props.view.selected.delete(songKey(s)))
  else visible.value.forEach((s) => props.view.selected.add(songKey(s)))
}

async function sendSelected() {
  if (await sendLetters(selectedSongs.value)) props.view.selected.clear()
}

defineExpose({ sendSelected, selectVisible })
</script>

<template>
  <section class="results">
    <div class="toolbar">
      <div class="count">
        <span class="mono big">{{ String(view.songs.length).padStart(2, '0') }}</span>
        <span class="faint">首</span>
        <template v-if="view.selected.size">
          <span class="dot">·</span>
          <span class="picked">已选 <b class="mono">{{ view.selected.size }}</b></span>
          <span v-if="hiddenSelected" class="hidden-note faint">（含 {{ hiddenSelected }} 首被筛选隐藏）</span>
        </template>
      </div>
      <label class="filter">
        <Icon name="search" :size="16" />
        <input v-model="view.filter" class="field" placeholder="在这些信里筛选…" @keydown.esc="view.filter = ''" />
      </label>
      <div class="actions">
        <button class="btn small ghost" :disabled="!visible.length" @click="selectVisible">
          {{ allVisibleSelected ? '取消全选' : view.filter ? '全选可见' : '全选' }}
        </button>
        <button class="btn small ghost" :disabled="!view.selected.size" @click="view.selected.clear()">清空选择</button>
        <button class="btn wax" :disabled="!view.selected.size" title="Ctrl+D" @click="sendSelected">
          <Icon name="send" :size="17" />
          寄出所选{{ view.selected.size ? ` · ${view.selected.size}` : '' }}
        </button>
      </div>
    </div>
    <TrackTable v-if="visible.length" :songs="visible" :selected="view.selected" :show-platform="showPlatform"
      @send-one="(song) => sendLetters([song])" />
    <p v-else class="no-match faint">没有符合「{{ view.filter }}」的曲目</p>
    <div v-if="more && !view.filter" class="more">
      <button class="btn" :disabled="loadingMore" @click="emit('more')">
        <Icon name="quill" :size="16" />{{ loadingMore ? '正在翻找…' : '再找一些' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.results {
  margin-top: 8px;
}
.toolbar {
  position: sticky;
  top: 0;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 14px 14px 12px;
  background: color-mix(in srgb, var(--paper) 82%, transparent);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid transparent;
}
.count {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  white-space: nowrap;
}
.big {
  font-size: 26px;
  color: var(--ink);
  line-height: 1;
}
.dot {
  color: var(--ink-faint);
  margin: 0 2px;
}
.picked {
  color: var(--violet-ink);
}
.picked b {
  font-weight: 400;
}
.hidden-note {
  font-size: 12px;
}
.filter {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-faint);
  width: 220px;
}
.filter .field {
  width: 100%;
  height: 34px;
  font-size: 14px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.more {
  display: flex;
  justify-content: center;
  padding: 26px 0 8px;
}
.no-match {
  text-align: center;
  padding: 48px 0;
}
@media (max-width: 1180px) {
  .filter {
    width: 160px;
  }
}
</style>
