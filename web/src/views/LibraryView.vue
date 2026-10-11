<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { store, loadLibrary, toast, go } from '../store.js'
import { api } from '../api.js'
import { player, current, playList, toggle, coverOf } from '../player.js'
import { duration, bytes } from '../format.js'
import PageHeader from '../components/PageHeader.vue'
import CoverArt from '../components/CoverArt.vue'
import EmptyState from '../components/EmptyState.vue'
import InkLoader from '../components/InkLoader.vue'
import Icon from '../components/Icon.vue'
import PressFlower from '../components/PressFlower.vue'
import { openMenu } from '../shelf.js'
import { sendBack, askSendBack, startPicking, stopPicking, togglePick, openDuplicates } from '../sendback.js'

const lib = store.library
const SORTS = { recent: '最近寄达', artist: '按歌手', title: '按歌名', album: '按专辑' }

const tracks = computed(() => {
  const q = lib.filter.trim().toLowerCase()
  let list = q ? lib.tracks.filter((t) => `${t.title} ${t.artist} ${t.album}`.toLowerCase().includes(q)) : lib.tracks.slice()
  const by = (k) => (a, b) => (a[k] || '').localeCompare(b[k] || '', 'zh-Hans-CN')
  if (lib.sort === 'artist') list.sort((a, b) => by('artist')(a, b) || by('album')(a, b) || by('title')(a, b))
  else if (lib.sort === 'title') list.sort(by('title'))
  else if (lib.sort === 'album') list.sort((a, b) => by('album')(a, b) || by('title')(a, b))
  return list
})
const totalSize = computed(() => lib.tracks.reduce((sum, t) => sum + (t.size || 0), 0))

const picked = computed(() => lib.tracks.filter((t) => sendBack.picked.has(t.id)))
const allPicked = computed(() => tracks.value.length > 0 && tracks.value.every((t) => sendBack.picked.has(t.id)))
function pickAll() {
  sendBack.picked = allPicked.value ? new Set() : new Set(tracks.value.map((t) => t.id))
}

function play(index) {
  const track = tracks.value[index]
  if (sendBack.picking) return togglePick(track.id)
  if (current.value?.id === track.id) toggle()
  else playList(tracks.value, index)
}

function playAll(shuffle = false) {
  if (!tracks.value.length) return
  player.mode = shuffle ? 'shuffle' : player.mode === 'shuffle' ? 'order' : player.mode
  playList(tracks.value, shuffle ? Math.floor(Math.random() * tracks.value.length) : 0)
}

async function reveal(target) {
  try {
    await api.reveal(target)
  } catch (error) {
    toast(error.message, 'error')
  }
}

onMounted(() => {
  if (!lib.loaded || lib.stale) loadLibrary()
})
onBeforeUnmount(stopPicking)
// Refresh when the shelf is out of date: on arrival, or while the page is already open.
watch(
  () => [store.view, lib.stale],
  ([view, stale]) => view === 'library' && stale && loadLibrary(),
)
</script>

