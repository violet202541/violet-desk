<script setup>
import { ref } from 'vue'
import { coverUrl } from '../api.js'
import { duration } from '../format.js'
import { songKey } from '../store.js'
import CoverArt from './CoverArt.vue'
import Icon from './Icon.vue'
import PlatformStamp from './PlatformStamp.vue'

const props = defineProps({
  songs: { type: Array, required: true },
  selected: { type: Set, required: true },
  showPlatform: { type: Boolean, default: true },
})
const emit = defineEmits(['send-one'])
const anchor = ref(null)

function toggle(index, event) {
  const song = props.songs[index]
  const key = songKey(song)
  if (event?.shiftKey && anchor.value !== null) {
    const [a, b] = [anchor.value, index].sort((x, y) => x - y)
    const on = !props.selected.has(key)
    for (let i = a; i <= b; i++) {
      const k = songKey(props.songs[i])
      on ? props.selected.add(k) : props.selected.delete(k)
    }
  } else if (props.selected.has(key)) props.selected.delete(key)
  else props.selected.add(key)
  anchor.value = index
}

function onKey(index, event) {
  if (event.key === ' ' || event.key === 'Enter') {
    event.preventDefault()
    toggle(index, event)
  } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    const rows = event.currentTarget.parentElement.children
    rows[index + (event.key === 'ArrowDown' ? 1 : -1)]?.focus()
  }
}
</script>

<template>
  <div class="table" :class="{ 'no-platform': !showPlatform }" role="listbox" aria-multiselectable="true">
    <div class="head">
      <span />
      <span class="num">№</span>
      <span>曲目</span>
      <span>专辑</span>
      <span class="right">时长</span>
      <span v-if="showPlatform">来源</span>
      <span />
    </div>
    <div class="rows">
      <div v-for="(song, i) in songs" :key="songKey(song)" class="row" :class="{ on: selected.has(songKey(song)) }"
        role="option" :aria-selected="selected.has(songKey(song))" tabindex="0" @click="toggle(i, $event)"
        @keydown="onKey(i, $event)">
        <span class="check" aria-hidden="true">
          <svg viewBox="0 0 20 20"><rect x="2.5" y="2.5" width="15" height="15" rx="2" />
            <path d="M5.5 10.5l3 3 6-7" pathLength="1" /></svg>
        </span>
        <span class="num mono">{{ String(i + 1).padStart(2, '0') }}</span>
        <span class="track">
          <CoverArt :src="coverUrl(song, 80)" :size="40" :seed="song.name" />
          <span class="names">
            <span class="name title-text ellipsis">{{ song.name }}</span>
            <span class="artist ellipsis">{{ song.artist || '佚名' }}</span>
          </span>
        </span>
        <span class="album ellipsis">{{ song.album || '—' }}</span>
        <span class="dur mono right">{{ duration(song.duration) }}</span>
        <span v-if="showPlatform"><PlatformStamp :platform="song.platform" small /></span>
        <span class="actions">
          <button class="icon-btn" title="只寄出这一首" @click.stop="emit('send-one', song)">
            <Icon name="send" :size="17" />
          </button>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.table {
  --cols: 34px 44px minmax(220px, 1.6fr) minmax(120px, 1fr) 64px 76px 44px;
}
.table.no-platform {
  --cols: 34px 44px minmax(220px, 1.6fr) minmax(120px, 1fr) 64px 44px;
}
.head,
.row {
  display: grid;
  grid-template-columns: var(--cols);
  align-items: center;
  gap: 12px;
  padding: 0 14px;
}
.head {
  height: 34px;
  font-family: var(--font-display);
  font-style: italic;
  font-size: 14px;
  color: var(--ink-faint);
  border-bottom: 1px solid var(--rule);
  letter-spacing: 0.04em;
}
.row {
  height: 60px;
  border-bottom: 1px dashed var(--rule);
  cursor: pointer;
  outline: none;
  transition: background 0.18s var(--ease);
  position: relative;
}
.row:hover {
  background: var(--violet-wash);
}
.row:focus-visible {
  background: var(--violet-wash);
  box-shadow: inset 2px 0 0 var(--violet-ink);
}
.row.on {
  background: var(--violet-wash-strong);
}
.row.on::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 3px;
  background: var(--violet-ink);
}
.check svg {
  width: 20px;
  height: 20px;
  display: block;
}
.check rect {
  fill: none;
  stroke: var(--ink-faint);
  stroke-width: 1.3;
}
.check path {
  fill: none;
  stroke: var(--violet-ink);
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  transition: stroke-dashoffset 0.28s var(--ease);
}
.on .check rect {
  stroke: var(--violet-ink);
}
.on .check path {
  stroke-dashoffset: 0;
}
.num {
  color: var(--ink-faint);
  font-size: 13px;
}
.head .num {
  font-family: var(--font-display);
}
.track {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.names {
  display: grid;
  min-width: 0;
  line-height: 1.35;
}
.name {
  font-size: 16px;
  color: var(--ink);
}
.artist,
.album {
  font-size: 13px;
  color: var(--ink-soft);
}
.album {
  color: var(--ink-faint);
}
.dur {
  font-size: 13px;
  color: var(--ink-soft);
}
.right {
  text-align: right;
}
.actions {
  opacity: 0;
  transition: opacity 0.2s var(--ease);
}
.row:hover .actions,
.row:focus-within .actions {
  opacity: 1;
}

@media (max-width: 1100px) {
  .table {
    --cols: 30px 34px minmax(200px, 1fr) 0 56px 70px 40px;
  }
  .table.no-platform {
    --cols: 30px 34px minmax(200px, 1fr) 0 56px 40px;
  }
  .album,
  .head span:nth-child(4) {
    visibility: hidden;
  }
}
</style>
