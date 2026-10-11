<script setup>
// 今日书桌：Violet 的来信、你的回信、今天的委托与约定。打开应用先来到这里。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { store, openLetter, runSearch, go } from '../store.js'
import { greetingFor } from '../greetings.js'
import { desk, loadDesk, quickCommission, startWriting, startFocus, clipToReply } from '../desk.js'
import { current, player } from '../player.js'
import { api } from '../api.js'
import { addDays, cnDay, cnMonth, daysBetween, hm, isoDate, weekdayOf, longDate } from '../format.js'
import Wordmark from '../components/Wordmark.vue'
import Nunkish from '../components/Nunkish.vue'
import SealImpression from '../components/SealImpression.vue'
import WaxSeal from '../components/WaxSeal.vue'
import Icon from '../components/Icon.vue'
import CommissionRow from '../components/CommissionRow.vue'
import LetterEnvelope from '../components/LetterEnvelope.vue'
import { resolve } from '../stationery.js'
import MoodStamp from '../components/MoodStamp.vue'
import TypeLine from '../components/TypeLine.vue'
import LetterRack from '../components/LetterRack.vue'
import journalArt from '../assets/art-journal.webp'
import tasksArt from '../assets/art-tasks.webp'

const quick = ref('')
const query = ref('')
const today = computed(() => desk.today)
const letter = computed(() => store.letters.today)
const dateTitle = computed(() => {
  const iso = today.value?.date || isoDate()
  const [, m, d] = iso.split('-').map(Number)
  return `${cnMonth(m)}月${cnDay(d)}日 · 星期${weekdayOf(iso)}`
})
const almanacLine = computed(() => {
  const a = today.value?.almanac
  if (!a?.lunar) return ''
  const parts = [`农历${a.lunar.month_name}${a.lunar.day_name}`, `${a.lunar.ganzhi}${a.lunar.zodiac}年`]
  return parts.join(' · ')
})
const marks = computed(() => {
  const a = today.value?.almanac
  return a ? [a.term, ...(a.festivals || [])].filter(Boolean) : []
})
// Re-read every few minutes so the line follows the hour without a reload.
const clock = ref(new Date())
const ticker = setInterval(() => (clock.value = new Date()), 5 * 60 * 1000)
onBeforeUnmount(() => clearInterval(ticker))
const greeting = computed(() => greetingFor({
  date: today.value?.date || isoDate(),
  hour: clock.value.getHours(),
  term: today.value?.almanac?.term || '',
  period: today.value?.almanac?.season?.term || '',
  weather: today.value?.reply?.weather || '',
}))
const season = computed(() => today.value?.almanac?.season)
const commissions = computed(() => today.value?.commissions || [])
const doneToday = computed(() => today.value?.done_today || [])
const reply = computed(() => today.value?.reply)
const excerpt = computed(() => (reply.value?.body || '').replace(/\s+/g, ' ').slice(0, 70))
const weekly = computed(() => today.value?.weekly)
// The song on the gramophone can be clipped into today's reply right from the desk.
const clippable = computed(() => current.value && !reply.value?.sealed_at && reply.value?.song?.id !== current.value.id)
const upcoming = computed(() => today.value?.upcoming || [])
// Overdue, today, tomorrow, the rest of the week — then one line for whatever lies further off.
const groups = computed(() => {
  const day = today.value?.date || isoDate()
  const tomorrow = addDays(day, 1)
  return [
    { id: 'late', label: '已过期', items: commissions.value.filter((c) => c.due_date && c.due_date < day) },
    { id: 'today', label: '今天', items: commissions.value.filter((c) => !c.due_date || c.due_date >= day) },
    { id: 'tomorrow', label: '明天', items: upcoming.value.filter((c) => c.due_date === tomorrow) },
    { id: 'week', label: '这周内', items: upcoming.value.filter((c) => c.due_date > tomorrow) },
  ].filter((g) => g.items.length)
})
const later = computed(() => today.value?.later || 0)
function seeLater() {
  desk.filter = 'upcoming'
  go('commissions')
}
const countLine = computed(() => [commissions.value.length && `${commissions.value.length} 份待办`,
  doneToday.value.length && `已送达 ${doneToday.value.length}`].filter(Boolean).join(' · '))
