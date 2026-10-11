<script setup>
// 信札：压花集（收藏）和一束束信札（自己的歌单）。
// 架子上：压花集是一张标本纸，信札是缎带扎好的信。点开一束，缎带解开，信一封封摊开。
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { store, loadLibrary } from '../store.js'
import { shelf, RIBBONS, loadShelf, openBundle, closeBundle, openPressed, setNote, togglePress, removeLetters,
  reorderLetters, untieBundle, playLetters, addToBundle, openMenu } from '../shelf.js'
import { player, current, playList, toggle, coverOf } from '../player.js'
import { duration, monthDay } from '../format.js'
import PageHeader from '../components/PageHeader.vue'
import BundleCard from '../components/BundleCard.vue'
import PressFlower from '../components/PressFlower.vue'
import Bloom from '../components/Bloom.vue'
import CoverArt from '../components/CoverArt.vue'
import InkLoader from '../components/InkLoader.vue'
import Icon from '../components/Icon.vue'

const detail = computed(() => shelf.detail)
const ribbon = computed(() => (RIBBONS[detail.value?.ribbon] || RIBBONS.violet).hue)
const letters = ref([]) // local copy, so dragging can reorder before saving
watch(() => shelf.detail?.letters, (list) => (letters.value = list ? [...list] : []), { immediate: true })
const pressedHere = computed(() => shelf.pressed.filter((p) => p.state === 'here'))
// Flowers on the herbarium sheet on the shelf: a few, scattered.
// Four at most, kept clear of the label in the lower right corner.
const specimens = computed(() => shelf.pressed.slice(0, 4))
const SPOTS = [
  { x: 9, y: 20, turn: -16, hue: 0 },
  { x: 50, y: 12, turn: 12, hue: -18 },
  { x: 26, y: 52, turn: -4, hue: 22 },
  { x: 60, y: 40, turn: 20, hue: -30 },
  { x: 8, y: 70, turn: 8, hue: 12 },
]

// ------------------------------------------------------------ playing

function playFrom(letter) {
  const here = letters.value.filter((l) => l.state === 'here')
  const index = here.findIndex((l) => l.id === letter.id)
  if (index < 0) return
  if (current.value?.id === letter.track_id) toggle()
  else playList(here.map((l) => l.track), index)
}

function playPressed(item) {
  const here = pressedHere.value
  const index = here.findIndex((p) => p.track_id === item.track_id)
  if (index < 0) return
  if (current.value?.id === item.track_id) toggle()
  else playList(here.map((p) => p.track), index)
}

const playPressedAll = (shuffle) => playLetters(pressedHere.value.map((p) => ({ ...p, state: 'here' })), shuffle)

// ------------------------------------------------------------ untying a bundle

const untying = ref(false)
watch(() => shelf.open, (id) => {
  if (!id || id === 'pressed') return
  untying.value = true
  setTimeout(() => (untying.value = false), 900)
})

// ------------------------------------------------------------ dragging letters into a new order

let dragFrom = -1
function dragStart(index, event) {
  dragFrom = index
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(index))
}
function dragOver(index) {
  if (dragFrom < 0 || dragFrom === index) return
  const list = [...letters.value]
  const [moved] = list.splice(dragFrom, 1)
  list.splice(index, 0, moved)
  letters.value = list
  dragFrom = index
}
function dragEnd() {
  if (dragFrom < 0) return
  dragFrom = -1
  const before = (detail.value?.letters || []).map((l) => l.id).join()
  const after = letters.value.map((l) => l.id)
  if (after.join() !== before) reorderLetters(detail.value, after)
}

// ------------------------------------------------------------ tucking in songs from the letter box

