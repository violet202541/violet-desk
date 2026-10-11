<script setup>
// 信箱：Violet 寄来的信、你写的回信、寄往未来的信，以及每周的封存袋。
import { computed, onMounted, ref } from 'vue'
import { store, loadLetters, updateLetter } from '../store.js'
import { desk, loadReplies, startWriting } from '../desk.js'
import { hm, longDate, daysBetween, isoDate } from '../format.js'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import Nunkish from '../components/Nunkish.vue'
import MoodStamp from '../components/MoodStamp.vue'
import WaxSeal from '../components/WaxSeal.vue'
import SealImpression from '../components/SealImpression.vue'
import LetterEnvelope from '../components/LetterEnvelope.vue'
import { resolve, paperVars } from '../stationery.js'
import Icon from '../components/Icon.vue'
import CipherText from '../components/CipherText.vue'

const TABS = [
  { id: 'letters', label: '来信', hint: 'Violet 每天寄来的信' },
  { id: 'replies', label: '回信', hint: '你写的日记' },
  { id: 'future', label: '寄往未来', hint: '还在路上、或已经寄到的信' },
  { id: 'weeks', label: '封存袋', hint: '每周的回顾' },
  { id: 'starred', label: '收藏', hint: '' },
]
const tab = computed({
  get: () => (TABS.some((t) => t.id === store.letters.filter) ? store.letters.filter : 'letters'),
  set: (v) => (store.letters.filter = v),
})

// 遮信: the reply cards turn to Telsis script for anyone looking over your shoulder. Not remembered.
const veiled = ref(false)
const letters = computed(() => store.letters.list.filter((l) => tab.value === 'letters' || l.starred))
const replies = computed(() => desk.replies.filter((r) => r.recipient !== 'future' || !r.sealed_at))
const future = computed(() => desk.replies.filter((r) => r.recipient === 'future' && r.sealed_at))
const starredReplies = computed(() => desk.replies.filter((r) => r.starred))
const counts = computed(() => ({
  letters: store.letters.list.length,
  replies: replies.value.length,
  future: future.value.length,
  weeks: desk.weeks.length,
  starred: store.letters.list.filter((l) => l.starred).length + starredReplies.value.length,
}))

function read(letter) {
  store.letters.reading = letter
  if (!letter.opened) updateLetter(letter.date, { opened: true })
}

function openReply(r) {
  if (!r.sealed_at) return startWriting(r)
  if (r.state === 'travelling') return
  desk.reading = r
}

// How far a letter to the future has travelled: 0 when written, 1 on the day it arrives.
function travelled(r) {
  const total = daysBetween(r.date, r.deliver_on)
  if (total <= 0) return 1
  return Math.min(1, Math.max(0.03, daysBetween(r.date, isoDate()) / total))
}

function label(date) {
  const [y, m, d] = date.split('-').map(Number)
  return { day: String(d).padStart(2, '0'), month: `${y} · ${String(m).padStart(2, '0')}` }
}

onMounted(() => {
  if (!store.letters.loaded) loadLetters()
  loadReplies()
})
</script>

