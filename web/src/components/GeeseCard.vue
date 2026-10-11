<script setup>
// 收件人名片：告诉鸿雁你是谁、关心什么。右边是这张名片的样子；写完当场试拣一个月的信给你看。
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../api.js'
import { geese, saveCard, shortTitle } from '../geese.js'
import { trapFocus } from '../dialog.js'
import Icon from './Icon.vue'
import InkToggle from './InkToggle.vue'
import GooseFigure from './GooseFigure.vue'

const box = ref(null)
const STEPS = ['学校', '年级', '关心的事', '送信', '试拣']
const step = ref(0)
const form = reactive({ school: 'nwpu', college: '', level: 'undergrad', entry_year: null, cares: [], avoid: [], mode: 'arrive', urgent: true })
const expanded = ref('')
const newWord = reactive({})
const custom = reactive({ name: '', words: '' })
const avoidWord = ref('')
const trial = reactive({ loading: false, result: null, error: '' })
const saving = ref(false)

const thisYear = new Date().getFullYear()
const years = computed(() => Array.from({ length: 7 }, (_, i) => thisYear - 6 + i).filter((y) => y <= thisYear))
const school = computed(() => geese.schools.find((s) => s.id === form.school) || geese.schools[0])
const gradeName = computed(() => {
  if (!form.entry_year) return ''
  const now = new Date()
  const year = now.getFullYear() - form.entry_year + (now.getMonth() >= 8 ? 1 : 0)
  if (form.level === 'graduate') return year >= 1 ? `研${['一', '二', '三', '四'][year - 1] || '究生'}` : ''
  return ['大一', '大二', '大三', '大四', '大五'][year - 1] || (year > 5 ? '已经毕业' : '')
})
const chosen = computed(() => new Set(form.cares.map((c) => c.id)))

watch(
  () => geese.carding,
  (open) => {
    if (!open) return
    const card = geese.card
    Object.assign(form, {
      school: card?.school || geese.schools[0]?.id || 'nwpu',
      college: card?.college || '',
      level: card?.level || 'undergrad',
      entry_year: card?.entry_year || null,
      cares: JSON.parse(JSON.stringify(card?.cares || geese.presets.filter((p) => ['contest', 'exam', 'aid', 'course'].includes(p.id)))),
      avoid: [...(card?.avoid || ['采购', '竞选结果', '竞选公告', '招标', '中标', '询价', '成交', '比选', '维修'])],
      mode: card?.mode || 'arrive',
      urgent: card?.urgent ?? true,
    })
    step.value = 0
    trial.result = null
    trial.error = ''
  },
)

function toggleCare(preset) {
  const index = form.cares.findIndex((c) => c.id === preset.id)
  if (index >= 0) form.cares.splice(index, 1)
  else if (form.cares.length < 9) form.cares.push(JSON.parse(JSON.stringify(preset)))
}
function addKeyword(care) {
  const word = (newWord[care.id] || '').trim()
  if (word && !care.keywords.includes(word)) care.keywords.push(word)
  newWord[care.id] = ''
}
function addCustom() {
  const name = custom.name.trim()
  const words = custom.words.split(/[,，、\s]+/).map((w) => w.trim()).filter(Boolean)
  if (!name || form.cares.length >= 9) return
  form.cares.push({ id: `my-${Date.now().toString(36)}`, name, keywords: words.length ? words : [name] })
  custom.name = ''
  custom.words = ''
}
function addAvoid() {
  const word = avoidWord.value.trim()
  if (word && !form.avoid.includes(word)) form.avoid.push(word)
  avoidWord.value = ''
}

function payload() {
  return JSON.parse(JSON.stringify(form))
}

async function runTrial() {
  step.value = 4
  trial.loading = true
  trial.error = ''
  trial.result = null
  try {
    trial.result = await api.geeseTrial(payload())
  } catch (error) {
    trial.error = error.message
  } finally {
    trial.loading = false
  }
}

async function send() {
  saving.value = true
  const saved = await saveCard(payload())
  saving.value = false
  if (saved) geese.carding = false
}

const canNext = computed(() => {
  if (step.value === 2) return form.cares.length > 0
  return true
})
function next() {
  if (step.value === 3) runTrial()
  else step.value++
}

const close = () => (geese.carding = false)
trapFocus(box, close)
</script>

