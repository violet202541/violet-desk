<script setup>
// 委托：所有要办的事。左边按日子和委托人分拣，右边是一沓委托单。
import { computed, onMounted, ref } from 'vue'
import { desk, loadCommissions, quickCommission } from '../desk.js'
import { isoDate, longDate, monthDay, relativeDay, addDays } from '../format.js'
import PageHeader from '../components/PageHeader.vue'
import CommissionRow from '../components/CommissionRow.vue'
import Icon from '../components/Icon.vue'
import tasksArt from '../assets/art-tasks.webp'

const quick = ref('')
const today = isoDate()
// Poetic names, with the plain meaning on hover (and read out by screen readers).
const FILTERS = [
  { id: 'today', label: '今日案头', hint: '今天：今天到期与逾期的委托' },
  { id: 'upcoming', label: '来日', hint: '接下来：排在以后日子的委托' },
  { id: 'someday', label: '闲笺', hint: '无期限：想做、还没定日子的事' },
  { id: 'all', label: '全部委托', hint: '所有还没办完的委托' },
  { id: 'done', label: '已送达', hint: '办完的委托' },
]
const EMPTY = {
  today: ['案头空空', '今天可以轻松一点。窗外的光很好。'],
  upcoming: ['来日方长', '还没有排在以后的委托。'],
  someday: ['闲笺一张也没有', '想做却还没定日子的事，可以先记在这里。'],
  all: ['一份委托都没有', '在上面写下一件事，就是一份新委托。'],
  done: ['还没有送达的委托', '办完一件，就在这里盖一枚邮戳。'],
}

const open = computed(() => desk.commissions.filter((c) => c.status === 'open' && (!desk.client || c.client === desk.client)))
const done = computed(() => desk.commissions.filter((c) => c.status === 'done' && (!desk.client || c.client === desk.client))
  .sort((a, b) => (b.completed_at || 0) - (a.completed_at || 0)))

const counts = computed(() => ({
  today: open.value.filter((c) => c.due_date && c.due_date <= today).length,
  upcoming: open.value.filter((c) => c.due_date && c.due_date > today).length,
  someday: open.value.filter((c) => !c.due_date).length,
  all: open.value.length,
  done: done.value.length,
}))

const groups = computed(() => {
  const f = desk.filter
  if (f === 'done') {
    const out = []
    for (const c of done.value.slice(0, 200)) {
      const day = isoDate(new Date(c.completed_at * 1000))
      if (!out.length || out[out.length - 1].key !== day) out.push({ key: day, label: `${relativeDay(day, today)} 送达`, items: [] })
      out[out.length - 1].items.push(c)
    }
    return out
  }
  if (f === 'someday') return [{ key: 'someday', label: '', items: open.value.filter((c) => !c.due_date) }]
  if (f === 'today') {
    const late = open.value.filter((c) => c.due_date && c.due_date < today)
    const now = open.value.filter((c) => c.due_date === today)
    return [
      late.length && { key: 'late', label: '误了邮期', hint: '逾期', tone: 'late', items: late },
      { key: 'today', label: `今天 · ${longDate(today)}`, items: now },
    ].filter(Boolean)
  }
  const list = f === 'upcoming' ? open.value.filter((c) => c.due_date && c.due_date > today) : open.value
  const out = []
  for (const c of list) {
    const key = c.due_date || 'someday'
    if (!out.length || out[out.length - 1].key !== key) {
      const near = key !== 'someday' && relativeDay(key, today)
      const label = key === 'someday' ? '闲笺' : ['今天', '明天', '后天', '昨天'].includes(near) ? `${near} · ${monthDay(key)}` : near
      out.push({ key, label, tone: key !== 'someday' && key < today ? 'late' : '', items: [] })
    }
    out[out.length - 1].items.push(c)
  }
  return out
})
const empty = computed(() => groups.value.every((g) => !g.items.length))

