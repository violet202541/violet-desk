<script setup>
// 信笺清单：摊在窗前的一张薄信笺，像薇尔莉特用打字机打的一份收信清单。
// 顶上一行分类小字（全部 · 每一项关心的事 · 未拆的信 · 旧信）；每封信一行，标题和截止日之间用点线连着；
// 急件在右边页缘盖「速达」，别着翡翠胸针的在左边页缘别着一枚胸针。
import { computed, ref, watch } from 'vue'
import { geese, leftLabel, makeCommission, openDrawer, openLetter, serial, updateLetter } from '../geese.js'
import ExpressStamp from './ExpressStamp.vue'
import Brooch from './Brooch.vue'
import EmptySatchel from './EmptySatchel.vue'
import InkLoader from './InkLoader.vue'
import Icon from './Icon.vue'

const page = computed(() => geese.drawer?.box || geese.selected || 'all')
const filters = computed(() => [
  { id: 'all', name: '全部', count: geese.letters.length },
  ...geese.cubbies.map((c) => ({ id: c.id, name: c.name, count: c.count, urgent: c.urgent })),
])

function sortLetters(list) {
  return [...list].sort((a, b) =>
    Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) ||
    Number(Boolean(a.read_at)) - Number(Boolean(b.read_at)) ||
    (b.published || '').localeCompare(a.published || ''))
}
const rows = computed(() => {
  if (geese.drawer) return geese.drawer.letters
  if (page.value === 'all') return sortLetters(geese.letters)
  return sortLetters(geese.letters.filter((l) => l.cubby === page.value))
})
const note = computed(() => {
  if (page.value === 'unopened') return '鸿雁没拣出来的信，30 天后清掉。哪封其实有用，拆开点「这封对我有用」。'
  if (page.value === 'archive') return '过了截止日期、或者送来满两周的信，收在这里，留一年。'
  const unread = rows.value.filter((l) => !l.read_at).length
  const urgent = rows.value.filter((l) => l.urgent && !l.read_at).length
  return [`${rows.value.length} 封`, unread && `${unread} 封没拆`, urgent && `${urgent} 封急件`].filter(Boolean).join(' · ')
})
const today = new Date()
const stamp = `${today.getFullYear()} · ${String(today.getMonth() + 1).padStart(2, '0')} · ${String(today.getDate()).padStart(2, '0')}`

function choose(id) {
  geese.drawer = null
  geese.selected = id
}
function pull(box) {
  query.value = ''
  if (geese.drawer?.box !== box) openDrawer(box)
}
const query = ref('')
let searchTimer = null
watch(query, (q) => {
  clearTimeout(searchTimer)
  if (geese.drawer?.box === 'archive') searchTimer = setTimeout(() => openDrawer('archive', q.trim()), 300)
})

const day = (d) => (d ? `${d.slice(5, 7)}·${d.slice(8, 10)}` : '—·—')
const from = (l) => (l.route_name || '').replace(/学院$/, '')
</script>

