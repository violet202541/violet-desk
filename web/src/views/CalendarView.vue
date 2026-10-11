<script setup>
// 邮戳簿：每一天是一枚邮票。写了回信的日子印火漆，办完委托的日子盖邮戳，听过歌的日子有一张小唱片。
import { computed, onMounted, ref } from 'vue'
import { store, openLetter, loadLibrary } from '../store.js'
import { desk, loadCalendar, selectDay, startWriting } from '../desk.js'
import { playList } from '../player.js'
import { cnDay, cnMonth, hm, isoDate, longDate, weekdayOf, WEEKDAYS } from '../format.js'
import PageHeader from '../components/PageHeader.vue'
import CommissionRow from '../components/CommissionRow.vue'
import MoodStamp from '../components/MoodStamp.vue'
import Icon from '../components/Icon.vue'
import InkLoader from '../components/InkLoader.vue'
import Bloom from '../components/Bloom.vue'
import { openPressed } from '../shelf.js'
import { openLetter as openGoose, shortTitle } from '../geese.js'
import calendarArt from '../assets/art-calendar.webp'

const today = isoDate()
const month = computed(() => desk.month || today.slice(0, 7))
const title = computed(() => {
  const [y, m] = month.value.split('-').map(Number)
  const year = String(y).split('').map((d) => '〇一二三四五六七八九'[d]).join('')
  return `${year}年 · ${cnMonth(m)}月`
})
const detail = computed(() => desk.detail)
const selected = computed(() => desk.selected || today)
const info = computed(() => detail.value?.almanac)
const season = computed(() => info.value?.season)
// Turning to the next month deals the stamps in from the right, the previous month from the left.
const dir = ref(1)

function shift(delta) {
  dir.value = delta
  const [y, m] = month.value.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  loadCalendar(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
}

function goToday() {
  dir.value = today.slice(0, 7) >= month.value ? 1 : -1
  loadCalendar(today.slice(0, 7))
  selectDay(today)
}

function pick(day) {
  if (day.date.slice(0, 7) !== month.value) {
    dir.value = day.date > selected.value ? 1 : -1
    loadCalendar(day.date.slice(0, 7))
  }
  selectDay(day.date)
}

function onKey(event, day) {
  const steps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }
  if (!(event.key in steps)) return
  event.preventDefault()
  const index = desk.days.findIndex((d) => d.date === day.date) + steps[event.key]
  const next = desk.days[index]
  if (next) {
    pick(next)
    requestAnimationFrame(() => document.querySelector(`[data-date="${next.date}"]`)?.focus())
  }
}

async function playListen(item) {
  if (!store.library.loaded) await loadLibrary()
  const tracks = store.library.tracks
  const index = tracks.findIndex((t) => t.id === item.track_id)
  if (index >= 0) playList(tracks, index)
}

function readReply(reply) {
  if (reply.sealed_at) desk.reading = reply
  else startWriting(reply)
}

onMounted(() => {
  if (!desk.month) loadCalendar(today.slice(0, 7))
  if (!desk.selected) selectDay(today)
})
</script>