async function add() {
  const title = quick.value
  quick.value = ''
  const due = desk.filter === 'someday' ? null : desk.filter === 'upcoming' ? addDays(today, 1) : today
  await quickCommission(title, { due_date: due, client: desk.client || '' })
}

function newCommission() {
  desk.editing = { due_date: desk.filter === 'someday' ? '' : today, client: desk.client || '' }
}

onMounted(() => {
  if (!desk.loaded) loadCommissions()
})
</script>

<template>
  <div class="commissions">
    <PageHeader eyebrow="Chapter II · Commissions" title="委托" script="commissions"
      subtitle="每一件要办的事，都是一份委托。办完了，就盖上「已送达」。">
      <button class="btn wax" @click="newCommission"><Icon name="plus" :size="15" />新的委托</button>
    </PageHeader>

    <div class="layout">
      <aside class="rail" aria-label="分拣">
        <button v-for="f in FILTERS" :key="f.id" class="pick" :class="{ on: desk.filter === f.id }" :title="f.hint"
          :aria-label="`${f.label}（${f.hint}）`" @click="desk.filter = f.id">
          <span>{{ f.label }}</span>
          <span class="n mono">{{ counts[f.id] || '' }}</span>
        </button>
        <p class="rail-title">委托人</p>
        <button class="pick" :class="{ on: !desk.client }" @click="desk.client = ''"><span>所有人</span></button>
        <button v-for="c in desk.clients" :key="c.client" class="pick client" :class="{ on: desk.client === c.client }"
          @click="desk.client = desk.client === c.client ? '' : c.client">
          <span class="ellipsis"><Icon name="user" :size="13" />{{ c.client }}</span>
          <span class="n mono">{{ c.open || '' }}</span>
        </button>
        <p v-if="!desk.clients.length" class="faint tiny">给委托写上「委托人」（自己、工作、某个项目），就能在这里分开看。</p>
      </aside>

      <section class="stack">
        <form v-if="desk.filter !== 'done'" class="quick" @submit.prevent="add">
          <Icon name="plus" :size="17" />
          <input v-model="quick" class="field" maxlength="200" aria-label="新委托"
            :placeholder="desk.filter === 'someday' ? '记下一件想做的事，回车' : desk.filter === 'upcoming' ? '接一份明天的委托，回车' : '接一份今天的委托，回车'" />
          <span v-if="desk.client" class="chip on">{{ desk.client }}</span>
        </form>

        <div v-if="desk.loaded && empty" class="empty">
          <img :src="tasksArt" alt="" draggable="false" />
          <p class="title-cn">{{ EMPTY[desk.filter][0] }}</p>
          <p class="faint">{{ EMPTY[desk.filter][1] }}</p>
        </div>

        <div v-for="g in groups" v-show="g.items.length" :key="g.key" class="group">
          <h3 v-if="g.label" class="group-title" :class="g.tone" :title="g.hint">{{ g.label }} <span class="faint mono">{{ g.items.length }}</span></h3>
          <TransitionGroup tag="div" name="slip" class="slips" :class="g.tone">
            <CommissionRow v-for="item in g.items" :key="item.id" :item="item" />
          </TransitionGroup>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 32px;
  align-items: start;
}
.rail {
  position: sticky;
  top: 10px;
  display: grid;
  gap: 2px;
}
.pick {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 12px;
  border-radius: var(--radius);
  font-size: 14.5px;
  color: var(--ink-soft);
  text-align: left;
}
.pick span:first-child {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.pick:hover {
  background: var(--violet-wash);
  color: var(--ink);
}
.pick.on {
  background: var(--violet-wash-strong);
  color: var(--violet-ink);
}
.n {
  font-size: 12px;
  color: var(--ink-faint);
}
.rail-title {
  margin: 18px 12px 4px;
  font-size: 12px;
  letter-spacing: 0.2em;
  color: var(--ink-faint);
}
.tiny {
  margin: 4px 12px;
  font-size: 12px;
  line-height: 1.6;
}
.stack {
  min-width: 0;
}
.quick {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 4px 4px 12px;
  margin-bottom: 18px;
  color: var(--ink-faint);
  background: var(--sheet);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sheet);
}
.quick .field {
  flex: 1;
  border: 0;
  font-size: 15.5px;
}
.group {
  margin-bottom: 22px;
}
.group-title {
  margin: 0 0 6px 6px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 15px;
  color: var(--ink-soft);
  letter-spacing: 0.06em;
}
.group-title.late {
  color: var(--danger);
}
.slips {
  display: grid;
  padding: 6px 4px;
  background:
    linear-gradient(90deg, transparent 22px, color-mix(in srgb, var(--danger) 18%, transparent) 22px 23px, transparent 23px),
    var(--sheet);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sheet);
}
.slips :deep(.row) {
  padding-left: 32px;
}
.slips :deep(.row + .row) {
  border-top: 1px dashed var(--rule);
  border-radius: 0;
}
.empty {
  display: grid;
  justify-items: center;
  gap: 6px;
  padding: 50px 0;
  text-align: center;
}
.empty img {
  width: 110px;
  margin-bottom: 8px;
  filter: drop-shadow(0 8px 12px rgba(60, 40, 20, 0.15));
}
.empty p {
  margin: 0;
}
.empty .title-cn {
  font-size: 19px;
}
@media (max-width: 1080px) {
  .layout {
    grid-template-columns: 150px minmax(0, 1fr);
    gap: 20px;
  }
}
/* Late slips wear the red-and-blue airmail border: they need to travel faster. */
.slips.late {
  border: 0;
  padding: 10px 8px;
  background:
    linear-gradient(90deg, transparent 26px, color-mix(in srgb, var(--danger) 18%, transparent) 26px 27px, transparent 27px) padding-box,
    linear-gradient(var(--sheet), var(--sheet)) padding-box,
    repeating-linear-gradient(135deg, #b3473d 0 10px, transparent 10px 15px, #34508f 15px 25px, transparent 25px 30px) border-box;
  border: 5px solid transparent;
}
:root[data-theme='dark'] .slips.late {
  background:
    linear-gradient(90deg, transparent 26px, color-mix(in srgb, var(--danger) 18%, transparent) 26px 27px, transparent 27px) padding-box,
    linear-gradient(var(--sheet), var(--sheet)) padding-box,
    repeating-linear-gradient(135deg, #b8574c 0 10px, transparent 10px 15px, #5a76b8 15px 25px, transparent 25px 30px) border-box;
}
.group {
  animation: group-in 0.5s var(--ease) backwards;
}
.group:nth-child(3) {
  animation-delay: 0.07s;
}
.group:nth-child(4) {
  animation-delay: 0.14s;
}
@keyframes group-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
}
.pick {
  position: relative;
  transition: background 0.2s var(--ease), color 0.2s var(--ease), padding 0.25s var(--ease);
}
.pick.on {
  padding-left: 18px;
}
.pick.on::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 50%;
  width: 5px;
  height: 5px;
  margin-top: -2.5px;
  border-radius: 50%;
  background: var(--violet-ink);
}
.slip-enter-active {
  transition: opacity 0.45s var(--ease), transform 0.45s var(--ease);
}
.slip-leave-active {
  transition: opacity 0.4s var(--ease), transform 0.4s var(--ease), max-height 0.45s var(--ease) 0.1s;
  max-height: 90px;
  overflow: hidden;
}
.slip-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}
.slip-leave-to {
  opacity: 0;
  transform: translateX(30px) rotate(1.5deg);
  max-height: 0;
}
.slip-move {
  transition: transform 0.45s var(--ease);
}
@media (prefers-reduced-motion: reduce) {
  .group {
    animation: none;
  }
}
</style>
