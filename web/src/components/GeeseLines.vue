<script setup>
// 窗前的信绳：每根麻绳是名片上的一项「关心的事」，绳头钉着一张纸签。信用木夹子夹在绳上，随风轻轻晃。
// 没拆的露正面（邮戳、短标题），拆过的翻成背面；急件用红夹子、盖速达戳；别着翡翠胸针的挂在最上面一根。
// 鼠标在一封信上停一会儿（或点一下），窗边吹来一阵风：同一根绳上的信依次一晃，这一封被揭起一角、脱开夹子，
// 翻飞着转到眼前，变成一张写满详情的明信片，风里带着几片紫罗兰花瓣。移开时，风又把它卷回绳上。
// 绳下是藤编信篮（未拆的信）和铁皮信盒（旧信）。
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { geese, leftLabel, makeCommission, openLetter, serial, shortTitle, updateLetter } from '../geese.js'
import ExpressStamp from './ExpressStamp.vue'
import Brooch from './Brooch.vue'
import EmptySatchel from './EmptySatchel.vue'
import GooseFigure from './GooseFigure.vue'
import Icon from './Icon.vue'

const props = defineProps({
  drawer: { type: String, default: '' },
})
const emit = defineEmits(['drawer'])

const GAP = 142 // between letters on a line
const LEAD = 150 // the tag at the head of each line
const root = ref(null)
const width = ref(1000)

function order(list) {
  return [...list].sort((a, b) =>
    Number(Boolean(a.read_at)) - Number(Boolean(b.read_at)) ||
    Number(b.urgent) - Number(a.urgent) ||
    (b.published || '').localeCompare(a.published || ''))
}
// Only lines with letters on them are strung up. A line with more letters than the window is wide
// carries on along a second rope just below it, the letters lined up under the ones above.
const perRope = computed(() => Math.max(1, Math.floor((width.value - LEAD - 56 - 70) / GAP) + 1))
const lines = computed(() => {
  const out = []
  const pinned = geese.letters.filter((l) => l.pinned)
  if (pinned.length) out.push({ id: '_pinned', name: '别着胸针', letters: order(pinned), pinned: true })
  for (const c of geese.cubbies) {
    const letters = order(geese.letters.filter((l) => l.cubby === c.id && !l.pinned))
    if (letters.length) out.push({ id: c.id, name: c.name, letters, unread: c.unread, urgent: c.urgent })
  }
  const ropes = []
  out.forEach((line, i) => {
    for (let start = 0; start < line.letters.length; start += perRope.value) {
      const letters = line.letters.slice(start, start + perRope.value)
      const span = width.value
      const sag = Math.min(26, 10 + span / 90)
      const rope = (x) => 14 + (4 * sag * x * (span - x)) / (span * span)
      ropes.push({
        ...line,
        id: `${line.id}:${start}`,
        first: start === 0,
        total: line.letters.length,
        span,
        sag,
        tilt: i % 2 ? 0.6 : -0.5,
        path: `M4 14 Q${span / 2} ${14 + 2 * sag} ${span - 4} 14`,
        items: letters.map((l, k) => {
          const x = LEAD + 56 + k * GAP
          return { letter: l, x, y: rope(x), k }
        }),
      })
    }
  })
  return ropes
})

// ------------------------------------------------------------ the wind brings a letter to you

const CARD_W = 320
const CARD_H = 226
const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const peek = reactive({ letter: null, x: 0, y: 0, landed: false })
const card = ref(null)
const shivering = ref('')
const taken = ref('') // the letter the wind has lifted off its peg
let source = null // the envelope the card came from
let dwell = null
let leave = null
let flight = null

function hover(letter, el) {
  clearTimeout(leave)
  if (peek.letter?.id === letter.id) return
  clearTimeout(dwell)
  shivering.value = letter.id
  dwell = setTimeout(() => blow(letter, el), 350)
}
function unhover() {
  clearTimeout(dwell)
  shivering.value = ''
  clearTimeout(leave)
  leave = setTimeout(windBack, 240)
}
function stay() {
  clearTimeout(leave)
}
function press(letter, el) {
  // A letter already in front of you opens; one on the line is blown to you at once.
  if (peek.letter?.id === letter.id && peek.landed) return open(letter, el)
  clearTimeout(dwell)
  blow(letter, el)
}