<template>
  <div class="stamp-book">
    <PageHeader eyebrow="Chapter III · The Stamp Book" title="邮戳簿" script="calendar"
      subtitle="每一天都是一枚邮票：火漆是回信，邮戳是送达的委托，唱片是那天的歌。">
      <button class="btn small" @click="desk.appointment = { kind: 'appointment', date: selected }"><Icon name="plus" :size="14" />约定</button>
      <button class="btn small" @click="desk.appointment = { kind: 'anniversary', date: selected }"><Icon name="cake" :size="14" />纪念日</button>
    </PageHeader>

    <div class="layout">
      <section class="month" aria-label="月历">
        <div class="month-nav">
          <button class="icon-btn" title="上个月" @click="shift(-1)"><Icon name="chevron" :size="18" class="flip" /></button>
          <h2 class="title-cn">{{ title }}</h2>
          <button class="icon-btn" title="下个月" @click="shift(1)"><Icon name="chevron" :size="18" /></button>
          <button class="btn small ghost today-btn" @click="goToday">回到今天</button>
        </div>
        <div class="weekdays" aria-hidden="true">
          <span v-for="w in WEEKDAYS" :key="w">{{ w }}</span>
        </div>
        <InkLoader v-if="desk.calendarLoading && !desk.days.length" label="正在翻开邮戳簿…" script="stamps" />
        <div v-else :key="month" class="grid" role="grid" :style="{ '--dir': dir }">
          <button v-for="(day, i) in desk.days" :key="day.date" class="cell stamp-edge" role="gridcell" :data-date="day.date"
            :style="{ '--i': i, '--tilt': ((i * 37) % 7) - 3 + 'deg' }"
            :class="{ out: day.date.slice(0, 7) !== month, today: day.date === today, on: day.date === selected,
                      festive: day.term || day.festivals.length, weekend: ['六', '日'].includes(weekdayOf(day.date)) }"
            :aria-label="`${longDate(day.date)} ${day.lunar || ''}`" :aria-selected="day.date === selected"
            :tabindex="day.date === selected ? 0 : -1" @click="pick(day)" @keydown="onKey($event, day)">
            <span class="inner">
            <span class="num mono">{{ Number(day.date.slice(8)) }}</span>
            <span class="lunar" :class="{ term: day.term, fest: day.festivals.length }">{{ day.label }}</span>
            <span class="marks">
              <MoodStamp v-if="day.reply?.mood" :value="day.reply.mood" :size="20" :label="false" class="mood" />
              <span v-else-if="day.reply" class="wax" :class="{ draft: !day.reply.sealed }" :title="day.reply.sealed ? '写了回信' : '回信草稿'" />
              <span v-if="day.done" class="postmark" :title="`送达 ${day.done} 份委托`">{{ day.done }}</span>
              <span v-if="day.listens" class="vinyl" :title="`听了 ${day.listens} 次歌`" />
              <Bloom v-if="day.pressed" class="pressed-mark" :size="17" :turn="-14" :title="`压了 ${day.pressed} 朵花`" />
            </span>
            <span v-if="day.appointments.length" class="plans">
              <span v-for="a in day.appointments.slice(0, 2)" :key="a.id" class="plan" :class="a.kind">{{ a.title }}</span>
            </span>
            <span v-if="day.open" class="due" :title="`${day.open} 份委托到期`">{{ day.open }}</span>
            </span>
          </button>
        </div>
      </section>

      <aside class="day-panel" aria-live="polite">
        <div v-if="detail && info" :key="selected" class="panel-body">
          <header class="day-head">
            <p class="eyebrow">{{ selected === today ? 'Today' : weekdayOf(selected) === '日' ? 'Sunday' : 'A day in the book' }}</p>
            <h2 class="title-cn">{{ cnMonth(Number(selected.slice(5, 7))) }}月{{ cnDay(Number(selected.slice(8))) }}日 · 星期{{ weekdayOf(selected) }}</h2>
            <p class="lunar-line">
              <span v-if="info.lunar">农历{{ info.lunar.month_name }}{{ info.lunar.day_name }} · {{ info.lunar.ganzhi }}年</span>
              <span v-for="m in [info.term, ...info.festivals].filter(Boolean)" :key="m" class="mark-day">{{ m }}</span>
            </p>
            <p v-if="season" class="season" :title="`${season.term}第${'一二三'[season.index]}候：${season.gloss}`">
              <span class="hou-mark">{{ season.term }} · {{ '一二三'[season.index] }}候</span>
              <span class="hou title-text">{{ season.hou }}</span>
            </p>
          </header>

          <section v-if="detail.letter" class="block">
            <h3><Icon name="envelope" :size="14" />那天的来信</h3>
            <button class="quote" @click="openLetter(detail.letter)">「{{ detail.letter.quote.text }}」</button>
          </section>

          <section class="block">
            <h3><Icon name="quill" :size="14" />回信</h3>
            <button v-for="r in detail.replies" :key="r.id" class="reply-line" @click="readReply(r)">
              <MoodStamp v-if="r.mood" :value="r.mood" :size="28" :label="false" />
              <span class="ellipsis">{{ r.body.slice(0, 40) || '（空白的信纸）' }}</span>
              <span class="faint tiny">{{ r.state === 'draft' ? '草稿' : r.recipient === 'future' ? '寄往未来' : '已寄出' }}</span>
            </button>
            <button v-if="!detail.replies.length && selected === today" class="btn small" @click="startWriting()">今天还没写，去动笔</button>
            <p v-else-if="!detail.replies.length" class="faint tiny">这一天没有写信。</p>
          </section>

          <section class="block">
            <h3><Icon name="commission" :size="14" />委托
              <button v-if="selected >= today" class="mini-link" @click="desk.editing = { due_date: selected }">＋ 这天的委托</button>
            </h3>
            <div v-if="detail.due.length || detail.completed.length" class="rows">
              <CommissionRow v-for="c in detail.due" :key="c.id" :item="c" compact />
              <CommissionRow v-for="c in detail.completed.filter((x) => !detail.due.some((d) => d.id === x.id))" :key="c.id" :item="c" compact />
            </div>
            <p v-else class="faint tiny">{{ selected < today ? '这一天没有委托。' : '还没有排在这天的委托。' }}</p>
          </section>

          <section class="block">
            <h3><Icon name="calendar" :size="14" />约定与纪念</h3>
            <button v-for="a in detail.appointments" :key="a.id" class="plan-line" @click="desk.appointment = a">
              <span class="mono when">{{ a.kind === 'anniversary' ? '' : a.start || '全天' }}</span>
              <Icon v-if="a.kind === 'anniversary'" name="cake" :size="14" class="cake" />
              <span class="ellipsis">{{ a.title }}<span v-if="a.years" class="faint"> · 第 {{ a.years }} 年</span></span>
            </button>
            <p v-if="!detail.appointments.length" class="faint tiny">没有约定。</p>
          </section>

          <section v-if="detail.listens.length" class="block">
            <h3><Icon name="music" :size="14" />那天的歌</h3>
            <button v-for="t in detail.listens.slice(0, 6)" :key="t.track_id" class="song-line" @click="playListen(t)">
              <span class="disc" />
              <span class="ellipsis">{{ t.title }}<span class="faint"> · {{ t.artist || '佚名' }}</span></span>
              <span class="faint tiny mono">×{{ t.count }}</span>
            </button>
          </section>

          <section v-if="detail.geese?.length" class="block">
            <h3><Icon name="goose" :size="14" />那天截止的学校通知</h3>
            <button v-for="g in detail.geese" :key="g.id" class="song-line" @click="openGoose(g)">
              <Icon name="envelope" :size="16" />
              <span class="ellipsis">{{ shortTitle(g.title, 34) }}<span class="faint"> · {{ g.route_name }}</span></span>
              <span v-if="g.commission_id" class="faint tiny">已成委托</span>
            </button>
          </section>

          <section v-if="detail.pressed?.length" class="block">
            <h3><Icon name="sparkle" :size="14" />那天压的花</h3>
            <button v-for="p in detail.pressed" :key="p.track_id" class="song-line" @click="openPressed(p.track_id)">
              <Bloom :size="20" :turn="-12" />
              <span class="ellipsis">{{ p.title }}<span class="faint"> · {{ p.artist || '佚名' }}</span></span>
              <span v-if="p.note" class="faint tiny ellipsis note-hint">「{{ p.note }}」</span>
            </button>
          </section>

          <p v-if="detail.focus_seconds" class="faint tiny focus"><Icon name="hourglass" :size="13" />那天专心代笔了 {{ hm(detail.focus_seconds) }}</p>
        </div>
        <div v-else class="panel-empty">
          <img :src="calendarArt" alt="" />
          <p class="faint">选一天，看看那天留下了什么。</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 28px;
  align-items: start;
}
.month-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.month-nav h2 {
  margin: 0 6px;
  min-width: 170px;
  text-align: center;
  font-weight: 400;
  font-size: 22px;
  letter-spacing: 0.1em;
}
.flip {
  transform: rotate(180deg);
}
.today-btn {
  margin-left: auto;
}
.weekdays,
.grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}
.weekdays span {
  text-align: center;
  font-family: var(--font-title);
  font-size: 13px;
  color: var(--ink-faint);
  padding-bottom: 4px;
}
.weekdays span:nth-child(n + 6) {
  color: color-mix(in srgb, var(--danger) 70%, var(--ink-faint));
}
.cell {
  --hole: 2px;
  display: block;
  min-height: 92px;
  text-align: left;
  color: var(--ink);
  transition: transform 0.25s var(--ease);
}
.inner {
  position: relative;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  align-content: start;
  height: 100%;
  min-height: 84px;
  padding: 5px 7px 4px;
  border: 1px solid var(--rule);
}
.cell:hover {
  transform: translateY(-2px) rotate(-0.6deg);
}
.cell.out {
  opacity: 0.45;
}
.cell.on {
  background: color-mix(in srgb, var(--violet-ink) 12%, var(--sheet-raised));
  transform: translateY(-3px);
}
.cell.today .inner {
  border: 1.5px solid var(--violet-ink);
}
.num {
  font-size: 19px;
  line-height: 1;
}
.weekend .num {
  color: color-mix(in srgb, var(--danger) 70%, var(--ink));
}
.lunar {
  font-size: 11px;
  color: var(--ink-faint);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.lunar.term {
  color: var(--emerald);
}
.lunar.fest {
  color: var(--danger);
}
.marks {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 6px;
  min-height: 22px;
}
.mood {
  transform: rotate(-6deg);
}
.wax {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, var(--wax-a), var(--wax-b));
}
.wax.draft {
  background: none;
  border: 1.5px dashed var(--violet-ink);
}
.postmark {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border: 1.2px solid var(--violet-ink);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--violet-ink);
  transform: rotate(-12deg);
}
.vinyl {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--gold) 0 2px, #2a2238 2.5px 5px, #4a4058 5.5px 6px, #2a2238 6.5px);
}
.plans {
  display: grid;
  gap: 1px;
  margin-top: 3px;
}
.plan {
  font-size: 10.5px;
  line-height: 1.35;
  padding: 0 4px;
  border-radius: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: var(--violet-wash);
  color: var(--violet-ink);
}
.plan.anniversary {
  background: var(--danger-wash);
  color: var(--danger);
}
.due {
  position: absolute;
  top: 6px;
  right: 7px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
  color: #fff;
  background: var(--gold);
}
.cell .lunar + .marks {
  margin-top: 4px;
}
/* ---- the day panel */
.day-panel {
  position: sticky;
  top: 10px;
  display: grid;
  gap: 16px;
  padding: 20px 20px 18px;
  background: var(--sheet);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sheet);
}
.day-head p,
.day-head h2 {
  margin: 0;
}
.day-head h2 {
  font-weight: 400;
  font-size: 21px;
  letter-spacing: 0.06em;
}
.lunar-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px !important;
  font-size: 13px;
  color: var(--ink-soft);
}
.mark-day {
  padding: 0 6px;
  border: 1px solid color-mix(in srgb, var(--danger) 45%, transparent);
  border-radius: 3px;
  color: var(--danger);
  font-family: var(--font-title);
}
.block h3 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 6px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 14px;
  color: var(--ink-soft);
}
.block h3 :deep(svg) {
  color: var(--violet-ink);
}
.quote {
  font-family: var(--font-title);
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--violet-ink);
  text-align: left;
}
.reply-line,
.plan-line,
.song-line {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 6px;
  border-radius: 4px;
  font-size: 13.5px;
  text-align: left;
}
.reply-line:hover,
.plan-line:hover,
.song-line:hover {
  background: var(--violet-wash);
}
.reply-line .ellipsis,
.plan-line .ellipsis,
.song-line .ellipsis {
  flex: 1;
  min-width: 0;
}
.when {
  font-size: 12px;
  color: var(--violet-ink);
}
.cake {
  color: var(--danger);
}
.disc {
  flex: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--gold) 0 2px, #2a2238 2.5px 5px, #4a4058 5.5px 6px, #2a2238 6.5px);
}
.rows {
  display: grid;
  margin: 0 -8px;
}
.tiny {
  font-size: 12px;
  margin: 0;
}
.focus {
  display: flex;
  align-items: center;
  gap: 5px;
}
.panel-empty {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 20px 0;
}
.panel-empty img {
  width: 100px;
}
@media (max-width: 1180px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .day-panel {
    position: static;
  }
  .cell,
  .inner {
    min-height: 74px;
  }
}
/* Turning the month deals the stamps in, one after another, each settling with its own small tilt. */
.grid .cell {
  animation: deal 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.15) backwards;
  animation-delay: calc(var(--i) * 11ms);
}
@keyframes deal {
  from {
    opacity: 0;
    transform: translate(calc(var(--dir) * 26px), -10px) rotate(var(--tilt)) scale(1.08);
  }
}
/* Today's stamp catches the light now and then. */
.cell.today .inner::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(115deg, transparent 35%, rgba(255, 255, 255, 0.55) 48%, transparent 60%) no-repeat;
  background-size: 250% 100%;
  background-position: 130% 0;
  animation: sheen 7s ease-in-out 1.2s infinite;
  pointer-events: none;
  mix-blend-mode: soft-light;
}
@keyframes sheen {
  0%,
  70% {
    background-position: 130% 0;
  }
  100% {
    background-position: -40% 0;
  }
}
/* The day's contents sit in their own sheet so they can turn like a leaf when another day is picked. */
.panel-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
  animation: leaf 0.45s var(--ease);
}
.day-head .season {
  margin-top: 10px;
}
@keyframes leaf {
  from {
    opacity: 0;
    transform: translateX(10px);
  }
}
.season {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 10px 0 0;
  padding: 8px 12px;
  border-left: 2px solid var(--gold-soft);
  background: color-mix(in srgb, var(--gold) 6%, transparent);
  cursor: help;
}
.hou-mark {
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--gold);
  white-space: nowrap;
}
.hou {
  font-size: 16px;
  letter-spacing: 0.16em;
  color: var(--ink);
}
.mini-link {
  margin-left: auto;
  font-size: 12px;
  color: var(--violet-ink);
  font-family: var(--font-body);
}
.mini-link:hover {
  text-decoration: underline;
}
@media (prefers-reduced-motion: reduce) {
  .grid .cell,
  .cell.today .inner::after,
  .panel-body {
    animation: none;
  }
}
.pressed-mark {
  flex: none;
}
.note-hint {
  max-width: 90px;
}
</style>