const seek = ref('')
const inside = computed(() => new Set(letters.value.map((l) => l.track_id).filter(Boolean)))
const matches = computed(() => {
  const q = seek.value.trim().toLowerCase()
  if (!q) return []
  return store.library.tracks
    .filter((t) => !inside.value.has(t.id) && `${t.title} ${t.artist} ${t.album}`.toLowerCase().includes(q))
    .slice(0, 8)
})
async function tuck(track, event) {
  await addToBundle(detail.value, { trackIds: [track.id] }, event.currentTarget)
}

// ------------------------------------------------------------ pressed-flower notes

const noteDraft = ref({})
async function saveNote(item) {
  const value = (noteDraft.value[item.track_id] ?? item.note).trim()
  if (value !== item.note) await setNote(item.track_id, value)
  delete noteDraft.value[item.track_id]
}
watch(() => [shelf.open, shelf.focusNote, shelf.pressed.length], async () => {
  if (shelf.open !== 'pressed' || !shelf.focusNote) return
  await nextTick()
  document.querySelector(`[data-note="${shelf.focusNote}"]`)?.focus()
  shelf.focusNote = ''
})

const pressedDate = (item) => monthDay(item.day)
const editBundle = () => (shelf.editing = { id: detail.value.id, name: detail.value.name, epigraph: detail.value.epigraph,
  ribbon: detail.value.ribbon, revision: detail.value.revision, covers: detail.value.covers })

onMounted(() => {
  if (!shelf.loaded) loadShelf()
  if (!store.library.loaded) loadLibrary()
})
</script>