<template>
  <article class="memo">
    <header class="memo-head">
      <p class="mono masthead">WILD GEESE POST — LETTERS RECEIVED</p>
      <p class="mono date">{{ stamp }}</p>
    </header>
    <h2 class="title-cn memo-title">收信清单</h2>

    <nav class="filters" aria-label="分类">
      <template v-for="(f, i) in filters" :key="f.id">
        <span v-if="i" class="dot" aria-hidden="true">·</span>
        <button class="filter" :class="{ on: page === f.id }" :aria-current="page === f.id ? 'page' : undefined" @click="choose(f.id)">
          {{ f.name }}<sup class="mono">{{ f.count }}</sup><span v-if="f.urgent" class="urgent-dot" title="有急件" />
        </button>
      </template>
      <span class="sep" aria-hidden="true">｜</span>
      <button class="filter drawer" :class="{ on: page === 'unopened' }" @click="pull('unopened')">未拆的信<sup class="mono">{{ geese.unopened }}</sup></button>
      <span class="dot" aria-hidden="true">·</span>
      <button class="filter drawer" :class="{ on: page === 'archive' }" @click="pull('archive')">旧信<sup class="mono">{{ geese.archived }}</sup></button>
    </nav>

    <div class="summary">
      <p class="faint">{{ note }}</p>
      <input v-if="page === 'archive'" v-model="query" class="field search" placeholder="搜旧信：标题、正文、驿路" aria-label="搜旧信" />
    </div>

    <InkLoader v-if="geese.drawer?.loading && !rows.length" label="翻信篮…" script="letters" />
    <ol v-else-if="rows.length" :key="page" class="entries">
      <li v-for="(l, i) in rows" :key="l.id" class="entry" :data-goose="l.id" :style="{ '--n': Math.min(i, 14) }"
        :class="{ read: l.read_at, pinned: l.pinned, sealed: page === 'unopened' }">
        <Brooch v-if="l.pinned" class="margin-brooch" :size="15" />
        <button class="line" :title="l.title" @click="openLetter(l, $event.currentTarget)">
          <span class="no mono">№ {{ serial(l) }}</span>
          <span class="date mono">{{ day(l.published) }}</span>
          <span class="from">{{ from(l) }}</span>
          <span class="subject">
            <span class="title-text">{{ l.title }}</span>
            <span v-if="l.reasons?.length" class="why">{{ page === 'unopened' ? '没拣它：' : '' }}{{ l.reasons.slice(0, 3).join(' · ') }}</span>
          </span>
          <span class="leader" aria-hidden="true" />
          <span class="due mono" :class="{ soon: l.days_left != null && l.days_left >= 0 && l.days_left <= 3 }">
            <template v-if="l.deadline">{{ l.deadline.slice(5).replace('-', '/') }}<small v-if="leftLabel(l)">{{ leftLabel(l) }}</small></template>
            <template v-else>—</template>
          </span>
        </button>
        <span class="tools">
          <span v-if="l.commission_id" class="done">已委托</span>
          <button v-else-if="page !== 'unopened'" class="icon-btn" title="记成委托（带上截止日）" @click="makeCommission(l)"><Icon name="commission" :size="14" /></button>
          <button v-if="page !== 'unopened'" class="icon-btn" :class="{ on: l.pinned }" :title="l.pinned ? '取下胸针' : '别上翡翠胸针'"
            @click="updateLetter(l, { pinned: !l.pinned })"><Icon name="brooch" :size="14" /></button>
        </span>
        <ExpressStamp v-if="l.urgent && !l.read_at && page !== 'unopened'" class="express" :size="62" :tilt="-14" />
      </li>
    </ol>
    <EmptySatchel v-else :title="page === 'archive' && query ? '没有搜到' : '这一栏还空着'"
      :hint="page === 'unopened' ? '没拣出来的信会放在这里。' : page === 'archive' ? '过了截止日期、或送来满两周的信，会收进旧信。' : '和这一项有关的信来了，会记在这里。'" />

    <footer class="memo-foot mono">— end of list —</footer>
  </article>
</template>

