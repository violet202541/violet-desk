<script setup>
// 拆开一封学校的信：正文铺在信纸上，截止日期和你关心的词用笔迹标出来，附件列在信尾。
// 纠错也在这里：「这封对我有用」「以后别送这类」——Violet 挑出候选词，你勾了才写进名片。
import { computed, nextTick, ref, watch } from 'vue'
import { api } from '../api.js'
import { geese, makeAppointment, makeCommission, serial, teach, updateLetter } from '../geese.js'
import { trapFocus } from '../dialog.js'
import { longDate } from '../format.js'
import Icon from './Icon.vue'
import InkLoader from './InkLoader.vue'
import ExpressStamp from './ExpressStamp.vue'

const box = ref(null)
const body = ref(null)
const letter = computed(() => geese.reading)
const sealed = computed(() => letter.value && !letter.value.passed)
const left = computed(() => {
  const n = letter.value?.days_left
  if (n == null || n < 0) return n < 0 ? '已经过了' : ''
  return ['就是今天', '就在明天', '就在后天'][n] || `还剩 ${n} 天`
})
const cubbyName = computed(() => {
  const c = geese.cubbies.find((x) => x.id === letter.value?.cubby)
  return c?.name || ''
})

// ------------------------------------------------------------ marking the text in pen

function escape(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function mark() {
  const root = body.value
  const item = letter.value
  if (!root || !item?.content) return
  const parts = []
  const words = (item.highlights || []).filter(Boolean)
  if (item.deadline) {
    const [y, m, d] = item.deadline.split('-').map(Number)
    parts.push({ re: `(?:${y}\\s*年\\s*)?0?${m}\\s*月\\s*0?${d}\\s*[日号]`, cls: 'due' })
  }
  if (words.length) parts.push({ re: words.map(escape).join('|'), cls: 'ink' })
  if (!parts.length) return
  const pattern = new RegExp(parts.map((p) => `(${p.re})`).join('|'), 'g')
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const nodes = []
  while (walker.nextNode()) nodes.push(walker.currentNode)
  for (const node of nodes) {
    const text = node.nodeValue
    pattern.lastIndex = 0
    if (!pattern.test(text)) continue
    pattern.lastIndex = 0
    const frag = document.createDocumentFragment()
    let last = 0
    for (const match of text.matchAll(pattern)) {
      if (match.index > last) frag.append(text.slice(last, match.index))
      const el = document.createElement('mark')
      const which = match.slice(1).findIndex((g) => g !== undefined)
      el.className = parts[which]?.cls || 'ink'
      el.textContent = match[0]
      frag.append(el)
      last = match.index + match[0].length
    }
    if (last < text.length) frag.append(text.slice(last))
    node.replaceWith(frag)
  }
  root.querySelectorAll('a[href]').forEach((a) => {
    a.target = '_blank'
    a.rel = 'noreferrer'
  })
}

watch(
  () => [letter.value?.id, letter.value?.content],
  async () => {
    teaching.value = null
    await nextTick()
    mark()
  },
)

// ------------------------------------------------------------ teaching

const teaching = ref(null) // { kind, words, picked: Set, care, loading }
async function startTeach(kind) {
  teaching.value = { kind, words: [], picked: new Set(), care: '', loading: true }
  try {
    const found = await api.geeseWords(letter.value.id)
    if (!teaching.value) return
    teaching.value.words = found.words
    teaching.value.care = found.guess || 'new' // nothing fits: a cubby of its own, named by the first word
  } finally {
    if (teaching.value) teaching.value.loading = false
  }
}
function toggleWord(word) {
  const set = teaching.value.picked
  set.has(word) ? set.delete(word) : set.add(word)
}
const careOptions = computed(() => {
  const mine = (geese.card?.cares || []).map((c) => ({ id: c.id, name: c.name }))
  const ids = new Set(mine.map((c) => c.id))
  const more = (geese.presets || []).filter((p) => !ids.has(p.id)).map((p) => ({ id: p.id, name: `${p.name}（新的一格）` }))
  return [...mine, ...more, { id: 'new', name: '新开一格，用勾选的第一个词命名' }]
})
async function confirmTeach(withWords = true) {
  const t = teaching.value
  const words = withWords ? [...t.picked] : []
  const data = { kind: t.kind, words }
  if (t.kind === 'useful') {
    data.care = t.care === 'new' ? `new-${Date.now()}` : t.care
    data.care_name = words[0] || '其他'
  }
  const item = await teach(letter.value, data)
  if (item) teaching.value = null
}

function close() {
  geese.reading = null
}
trapFocus(box, close)
</script>

<template>
  <Transition name="reader">
    <div v-if="letter" class="backdrop" @mousedown.self="close">
      <div ref="box" class="paper" :class="{ express: letter.urgent }" role="dialog" aria-modal="true" aria-labelledby="goose-title">
        <button class="icon-btn close" title="放回去 (Esc)" @click="close"><Icon name="close" :size="16" /></button>
        <ExpressStamp v-if="letter.urgent" class="express" :size="84" :tilt="-12" />

        <header class="head">
          <div class="postmark" aria-hidden="true">
            <span class="ring"><span>{{ (letter.route_name || '').slice(0, 4) }}</span><span class="mono">{{ (letter.published || '').slice(5) }}</span></span>
          </div>
          <div class="from">
            <p class="register mono">Wild Geese Post · No. {{ serial(letter) }}<template v-if="letter.fetched_at"> · 收于 {{ new Date(letter.fetched_at * 1000).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }).replace('/', '·') }}</template></p>
            <p class="eyebrow">{{ letter.route_name }}<template v-if="letter.published"> · {{ longDate(letter.published) }}</template></p>
            <h2 id="goose-title" class="title-cn selectable">{{ letter.title }}</h2>
            <p v-if="letter.reasons?.length" class="why">
              <Icon name="goose" :size="15" />
              <template v-if="sealed">鸿雁没把它拣出来：{{ letter.reasons.join('、') }}</template>
              <template v-else>鸿雁把它夹在「{{ cubbyName || '杂信' }}」那根绳上，因为提到了{{ letter.reasons.join('、') }}</template>
            </p>
          </div>
        </header>

        <div v-if="letter.deadline" class="due-banner" :class="{ soon: letter.days_left != null && letter.days_left <= 3 }">
          <span class="due-date title-cn">{{ Number(letter.deadline.slice(5, 7)) }} 月 {{ Number(letter.deadline.slice(8)) }} 日 截止</span>
          <span v-if="left" class="due-left">{{ left }}</span>
          <span v-if="letter.deadline_text" class="due-clause faint">「{{ letter.deadline_text }}」</span>
        </div>

        <div class="content-wrap">
          <InkLoader v-if="geese.readingLoading && !letter.content" class="loader" label="鸿雁正把正文叼回来…" script="unsealing" />
          <div v-else-if="letter.content" ref="body" class="content selectable" v-html="letter.content" />
          <p v-else class="faint missing">
            正文没能取回来{{ letter.detail_error ? `（${letter.detail_error}）` : '' }}。可以去原网页看看。
          </p>
        </div>

        <section v-if="letter.attachments?.length" class="attachments">
          <p class="eyebrow">信尾附件</p>
          <a v-for="a in letter.attachments" :key="a.url" class="attachment" :href="a.url" target="_blank" rel="noreferrer">
            <Icon name="download" :size="14" />{{ a.name }}
          </a>
        </section>

        <Transition name="fold">
          <section v-if="teaching" class="teach">
            <p class="teach-title title-cn">
              {{ teaching.kind === 'useful' ? '这封对你有用。要让鸿雁以后也把这类信拣出来吗？' : '以后别送这类。要让鸿雁记住哪些词吗？' }}
            </p>
            <p v-if="teaching.loading" class="faint small">正在从标题里挑词…</p>
            <template v-else>
              <p class="faint small">勾上想记住的词；一个也不勾，就只处理这一封。</p>
              <div class="words">
                <button v-for="w in teaching.words" :key="w" class="chip" :class="{ on: teaching.picked.has(w) }" @click="toggleWord(w)">{{ w }}</button>
                <span v-if="!teaching.words.length" class="faint small">标题里没有挑出合适的词。</span>
              </div>
              <label v-if="teaching.kind === 'useful' && teaching.picked.size" class="care-pick">
                夹在哪根绳上：
                <select v-model="teaching.care" class="field">
                  <option v-for="c in careOptions" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </label>
              <div class="teach-actions">
                <button class="btn ghost small" @click="teaching = null">算了</button>
                <button class="btn small" @click="confirmTeach(false)">只{{ teaching.kind === 'useful' ? '收下' : '放回' }}这一封</button>
                <button class="btn wax small" :disabled="!teaching.picked.size" @click="confirmTeach(true)">记进名片</button>
              </div>
            </template>
          </section>
        </Transition>

        <footer class="actions">
          <a class="btn ghost small" :href="letter.link" target="_blank" rel="noreferrer"><Icon name="link" :size="14" />去原网页</a>
          <span class="spacer" />
          <button v-if="sealed" class="btn small" @click="startTeach('useful')"><Icon name="check" :size="14" />这封对我有用</button>
          <template v-else>
            <button class="btn ghost small" @click="startTeach('not')">以后别送这类</button>
            <button class="btn ghost small" :class="{ on: letter.pinned }" @click="updateLetter(letter, { pinned: !letter.pinned })">
              <Icon name="brooch" :size="14" />{{ letter.pinned ? '取下胸针' : '别上胸针' }}
            </button>
            <button v-if="!letter.appointment_id" class="btn small" @click="makeAppointment(letter)">
              <Icon name="calendar" :size="14" />写进约定
            </button>
            <button v-if="!letter.commission_id" class="btn wax small" @click="makeCommission(letter)">
              <Icon name="commission" :size="14" />记成委托
            </button>
            <span v-else class="linked"><Icon name="check" :size="14" />已记成委托</span>
          </template>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: var(--titlebar-h, 0px) 0 0 0;
  z-index: 70;
  display: grid;
  place-items: center;
  background: rgba(30, 22, 40, 0.38);
  backdrop-filter: blur(3px);
}
.paper {
  position: relative;
  /* A column, not a grid of fixed rows: the deadline banner, attachments and teaching box come and go,
     and only the body may shrink (and scroll) when the letter is long. */
  display: flex;
  flex-direction: column;
  width: min(780px, calc(100vw - 48px));
  max-height: calc(100vh - var(--titlebar-h, 0px) - 48px);
  padding: 30px 40px 18px;
  border-radius: 4px;
  background:
    repeating-linear-gradient(180deg, transparent 0 31px, color-mix(in srgb, var(--violet-ink) 7%, transparent) 31px 32px),
    linear-gradient(180deg, var(--sheet-raised), var(--sheet));
  box-shadow: var(--shadow-lift), 0 0 0 1px var(--rule);
}
.close {
  position: absolute;
  top: 10px;
  right: 10px;
}
.head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  padding-right: 24px;
}
.ring {
  display: grid;
  place-items: center;
  align-content: center;
  width: 70px;
  height: 70px;
  border-radius: 50%;
  border: 1.5px solid var(--violet-ink);
  box-shadow: inset 0 0 0 3px var(--sheet), inset 0 0 0 4px var(--violet-ink);
  color: var(--violet-ink);
  font-family: var(--font-title);
  font-size: 13px;
  line-height: 1.2;
  transform: rotate(-10deg);
  opacity: 0.85;
}
.ring .mono {
  font-size: 11px;
}
.register {
  margin: 0 0 4px;
  font-size: 11.5px;
  letter-spacing: 0.12em;
  color: var(--ink-faint);
}
.paper > .express {
  position: absolute;
  top: 40px;
  right: 50px;
  z-index: 1;
}
.paper.express .head {
  padding-right: 92px;
}
.from .eyebrow {
  margin: 0 0 4px;
}
h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 400;
  line-height: 1.45;
}
.why {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--violet-ink);
}
.due-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 14px;
  margin: 16px 0 0;
  padding: 10px 14px;
  border-left: 3px solid var(--gold);
  background: var(--gold-soft);
  border-radius: 0 var(--radius) var(--radius) 0;
}
.due-banner.soon {
  border-left-color: var(--danger);
  background: var(--danger-wash);
}
.due-date {
  font-size: 17px;
}
.due-left {
  color: var(--danger);
  font-family: var(--font-title);
}
.due-banner:not(.soon) .due-left {
  color: var(--gold);
}
.due-clause {
  flex-basis: 100%;
  font-size: 12.5px;
}
.paper > * {
  flex: none;
}
.paper > .content-wrap {
  flex: 0 1 auto;
  min-height: 120px;
  margin-top: 14px;
  overflow-y: auto;
  padding-right: 6px;
}
.loader {
  margin: 40px auto;
}
.content {
  font-size: 15.5px;
  line-height: 2;
  color: var(--ink);
}
.content :deep(p) {
  margin: 0 0 6px;
  text-indent: 0;
}
.content :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13.5px;
  line-height: 1.6;
}
.content :deep(td),
.content :deep(th) {
  border: 1px solid var(--rule-strong);
  padding: 4px 8px;
}
.content :deep(a) {
  color: var(--violet-ink);
}
.content :deep(h4) {
  margin: 10px 0 4px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 17px;
}
.content :deep(.img-note) {
  color: var(--ink-faint);
  font-size: 13px;
}
/* Highlighter-pen marks: violet for the words you care about, red ink round the deadline. */
.content :deep(mark.ink) {
  padding: 0 1px;
  background: linear-gradient(176deg, transparent 50%, color-mix(in srgb, var(--violet-ink) 42%, transparent) 50% 92%, transparent 92%);
  color: inherit;
  -webkit-box-decoration-break: clone;
  box-decoration-break: clone;
}
.content :deep(mark.due) {
  position: relative;
  background: none;
  color: var(--danger);
  font-weight: 600;
}
.content :deep(mark.due)::after {
  content: '';
  position: absolute;
  inset: -2px -6px;
  border: 1.5px solid currentColor;
  border-radius: 50% 46% 52% 48% / 60% 52% 48% 40%;
  transform: rotate(-3deg);
  opacity: 0.7;
  pointer-events: none;
}
.missing {
  margin: 30px 0;
  text-align: center;
}
.attachments {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--rule-strong);
}
.attachments .eyebrow {
  margin: 0;
  flex-basis: 100%;
}
.attachment {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 12px;
  background: var(--violet-wash);
  color: var(--violet-ink);
  font-size: 13px;
  text-decoration: none;
}
.attachment:hover {
  background: var(--violet-wash-strong);
}
.teach {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--paper);
  box-shadow: inset 0 0 0 1px var(--rule);
}
.teach p {
  margin: 0 0 6px;
}
.teach-title {
  font-size: 15px;
}
.small {
  font-size: 12.5px;
}
.words {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0;
}
.care-pick {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-soft);
}
.care-pick .field {
  width: auto;
  height: 32px;
}
.teach-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--rule);
}
.actions .spacer {
  flex: 1;
}
.btn.on {
  color: var(--gold);
}
.linked {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--emerald);
  font-size: 13px;
}
.reader-enter-from,
.reader-leave-to {
  opacity: 0;
}
.reader-enter-from .paper {
  transform: translateY(24px) rotate(-1deg) scale(0.97);
}
.reader-leave-to .paper {
  transform: translateY(12px) scale(0.98);
}
.reader-enter-active,
.reader-leave-active,
.reader-enter-active .paper,
.reader-leave-active .paper {
  transition: all 0.35s var(--ease);
}
.fold-enter-from,
.fold-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
.fold-enter-active,
.fold-leave-active {
  transition: all 0.25s var(--ease);
}
@media (max-width: 700px) {
  .paper {
    padding: 24px 18px 14px;
  }
  .head {
    grid-template-columns: minmax(0, 1fr);
  }
  .postmark {
    display: none;
  }
}
</style>