<template>
  <div>
    <PageHeader eyebrow="Chapter IV · The Mailbox" title="信箱" script="mailbox"
      subtitle="寄来的、寄出的，都收在这里。">
      <button v-if="tab === 'replies' || tab === 'starred'" class="btn small ghost" :class="{ on: veiled }"
        title="用泰尔西斯文字遮住回信的字迹，旁人看不懂" @click="veiled = !veiled">
        <Icon name="cover" :size="14" />{{ veiled ? '掀开' : '遮信' }}
      </button>
      <button class="btn small" @click="startWriting()"><Icon name="quill" :size="14" />写回信</button>
    </PageHeader>

    <div class="tabs" role="tablist">
      <button v-for="t in TABS" :key="t.id" class="chip" :class="{ on: tab === t.id }" role="tab" :aria-selected="tab === t.id"
        :title="t.hint" @click="tab = t.id">
        {{ t.label }}<span v-if="counts[t.id]" class="n mono">{{ counts[t.id] }}</span>
      </button>
    </div>

    <!-- Violet's letters -->
    <template v-if="tab === 'letters' || tab === 'starred'">
      <EmptyState v-if="store.letters.loaded && !letters.length && !(tab === 'starred' && starredReplies.length)" script="no letters"
        :title="tab === 'starred' ? '还没有收藏的信' : '信箱还是空的'" hint="每天第一次打开 Violet 时，会有一封新的信放在书桌上。" />
      <div class="letters">
        <button v-for="(l, i) in letters" :key="l.date" class="card" :class="{ unread: !l.opened, starred: l.starred }"
          :style="{ '--tilt': ((i * 29) % 5) / 2.5 - 1 + 'deg' }" @click="read(l)">
          <span class="stamp">
            <span class="day mono">{{ label(l.date).day }}</span>
            <span class="month mono">{{ label(l.date).month }}</span>
          </span>
          <span class="quote title-text">{{ l.quote.text }}</span>
          <span class="by faint">—— {{ l.quote.author }}</span>
          <span class="meta faint">
            <span>{{ l.weekday }}</span>
            <span v-if="l.songs.length">♪ {{ l.songs.length }} 首新歌</span>
            <span v-if="l.old">一封旧信</span>
          </span>
          <span v-if="!l.opened" class="new">未拆</span>
          <span v-if="l.starred" class="fav">★</span>
          <Nunkish class="corner" :text="l.date.slice(5).replace('-', '')" :size="9" />
        </button>
        <template v-if="tab === 'starred'">
          <button v-for="r in starredReplies" :key="r.id" class="card reply" @click="openReply(r)">
            <span class="stamp"><span class="day mono">{{ label(r.date).day }}</span><span class="month mono">{{ label(r.date).month }}</span></span>
            <CipherText class="body" :text="r.body" :veiled="veiled" :clamp="4" />
            <span class="meta faint"><span>你的回信</span></span>
            <span class="fav">★</span>
          </button>
        </template>
      </div>
    </template>

    <!-- The user's replies -->
    <template v-else-if="tab === 'replies'">
      <EmptyState v-if="desk.repliesLoaded && !replies.length" script="write" title="还没有写过回信"
        hint="在书桌上点「动笔」，给 Violet 写第一封。">
        <button class="btn wax" @click="startWriting()">去写第一封</button>
      </EmptyState>
      <div class="letters">
        <button v-for="(r, i) in replies" :key="r.id" class="card reply letter-sheet daylight" :class="{ draft: !r.sealed_at }"
          :style="{ '--tilt': ((i * 31) % 5) / 2.5 - 1 + 'deg', ...paperVars(resolve(r.stationery)) }" @click="openReply(r)">
          <span class="stamp"><span class="day mono">{{ label(r.date).day }}</span><span class="month mono">{{ label(r.date).month }}</span></span>
          <CipherText class="body" :text="r.body || '（空白的信纸）'" :veiled="veiled" :clamp="4" />
          <span class="meta faint">
            <span>{{ r.sealed_at ? '已寄给 Violet' : '草稿 · 点开接着写' }}</span>
            <span v-if="r.photos.length"><Icon name="photo" :size="12" /> {{ r.photos.length }}</span>
            <span v-if="r.song">♪ {{ r.song.title }}</span>
          </span>
          <MoodStamp v-if="r.mood" class="mood" :value="r.mood" :size="40" :tilt="8" :label="false" />
          <SealImpression v-else-if="r.sealed_at" class="mood" :color="resolve(r.stationery).seal_color"
            :motif="resolve(r.stationery).seal_motif" :initials="resolve(r.stationery).seal_initials" :size="38" :tilt="-8" />
        </button>
      </div>
    </template>

    <!-- Letters to the future -->
    <template v-else-if="tab === 'future'">
      <EmptyState v-if="desk.repliesLoaded && !future.length" script="someday" title="还没有寄往未来的信"
        hint="写回信时，封缄那一步选「未来的我」，挑一个日子。" />
      <div class="letters">
        <button v-for="r in future" :key="r.id" class="card future" :class="r.state" @click="openReply(r)">
          <LetterEnvelope class="envelope-art" :stationery="resolve(r.stationery)" side="front" to="未来的我"
            :width="['chinese', 'pouch'].includes(resolve(r.stationery).envelope) ? 92 : 170"
            :postmark="r.state === 'travelling' ? '' : r.deliver_on.replaceAll('-', '·')" />
          <span class="title-cn">{{ r.state === 'travelling' ? `寄往 ${longDate(r.deliver_on)}` : `${longDate(r.deliver_on)} 寄到了` }}</span>
          <span class="faint small">写于 {{ longDate(r.date) }}</span>
          <span class="faint small">{{ r.state === 'travelling' ? '在路上，到那天才能拆开。' : r.opened_at ? '已经拆开过' : '还没拆，点开看看' }}</span>
          <span v-if="r.state === 'travelling'" class="route" :style="{ '--p': travelled(r) }"
            :title="`已经走了 ${Math.round(travelled(r) * 100)}% 的路，还有 ${daysBetween(isoDate(), r.deliver_on)} 天`">
            <span class="trail" /><span class="traveller" />
          </span>
        </button>
      </div>
    </template>

    <!-- Weekly packets -->
    <template v-else>
      <EmptyState v-if="desk.repliesLoaded && !desk.weeks.length" script="weeks" title="还没有封存过一周"
        hint="每个周日，书桌上会出现这一周的封存袋。" />
      <div class="letters">
        <button v-for="w in desk.weeks" :key="w.week" class="card packet" @click="desk.weekly = w">
          <span class="title-cn">{{ w.start.slice(5).replace('-', '/') }} — {{ w.end.slice(5).replace('-', '/') }}</span>
          <span class="faint small">送达 {{ w.summary.done?.length || 0 }} 份委托 · {{ w.summary.replies || 0 }} 封回信 · 代笔 {{ hm(w.summary.focus_seconds) }}</span>
          <span v-if="w.note" class="note">「{{ w.note }}」</span>
          <WaxSeal class="mood" :size="34" tone="gold"><span class="v">V</span></WaxSeal>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: -4px 0 22px;
}
.n {
  margin-left: 6px;
  font-size: 11px;
  color: var(--ink-faint);
}
.letters {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 22px;
  padding-bottom: 24px;
}
.card {
  position: relative;
  display: grid;
  align-content: start;
  gap: 8px;
  min-height: 180px;
  padding: 20px 22px 16px;
  text-align: left;
  background: linear-gradient(160deg, var(--sheet-raised), var(--sheet));
  border: 1px solid var(--rule);
  box-shadow: var(--shadow-sheet);
  transform: rotate(var(--tilt, 0deg));
  transition: transform 0.35s var(--ease), box-shadow 0.35s var(--ease);
}
.card:hover {
  transform: rotate(0) translateY(-4px);
  box-shadow: var(--shadow-lift);
}
.stamp {
  display: flex;
  align-items: baseline;
  gap: 10px;
  color: var(--violet-ink);
}
.day {
  font-size: 30px;
  line-height: 1;
}
.month {
  font-size: 12px;
  color: var(--ink-faint);
}
.quote {
  font-size: 16.5px;
  line-height: 1.7;
  color: var(--ink);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.body {
  font-size: 14.5px;
  line-height: 1.8;
  color: var(--ink-soft);
  white-space: pre-line;
}
.reply {
  background: linear-gradient(90deg, transparent 12px, var(--letter-margin) 12px 13px, transparent 13px);
}
.reply .body {
  font-family: var(--letter-font);
  color: var(--letter-ink);
}
.draft {
  border-style: dashed;
}
.by,
.meta,
.small {
  font-size: 12.5px;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: auto;
}
.meta span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.new {
  position: absolute;
  top: 16px;
  right: 18px;
  padding: 0 8px;
  border-radius: 3px;
  font-size: 12px;
  color: var(--wax-text);
  background: radial-gradient(120% 140% at 30% 20%, var(--wax-a), var(--wax-b));
}
.fav {
  position: absolute;
  top: 14px;
  right: 18px;
  color: var(--gold);
}
.unread .fav {
  right: 62px;
}
.corner {
  position: absolute;
  right: 16px;
  bottom: 14px;
  color: var(--violet-ink);
  opacity: 0.35;
}
.mood {
  position: absolute;
  top: 12px;
  right: 14px;
}
.v {
  font-size: 18px;
  transform: translate(1px, 2px);
}
.future {
  justify-items: center;
  text-align: center;
  align-content: center;
}
.future.travelling {
  opacity: 0.82;
  background: repeating-linear-gradient(135deg, transparent 0 12px, color-mix(in srgb, var(--gold) 6%, transparent) 12px 13px),
    linear-gradient(160deg, var(--sheet-raised), var(--sheet));
}
.envelope-art {
  margin-bottom: 6px;
}
.packet {
  color: #3b2f22;
  background:
    repeating-linear-gradient(95deg, transparent 0 3px, rgba(120, 85, 40, 0.04) 3px 4px),
    #d8c09a;
  border-color: rgba(90, 60, 30, 0.25);
}
.packet .faint {
  color: #6a5235;
}
.note {
  font-family: var(--font-title);
  font-size: 15px;
  line-height: 1.7;
}
/* Letters slide into their pigeonholes one after another when a tab opens. */
.letters > .card {
  animation: post-in 0.55s cubic-bezier(0.2, 0.85, 0.3, 1.1) backwards;
}
.letters > .card:nth-child(2) {
  animation-delay: 0.05s;
}
.letters > .card:nth-child(3) {
  animation-delay: 0.1s;
}
.letters > .card:nth-child(4) {
  animation-delay: 0.15s;
}
.letters > .card:nth-child(5) {
  animation-delay: 0.2s;
}
.letters > .card:nth-child(6) {
  animation-delay: 0.25s;
}
.letters > .card:nth-child(n + 7) {
  animation-delay: 0.3s;
}
@keyframes post-in {
  from {
    opacity: 0;
    transform: translateY(18px) rotate(calc(var(--tilt, 0deg) * 3));
  }
}
/* A letter to the future, travelling: a dotted route with the envelope somewhere along it. */
.route {
  position: relative;
  display: block;
  justify-self: stretch;
  width: calc(100% - 24px);
  margin-left: 12px;
  height: 14px;
  margin-top: 6px;
}
.trail {
  position: absolute;
  left: 0;
  right: 0;
  top: 6px;
  border-top: 1.5px dashed var(--rule-strong);
}
.trail::after {
  content: '';
  position: absolute;
  left: 0;
  top: -1.5px;
  width: calc(var(--p) * 100%);
  border-top: 1.5px solid var(--gold);
}
.traveller {
  position: absolute;
  top: 0;
  left: calc(var(--p) * 100%);
  width: 18px;
  height: 12px;
  margin-left: -9px;
  border: 1px solid var(--gold);
  border-radius: 2px;
  background:
    linear-gradient(to bottom right, transparent calc(50% - 0.5px), var(--gold) 50%, transparent calc(50% + 0.5px)) left top / 50% 60% no-repeat,
    linear-gradient(to bottom left, transparent calc(50% - 0.5px), var(--gold) 50%, transparent calc(50% + 0.5px)) right top / 50% 60% no-repeat,
    var(--sheet-raised);
  animation: bob 2.4s ease-in-out infinite;
}
@keyframes bob {
  50% {
    transform: translateY(-2px) rotate(-4deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .letters > .card,
  .traveller {
    animation: none;
  }
}
</style>