async function blow(letter, el) {
  shivering.value = ''
  if (peek.letter) await windBack(true)
  const box = root.value.getBoundingClientRect()
  const r = el.querySelector('.paper').getBoundingClientRect()
  // Where it settles: above its place on the line (below it near the top of the page), never off the edges.
  const cx = Math.min(Math.max(r.left + r.width / 2 - box.left, CARD_W / 2 + 6), box.width - CARD_W / 2 - 6)
  // Above the letter if the window has room for it there, otherwise just below.
  const y = r.top - CARD_H - 18 > 70 ? r.top - box.top - CARD_H - 18 : r.bottom - box.top + 24
  Object.assign(peek, { letter, x: cx - CARD_W / 2, y, landed: false })
  source = el
  taken.value = letter.id
  gust(el, r, box)
  await nextTick()
  const node = card.value
  if (!node) return
  if (reduced()) {
    peek.landed = true
    return
  }
  // From the envelope's own place and size, through a lifted corner and a tumble, to the card in front of you.
  const dx = r.left + r.width / 2 - box.left - (peek.x + CARD_W / 2)
  const dy = r.top + r.height / 2 - box.top - (peek.y + CARD_H / 2)
  const k = r.width / CARD_W
  const P = 'perspective(1100px) '
  flight = node.animate(
    [
      { transform: `${P}translate(${dx}px, ${dy}px) scale(${k}) rotateZ(-1deg) rotateX(0deg) rotateY(0deg)`, offset: 0 },
      { transform: `${P}translate(${dx}px, ${dy - 8}px) scale(${k}) rotateZ(-9deg) rotateX(34deg) rotateY(-14deg) skewY(-3deg)`, offset: 0.16 },
      { transform: `${P}translate(${dx * 0.62 - 40}px, ${dy * 0.55 - 60}px) scale(${k * 1.7}) rotateZ(-18deg) rotateX(48deg) rotateY(-80deg) skewY(5deg)`, offset: 0.42 },
      { transform: `${P}translate(${dx * 0.18 + 14}px, ${dy * 0.12 - 22}px) scale(1.06) rotateZ(6deg) rotateX(-14deg) rotateY(-168deg) skewY(-2deg)`, offset: 0.74 },
      { transform: `${P}translate(0px, 4px) scale(0.99) rotateZ(-2deg) rotateX(4deg) rotateY(-182deg)`, offset: 0.9 },
      { transform: `${P}translate(0px, 0px) scale(1) rotateZ(-1.2deg) rotateX(0deg) rotateY(-180deg)`, offset: 1 },
    ],
    { duration: 900, easing: 'cubic-bezier(0.32, 0.6, 0.3, 1)', fill: 'forwards' },
  )
  flight.onfinish = () => (peek.landed = true)
}

// The wind takes it back to its peg.
async function windBack(quick = false) {
  clearTimeout(leave)
  const node = card.value
  const el = source
  if (!peek.letter) return
  if (node && el && !reduced()) {
    peek.landed = false
    const box = root.value.getBoundingClientRect()
    const r = el.querySelector('.paper').getBoundingClientRect()
    const dx = r.left + r.width / 2 - box.left - (peek.x + CARD_W / 2)
    const dy = r.top + r.height / 2 - box.top - (peek.y + CARD_H / 2)
    const k = r.width / CARD_W
    const P = 'perspective(1100px) '
    flight?.cancel()
    const back = node.animate(
      [
        { transform: `${P}translate(0px, 0px) scale(1) rotateZ(-1.2deg) rotateY(-180deg)` },
        { transform: `${P}translate(${dx * 0.4 + 30}px, ${dy * 0.4 - 40}px) scale(${(1 + k) / 2}) rotateZ(14deg) rotateX(30deg) rotateY(-90deg)`, offset: 0.45 },
        { transform: `${P}translate(${dx}px, ${dy}px) scale(${k}) rotateZ(-1deg) rotateX(0deg) rotateY(0deg)` },
      ],
      { duration: quick ? 260 : 560, easing: 'cubic-bezier(0.5, 0, 0.4, 1)', fill: 'forwards' },
    )
    await back.finished.catch(() => {})
  }
  taken.value = ''
  if (el && !reduced()) el.querySelector('.swing')?.animate(
    [{ transform: 'translateY(-6px) rotate(-5deg)' }, { transform: 'translateY(1px) rotate(2deg)' }, { transform: 'none' }],
    { duration: 520, easing: 'ease-out', composite: 'add' },
  )
  peek.letter = null
  source = null
}