<template>
  <div>
    <PageHeader eyebrow="Music · The Letter Box" title="书信匣" script="memories"
      :subtitle="lib.loaded ? `${lib.tracks.length} 封信 · ${bytes(totalSize)} · 都已妥善收好` : '本地曲库'">
      <button class="btn small" :disabled="!tracks.length" @click="playAll(false)"><Icon name="play" :size="15" />依次聆听</button>
      <button class="btn small" :disabled="!tracks.length" @click="playAll(true)"><Icon name="shuffle" :size="15" />随手翻阅</button>
    </PageHeader>

    <div class="toolbar">
      <label class="filter">
        <Icon name="search" :size="16" />
        <input v-model="lib.filter" class="field" placeholder="找一封信：歌名、歌手或专辑" @keydown.esc="lib.filter = ''" />
      </label>
      <div class="sorts">
        <button v-for="(label, key) in SORTS" :key="key" class="sort" :class="{ on: lib.sort === key }" @click="lib.sort = key">
          {{ label }}
        </button>
      </div>
      <div class="tools">
        <button class="icon-btn" :class="{ on: sendBack.picking }" title="整理：勾选几首，一起夹进信札或退回"
          :disabled="!lib.tracks.length" @click="sendBack.picking ? stopPicking() : startPicking()"><Icon name="tidy" :size="18" /></button>
        <button class="icon-btn" title="找出重复的歌" :disabled="lib.tracks.length < 2" @click="openDuplicates"><Icon name="twins" :size="18" /></button>
        <span class="divider" aria-hidden="true" />
        <button class="icon-btn" :class="{ on: lib.mode === 'grid' }" title="卡片" @click="lib.mode = 'grid'"><Icon name="grid" :size="18" /></button>
        <button class="icon-btn" :class="{ on: lib.mode === 'list' }" title="列表" @click="lib.mode = 'list'"><Icon name="list" :size="18" /></button>
        <button class="icon-btn" title="重新整理书信匣" :disabled="lib.loading" @click="loadLibrary(true)">
          <Icon name="refresh" :size="18" :class="{ spin: lib.loading }" />
        </button>
        <button class="icon-btn" title="打开下载文件夹" @click="reveal({ folder: 'out' })"><Icon name="folder" :size="18" /></button>
      </div>
    </div>

    <InkLoader v-if="lib.loading && !lib.loaded" label="正在整理书信匣…" script="sorting" />
    <EmptyState v-else-if="lib.error" script="sorry" title="书信匣打不开" :hint="lib.error" />
    <EmptyState v-else-if="lib.loaded && !lib.tracks.length" script="empty" title="书信匣还是空的"
      :hint="`下载的歌会收在 ${store.settings?.out_dir_abs || '下载目录'}，也可以在设置里添加其他音乐文件夹。`">
      <button class="btn" @click="go('search')">去寻找第一首歌</button>
    </EmptyState>
    <p v-else-if="lib.loaded && !tracks.length" class="no-match faint">没有符合「{{ lib.filter }}」的信</p>

    <div v-else-if="lib.mode === 'grid'" class="grid">
      <div v-for="(t, i) in tracks" :key="t.id" class="card-wrap" :class="{ picking: sendBack.picking, picked: sendBack.picked.has(t.id) }">
      <button class="card" :class="{ playing: current?.id === t.id }" :aria-pressed="sendBack.picking ? sendBack.picked.has(t.id) : undefined"
        :style="{ '--tilt': ((i * 37) % 7) / 3 - 1 + 'deg' }" @click="play(i)">
        <span class="frame">
          <CoverArt :src="coverOf(t)" size="100%" :seed="t.title" :radius="2" />
          <span v-if="sendBack.picking" class="tick" aria-hidden="true"><Icon name="check" :size="15" /></span>
          <span v-else class="overlay">
            <Icon :name="current?.id === t.id && player.playing ? 'pause' : 'play'" :size="26" />
          </span>
          <span v-if="current?.id === t.id && player.playing" class="bars" aria-hidden="true"><i /><i /><i /></span>
        </span>
        <span class="card-title title-text ellipsis">{{ t.title }}</span>
        <span class="card-artist ellipsis">{{ t.artist || '佚名' }}</span>
      </button>
      <span v-if="!sendBack.picking" class="card-tools">
        <PressFlower :track="t" :size="15" />
        <button class="icon-btn tool" title="夹进信札（加入歌单）" @click="openMenu([t], $event)"><Icon name="bundle" :size="15" /></button>
        <button class="icon-btn tool back" title="退回（移进回收站）" @click="askSendBack([t])"><Icon name="sendback" :size="15" /></button>
      </span>
      </div>
    </div>

    <div v-else class="list">
      <div v-for="(t, i) in tracks" :key="t.id" class="lrow" :class="{ playing: current?.id === t.id, picked: sendBack.picked.has(t.id) }" tabindex="0"
        @click="sendBack.picking && togglePick(t.id)" @dblclick="!sendBack.picking && play(i)" @keydown.enter="play(i)">
        <span v-if="sendBack.picking" class="check" :class="{ on: sendBack.picked.has(t.id) }" role="checkbox"
          :aria-checked="sendBack.picked.has(t.id)" aria-label="勾选"><Icon name="check" :size="13" /></span>
        <button v-else class="icon-btn play" :title="current?.id === t.id && player.playing ? '暂停' : '播放'" @click="play(i)">
          <Icon :name="current?.id === t.id && player.playing ? 'pause' : 'play'" :size="16" />
        </button>
        <CoverArt :src="coverOf(t)" :size="38" :seed="t.title" />
        <span class="names">
          <span class="title-text ellipsis">{{ t.title }}</span>
          <span class="soft ellipsis small">{{ t.artist || '佚名' }}</span>
        </span>
        <span class="faint ellipsis small">{{ t.album || '—' }}</span>
        <span class="badges">
          <span class="fmt mono">{{ t.ext.toUpperCase() }}</span>
          <span v-if="t.has_lyrics" class="fmt lyr" title="有歌词">词</span>
        </span>
        <span class="mono soft small right">{{ duration(t.duration) }}</span>
        <PressFlower :track="t" :size="15" />
        <button class="icon-btn" title="夹进信札（加入歌单）" @click.stop="openMenu([t], $event)"><Icon name="bundle" :size="16" /></button>
        <button class="icon-btn" title="在文件夹中显示" @click.stop="reveal({ track: t.id })"><Icon name="folder" :size="16" /></button>
        <button class="icon-btn back" title="退回（移进回收站）" @click.stop="askSendBack([t])"><Icon name="sendback" :size="16" /></button>
      </div>
    </div>

    <!-- 整理: a slip that rises from the bottom while songs are being picked -->
    <Transition name="rise">
      <div v-if="sendBack.picking" class="pickbar sheet" role="toolbar" aria-label="整理">
        <span class="count title-cn">{{ picked.length ? `勾了 ${picked.length} 首` : '点歌勾选' }}</span>
        <button class="btn small ghost" @click="pickAll">{{ allPicked ? '全不选' : '全选这一页' }}</button>
        <span class="grow" />
        <button class="btn small" :disabled="!picked.length" @click="openMenu(picked, $event)"><Icon name="bundle" :size="14" />夹进信札</button>
        <button class="btn small wax red" :disabled="!picked.length" @click="askSendBack(picked)">
          <Icon name="sendback" :size="14" />{{ picked.length ? `退回 ${picked.length} 首` : '退回' }}
        </button>
        <button class="btn small ghost" @click="stopPicking">完成</button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 22px;
  margin-bottom: 22px;
}
.filter {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 300px;
  color: var(--ink-faint);
}
.filter .field {
  flex: 1;
  height: 36px;
}
.sorts {
  display: flex;
  gap: 4px;
}
.sort {
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13.5px;
  color: var(--ink-faint);
  transition: all 0.2s var(--ease);
}
.sort:hover {
  color: var(--ink);
}
.sort.on {
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.tools {
  margin-left: auto;
  display: flex;
  gap: 2px;
}
.icon-btn.on {
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.no-match {
  text-align: center;
  padding: 48px 0;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(156px, 1fr));
  gap: 30px 26px;
  padding: 4px 4px 24px;
}
.card {
  display: grid;
  gap: 3px;
  text-align: left;
  min-width: 0;
}
.frame {
  position: relative;
  display: block;
  padding: 7px 7px 7px;
  background: var(--sheet-raised);
  box-shadow: var(--shadow-sheet);
  transform: rotate(var(--tilt));
  transition: transform 0.35s var(--ease), box-shadow 0.35s var(--ease);
  margin-bottom: 9px;
}
.card:hover .frame,
.card:focus-visible .frame,
.card.playing .frame {
  transform: rotate(0) translateY(-4px);
  box-shadow: var(--shadow-lift);
}
.overlay {
  position: absolute;
  inset: 7px;
  display: grid;
  place-items: center;
  color: #fff;
  background: rgba(30, 20, 45, 0.38);
  opacity: 0;
  transition: opacity 0.25s var(--ease);
}
.card:hover .overlay {
  opacity: 1;
}
.bars {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 14px;
  padding: 3px 4px;
  border-radius: 3px;
  background: rgba(20, 14, 30, 0.6);
}
.bars i {
  width: 3px;
  background: #f1e3c4;
  animation: bar 0.9s ease-in-out infinite;
}
.bars i:nth-child(2) {
  animation-delay: -0.3s;
}
.bars i:nth-child(3) {
  animation-delay: -0.6s;
}
@keyframes bar {
  0%,
  100% {
    height: 3px;
  }
  50% {
    height: 11px;
  }
}
.card-title {
  font-size: 15.5px;
  color: var(--ink);
  padding: 0 4px;
}
.card.playing .card-title {
  color: var(--violet-ink);
}
.card-artist {
  font-size: 13px;
  color: var(--ink-faint);
  padding: 0 4px;
}

.list {
  border-top: 1px solid var(--rule);
}
.lrow {
  display: grid;
  grid-template-columns: 36px 38px minmax(200px, 1.4fr) minmax(120px, 1fr) 76px 56px 30px 32px 36px 36px;
  align-items: center;
  gap: 12px;
  height: 56px;
  padding: 0 10px;
  border-bottom: 1px dashed var(--rule);
  outline: none;
}
.lrow:hover,
.lrow:focus-visible {
  background: var(--violet-wash);
}
.lrow.playing {
  background: var(--violet-wash-strong);
}
.lrow.playing .names .title-cn {
  color: var(--violet-ink);
}
.names {
  display: grid;
  min-width: 0;
  line-height: 1.35;
}
.small {
  font-size: 13px;
}
.right {
  text-align: right;
}
.badges {
  display: flex;
  gap: 4px;
}
.fmt {
  font-size: 11px;
  padding: 0 5px;
  border: 1px solid var(--rule-strong);
  border-radius: 3px;
  color: var(--ink-soft);
  line-height: 18px;
}
.lyr {
  font-family: var(--font-title);
  color: var(--violet-ink);
  border-color: var(--violet-wash-strong);
}
.divider {
  width: 1px;
  height: 18px;
  margin: 0 6px;
  align-self: center;
  background: var(--rule-strong);
}
/* The send-back button is the one red thing among the tools. */
.icon-btn.back {
  color: color-mix(in srgb, var(--danger) 80%, var(--ink-soft));
}
.icon-btn.back:hover {
  color: var(--danger);
  background: var(--danger-wash);
}
.lrow .icon-btn.back {
  opacity: 0;
}
.lrow:hover .icon-btn.back,
.lrow:focus-within .icon-btn.back {
  opacity: 1;
}
/* 整理 */
.tick {
  position: absolute;
  top: 12px;
  left: 12px;
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1.5px solid #fff;
  background: rgba(30, 20, 45, 0.3);
  color: transparent;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
  transition: all 0.2s var(--ease);
}
.picked .tick {
  border-color: var(--violet-ink);
  background: var(--violet-ink);
  color: #fff;
}
.picking .card .frame {
  transform: rotate(0);
}
.picked .card .frame {
  box-shadow: 0 0 0 2px var(--violet-ink), var(--shadow-lift);
  transform: translateY(-3px);
}
.check {
  justify-self: center;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 5px;
  border: 1.5px solid var(--rule-strong);
  color: transparent;
  transition: all 0.2s var(--ease);
}
.check.on {
  border-color: var(--violet-ink);
  background: var(--violet-ink);
  color: #fff;
}
.lrow.picked {
  background: var(--violet-wash);
}
.pickbar {
  position: sticky;
  bottom: 14px;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 8px;
  width: min(720px, 100%);
  margin: 10px auto 0;
  padding: 10px 14px 10px 20px;
  border-radius: 999px;
  box-shadow: var(--shadow-lift);
}
.pickbar .count {
  font-size: 15px;
  min-width: 80px;
}
.pickbar .grow {
  flex: 1;
}
.rise-enter-from,
.rise-leave-to {
  opacity: 0;
  transform: translateY(16px);
}
.rise-enter-active,
.rise-leave-active {
  transition: all 0.3s var(--ease);
}
/* Tools sit on the corner of the cover. A pressed song keeps its flower there for good. */
.card-wrap {
  position: relative;
  min-width: 0;
}
.card-wrap > .card {
  width: 100%;
}
.card-tools {
  position: absolute;
  top: -4px;
  right: -6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.card-tools > * {
  background: var(--sheet-raised);
  box-shadow: 0 2px 6px -2px rgba(40, 20, 60, 0.35);
  opacity: 0;
  transform: scale(0.85);
  transition: opacity 0.2s var(--ease), transform 0.25s var(--ease);
}
.card-tools .tool {
  width: 27px;
  height: 27px;
  border-radius: 50%;
}
.card-wrap:hover .card-tools > *,
.card-tools > :focus-visible,
.card-tools > .pressed {
  opacity: 1;
  transform: none;
}
</style>