const allDone = computed(() => !commissions.value.length && doneToday.value.length > 0)
// The seal presses in with a flourish only right after the last delivery; afterwards it simply rests there.
const pressing = ref(false)
watch(() => desk.finished, (at) => {
  if (!at) return
  pressing.value = true
  setTimeout(() => (pressing.value = false), 2400)
})

function countdown(item) {
  const gap = daysBetween(today.value.date, item.on)
  return gap === 1 ? '明天' : `还有 ${gap} 天`
}

async function addQuick() {
  const title = quick.value
  quick.value = ''
  await quickCommission(title)
}

function search() {
  const q = query.value.trim()
  if (!q) return go('search')
  store.search.query = q
  query.value = ''
  go('search')
  runSearch()
}

async function openArrival(item) {
  try {
    desk.reading = await api.openReply(item.id)
    loadDesk(true)
  } catch (error) {
    desk.reading = item
  }
}

onMounted(() => {
  if (!desk.today) loadDesk()
})
</script>

<template>
  <div class="desk-view">
    <header class="hero">
      <p class="eyebrow"><TypeLine :text="`${greeting[0]} · ${greeting[1]}`" :delay="500" /></p>
      <Wordmark class="mark" :height="92" />
      <div class="signature">
        <span class="rule" />
        <Nunkish text="violet evergarden" :size="16" :weight="4.2" />
        <span class="rule" />
      </div>
      <h1 class="date title-cn">{{ dateTitle }}</h1>
      <p class="almanac">
        <span>{{ almanacLine }}</span>
        <span v-for="m in marks" :key="m" class="mark-day">{{ m }}</span>
      </p>
      <p v-if="season" class="season" :title="`${season.term}第${'一二三'[season.index]}候：${season.gloss}`">
        <span class="hou-mark">{{ season.term }} · {{ '一二三'[season.index] }}候</span>
        <span class="hou title-text">{{ season.hou }}</span>
      </p>
      <Transition name="rise">
        <button v-if="clippable" class="now-playing" :title="`把「${current.title}」夹进今天的回信`"
          @click="clipToReply(current, $event.currentTarget)">
          <span class="record" :class="{ spinning: player.playing }" />
          <span class="np-text">正在听<span class="title-text">「{{ current.title }}」</span></span>
          <span class="np-clip"><Icon name="envelope" :size="13" />夹进回信</span>
        </button>
      </Transition>
    </header>

    <div v-if="desk.error && !today" class="sheet card error-card">
      <p>书桌没能打开：{{ desk.error }}</p>
      <button class="btn small" @click="loadDesk()">再试一次</button>
    </div>

    <div v-if="today" class="surface">
      <div class="column">
        <!-- Violet's letter -->
        <section class="card letter-card" aria-labelledby="desk-letter">
          <h2 id="desk-letter" class="card-title"><Icon name="envelope" :size="17" />今日来信</h2>
          <button v-if="letter && !letter.opened" class="envelope drop" title="拆开今天的信" @click="openLetter(letter)">
            <span class="flap" />
            <span class="seal"><SealImpression color="violet" motif="monogram" :size="60" /></span>
            <span class="to title-cn">致 · 你</span>
            <Nunkish class="post" text="violet post" :size="9" />
          </button>
          <button v-else-if="letter" class="opened" @click="openLetter(letter)">
            <span class="quote title-text">「{{ letter.quote.text }}」</span>
            <span class="by">—— {{ letter.quote.author }}</span>
            <span class="reread"><Icon name="letter" :size="14" />重读这封信</span>
          </button>
          <p v-else class="faint pending">邮差还在路上……</p>
          <p v-if="letter && !letter.opened" class="hint">今天的信放在桌上了，点一下拆开。</p>

          <div v-for="item in today.arrivals" :key="item.id" class="arrival" @click="openArrival(item)">
            <WaxSeal tone="gold" :size="34"><Icon name="future" :size="15" /></WaxSeal>
            <div>
              <p class="title-cn">一封来自 {{ longDate(item.date) }} 的信</p>
              <p class="faint small">那天的你写给今天的你。</p>
            </div>
            <span class="btn small wax">拆开</span>
          </div>
        </section>

        <!-- The user's reply -->
        <section class="card reply-card" aria-labelledby="desk-reply">
          <h2 id="desk-reply" class="card-title"><Icon name="quill" :size="17" />回信</h2>
          <div v-if="!reply" class="reply-empty">
            <img :src="journalArt" alt="" class="art" draggable="false" />
            <div>
              <p class="title-cn lead">给 Violet 写一封回信吧。</p>
              <p class="faint small">今天发生了什么、想到了什么，都可以写。也可以寄给未来的自己。</p>
              <button class="btn wax" @click="startWriting()"><Icon name="quill" :size="15" />动笔</button>
            </div>
          </div>
          <div v-else-if="!reply.sealed_at" class="reply-draft">
            <p class="excerpt">{{ excerpt || '（信纸已经铺好，还没写字）' }}<span v-if="excerpt" class="ellipsis-mark">……</span></p>
            <button class="btn wax" @click="startWriting(reply)"><Icon name="quill" :size="15" />接着写</button>
          </div>
          <div v-else class="reply-sealed">
            <LetterEnvelope class="mini-envelope" :stationery="resolve(reply.stationery)" side="back"
              :width="['chinese', 'pouch'].includes(resolve(reply.stationery).envelope) ? 42 : 72" />
            <div>
              <p class="title-cn">{{ reply.recipient === 'future' ? `寄往 ${longDate(reply.deliver_on)}` : '今天的回信已经寄出' }}</p>
              <p class="faint small">{{ reply.recipient === 'future' ? '它会在那一天回到你的书桌上。' : 'Violet 会好好收着。' }}</p>
            </div>
            <MoodStamp v-if="reply.mood" :value="reply.mood" :size="38" :tilt="6" />
            <button class="btn small" @click="desk.reading = reply">重读</button>
          </div>
        </section>

        <!-- 鸿雁: the most relevant unopened school letters, standing in a small rack -->
        <LetterRack />
      </div>

      <div class="column">
        <!-- Today's commissions -->
        <section class="card commissions-card" aria-labelledby="desk-commissions">
          <h2 id="desk-commissions" class="card-title">
            <Icon name="commission" :size="17" />近日委托
            <span class="count faint">{{ countLine }}</span>
            <button class="link" @click="go('commissions')">全部委托</button>
          </h2>
          <form class="quick" @submit.prevent="addQuick">
            <Icon name="plus" :size="16" />
            <input v-model="quick" class="field" maxlength="200" placeholder="接一份新委托，回车记下（默认今天）" aria-label="新委托" />
          </form>
          <div v-if="allDone" class="finished" :class="{ pressing }">
            <WaxSeal class="day-seal" :size="58" tone="gold" :pressed="pressing"><span class="seal-v">毕</span></WaxSeal>
            <div>
              <p class="title-cn">今日事毕</p>
              <p class="faint small">今天的 {{ doneToday.length }} 份委托都送达了。剩下的时间，是你自己的。</p>
            </div>
          </div>
          <div v-if="groups.length || doneToday.length" class="groups">
            <section v-for="g in groups" :key="g.id" class="group" :class="g.id">
              <h3 class="group-label">{{ g.label }}<span class="mono">{{ g.items.length }}</span></h3>
              <TransitionGroup tag="div" name="slip" class="list">
                <CommissionRow v-for="item in g.items" :key="item.id" :item="item" compact postpone />
              </TransitionGroup>
            </section>
            <TransitionGroup v-if="doneToday.length" tag="div" name="slip" class="list done-list">
              <CommissionRow v-for="item in doneToday.slice(0, 3)" :key="item.id" :item="item" compact />
            </TransitionGroup>
          </div>
          <div v-else class="all-clear">
            <img :src="tasksArt" alt="" class="art small-art" draggable="false" />
            <p class="faint">今天没有待办的委托。<br />可以去寻一首歌，或者什么都不做。</p>
          </div>
          <button v-if="later" class="link later-line" @click="seeLater">之后还有 {{ later }} 份委托 →</button>
          <p v-if="today.focus_seconds" class="focus-note faint"><Icon name="hourglass" :size="13" />今天专心代笔了 {{ hm(today.focus_seconds) }}</p>
          <button v-else-if="commissions.length" class="link focus-start" @click="startFocus(commissions[0])">
            <Icon name="hourglass" :size="13" />从「{{ commissions[0].title }}」开始代笔时间
          </button>
        </section>

        <!-- Appointments and anniversaries -->
        <section class="card plans-card" aria-labelledby="desk-plans">
          <h2 id="desk-plans" class="card-title">
            <Icon name="calendar" :size="17" />约定与纪念
            <button class="link" @click="desk.appointment = { kind: 'appointment', date: today.date }">＋ 约定</button>
            <button class="link" @click="desk.appointment = { kind: 'anniversary', date: today.date }">＋ 纪念日</button>
          </h2>
          <ul v-if="today.appointments.length || today.ahead.length" class="plans">
            <li v-for="item in today.appointments" :key="item.id + item.on" class="plan today-plan"
              @click="desk.appointment = item">
              <span class="when mono">{{ item.kind === 'anniversary' ? '今天' : item.start || '全天' }}</span>
              <span class="what"><Icon v-if="item.kind === 'anniversary'" name="cake" :size="14" />{{ item.title }}
                <span v-if="item.years" class="faint small">· 第 {{ item.years }} 年</span></span>
              <span v-if="item.place" class="faint small"><Icon name="pin" :size="12" />{{ item.place }}</span>
            </li>
            <li v-for="item in today.ahead" :key="item.id + item.on" class="plan" @click="desk.appointment = item">
              <span class="when">{{ countdown(item) }}</span>
              <span class="what"><Icon v-if="item.kind === 'anniversary'" name="cake" :size="14" />{{ item.title }}</span>
              <span class="faint small">{{ item.on.slice(5).replace('-', '/') }}</span>
            </li>
          </ul>
          <p v-else class="faint small empty-plans">接下来一个月没有约定。生日和纪念日记在这里，每年都会提醒。</p>
        </section>

        <!-- Sunday's weekly packet -->
        <section v-if="weekly" class="card weekly-card">
          <h2 class="card-title"><Icon name="archive" :size="17" />本周封存袋 <span class="faint count">{{ weekly.start.slice(5) }} — {{ weekly.end.slice(5) }}</span></h2>
          <p class="weekly-line">
            送达 <b>{{ weekly.summary.done.length }}</b> 份委托 · 写了 <b>{{ weekly.summary.replies }}</b> 封回信 ·
            代笔 <b>{{ hm(weekly.summary.focus_seconds) }}</b>
          </p>
          <p v-if="weekly.summary.songs.length" class="faint small">这周听得最多的是「{{ weekly.summary.songs[0].title }}」。</p>
          <button class="btn small wax" @click="desk.weekly = weekly"><Icon name="archive" :size="14" />封存这一周</button>
        </section>
      </div>
    </div>

    <form class="quick-search" @submit.prevent="search">
      <Icon name="music" :size="18" class="nib" />
      <input v-model="query" class="field" placeholder="想听点什么？写下歌名，Violet 去替你找" aria-label="寻歌" />
      <button class="btn small" type="submit">寻歌</button>
    </form>
  </div>