<style scoped>
/* A thin sheet laid in front of the window: the room shows faintly through it. */
.memo {
  position: relative;
  max-width: 980px;
  padding: 30px 64px 26px 58px;
  border-radius: 2px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.35), transparent 120px),
    color-mix(in srgb, var(--memo-paper) 88%, transparent);
  backdrop-filter: blur(3px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.6) inset, 0 0 0 1px rgba(120, 90, 50, 0.08), 0 28px 50px -30px rgba(60, 40, 20, 0.5);
  transform: rotate(-0.35deg);
  --memo-paper: #fdfaf2;
  --memo-ink: #2f2638;
  --memo-faint: #776c7e;
  --memo-rule: rgba(110, 80, 50, 0.16);
  color: var(--memo-ink);
}
:root[data-theme='dark'] .memo {
  --memo-paper: #27222f;
  --memo-ink: #ece3d3;
  --memo-faint: #ab9fa8;
  --memo-rule: rgba(239, 230, 214, 0.12);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) .memo {
    --memo-paper: #27222f;
    --memo-ink: #ece3d3;
    --memo-faint: #ab9fa8;
    --memo-rule: rgba(239, 230, 214, 0.12);
  }
}
.memo-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.memo-head p {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.22em;
  color: var(--memo-faint);
}
.memo-title {
  margin: 10px 0 14px;
  font-size: 26px;
  font-weight: 400;
  letter-spacing: 0.4em;
}
/* ------------------------------------------------------------ the filter line */
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--memo-rule);
}
.filter {
  position: relative;
  padding: 2px 2px 4px;
  font-family: var(--font-title);
  font-size: 14.5px;
  letter-spacing: 0.08em;
  color: var(--memo-faint);
  transition: color 0.2s var(--ease);
}
.filter sup {
  margin-left: 3px;
  font-size: 10.5px;
  letter-spacing: 0;
}
.filter:hover {
  color: var(--memo-ink);
}
/* The chosen one is underlined in violet ink, the way a pen would mark it. */
.filter.on {
  color: var(--violet-ink);
}
.filter.on::after {
  content: '';
  position: absolute;
  left: -2px;
  right: -2px;
  bottom: 0;
  height: 6px;
  background: no-repeat center / 100% 100%
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 6' preserveAspectRatio='none'%3E%3Cpath d='M1 4 Q30 1.5 55 3.2 T99 2.4' fill='none' stroke='%236e4fa3' stroke-width='1.6' stroke-linecap='round'/%3E%3C/svg%3E");
}
.urgent-dot {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-left: 3px;
  border-radius: 50%;
  background: #a8392f;
  vertical-align: 6px;
}
.dot,
.sep {
  color: var(--memo-faint);
  opacity: 0.6;
}
.sep {
  margin: 0 4px;
}
.summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  margin: 10px 0 4px;
}
.summary p {
  margin: 0;
  font-size: 12.5px;
  color: var(--memo-faint);
}
.search {
  width: 260px;
}
/* ------------------------------------------------------------ the entries */
.entries {
  margin: 0;
  padding: 0;
  list-style: none;
}
.entry {
  position: relative;
  border-bottom: 1px dashed var(--memo-rule);
  animation: typed 0.4s var(--ease) both;
  animation-delay: calc(var(--n) * 35ms);
}
@keyframes typed {
  /* Typed in from the left; the inset leaves room for the stamps and brooches in the margins. */
  from {
    opacity: 0;
    clip-path: inset(-40px 100% -40px -60px);
  }
  to {
    clip-path: inset(-40px -120px -40px -60px);
  }
}
.line {
  display: grid;
  grid-template-columns: 58px 46px 84px minmax(0, auto) minmax(24px, 1fr) auto;
  align-items: baseline;
  gap: 10px;
  width: 100%;
  padding: 12px 0 10px;
  text-align: left;
  color: inherit;
}
.no,
.date {
  font-size: 12.5px;
  color: var(--memo-faint);
}
.from {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-title);
  font-size: 13.5px;
  color: var(--violet-ink);
}
.subject {
  display: grid;
  gap: 2px;
  min-width: 0;
  max-width: 560px;
}
.subject .title-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
}
.why {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--memo-faint);
}
/* Dotted leaders from the subject to the date, like a typed table of contents. */
.leader {
  align-self: baseline;
  height: 1px;
  border-bottom: 1.5px dotted color-mix(in srgb, var(--memo-faint) 55%, transparent);
  transform: translateY(-4px);
}
.due {
  display: grid;
  justify-items: end;
  font-size: 13px;
  color: var(--memo-ink);
}
.due small {
  font-family: var(--font-title);
  font-size: 11.5px;
  color: var(--memo-faint);
}
.due.soon,
.due.soon small {
  color: #a4453a;
}
:root[data-theme='dark'] .due.soon,
:root[data-theme='dark'] .due.soon small {
  color: #e59184;
}
.read .line {
  opacity: 0.55;
}
.margin-brooch {
  position: absolute;
  left: -32px;
  top: 12px;
}
.express {
  position: absolute;
  right: -60px;
  top: 2px;
  pointer-events: none;
}
.tools {
  position: absolute;
  right: 74px;
  top: 50%;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 0 4px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--memo-paper) 92%, transparent);
  transform: translateY(-50%);
  opacity: 0;
  transition: opacity 0.2s var(--ease);
}
.tools .icon-btn.on {
  color: var(--emerald);
}
.done {
  padding: 0 5px;
  border: 1.3px solid var(--emerald);
  border-radius: 3px;
  color: var(--emerald);
  font-family: var(--font-title);
  font-size: 11px;
  letter-spacing: 0.12em;
}
.entry:hover .tools,
.entry:focus-within .tools {
  opacity: 1;
}
.entry:hover .line {
  background: linear-gradient(90deg, transparent, var(--violet-wash) 10%, var(--violet-wash) 90%, transparent);
}
.memo-foot {
  margin-top: 18px;
  text-align: center;
  font-size: 11.5px;
  letter-spacing: 0.3em;
  color: var(--memo-faint);
  opacity: 0.7;
}
@media (max-width: 900px) {
  .memo {
    padding: 24px 22px;
    transform: none;
  }
  .line {
    grid-template-columns: 46px 70px minmax(0, 1fr) auto;
  }
  .no,
  .leader {
    display: none;
  }
  .express {
    right: -10px;
    top: -6px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .entry {
    animation: none;
  }
}
</style>