// A gust from the window (on the right): the letters on that line swing one after another, and a few petals blow past.
function gust(el, r, box) {
  if (reduced()) return
  const line = el.closest('.track')
  const all = [...line.querySelectorAll('.env')]
  const right = Math.max(...all.map((e) => e.getBoundingClientRect().left))
  for (const other of all) {
    if (other === el) continue
    const at = other.getBoundingClientRect().left
    other.querySelector('.swing')?.animate(
      [{ transform: 'rotate(0deg)' }, { transform: 'rotate(-7deg)' }, { transform: 'rotate(3deg)' }, { transform: 'rotate(-1deg)' }, { transform: 'rotate(0deg)' }],
      { duration: 1100, delay: Math.max(0, (right - at) * 0.9), easing: 'ease-out', composite: 'add' },
    )
  }
  const layer = root.value.querySelector('.petals')
  const y0 = r.top - box.top
  for (let i = 0; i < 9; i++) {
    const petal = document.createElement('span')
    petal.className = i < 6 ? 'petal' : 'mote'
    layer.appendChild(petal)
    const from = box.width + 20 + Math.random() * 80
    const to = Math.max(-60, r.left - box.left - 220 - Math.random() * 260)
    const yA = y0 - 90 + Math.random() * 150
    const yB = yA + (Math.random() - 0.4) * 140
    const spin = (Math.random() > 0.5 ? 1 : -1) * (300 + Math.random() * 400)
    const motion = petal.animate(
      [
        { transform: `translate(${from}px, ${yA}px) rotate(0deg)`, opacity: 0 },
        { opacity: 1, offset: 0.12 },
        { transform: `translate(${(from + to) / 2}px, ${(yA + yB) / 2 - 40}px) rotate(${spin / 2}deg) rotateX(60deg)`, offset: 0.5 },
        { opacity: 0.9, offset: 0.85 },
        { transform: `translate(${to}px, ${yB}px) rotate(${spin}deg)`, opacity: 0 },
      ],
      { duration: 1300 + Math.random() * 700, delay: Math.random() * 260, easing: 'cubic-bezier(0.3, 0.2, 0.4, 1)', fill: 'both' },
    )
    motion.onfinish = () => petal.remove()
  }
}

function open(letter, el) {
  clearTimeout(dwell)
  taken.value = ''
  flight?.cancel()
  peek.letter = null
  source = null
  openLetter(letter, el)
}
function act(fn) {
  const letter = peek.letter
  windBack(true).then(() => fn(letter))
}

// ------------------------------------------------------------ the goose passes when letters arrive