<template>
  <div class="shelf-view">
    <PageHeader eyebrow="Music · Keepsakes" title="信札" script="keepsakes"
      subtitle="喜欢的歌，压成一朵花；想放在一起听的歌，扎成一束信札。">
      <button class="btn wax" @click="shelf.editing = {}"><Icon name="ribbon" :size="16" />扎一束新信札</button>
    </PageHeader>

    <!-- The shelf -->
    <template v-if="!shelf.open">
      <InkLoader v-if="!shelf.loaded" label="正在把信札摆上架…" script="keepsakes" />
      <div v-else class="shelf-grid">
        <button class="slot herbarium" title="压花集：收藏的歌" @click="openPressed()">
          <span class="sheet-paper">
            <span class="tape" />
            <span class="herb-title title-cn">压花集</span>
            <span class="herb-sub mono">{{ shelf.pressed.length ? `${shelf.pressed.length} 朵` : 'Herbarium' }}</span>
            <span v-for="(p, i) in specimens" :key="p.track_id" class="specimen"
              :style="{ left: SPOTS[i].x + '%', top: SPOTS[i].y + '%' }">
              <Bloom :size="34" :hue="SPOTS[i].hue" :turn="SPOTS[i].turn" />
              <span class="label">{{ p.title }}</span>
            </span>
            <span v-if="!shelf.pressed.length" class="herb-empty">
              <Bloom :size="40" :turn="-10" />
              <span>在书信匣或播放条上点那朵小花，喜欢的歌就会压进来。</span>
            </span>
          </span>
          <span class="caption">
            <span class="name title-text">压花集</span>
            <span class="meta">收藏的歌{{ shelf.pressed.length ? ` · ${shelf.pressed.length} 首` : '' }}</span>
          </span>
        </button>

        <button v-for="(b, i) in shelf.bundles" :key="b.id" class="slot" :style="{ '--i': i }" @click="openBundle(b.id)">
          <BundleCard :bundle="b" :tilt="((i * 37) % 7) / 2.5 - 1.2" />
        </button>

        <button class="slot tie-new" @click="shelf.editing = {}">
          <span class="dashed">
            <Icon name="ribbon" :size="30" />
            <span class="title-cn">扎一束新信札</span>
            <span class="faint small">{{ shelf.bundles.length ? '给另一种心情一束信' : '你自己的第一份歌单' }}</span>
          </span>
        </button>
      </div>
    </template>

    <!-- 压花集 -->
    <template v-else-if="shelf.open === 'pressed'">
      <div class="detail-head">
        <button class="btn small ghost" @click="closeBundle"><Icon name="chevron" :size="14" class="back" />回到信札架</button>
      </div>
      <header class="opened herb-head">
        <Bloom :size="54" :turn="-18" class="head-bloom" />
        <div class="opened-text">
          <h2 class="title-cn">压花集</h2>
          <p class="epigraph">喜欢的歌，像一朵花一样压在书页之间。</p>
          <p class="meta mono">{{ shelf.pressed.length }} 朵</p>
        </div>
        <div class="opened-actions">
          <button class="btn small wax" :disabled="!pressedHere.length" @click="playPressedAll(false)"><Icon name="play" :size="14" />从头读起</button>
          <button class="btn small" :disabled="!pressedHere.length" @click="playPressedAll(true)"><Icon name="shuffle" :size="14" />随手抽一封</button>
        </div>
      </header>

      <p v-if="!shelf.pressed.length" class="empty faint">还没有压过花。在书信匣的歌上、或者播放条上点那朵小花，就能把喜欢的歌压进来。</p>
      <div class="specimens">
        <article v-for="(p, i) in shelf.pressed" :key="p.track_id" class="card-specimen" :class="[p.state, { playing: current?.id === p.track_id }]"
          :style="{ '--i': i }">
          <span class="tape" />
          <Bloom class="bloom" :size="46" :hue="SPOTS[i % 5].hue" :turn="SPOTS[i % 5].turn" />
          <button class="cover" :disabled="p.state !== 'here'" :title="p.state === 'here' ? '播放' : '书信匣里找不到这首歌了'" @click="playPressed(p)">
            <CoverArt :src="p.state === 'here' ? coverOf(p.track) : ''" :size="56" :seed="p.title" :radius="2" />
            <span v-if="p.state === 'here'" class="play-hint"><Icon :name="current?.id === p.track_id && player.playing ? 'pause' : 'play'" :size="18" /></span>
          </button>
          <div class="spec-text">
            <p class="title-text spec-title">{{ p.title }}</p>
            <p class="faint spec-artist">{{ p.artist || '佚名' }}</p>
            <p class="spec-date mono">{{ pressedDate(p) }} 压<span v-if="p.state === 'lost'" class="lost"> · 遗失</span></p>
          </div>
          <input class="note" :data-note="p.track_id" :value="noteDraft[p.track_id] ?? p.note" maxlength="120"
            placeholder="写一句压花笺：为什么喜欢它" @input="noteDraft[p.track_id] = $event.target.value"
            @keydown.enter="$event.target.blur()" @blur="saveNote(p)" />
          <div class="spec-actions">
            <button v-if="p.state === 'here'" class="icon-btn" title="夹进信札" @click="openMenu([p.track], $event)"><Icon name="bundle" :size="16" /></button>
            <button class="icon-btn" title="从书页间取出来（取消收藏）" @click="togglePress({ id: p.track_id, title: p.title })"><Icon name="close" :size="15" /></button>
          </div>
        </article>
      </div>
    </template>

    <!-- One bundle, untied -->
    <template v-else>
      <div class="detail-head">
        <button class="btn small ghost" @click="closeBundle"><Icon name="chevron" :size="14" class="back" />回到信札架</button>
      </div>
      <InkLoader v-if="!detail" label="正在解开缎带…" script="untying" />
      <template v-else>
        <header class="opened" :class="{ untying }" :style="{ '--ribbon': ribbon }">
          <span class="ribbon-strip" />
          <svg class="loose-bow" viewBox="0 0 60 44" aria-hidden="true">
            <path d="M30 20 C 20 4, 4 6, 6 18 C 8 28, 22 26, 30 20 Z" />
            <path d="M30 20 C 40 4, 56 6, 54 18 C 52 28, 38 26, 30 20 Z" />
            <path d="M28 22 L 18 42 L 24 39 L 27 43 L 31 23 Z" class="tail" />
            <path d="M32 22 L 42 42 L 36 39 L 33 43 L 29 23 Z" class="tail" />
            <ellipse cx="30" cy="20.5" rx="4.5" ry="4" />
          </svg>
          <div class="opened-text">
            <h2 class="title-cn">{{ detail.name }}</h2>
            <p v-if="detail.epigraph" class="epigraph">{{ detail.epigraph }}</p>
            <p class="meta mono">{{ detail.count }} 封<template v-if="detail.duration"> · {{ duration(detail.duration) }}</template>
              <span v-if="detail.pending" class="pending"> · {{ detail.pending }} 封在路上</span>
              <span v-if="detail.lost" class="lost"> · {{ detail.lost }} 封遗失</span></p>
          </div>
          <div class="opened-actions">
            <button class="btn small wax" :disabled="!detail.here" @click="playLetters(letters)"><Icon name="play" :size="14" />从头读起</button>
            <button class="btn small" :disabled="!detail.here" @click="playLetters(letters, true)"><Icon name="shuffle" :size="14" />随手抽一封</button>
            <button class="btn small ghost" title="改名字、题记或缎带" @click="editBundle"><Icon name="ribbon" :size="14" />重新扎</button>
            <button class="btn small ghost danger" title="拆散这束信札（歌还在书信匣里）" @click="untieBundle(detail)"><Icon name="trash" :size="14" />拆散</button>
          </div>
        </header>

        <label class="seek">
          <Icon name="plus" :size="16" />
          <input v-model="seek" class="field" placeholder="从书信匣里找一封夹进来：歌名、歌手或专辑" @keydown.esc="seek = ''" />
        </label>
        <div v-if="matches.length" class="matches">
          <button v-for="t in matches" :key="t.id" class="match" @click="tuck(t, $event)">
            <CoverArt :src="coverOf(t)" :size="28" :seed="t.title" />
            <span class="ellipsis"><span class="title-text">{{ t.title }}</span><span class="faint"> · {{ t.artist || '佚名' }}</span></span>
            <span class="tuck-label"><Icon name="envelope" :size="13" />夹进来</span>
          </button>
        </div>
        <p v-else-if="seek.trim()" class="faint small no-match">书信匣里没有别的「{{ seek }}」了</p>

        <p v-if="!letters.length" class="empty faint">这束信札还是空的。用上面的输入框找几首歌，或者在书信匣里点歌旁边的缎带图标。</p>
        <TransitionGroup tag="ol" name="letter" class="letters" :class="{ fanning: untying }">
          <li v-for="(l, i) in letters" :key="l.id" class="letter" :class="[l.state, { playing: current?.id === l.track_id }]"
            :style="{ '--i': i }" draggable="true" @dragstart="dragStart(i, $event)" @dragover.prevent="dragOver(i)"
            @dragend="dragEnd" @drop.prevent="dragEnd" @dblclick="playFrom(l)">
            <span class="grip" title="拖动调整顺序" aria-hidden="true">⋮⋮</span>
            <span class="no mono">{{ String(i + 1).padStart(2, '0') }}</span>
            <button class="cover" :disabled="l.state !== 'here'" :title="l.state === 'here' ? '播放' : ''" @click="playFrom(l)">
              <CoverArt :src="l.state === 'here' ? coverOf(l.track) : ''" :size="38" :seed="l.title" />
              <span v-if="l.state === 'here'" class="play-hint"><Icon :name="current?.id === l.track_id && player.playing ? 'pause' : 'play'" :size="15" /></span>
            </button>
            <span class="names">
              <span class="title-text ellipsis">{{ l.title }}</span>
              <span class="faint small ellipsis">{{ l.artist || '佚名' }}<template v-if="l.album"> · {{ l.album }}</template></span>
            </span>
            <span v-if="l.state === 'pending'" class="state pending" title="下载完成、寄进书信匣后会自动收进来">在路上</span>
            <span v-else-if="l.state === 'lost'" class="state lost" title="书信匣里找不到这个文件了：被挪走或删除了？">遗失</span>
            <span v-else class="mono faint small">{{ duration(l.track?.duration) }}</span>
            <PressFlower v-if="l.state === 'here'" :track="l.track" :size="16" />
            <span v-else />
            <button class="icon-btn pull" title="从这束信札里抽出来" @click="removeLetters(detail, [l])"><Icon name="close" :size="14" /></button>
          </li>
        </TransitionGroup>
      </template>
    </template>
  </div>