<template>
  <Transition name="modal">
    <div v-if="geese.carding" class="backdrop" @mousedown.self="close">
      <div ref="box" class="dialog sheet" role="dialog" aria-modal="true" aria-labelledby="card-title">
        <button class="icon-btn close" title="关上 (Esc)" @click="close"><Icon name="close" :size="16" /></button>
        <div class="form">
          <p class="eyebrow">A card for the wild geese</p>
          <h2 id="card-title" class="title-cn">{{ geese.card ? '改一改收件人名片' : '写一张收件人名片' }}</h2>
          <ol class="steps" aria-label="步骤">
            <li v-for="(name, i) in STEPS" :key="name" :class="{ on: i === step, done: i < step }">
              <button :disabled="i === 4 && step < 4" @click="i === 4 ? runTrial() : (step = i)">{{ name }}</button>
            </li>
          </ol>

          <!-- 1. school and college -->
          <section v-if="step === 0" class="pane">
            <p class="lead">鸿雁要去哪所学校取信？</p>
            <div class="choices">
              <button v-for="s in geese.schools" :key="s.id" class="choice" :class="{ on: form.school === s.id }" @click="form.school = s.id">
                <span class="title-cn">{{ s.name }}</span>
              </button>
            </div>
            <label class="field-label" for="card-college">你在哪个学院？<span class="faint">学院的通知会多看一眼，别的学院的会略过</span></label>
            <select id="card-college" v-model="form.college" class="field">
              <option value="">不选学院（只收校级通知）</option>
              <option v-for="c in school?.colleges || []" :key="c" :value="c">{{ c }}</option>
            </select>
          </section>

          <!-- 2. level and year -->
          <section v-else-if="step === 1" class="pane">
            <p class="lead">你读本科还是研究生，哪一年入学？</p>
            <div class="choices two">
              <button class="choice" :class="{ on: form.level === 'undergrad' }" @click="form.level = 'undergrad'">
                <span class="title-cn">本科生</span><span class="faint small">研究生的通知会往后放</span>
              </button>
              <button class="choice" :class="{ on: form.level === 'graduate' }" @click="form.level = 'graduate'">
                <span class="title-cn">研究生</span><span class="faint small">本科教学的通知会往后放</span>
              </button>
            </div>
            <p class="field-label">入学年份 <span class="faint">提到「{{ form.entry_year || 'XXXX' }}级」的通知会被拣出来</span></p>
            <div class="years">
              <button v-for="y in years" :key="y" class="chip" :class="{ on: form.entry_year === y }"
                @click="form.entry_year = form.entry_year === y ? null : y">{{ y }} 级</button>
            </div>
            <p v-if="gradeName" class="faint small grade">现在是{{ gradeName }}。</p>
          </section>

          <!-- 3. cares and avoids -->
          <section v-else-if="step === 2" class="pane">
            <p class="lead">关心哪些事？<span class="faint small">每勾一项，窗前就多一根信绳（最多九根）</span></p>
            <div class="presets">
              <button v-for="p in geese.presets" :key="p.id" class="chip" :class="{ on: chosen.has(p.id) }" :title="p.keywords.join('、')"
                @click="toggleCare(p)">{{ p.name }}</button>
            </div>
            <ul class="cares">
              <li v-for="care in form.cares" :key="care.id" class="care" :class="{ open: expanded === care.id }">
                <button class="care-head" @click="expanded = expanded === care.id ? '' : care.id">
                  <span class="title-cn">{{ care.name }}</span>
                  <span class="faint small ellipsis">{{ care.keywords.join('、') }}</span>
                  <Icon name="down" :size="14" class="chev" />
                </button>
                <div v-if="expanded === care.id" class="care-words">
                  <span v-for="(w, i) in care.keywords" :key="w" class="tag">{{ w }}
                    <button :title="`去掉「${w}」`" @click="care.keywords.splice(i, 1)"><Icon name="close" :size="11" /></button>
                  </span>
                  <input v-model="newWord[care.id]" class="field mini" maxlength="20" placeholder="加一个词，回车"
                    @keydown.enter.prevent="addKeyword(care)" />
                  <button class="link danger" @click="form.cares.splice(form.cares.indexOf(care), 1)">不要这一格</button>
                </div>
              </li>
            </ul>
            <div v-if="form.cares.length < 9" class="custom">
              <input v-model="custom.name" class="field mini" maxlength="12" placeholder="新的一格，如：航模" />
              <input v-model="custom.words" class="field mini wide" maxlength="120" placeholder="相关的词，用顿号隔开：无人机、飞控" @keydown.enter.prevent="addCustom" />
              <button class="btn small" :disabled="!custom.name.trim()" @click="addCustom"><Icon name="plus" :size="14" />加上</button>
            </div>
            <p class="field-label">不想看的事 <span class="faint">标题里出现这些词，就直接放进未拆的信</span></p>
            <div class="avoid">
              <span v-for="(w, i) in form.avoid" :key="w" class="tag muted">{{ w }}
                <button :title="`去掉「${w}」`" @click="form.avoid.splice(i, 1)"><Icon name="close" :size="11" /></button>
              </span>
              <input v-model="avoidWord" class="field mini" maxlength="20" placeholder="加一个，回车" @keydown.enter.prevent="addAvoid" />
            </div>
          </section>

          <!-- 4. how to deliver -->
          <section v-else-if="step === 3" class="pane">
            <p class="lead">鸿雁什么时候来送信？</p>
            <div class="choices two">
              <button class="choice" :class="{ on: form.mode === 'arrive' }" @click="form.mode = 'arrive'">
                <span class="title-cn">随到随取</span>
                <span class="faint small">每条驿路按自己的节奏去取，默认两小时一次</span>
              </button>
              <button class="choice" :class="{ on: form.mode === 'morning' }" @click="form.mode = 'morning'">
                <span class="title-cn">晨间一批</span>
                <span class="faint small">每天早上取一次，和 Violet 的来信一起到</span>
              </button>
            </div>
            <InkToggle v-model="form.urgent" label="急件敲门"
              hint="很相关、或三天内截止的信，弹一条系统通知；同时到的几封合成一条，夜里 23 点到 7 点不打扰。" />
          </section>

          <!-- 5. the trial -->
          <section v-else class="pane trial">
            <div v-if="trial.loading" class="flying">
              <div class="vee" aria-hidden="true">
                <GooseFigure v-for="i in 5" :key="i" class="vee-goose" :size="54" :delay="i * 0.11" :letter="i === 1"
                  :style="{ '--k': Math.abs(i - 3) + 0, '--side': i < 3 ? -1 : 1 }" />
              </div>
              <p class="title-cn">鸿雁出发了，正把这一个月的信一封封叼回来…</p>
              <p class="faint small">
                <template v-if="geese.progress">{{ geese.progress.route || '驿路' }} · {{ geese.progress.done }}/{{ geese.progress.total }}</template>
                <template v-else>第一次去各处取信要一会儿，每个网站都要客客气气地敲门。</template>
              </p>
            </div>
            <div v-else-if="trial.error" class="faint">试拣没能完成：{{ trial.error }}</div>
            <div v-else-if="trial.result" class="result">
              <p class="verdict title-cn">
                按这张名片，这个月你会收到 <b>{{ trial.result.kept_count }}</b> 封，
                另外 <b>{{ trial.result.sealed }}</b> 封会放进「未拆的信」。
              </p>
              <p class="faint small">
                <template v-for="(c, i) in trial.result.cubbies" :key="c.id">{{ i ? '、' : '' }}{{ c.name }} {{ c.count }}</template>
                <template v-if="!trial.result.cubbies.length">这个月没有拣出和你有关的通知，可以回去多勾几项关心的事。</template>
              </p>
              <ul class="kept">
                <li v-for="l in trial.result.kept.slice(0, 12)" :key="l.id">
                  <span class="mono faint">{{ (l.published || '').slice(5) }}</span>
                  <span class="ellipsis">{{ shortTitle(l.title, 40) }}</span>
                  <span class="why faint small ellipsis">{{ l.reasons.join(' · ') }}</span>
                </li>
              </ul>
              <p v-for="r in trial.result.routes.filter((x) => x.error)" :key="r.id" class="faint small warn">
                <Icon name="route" :size="13" />{{ r.name }}{{ r.column ? '·' + r.column : '' }} 这次没取到：{{ r.error.split(':').slice(1).join(':') }}
              </p>
            </div>
          </section>

          <div class="actions">
            <button v-if="step > 0" class="btn ghost" :disabled="trial.loading" @click="step = Math.min(step, 4) - 1">回去改改</button>
            <span class="spacer" />
            <button v-if="step < 4" class="btn" :class="{ wax: step === 3 }" :disabled="!canNext" @click="next">
              {{ step === 3 ? '试拣一下' : '下一步' }}
            </button>
            <button v-else class="btn wax" :disabled="trial.loading || saving" @click="send">
              <Icon name="goose" :size="16" />就这样，寄出名片
            </button>
          </div>
        </div>

        <!-- The card itself -->
        <div class="preview" aria-hidden="true">
          <div class="calling-card">
            <p class="card-eyebrow">收件人 · Recipient</p>
            <GooseFigure class="emblem" :size="62" still :letter="false" />
            <p class="card-name title-cn">{{ form.college || school?.name || '一位同学' }}</p>
            <p class="card-line">
              {{ form.entry_year ? `${form.entry_year} 级` : '入学年份未填' }} · {{ form.level === 'graduate' ? '研究生' : '本科' }}<template v-if="gradeName"> · {{ gradeName }}</template>
            </p>
            <hr />
            <p class="card-label">关心</p>
            <div class="card-cares">
              <span v-for="c in form.cares" :key="c.id" class="card-stamp">{{ c.name }}</span>
              <span v-if="!form.cares.length" class="faint small">还没有勾选</span>
            </div>
            <p v-if="form.avoid.length" class="card-label">不看</p>
            <p v-if="form.avoid.length" class="card-avoid">{{ form.avoid.slice(0, 6).join(' · ') }}{{ form.avoid.length > 6 ? ' …' : '' }}</p>
            <p class="card-foot">
              <span>{{ form.mode === 'morning' ? '晨间一批' : '随到随取' }}{{ form.urgent ? ' · 急件敲门' : '' }}</span>
              <span class="seal title-cn">{{ school?.short || '鸿雁' }}</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: var(--titlebar-h, 0px) 0 0 0;
  z-index: 80;
  display: grid;
  place-items: center;
  background: rgba(30, 22, 40, 0.38);
  backdrop-filter: blur(3px);
}
.dialog {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 290px;
  gap: 30px;
  width: min(900px, calc(100vw - 48px));
  max-height: calc(100vh - var(--titlebar-h, 0px) - 48px);
  overflow-y: auto;
  padding: 30px 34px 24px;
}
.close {
  position: absolute;
  top: 12px;
  right: 12px;
}
.form {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
}
.form h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 400;
}
.eyebrow {
  margin: 0;
}
.steps {
  display: flex;
  gap: 4px;
  margin: 6px 0 4px;
  padding: 0;
  list-style: none;
  counter-reset: step;
}
.steps li {
  counter-increment: step;
}
.steps button {
  padding: 3px 10px 3px 6px;
  border-radius: 12px;
  font-size: 12.5px;
  color: var(--ink-faint);
}
.steps button::before {
  content: counter(step);
  display: inline-grid;
  place-items: center;
  width: 17px;
  height: 17px;
  margin-right: 5px;
  border-radius: 50%;
  border: 1px solid currentColor;
  font-size: 10.5px;
}
.steps li.done button {
  color: var(--violet-ink);
}
.steps li.on button {
  background: var(--violet-wash);
  color: var(--violet-ink);
}
.pane {
  display: grid;
  gap: 8px;
  min-height: 300px;
  align-content: start;
}
.lead {
  margin: 8px 0 2px;
  font-family: var(--font-title);
  font-size: 17px;
}
.small {
  font-size: 12.5px;
}
.field-label {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--ink-soft);
}
.choices {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}
.choices.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.choice {
  display: grid;
  gap: 2px;
  padding: 12px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--rule-strong);
  text-align: left;
  transition: border-color 0.2s var(--ease), background 0.2s var(--ease);
}
.choice:hover {
  background: var(--violet-wash);
}
.choice.on {
  border-color: var(--violet-ink);
  background: var(--violet-wash);
  box-shadow: inset 0 0 0 1px var(--violet-ink);
}
.choice .title-cn {
  font-size: 16px;
}
.years,
.presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.grade {
  margin: 0;
}
.cares {
  display: grid;
  gap: 4px;
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
}
.care {
  border-radius: var(--radius);
  background: var(--paper);
}
.care-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  text-align: left;
}
.chev {
  color: var(--ink-faint);
  transition: transform 0.2s var(--ease);
}
.care.open .chev {
  transform: rotate(180deg);
}
.care-words,
.avoid {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 0 10px 10px;
}
.avoid {
  padding: 0;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 4px 1px 9px;
  border-radius: 11px;
  background: var(--violet-wash);
  color: var(--violet-ink);
  font-size: 13px;
}
.tag.muted {
  background: var(--danger-wash);
  color: var(--danger);
}
.tag button {
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  opacity: 0.6;
}
.tag button:hover {
  opacity: 1;
}
.field.mini {
  width: 150px;
  height: 30px;
  font-size: 13px;
}
.field.mini.wide {
  width: 230px;
}
.custom {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
.link {
  font-size: 12.5px;
  color: var(--violet-ink);
}
.link:hover {
  text-decoration: underline;
}
.link.danger {
  margin-left: auto;
  color: var(--danger);
}
.trial {
  align-content: center;
}
.flying {
  display: grid;
  justify-items: center;
  gap: 8px;
  text-align: center;
}
.flying p {
  margin: 0;
}
.vee {
  position: relative;
  width: 300px;
  height: 120px;
  animation: drift 3s ease-in-out infinite alternate;
}
.vee-goose {
  position: absolute;
  left: calc(50% - 27px + var(--side) * var(--k) * 58px);
  top: calc(var(--k) * 26px);
  --goose-ink: var(--ink-soft);
}
@keyframes drift {
  from {
    transform: translate(-10px, 4px);
  }
  to {
    transform: translate(10px, -4px);
  }
}
.verdict {
  margin: 0;
  font-size: 17px;
  line-height: 1.6;
}
.verdict b {
  color: var(--violet-ink);
  font-size: 22px;
  font-weight: 400;
}
.kept {
  display: grid;
  gap: 2px;
  max-height: 250px;
  margin: 6px 0 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}
.kept li {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) minmax(0, 150px);
  gap: 8px;
  align-items: baseline;
  padding: 5px 4px;
  border-bottom: 1px dashed var(--rule);
  font-size: 13.5px;
}
.warn {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 2px 0 0;
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}
.actions .spacer {
  flex: 1;
}
/* The calling card: thick cream stock, letterpressed type, a gold goose. */
.preview {
  display: grid;
  align-content: center;
  padding-left: 26px;
  border-left: 1px dashed var(--rule-strong);
}
.calling-card {
  position: relative;
  padding: 20px 20px 16px;
  border-radius: 5px;
  background:
    radial-gradient(120% 80% at 20% 0%, rgba(255, 255, 255, 0.55), transparent 60%),
    linear-gradient(160deg, #fbf4e4, #efe3c8);
  color: #3a2f45;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.9) inset, 0 2px 3px rgba(60, 40, 20, 0.12), 0 22px 30px -20px rgba(60, 40, 20, 0.5);
  transform: rotate(1.4deg);
}
.calling-card p {
  margin: 0;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.7);
}
.card-eyebrow {
  font-size: 10.5px;
  letter-spacing: 0.25em;
  color: #8a7a64;
  text-transform: uppercase;
}
.emblem {
  position: absolute;
  top: 12px;
  right: 12px;
  --goose-ink: #b08a3e;
  --goose-cheek: #f6ecd5;
  filter: drop-shadow(0 1px 0 rgba(255, 255, 255, 0.8));
}
.card-name {
  margin-top: 16px !important;
  font-size: 20px;
  line-height: 1.35;
  color: #2a2238;
}
.card-line {
  margin-top: 4px !important;
  font-size: 13px;
  color: #5b5068;
}
.calling-card hr {
  margin: 14px 0 10px;
  border: 0;
  border-top: 1px solid rgba(58, 47, 69, 0.18);
}
.card-label {
  margin-top: 6px !important;
  font-size: 11px;
  letter-spacing: 0.2em;
  color: #8a7a64;
}
.card-cares {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 4px;
}
.card-stamp {
  padding: 1px 8px;
  border: 1px solid rgba(94, 63, 143, 0.55);
  border-radius: 2px;
  color: #5e3f8f;
  font-family: var(--font-title);
  font-size: 12.5px;
}
.card-avoid {
  margin-top: 3px !important;
  font-size: 12px;
  color: #8a6a60;
}
.card-foot {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  margin-top: 16px !important;
  font-size: 11.5px;
  color: #6a5f73;
}
.seal {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  border: 1.5px solid #a4453a;
  color: #a4453a;
  font-size: 12px;
  transform: rotate(-12deg);
  opacity: 0.8;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .dialog {
  transform: translateY(14px) scale(0.98);
}
.modal-enter-active,
.modal-leave-active,
.modal-enter-active .dialog {
  transition: all 0.3s var(--ease);
}
@media (max-width: 820px) {
  .dialog {
    grid-template-columns: minmax(0, 1fr);
  }
  .preview {
    display: none;
  }
}
</style>