const flying = ref(false)
const fresh = ref(new Set())
let flyTimer = null
watch(
  () => geese.arrival,
  (n, old) => {
    if (!n || n === old || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    clearTimeout(flyTimer)
    flying.value = false
    requestAnimationFrame(() => (flying.value = true))
    fresh.value = new Set(geese.arrivedIds)
    flyTimer = setTimeout(() => {
      flying.value = false
      fresh.value = new Set()
    }, 4200)
  },
)

let observer = null
onMounted(() => {
  observer = new ResizeObserver(() => (width.value = root.value?.clientWidth || 1000))
  observer.observe(root.value)
  nextTick(() => (width.value = root.value?.clientWidth || 1000))
})
onBeforeUnmount(() => {
  observer?.disconnect()
  clearTimeout(dwell)
  clearTimeout(leave)
  clearTimeout(flyTimer)
})

const day = (d) => (d ? `${d.slice(5, 7)}·${d.slice(8, 10)}` : '')
const mark = (l) => (l.route_name || '').replace(/学院$/, '').slice(0, 3)
const sway = (l) => (Number(serial(l)) % 9) * -0.53
</script>

<template>
  <div ref="root" class="lines">
    <div v-if="flying" class="flight" aria-hidden="true">
      <GooseFigure class="flyer" :size="96" :letter="true" />
    </div>

    <EmptySatchel v-if="!lines.length" title="窗前还没有信"
      hint="和名片上「关心的事」有关的信来了，会一封封夹在这里。没拣出来的，在下面的信篮里。" />
    <section v-for="line in lines" :key="line.id" class="line" :class="{ pinned: line.pinned, cont: !line.first }"
      :aria-label="line.first ? `${line.name}：${line.total} 封` : `${line.name}（续）`">
      <div class="row">
        <div class="track" :style="{ height: 150 + line.sag + 'px' }">
          <svg class="rope" :width="line.span" :height="40 + line.sag * 2" aria-hidden="true">
            <path :d="line.path" class="twine" />
            <path :d="line.path" class="twist" />
          </svg>
          <!-- the tag nailed at the head of the line; a rope that carries on has only its nail -->
          <div class="head" :style="{ '--tilt': line.tilt * 4 + 'deg' }">
            <span class="nail" />
            <span v-if="line.first" class="tag">
              <span class="tag-name">{{ line.name }}</span>
              <span class="tag-count mono">{{ line.unread ? `${line.unread} / ${line.total}` : line.total }}</span>
            </span>
          </div>

          <button v-for="it in line.items" :key="it.letter.id" class="env" :data-goose="it.letter.id"
            :class="{ read: it.letter.read_at, urgent: it.letter.urgent && !it.letter.read_at, pinned: it.letter.pinned, fresh: fresh.has(it.letter.id),
              shiver: shivering === it.letter.id, taken: taken === it.letter.id }"
            :style="{ left: it.x + 'px', top: it.y + 'px', '--sway': sway(it.letter) + 's', '--k': it.k }"
            :aria-label="it.letter.title" @mouseenter="hover(it.letter, $event.currentTarget)" @mouseleave="unhover"
            @focus="hover(it.letter, $event.currentTarget)" @blur="unhover" @click="press(it.letter, $event.currentTarget)">
            <span class="swing">
              <svg class="peg" viewBox="0 0 12 30" aria-hidden="true">
                <rect x="1" y="0" width="4.6" height="30" rx="1.6" class="half" />
                <rect x="6.4" y="0" width="4.6" height="30" rx="1.6" class="half" />
                <circle cx="6" cy="13" r="2.6" class="spring" />
              </svg>
              <span class="paper">
                <Brooch v-if="it.letter.pinned" class="brooch" :size="15" />
                <template v-if="!it.letter.read_at">
                  <span class="ring"><span>{{ mark(it.letter) }}</span><span class="mono">{{ day(it.letter.published) }}</span></span>
                  <ExpressStamp v-if="it.letter.urgent" class="mini-express" :size="40" :tilt="-14" />
                  <span v-else class="postage"><span /></span>
                  <span class="short">{{ shortTitle(it.letter.title, 15) }}</span>
                </template>
                <template v-else>
                  <span class="flap" />
                  <span class="broken-seal" />
                  <span class="short back">{{ shortTitle(it.letter.title, 15) }}</span>
                </template>
              </span>
              <span v-if="it.letter.deadline" class="due" :class="{ soon: it.letter.days_left != null && it.letter.days_left <= 3 }">
                <span class="thread" />
                <span class="due-tag mono">{{ it.letter.deadline.slice(5).replace('-', '/') }}</span>
              </span>
            </span>
          </button>
        </div>
      </div>
    </section>

    <!-- The basket and the tin under the lines. -->
    <div class="floor">
      <button class="basket" :class="{ open: drawer === 'unopened' }" :aria-expanded="drawer === 'unopened'" @click="emit('drawer', 'unopened')">
        <svg viewBox="0 0 150 92" aria-hidden="true">
          <g class="peek-letters">
            <rect x="34" y="8" width="44" height="32" rx="2" transform="rotate(-10 56 24)" />
            <rect x="66" y="4" width="46" height="33" rx="2" transform="rotate(8 89 20)" />
          </g>
          <path class="wicker" d="M14 34 L136 34 L124 86 Q75 92 26 86 Z" />
          <path class="weave" d="M20 46 Q75 52 130 46 M22 58 Q75 64 128 58 M24 70 Q75 76 126 70 M45 35 L40 88 M75 35 L75 90 M105 35 L110 88" />
          <path class="rim" d="M10 33 Q75 26 140 33 Q75 40 10 33 Z" />
        </svg>
        <span class="label"><span class="title-cn">未拆的信</span><span class="mono">{{ geese.unopened }}</span></span>
      </button>
      <button class="tin" :class="{ open: drawer === 'archive' }" :aria-expanded="drawer === 'archive'" @click="emit('drawer', 'archive')">
        <svg viewBox="0 0 150 92" aria-hidden="true">
          <rect class="box" x="22" y="36" width="106" height="50" rx="4" />
          <rect class="lid" x="16" y="24" width="118" height="16" rx="4" />
          <path class="band" d="M22 62 H128" />
          <rect class="plate" x="58" y="48" width="34" height="20" rx="2" />
        </svg>
        <span class="label"><span class="title-cn">旧信</span><span class="mono">{{ geese.archived }}</span></span>
      </button>
    </div>

    <div class="petals" aria-hidden="true" />

    <!-- The letter the wind brought: its envelope face first, its postcard face once it has turned to you. -->
    <div v-if="peek.letter" ref="card" class="flown" :class="{ landed: peek.landed }"
      :style="{ left: peek.x + 'px', top: peek.y + 'px', width: CARD_W + 'px', height: CARD_H + 'px' }"
      @mouseenter="stay" @mouseleave="unhover">
      <div class="face face-envelope" aria-hidden="true">
        <Brooch v-if="peek.letter.pinned" class="brooch big" :size="30" />
        <span class="pc-ring big"><span>{{ mark(peek.letter) }}</span><span class="mono">{{ day(peek.letter.published) }}</span></span>
        <ExpressStamp v-if="peek.letter.urgent && !peek.letter.read_at" class="front-express" :size="96" :tilt="-14" />
        <span v-else class="front-postage"><span /></span>
        <span class="front-title">{{ shortTitle(peek.letter.title, 15) }}</span>
      </div>
      <article class="face face-card">
        <button class="pc-body" @click="open(peek.letter, $event.currentTarget)">
          <span class="pc-top">
            <span class="pc-ring"><span>{{ mark(peek.letter) }}</span><span class="mono">{{ day(peek.letter.published) }}</span></span>
            <span class="pc-from">{{ peek.letter.route_name }}</span>
            <Brooch v-if="peek.letter.pinned" class="pc-brooch" :size="18" />
            <ExpressStamp v-if="peek.letter.urgent && !peek.letter.read_at" class="pc-express" :size="58" :tilt="-10" />
          </span>
          <span class="pc-title">{{ peek.letter.title }}</span>
          <span v-if="peek.letter.reasons?.length" class="pc-why">因为 {{ peek.letter.reasons.slice(0, 3).join(' · ') }}</span>
          <span v-if="peek.letter.deadline" class="pc-due" :class="{ soon: peek.letter.days_left != null && peek.letter.days_left <= 3 }">
            <span class="mono">{{ peek.letter.deadline.slice(5).replace('-', '/') }} 截止</span>
            <span v-if="leftLabel(peek.letter)" class="left">{{ leftLabel(peek.letter) }}</span>
          </span>
        </button>
        <footer class="pc-tools">
          <span v-if="peek.letter.commission_id" class="done">已成委托</span>
          <button v-else class="pc-btn" @click="act(makeCommission)"><Icon name="commission" :size="13" />记成委托</button>
          <button class="pc-btn" :class="{ on: peek.letter.pinned }" @click="act((l) => updateLetter(l, { pinned: !l.pinned }))">
            <Icon name="brooch" :size="13" />{{ peek.letter.pinned ? '取下胸针' : '别上胸针' }}
          </button>
          <button class="pc-btn open" @click="open(peek.letter, $event.currentTarget)"><Icon name="envelope" :size="13" />拆开</button>
        </footer>
      </article>
    </div>
  </div>