</template>

<style scoped>
.shelf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 38px 32px;
  padding: 10px 6px 30px;
}
.slot {
  display: block;
  min-width: 0;
  text-align: left;
  animation: shelve 0.6s cubic-bezier(0.2, 0.85, 0.3, 1.1) backwards;
  animation-delay: calc(var(--i, 0) * 60ms + 60ms);
}
@keyframes shelve {
  from {
    opacity: 0;
    transform: translateY(16px) rotate(-2deg);
  }
}
/* ---- the herbarium sheet */
.herbarium {
  display: grid;
  gap: 12px;
  animation-delay: 0s;
}
.sheet-paper {
  position: relative;
  display: block;
  aspect-ratio: 16 / 10.5;
  background:
    radial-gradient(120% 90% at 30% 20%, rgba(255, 255, 255, 0.5), transparent 60%),
    linear-gradient(170deg, #f7f0dc, #ece0c2);
  border: 1px solid var(--rule-strong);
  box-shadow: var(--shadow-sheet);
  transform: rotate(1.2deg);
  transition: transform 0.45s var(--ease), box-shadow 0.45s var(--ease);
  overflow: hidden;
}
:root[data-theme='dark'] .sheet-paper {
  background: linear-gradient(170deg, #3a3245, #2c2636);
}
.herbarium:hover .sheet-paper {
  transform: rotate(0deg) translateY(-4px);
  box-shadow: var(--shadow-lift);
}
.tape {
  position: absolute;
  top: -6px;
  left: 50%;
  width: 70px;
  height: 18px;
  margin-left: -35px;
  background: rgba(214, 196, 150, 0.55);
  transform: rotate(-3deg);
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.06);
}
.herb-title {
  position: absolute;
  right: 12px;
  bottom: 10px;
  font-size: 15px;
  letter-spacing: 0.3em;
  color: color-mix(in srgb, var(--ink) 70%, transparent);
}
.herb-sub {
  position: absolute;
  right: 12px;
  bottom: 30px;
  font-size: 10.5px;
  color: var(--ink-faint);
}
.specimen {
  position: absolute;
  display: grid;
  justify-items: center;
  gap: 2px;
  max-width: 30%;
  transition: transform 0.5s var(--ease);
}
.herbarium:hover .specimen:nth-child(odd) {
  transform: rotate(-6deg);
}
.herbarium:hover .specimen:nth-child(even) {
  transform: rotate(5deg);
}
.specimen .label {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-body);
  font-size: 10.5px;
  color: color-mix(in srgb, var(--ink) 70%, transparent);
  border-top: 1px solid rgba(120, 100, 70, 0.3);
  padding-top: 1px;
}
.herb-empty {
  position: absolute;
  inset: 20% 16% 26%;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 8px;
  text-align: center;
  font-size: 12px;
  color: var(--ink-faint);
}
.caption {
  display: grid;
  gap: 2px;
  padding: 0 4px;
}
.caption .name {
  font-size: 16px;
  color: var(--ink);
}
.caption .meta {
  font-size: 11.5px;
  color: var(--ink-faint);
}
/* ---- tie a new one */
.tie-new .dashed {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 6px;
  aspect-ratio: 16 / 10.5;
  border: 1.5px dashed var(--rule-strong);
  border-radius: 6px;
  color: var(--ink-faint);
  transition: color 0.25s var(--ease), border-color 0.25s var(--ease), background 0.25s var(--ease);
}
.tie-new:hover .dashed {
  color: var(--violet-ink);
  border-color: var(--violet-ink);
  background: var(--violet-wash);
}
.tie-new .title-cn {
  font-size: 15px;
  color: inherit;
}
.small {
  font-size: 12.5px;
}
/* ---- an opened bundle / the herbarium */
.detail-head {
  margin: -6px 0 14px;
}
.back {
  transform: scaleX(-1);
}
.opened {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 22px;
  padding: 22px 24px 22px 34px;
  margin-bottom: 18px;
  background: var(--sheet);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sheet);
  overflow: hidden;
}
.herb-head {
  padding-left: 24px;
}
.ribbon-strip {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 10px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.2), transparent 40%, rgba(0, 0, 0, 0.15)), var(--ribbon);
}
.loose-bow {
  width: 58px;
  fill: var(--ribbon);
  filter: drop-shadow(0 2px 2px rgba(30, 10, 40, 0.3));
  overflow: visible;
}
.loose-bow .tail {
  filter: brightness(0.88);
}
/* Opening a bundle: the bow loosens and slips off, the ribbon slides back to the edge. */
.untying .loose-bow {
  animation: untie 0.9s cubic-bezier(0.4, 0, 0.3, 1);
}
.untying .ribbon-strip {
  animation: slide-ribbon 0.9s var(--ease);
}
@keyframes untie {
  0% {
    transform: scale(1.25) rotate(0deg);
  }
  35% {
    transform: scale(1.35, 0.9) rotate(-10deg);
  }
  100% {
    transform: none;
  }
}
@keyframes slide-ribbon {
  from {
    transform: translateX(120px);
    width: 40px;
  }
}
.opened-text {
  min-width: 0;
}
.opened-text h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 400;
}
.opened-text p {
  margin: 4px 0 0;
}
.epigraph {
  font-style: italic;
  color: var(--ink-soft);
  font-size: 14px;
}
.meta {
  font-size: 12px;
  color: var(--ink-faint);
}
.pending {
  color: var(--gold);
}
.lost {
  color: var(--danger);
}
.opened-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  max-width: 320px;
}
.danger:hover {
  color: var(--danger);
}
.head-bloom {
  margin: -6px 0;
}
/* ---- tucking songs in */
.seek {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px 6px 4px;
  color: var(--ink-faint);
  border-bottom: 1px solid var(--rule-strong);
}
.seek .field {
  flex: 1;
  border: 0;
  height: 36px;
}
.matches {
  display: grid;
  gap: 2px;
  margin: 8px 0 14px;
  padding: 6px;
  background: var(--sheet);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
}
.match {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 5px 8px;
  border-radius: var(--radius);
  text-align: left;
  font-size: 14px;
}
.match:hover {
  background: var(--violet-wash);
}
.tuck-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--violet-ink);
}
.no-match {
  margin: 8px 4px 14px;
}
.empty {
  margin: 24px 4px;
  line-height: 1.8;
}
/* ---- the letters, spread out */
.letters {
  position: relative;
  list-style: none;
  margin: 12px 0 30px;
  padding: 0;
  display: grid;
  gap: 4px;
}
.letter {
  display: grid;
  grid-template-columns: 14px 26px 38px minmax(0, 1fr) 70px 30px 30px;
  align-items: center;
  gap: 10px;
  padding: 6px 10px 6px 6px;
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--sheet) 70%, transparent);
  border: 1px solid transparent;
  transition: background 0.2s var(--ease), border-color 0.2s var(--ease);
}
.letter:hover {
  background: var(--sheet);
  border-color: var(--rule);
}
.letter.playing {
  border-color: color-mix(in srgb, var(--ribbon, var(--violet-ink)) 60%, transparent);
  background: var(--violet-wash);
}
.letters.fanning .letter {
  animation: fan 0.55s cubic-bezier(0.2, 0.85, 0.3, 1.1) backwards;
  animation-delay: calc(0.25s + min(var(--i), 12) * 40ms);
}
@keyframes fan {
  from {
    opacity: 0;
    transform: translateX(-24px) rotate(-1.5deg);
  }
}
.grip {
  font-size: 11px;
  letter-spacing: -2px;
  color: var(--ink-ghost);
  cursor: grab;
  opacity: 0;
}
.letter:hover .grip {
  opacity: 1;
}
.no {
  font-size: 12px;
  color: var(--ink-faint);
}
.cover {
  position: relative;
  display: block;
}
.play-hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  background: rgba(30, 20, 40, 0.35);
  opacity: 0;
  transition: opacity 0.2s var(--ease);
}
.cover:hover .play-hint,
.playing .play-hint {
  opacity: 1;
}
.names {
  display: grid;
  min-width: 0;
}
.names .title-text {
  font-size: 15px;
}
.letter.pending,
.letter.lost {
  opacity: 0.72;
}
.state {
  justify-self: start;
  padding: 0 7px;
  border-radius: 3px;
  font-size: 11.5px;
  border: 1px dashed currentColor;
}
.state.pending {
  color: var(--gold);
}
.state.lost {
  color: var(--danger);
}
.pull {
  opacity: 0;
}
.letter:hover .pull,
.pull:focus-visible {
  opacity: 1;
}
.letter-move {
  transition: transform 0.3s var(--ease);
}
.letter-enter-active,
.letter-leave-active {
  transition: opacity 0.35s var(--ease), transform 0.35s var(--ease);
}
.letter-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.letter-leave-to {
  opacity: 0;
  transform: translateX(30px) rotate(1deg);
}
.letter-leave-active {
  position: absolute;
  width: 100%;
}
/* ---- the herbarium, opened */
.specimens {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 22px;
  padding-bottom: 30px;
}
.card-specimen {
  position: relative;
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  grid-template-areas: 'cover text actions' 'note note note';
  gap: 10px 14px;
  padding: 22px 16px 14px;
  background: linear-gradient(170deg, var(--sheet-raised), var(--sheet));
  border: 1px solid var(--rule);
  box-shadow: var(--shadow-sheet);
  animation: shelve 0.55s cubic-bezier(0.2, 0.85, 0.3, 1.1) backwards;
  animation-delay: calc(min(var(--i), 10) * 50ms);
}
.card-specimen.playing {
  border-color: var(--violet-ink);
}
.card-specimen .tape {
  width: 54px;
  margin-left: -27px;
  top: -7px;
}
.card-specimen .bloom {
  position: absolute;
  right: 12px;
  bottom: 40px;
  opacity: 0.9;
  pointer-events: none;
}
.card-specimen .cover {
  grid-area: cover;
}
.spec-text {
  grid-area: text;
  min-width: 0;
}
.spec-text p {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.spec-title {
  font-size: 15.5px;
}
.spec-artist {
  font-size: 12.5px;
}
.spec-date {
  margin-top: 4px !important;
  font-size: 11px;
  color: var(--gold);
}
.spec-actions {
  grid-area: actions;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.note {
  grid-area: note;
  width: 100%;
  border: 0;
  border-bottom: 1px dashed var(--rule-strong);
  background: transparent;
  font-family: var(--font-body);
  font-size: 13px;
  font-style: italic;
  color: var(--ink-soft);
  padding: 4px 2px;
}
.note:focus {
  outline: none;
  border-bottom-color: var(--violet-ink);
  font-style: normal;
}
.card-specimen.lost {
  opacity: 0.7;
}
@media (prefers-reduced-motion: reduce) {
  .slot,
  .card-specimen,
  .letters.fanning .letter,
  .untying .loose-bow,
  .untying .ribbon-strip {
    animation: none;
  }
}
@media (max-width: 980px) {
  .opened {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .opened-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
    max-width: none;
  }
}
</style>