</template>

<style scoped>
.desk-view {
  max-width: 1100px;
  margin: 0 auto;
  padding-bottom: 20px;
}
.hero {
  position: relative;
  display: grid;
  justify-items: center;
  text-align: center;
  padding-top: 2vh;
}
/* A pool of lamplight on the paper, so the words read clearly over the painting. */
.hero::before {
  content: '';
  position: absolute;
  inset: -10px calc(50% - 230px) -16px;
  z-index: -1;
  background: radial-gradient(50% 50% at 50% 55%, color-mix(in srgb, var(--paper) 92%, transparent) 40%, color-mix(in srgb, var(--paper) 55%, transparent) 70%, transparent 100%);
  pointer-events: none;
}
.hero .eyebrow {
  margin: 0;
}
.mark {
  margin: 4px 0 0;
}
.signature {
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--gold);
  opacity: 0.85;
}
.rule {
  width: 64px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold-soft));
}
.rule:last-child {
  transform: scaleX(-1);
}
.date {
  margin: 14px 0 2px;
  font-size: 26px;
  font-weight: 400;
  letter-spacing: 0.14em;
}
.almanac {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin: 0;
  font-size: 13.5px;
  color: var(--ink-soft);
  letter-spacing: 0.08em;
}
.mark-day {
  padding: 0 8px;
  border: 1px solid color-mix(in srgb, var(--danger) 45%, transparent);
  border-radius: 3px;
  color: var(--danger);
  font-family: var(--font-title);
}
.surface {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  gap: 22px;
  margin-top: 30px;
  align-items: start;
}
.column {
  display: grid;
  gap: 22px;
}
.card {
  position: relative;
  padding: 18px 22px 18px;
  background: color-mix(in srgb, var(--sheet) 90%, transparent);
  backdrop-filter: blur(3px);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sheet);
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 17px;
  color: var(--ink);
}
.card-title :deep(svg) {
  color: var(--violet-ink);
}
.count {
  font-family: var(--font-body);
  font-size: 12.5px;
}
.link {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--violet-ink);
  font-family: var(--font-body);
}
.link + .link {
  margin-left: 6px;
}
.link:hover {
  text-decoration: underline;
}
.small {
  font-size: 12.5px;
}
p {
  margin: 0;
}
.art {
  width: 92px;
  height: auto;
  flex: none;
  filter: drop-shadow(0 6px 10px rgba(60, 40, 20, 0.15));
}
.small-art {
  width: 64px;
}
/* ---- the envelope on the desk */
.letter-card {
  display: grid;
  justify-items: center;
}
.letter-card .card-title {
  justify-self: stretch;
}
.envelope {
  position: relative;
  width: min(330px, 100%);
  aspect-ratio: 330 / 200;
  margin: 6px 0 4px;
  border-radius: 5px;
  background:
    linear-gradient(to top right, transparent calc(50% - 0.5px), var(--rule-strong) 50%, transparent calc(50% + 0.5px)) left bottom / 50% 62% no-repeat,
    linear-gradient(to top left, transparent calc(50% - 0.5px), var(--rule-strong) 50%, transparent calc(50% + 0.5px)) right bottom / 50% 62% no-repeat,
    linear-gradient(160deg, var(--sheet-raised), var(--paper-deep));
  border: 1px solid var(--rule-strong);
  box-shadow: var(--shadow-lift);
  transition: transform 0.4s var(--ease);
}
.envelope:hover {
  transform: translateY(-3px) rotate(-0.6deg);
}
.envelope .flap {
  position: absolute;
  inset: 0 0 auto 0;
  height: 56%;
  background: linear-gradient(170deg, var(--sheet-raised), var(--paper-deep));
  clip-path: polygon(0 0, 100% 0, 50% 100%);
  filter: drop-shadow(0 2px 2px rgba(60, 40, 20, 0.15));
}
.envelope .seal {
  position: absolute;
  left: 50%;
  top: 56%;
  transform: translate(-50%, -50%);
}
.seal-v {
  font-size: 30px;
  transform: translate(1px, 3px);
}
.seal-v.small {
  font-size: 18px;
}
.envelope .to {
  position: absolute;
  right: 18px;
  bottom: 12px;
  font-size: 13px;
  letter-spacing: 0.3em;
  color: var(--ink-soft);
}
.envelope .post {
  position: absolute;
  left: 16px;
  bottom: 14px;
  color: var(--violet-ink);
  opacity: 0.5;
}
.drop {
  animation: drop 1.2s cubic-bezier(0.2, 0.9, 0.3, 1.05) both;
}
@keyframes drop {
  0% {
    opacity: 0;
    transform: translate(-40px, -120px) rotate(-16deg);
  }
  60% {
    opacity: 1;
    transform: translate(4px, 6px) rotate(2deg);
  }
  100% {
    transform: none;
  }
}
.hint {
  font-size: 12.5px;
  color: var(--ink-faint);
}
.opened {
  display: grid;
  gap: 6px;
  width: 100%;
  padding: 16px 18px 12px 22px;
  text-align: left;
  border-left: 2px solid var(--gold-soft);
  background: color-mix(in srgb, var(--gold) 5%, transparent);
  border-radius: 0 var(--radius) var(--radius) 0;
}
.opened .quote {
  font-size: 17px;
  line-height: 1.75;
  color: var(--violet-ink);
}
.opened .by {
  justify-self: end;
  font-size: 13px;
  color: var(--ink-soft);
}
.reread {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--violet-ink);
}
.pending {
  padding: 30px 0;
}
.arrival {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  width: 100%;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--gold) 9%, transparent);
  cursor: pointer;
}
/* ---- reply */
.reply-empty {
  display: flex;
  gap: 16px;
  align-items: center;
}
.reply-empty .lead {
  font-size: 17px;
  margin-bottom: 4px;
}
.reply-empty .btn {
  margin-top: 12px;
}
.reply-draft {
  display: grid;
  gap: 12px;
  justify-items: start;
}
.excerpt {
  font-size: 15px;
  line-height: 1.9;
  color: var(--ink-soft);
  padding-left: 14px;
  border-left: 2px solid var(--violet-wash-strong);
}
.reply-sealed {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 14px;
}
.mini-envelope {
  transform: rotate(-4deg);
}
/* ---- commissions */
.quick {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-faint);
  margin-bottom: 4px;
}
.quick .field {
  flex: 1;
  height: 36px;
}
.list {
  display: grid;
  margin: 0 -10px;
}
.groups {
  display: grid;
  gap: 8px;
}
.group-label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 2px 0 0;
  font-family: var(--font-title);
  font-size: 12.5px;
  font-weight: 400;
  letter-spacing: 0.12em;
  color: var(--ink-faint);
}
.group-label .mono {
  font-size: 11px;
  letter-spacing: 0;
}
.group.late .group-label {
  color: var(--danger);
}
/* What is further off is only hinted at: a little paler. */
.group.tomorrow .list,
.group.week .list {
  opacity: 0.86;
}
.done-list {
  border-top: 1px dashed var(--rule);
  padding-top: 4px;
}
.later-line {
  display: block;
  margin: 8px 0 0;
  font-size: 12.5px;
}
.all-clear {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 0 4px;
  font-size: 13.5px;
  line-height: 1.7;
}
.focus-note,
.focus-start {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 10px;
  font-size: 12.5px;
}
.focus-start {
  margin-left: 0;
}
/* ---- plans */
.plans {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 2px;
}
.plan {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) auto;
  align-items: baseline;
  gap: 10px;
  padding: 6px 8px;
  border-radius: var(--radius);
  cursor: pointer;
}
.plan:hover {
  background: var(--violet-wash);
}
.plan .when {
  font-size: 12.5px;
  color: var(--ink-faint);
}
.today-plan .when {
  color: var(--violet-ink);
}
.plan .what {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plan .what :deep(svg) {
  color: var(--danger);
  flex: none;
}
.empty-plans {
  line-height: 1.7;
}
/* ---- weekly */
.weekly-card {
  display: grid;
  gap: 8px;
  justify-items: start;
  background:
    repeating-linear-gradient(135deg, transparent 0 14px, color-mix(in srgb, var(--gold) 5%, transparent) 14px 15px),
    color-mix(in srgb, var(--sheet) 92%, transparent);
}
.weekly-line b {
  font-family: var(--font-mono);
  font-weight: 400;
  color: var(--violet-ink);
  font-size: 17px;
}
.error-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 24px;
  padding: 14px 18px;
  color: var(--danger);
}
/* ---- quick search */
.quick-search {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 620px;
  margin: 34px auto 0;
  padding: 0 4px 8px;
  border-bottom: 1px solid var(--rule-strong);
}
.quick-search .field {
  flex: 1;
  border: 0;
  font-family: var(--font-title);
  font-size: 17px;
}
.quick-search .nib {
  color: var(--violet-ink);
}
@media (max-width: 1100px) {
  .surface {
    grid-template-columns: minmax(0, 1fr);
  }
}
.season {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 8px 0 0;
  cursor: help;
}
.hou-mark {
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--gold);
}
.hou {
  font-size: 15px;
  letter-spacing: 0.22em;
  color: var(--ink-soft);
}
/* The gramophone on the desk: the record turns while the song plays. */
.now-playing {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding: 5px 14px 5px 6px;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: color-mix(in srgb, var(--sheet) 80%, transparent);
  font-size: 13px;
  color: var(--ink-soft);
  transition: border-color 0.2s var(--ease), transform 0.25s var(--ease);
}
.now-playing:hover {
  border-color: var(--violet-ink);
  transform: translateY(-1px);
}
.record {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background:
    radial-gradient(circle, var(--wax-a) 0 3px, #1d1724 3.5px 4px, transparent 4.5px),
    repeating-radial-gradient(circle, #1d1724 0 1.2px, #2f2838 1.2px 2.2px);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}
.record.spinning {
  animation: spin 3.2s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.np-text {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.np-clip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding-left: 10px;
  border-left: 1px solid var(--rule);
  color: var(--violet-ink);
}
.rise-enter-active,
.rise-leave-active {
  transition: opacity 0.4s var(--ease), transform 0.4s var(--ease);
}
.rise-enter-from,
.rise-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
/* The envelope rests on the desk, breathing a little, and catches the window light now and then. */
.envelope.drop {
  animation: drop 1.2s cubic-bezier(0.2, 0.9, 0.3, 1.05) both, float 6s ease-in-out 1.4s infinite;
}
@keyframes float {
  0%,
  100% {
    transform: none;
  }
  50% {
    transform: translateY(-3px) rotate(-0.4deg);
  }
}
.envelope::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(115deg, transparent 38%, rgba(255, 255, 255, 0.5) 50%, transparent 62%) no-repeat;
  background-size: 260% 100%;
  background-position: 140% 0;
  animation: sheen 8s ease-in-out 2.5s infinite;
  mix-blend-mode: soft-light;
  pointer-events: none;
}
@keyframes sheen {
  0%,
  75% {
    background-position: 140% 0;
  }
  100% {
    background-position: -40% 0;
  }
}
.envelope .seal {
  transition: transform 0.4s cubic-bezier(0.3, 1.5, 0.5, 1);
}
.envelope:hover .seal {
  transform: translate(-50%, -50%) scale(1.08) rotate(-6deg);
}
/* 今日事毕 */
.finished {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 6px 0 10px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: radial-gradient(120% 140% at 0% 50%, color-mix(in srgb, var(--gold) 14%, transparent), transparent 70%);
}
.finished .title-cn {
  font-size: 19px;
  letter-spacing: 0.3em;
  color: var(--gold);
}
.day-seal .seal-v {
  font-family: var(--font-title);
  font-size: 22px;
  transform: none;
}
.finished.pressing .day-seal {
  animation: press 0.9s cubic-bezier(0.3, 1.6, 0.4, 1) both;
}
.finished.pressing > div {
  animation: ink-in 1.2s var(--ease) 0.3s both;
}
@keyframes press {
  0% {
    transform: scale(2.4) rotate(-30deg);
    opacity: 0;
  }
  55% {
    transform: scale(0.9) rotate(4deg);
    opacity: 1;
  }
  100% {
    transform: none;
  }
}
@keyframes ink-in {
  from {
    opacity: 0;
    filter: blur(4px);
    letter-spacing: 0.5em;
  }
}
/* Slips come and go from the day's list. */
.slip-enter-active {
  transition: opacity 0.45s var(--ease), transform 0.45s var(--ease);
}
.slip-leave-active {
  transition: opacity 0.4s var(--ease), transform 0.4s var(--ease), max-height 0.45s var(--ease) 0.1s;
  max-height: 80px;
  overflow: hidden;
}
.slip-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.slip-leave-to {
  opacity: 0;
  transform: translateX(24px) rotate(1.5deg);
  max-height: 0;
}
.slip-move {
  transition: transform 0.45s var(--ease);
}
@media (prefers-reduced-motion: reduce) {
  .envelope.drop,
  .envelope::after,
  .record.spinning,
  .finished.pressing .day-seal,
  .finished.pressing > div {
    animation: none;
  }
}
</style>