</template>

<style scoped>
.lines {
  position: relative;
  display: grid;
  gap: 4px;
  --rope: #8f6d45;
  --rope-hi: #d8bd8c;
  --peg: #d7b98a;
  --peg-edge: #9c7a4c;
  --env-a: #fffbf2;
  --env-b: #f2e7d1;
  --env-ink: #2f2638;
  --tag-paper: #fcf6e8;
}
:root[data-theme='dark'] .lines {
  --rope: #b48d5c;
  --rope-hi: #e0c48f;
  --peg: #a4855a;
  --peg-edge: #6c5233;
  --env-a: #ece2cd;
  --env-b: #dccfb4;
  --tag-paper: #e8dcc4;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) .lines {
    --rope: #b48d5c;
    --rope-hi: #e0c48f;
    --peg: #a4855a;
    --peg-edge: #6c5233;
    --env-a: #ece2cd;
    --env-b: #dccfb4;
    --tag-paper: #e8dcc4;
  }
}
/* ------------------------------------------------------------ a line */
.row {
  position: relative;
}
/* A rope that carries on hangs a little closer under the one before it. */
.line.cont {
  margin-top: -14px;
}
.track {
  position: relative;
}
.rope {
  position: absolute;
  left: 0;
  top: 0;
  overflow: visible;
  pointer-events: none;
}
.twine {
  fill: none;
  stroke: var(--rope);
  stroke-width: 2;
  stroke-linecap: round;
  filter: drop-shadow(0 3px 2px rgba(60, 40, 20, 0.18));
}
.twist {
  fill: none;
  stroke: var(--rope-hi);
  stroke-width: 1;
  stroke-dasharray: 2 4;
  opacity: 0.8;
}
.head {
  position: absolute;
  left: 0;
  top: 2px;
  display: flex;
  align-items: flex-start;
  gap: 0;
}
.nail {
  width: 10px;
  height: 10px;
  margin-top: 7px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #e9dcc0, #7c6446 70%);
  box-shadow: 0 1px 2px rgba(40, 25, 10, 0.4);
}
.tag {
  display: grid;
  gap: 1px;
  margin: 14px 0 0 -4px;
  padding: 6px 14px 7px 16px;
  min-width: 92px;
  background: var(--tag-paper);
  color: #3a2d22;
  clip-path: polygon(10px 0, 100% 0, 100% 100%, 10px 100%, 0 50%);
  filter: drop-shadow(0 2px 3px rgba(60, 40, 20, 0.22));
  transform: rotate(var(--tilt));
  transform-origin: 0 0;
}
.tag-name {
  font-family: var(--font-title);
  font-size: 15px;
  letter-spacing: 0.14em;
}
.tag-count {
  font-size: 11px;
  opacity: 0.7;
}
.pinned .tag {
  color: #24584a;
}
/* ------------------------------------------------------------ a letter on the line */
.env {
  position: absolute;
  width: 0;
  height: 0;
  padding: 0;
  z-index: 1;
}
.swing {
  position: absolute;
  left: -62px;
  top: -10px;
  display: block;
  width: 124px;
  transform-origin: 62px 4px;
  animation: sway 5.5s ease-in-out infinite alternate;
  animation-delay: var(--sway);
}
@keyframes sway {
  from {
    transform: rotate(-1.6deg);
  }
  to {
    transform: rotate(1.8deg);
  }
}
.env.fresh .swing {
  animation: clip-on 0.9s cubic-bezier(0.3, 1.4, 0.5, 1) both, sway 5.5s ease-in-out 0.9s infinite alternate;
  animation-delay: calc(1.3s + var(--k) * 0.12s), calc(2.2s + var(--k) * 0.12s);
}
@keyframes clip-on {
  from {
    transform: translateY(-80px) rotate(-12deg);
    opacity: 0;
  }
}
.peg {
  position: absolute;
  left: 56px;
  top: 0;
  z-index: 2;
  width: 12px;
  height: 30px;
}
.half {
  fill: var(--peg);
  stroke: var(--peg-edge);
  stroke-width: 0.6;
}
.spring {
  fill: none;
  stroke: #8c8c8c;
  stroke-width: 1.2;
}
.urgent .half {
  fill: #c0574b;
  stroke: #7d2b23;
}
.pinned .half {
  fill: #4f9a80;
  stroke: #24584a;
}
.paper {
  position: relative;
  display: block;
  margin-top: 16px;
  width: 124px;
  height: 88px;
  padding: 8px 9px;
  border-radius: 2px;
  background:
    linear-gradient(150deg, rgba(255, 255, 255, 0.6), transparent 45%),
    linear-gradient(180deg, var(--env-a), var(--env-b));
  color: var(--env-ink);
  text-align: left;
  box-shadow: 0 0 0 1px rgba(120, 90, 50, 0.1), 0 10px 16px -10px rgba(60, 40, 20, 0.5), 0 2px 3px -2px rgba(60, 40, 20, 0.3);
  transition: transform 0.35s var(--ease), box-shadow 0.35s var(--ease);
}
.urgent .paper {
  width: 134px;
  margin-left: -5px;
  height: 92px;
}
.pinned .paper {
  box-shadow: 0 0 0 1px rgba(46, 107, 88, 0.55), 0 10px 16px -10px rgba(60, 40, 20, 0.5);
}
.env:hover .paper,
.env:focus-visible .paper {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 0 0 1px rgba(120, 90, 50, 0.12), 0 16px 22px -12px rgba(60, 40, 20, 0.55);
}
.env:focus-visible {
  outline: none;
}
.ring {
  position: absolute;
  left: 7px;
  top: 7px;
  display: grid;
  place-items: center;
  align-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1.2px solid #6e4fa3;
  color: #6e4fa3;
  font-family: var(--font-title);
  font-size: 8.5px;
  line-height: 1.15;
  transform: rotate(-10deg);
  opacity: 0.8;
}
.ring .mono {
  font-size: 7.5px;
}
.postage {
  position: absolute;
  right: 8px;
  top: 7px;
  width: 18px;
  height: 22px;
  padding: 2px;
  background: #fffdf8;
  box-shadow: 0 1px 1px rgba(60, 40, 20, 0.3);
  transform: rotate(4deg);
}
.postage span {
  display: block;
  height: 100%;
  background: linear-gradient(160deg, #e7ddf3, #cdbbe6);
}
.pinned .postage span {
  background: linear-gradient(160deg, #d9eee4, #b2d6c4);
}
.mini-express {
  position: absolute;
  right: 2px;
  top: 4px;
}
.short {
  position: absolute;
  left: 9px;
  right: 9px;
  bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.4;
}
/* The envelope the wind has taken: only the empty peg stays on the line. */
.env.taken .paper,
.env.taken .due {
  visibility: hidden;
}
/* Waiting for the gust: the letter trembles a little first. */
.env.shiver .swing {
  animation: shiver 0.14s ease-in-out infinite alternate;
}
@keyframes shiver {
  from {
    transform: rotate(-1.4deg);
  }
  to {
    transform: rotate(1.6deg) translateY(-1px);
  }
}
.paper .brooch {
  position: absolute;
  left: 46px;
  top: 6px;
  z-index: 1;
}
/* Petals and dust carried by the wind. */
.petals {
  position: absolute;
  inset: 0;
  z-index: 19;
  overflow: hidden;
  pointer-events: none;
}
.petals :deep(.petal) {
  position: absolute;
  left: 0;
  top: 0;
  width: 13px;
  height: 9px;
  border-radius: 80% 10% 80% 10%;
  background: radial-gradient(circle at 30% 40%, #d9c4f2, #8d6ac6 75%);
  opacity: 0;
}
.petals :deep(.mote) {
  position: absolute;
  left: 0;
  top: 0;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 244, 214, 0.95);
  box-shadow: 0 0 6px rgba(255, 236, 190, 0.9);
  opacity: 0;
}
/* The back of an opened letter: its flap and the broken seal. */
.read .paper {
  background: linear-gradient(180deg, #f6f1e6, #e9e0cf);
}
.flap {
  position: absolute;
  inset: 0 0 auto 0;
  height: 46px;
  background: linear-gradient(176deg, rgba(120, 90, 50, 0.12), rgba(120, 90, 50, 0.03));
  clip-path: polygon(0 0, 100% 0, 50% 100%);
}
.broken-seal {
  position: absolute;
  left: calc(50% - 6px);
  top: 38px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #a58cc9, #6c5296);
  clip-path: polygon(0 0, 100% 0, 100% 45%, 55% 52%, 48% 100%, 0 100%);
  opacity: 0.55;
}
.short.back {
  color: #6a5f73;
  -webkit-line-clamp: 1;
}
/* The deadline on a small tag hanging from the letter by a thread. */
.due {
  position: absolute;
  left: 50%;
  top: 100%;
  display: grid;
  justify-items: center;
  transform: translateX(-50%);
}
.thread {
  width: 1px;
  height: 9px;
  background: var(--rope);
}
.due-tag {
  padding: 1px 6px;
  border-radius: 2px;
  background: var(--tag-paper);
  color: #5b5068;
  font-size: 10.5px;
  box-shadow: 0 2px 3px -1px rgba(60, 40, 20, 0.3);
  transform: rotate(-3deg);
}
.due.soon .due-tag {
  color: #a4453a;
  box-shadow: 0 0 0 1px rgba(164, 69, 58, 0.45), 0 2px 3px -1px rgba(60, 40, 20, 0.3);
}
.read .due {
  opacity: 0.7;
}
/* ------------------------------------------------------------ the letter the wind brought */
.flown {
  position: absolute;
  z-index: 20;
  transform-style: preserve-3d;
  transform: perspective(1100px) rotateZ(-1.2deg) rotateY(-180deg);
}
.face {
  position: absolute;
  inset: 0;
  border-radius: 3px;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  background:
    linear-gradient(150deg, rgba(255, 255, 255, 0.7), transparent 45%),
    linear-gradient(180deg, var(--env-a), var(--env-b));
  color: var(--env-ink);
  box-shadow: 0 0 0 1px rgba(120, 90, 50, 0.12), 0 26px 40px -18px rgba(50, 30, 15, 0.55);
}
/* The envelope face, the same as on the line, only bigger. */
.face-envelope .pc-ring.big {
  position: absolute;
  left: 18px;
  top: 18px;
  width: 88px;
  height: 88px;
  font-size: 21px;
}
.face-envelope .pc-ring.big .mono {
  font-size: 17px;
}
.front-postage {
  position: absolute;
  right: 20px;
  top: 18px;
  width: 46px;
  height: 56px;
  padding: 5px;
  background: #fffdf8;
  box-shadow: 0 1px 2px rgba(60, 40, 20, 0.3);
  transform: rotate(4deg);
}
.front-postage span {
  display: block;
  height: 100%;
  background: linear-gradient(160deg, #e7ddf3, #cdbbe6);
}
.front-express {
  position: absolute;
  right: 8px;
  top: 10px;
}
.front-title {
  position: absolute;
  left: 22px;
  right: 22px;
  bottom: 22px;
  font-size: 29px;
  line-height: 1.4;
}
.brooch.big {
  position: absolute;
  left: 112px;
  top: 14px;
}
/* The postcard face: what the letter is, at a glance. */
.face-card {
  transform: rotateY(180deg);
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
}
.pc-brooch {
  margin-left: 2px;
}
.pc-body {
  display: grid;
  gap: 8px;
  width: 100%;
  padding: 14px 16px 10px;
  text-align: left;
  color: inherit;
}
.pc-top {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
}
.pc-ring {
  display: grid;
  place-items: center;
  align-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1.4px solid #6e4fa3;
  box-shadow: inset 0 0 0 2px var(--env-a), inset 0 0 0 3px #6e4fa3;
  color: #6e4fa3;
  font-family: var(--font-title);
  font-size: 10.5px;
  line-height: 1.1;
  transform: rotate(-9deg);
}
.pc-ring .mono {
  font-size: 9px;
}
.pc-from {
  font-family: var(--font-title);
  font-size: 13px;
  letter-spacing: 0.08em;
  color: #6e4fa3;
}
.pc-express {
  position: absolute;
  right: -4px;
  top: -4px;
}
.pc-title {
  font-size: 15px;
  line-height: 1.6;
}
.pc-why {
  font-size: 12px;
  color: #6a5f73;
}
.pc-due {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding-top: 6px;
  border-top: 1px dashed rgba(120, 90, 50, 0.25);
  font-size: 12px;
  color: #5b5068;
}
.pc-due .left {
  font-family: var(--font-title);
}
.pc-due.soon .left {
  position: relative;
  padding: 0 4px;
  color: #a4453a;
}
.pc-due.soon .left::after {
  content: '';
  position: absolute;
  inset: -2px -5px;
  border: 1.4px solid currentColor;
  border-radius: 48% 52% 45% 55% / 60% 50% 50% 40%;
  transform: rotate(-4deg);
  opacity: 0.7;
}
.pc-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  padding: 6px 10px 10px;
}
.pc-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 12px;
  color: #5b5068;
  transition: background 0.2s var(--ease);
}
.pc-btn:hover {
  background: rgba(110, 79, 163, 0.1);
}
.pc-btn.open {
  background: #6e4fa3;
  color: #fff;
}
.pc-btn.on {
  color: #2e6b58;
}
.done {
  margin-right: auto;
  padding: 0 6px;
  border: 1.4px solid #2e6b58;
  border-radius: 3px;
  color: #2e6b58;
  font-family: var(--font-title);
  font-size: 11px;
  letter-spacing: 0.14em;
  transform: rotate(-6deg);
}
/* ------------------------------------------------------------ the basket and the tin */
.floor {
  display: flex;
  justify-content: flex-end;
  gap: 26px;
  margin-top: 6px;
  padding-right: 10px;
}
.basket,
.tin {
  display: grid;
  justify-items: center;
  gap: 2px;
  padding: 0;
  transition: transform 0.3s var(--ease);
}
.basket svg,
.tin svg {
  width: 120px;
  height: 74px;
  overflow: visible;
  filter: drop-shadow(0 8px 6px rgba(60, 40, 20, 0.25));
}
.basket:hover,
.tin:hover {
  transform: translateY(-3px);
}
.basket.open,
.tin.open {
  transform: translateY(-5px);
}
.peek-letters rect {
  fill: var(--env-a);
  stroke: rgba(120, 90, 50, 0.3);
  stroke-width: 0.8;
}
.wicker {
  fill: #c9a26a;
  stroke: #8a6436;
  stroke-width: 1.2;
}
.weave {
  fill: none;
  stroke: #9b7444;
  stroke-width: 1;
  opacity: 0.7;
}
.rim {
  fill: #b8905a;
  stroke: #8a6436;
  stroke-width: 1.2;
}
.box {
  fill: #9eb3b0;
  stroke: #5f7471;
  stroke-width: 1.2;
}
.lid {
  fill: #b5c7c4;
  stroke: #5f7471;
  stroke-width: 1.2;
}
.tin.open .lid {
  transform: translate(10px, -10px) rotate(-8deg);
  transform-origin: 30px 24px;
}
.lid {
  transition: transform 0.35s var(--ease);
}
.band {
  stroke: #7d918e;
  stroke-width: 1;
}
.plate {
  fill: #f4ecd9;
  stroke: #8a7a5a;
  stroke-width: 0.8;
}
.label {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 2px 10px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--sheet) 82%, transparent);
  backdrop-filter: blur(2px);
  font-size: 13.5px;
  color: var(--ink);
}
.label .mono {
  font-size: 11.5px;
  color: var(--ink-faint);
}
.open .label {
  color: var(--violet-ink);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--violet-ink) 40%, transparent);
}
/* ------------------------------------------------------------ the goose overhead */
.flight {
  position: absolute;
  inset: -40px 0 auto 0;
  height: 80px;
  z-index: 3;
  pointer-events: none;
}
.flyer {
  position: absolute;
  left: 0;
  top: 0;
  --goose-ink: var(--ink-soft);
  animation: cross 3.4s cubic-bezier(0.35, 0.1, 0.55, 0.9) forwards;
}
@keyframes cross {
  0% {
    transform: translate(-140px, 40px) rotate(-6deg);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  50% {
    transform: translate(calc(40vw - 140px), 6px) rotate(2deg);
  }
  88% {
    opacity: 1;
  }
  100% {
    transform: translate(calc(80vw - 60px), -20px) rotate(-10deg);
    opacity: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .swing,
  .env.fresh .swing,
  .flyer {
    animation: none;
  }
}
</style>
