<script setup>
// 回信：铺开一张信纸，写给 Violet，或者寄给未来的自己。
// 停笔约一秒自动收好；输入法拼字时不打断；离开页面前先存。
// 信纸、字、火漆、邮票与信封从文具匣里挑，封缄时连同落款一起记在这封信上。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { signoff } from '../address.js'
import { promptFor } from '../prompts.js'
import { resolve, paperVars, LETTERHEADS } from '../stationery.js'
import { shrinkImage } from '../images.js'
import { api, photoUrl, libraryCoverUrl } from '../api.js'
import { store, toast, go } from '../store.js'
import { desk, refresh } from '../desk.js'
import { current } from '../player.js'
import { sound } from '../sound.js'
import { flyTo, typeInto } from '../motion.js'
import { addDays, isoDate, longDate, relativeDay, timeOfDay } from '../format.js'
import { MOODS, WEATHERS } from '../stamps.js'
import MoodStamp from '../components/MoodStamp.vue'
import SealImpression from '../components/SealImpression.vue'
import LetterEnvelope from '../components/LetterEnvelope.vue'
import StationeryPicker from '../components/StationeryPicker.vue'
import Icon from '../components/Icon.vue'
import Nunkish from '../components/Nunkish.vue'
import CoverArt from '../components/CoverArt.vue'
import CipherText from '../components/CipherText.vue'

const reply = computed(() => desk.writing)
const body = ref('')
const status = ref('saved') // saved | dirty | saving | error
const savedAt = ref(0)
const error = ref('')
const covered = ref(false)
const composing = ref(false)
const textarea = ref(null)
const fileInput = ref(null)
const listens = ref([])
const sealing = ref(null) // null | 'choose' | 'folding'
const recipient = ref('violet')
const deliverOn = ref(addDays(isoDate(), 365))
const dragging = ref(false)
const day = ref(null)
const used = ref(new Set())
let caret = null // where the writer last left the cursor; gleaned lines go there
let timer = null
let pending = {}

const sealed = computed(() => Boolean(reply.value?.sealed_at))
const set = computed(() => resolve(reply.value?.stationery))
const sheetVars = computed(() => paperVars(set.value))
const letterhead = computed(() => LETTERHEADS[set.value.letterhead] || LETTERHEADS.none)
const signed = computed(() => (sealed.value ? reply.value?.stationery?.signoff || '' : signoff()))
const kitTab = ref('paper')
const kitOpen = ref(false)

function setStationery(patch) {
  if (sealed.value) return
  const stationery = { ...(reply.value.stationery || {}), ...patch }
  desk.writing = { ...reply.value, stationery }
  queue({ stationery }, 100)
}
const words = computed(() => body.value.replace(/\s/g, '').length)
const statusText = computed(() => {
  if (status.value === 'saving') return '正在收好…'
  if (status.value === 'dirty') return '还没收好'
  if (status.value === 'error') return `没能保存：${error.value}`
  return savedAt.value ? `已收好 · ${timeOfDay(savedAt.value)}` : '已收好'
})
const FUTURE = [
  { label: '一个月后', days: 30 },
  { label: '半年后', days: 182 },
  { label: '一年后', days: 365 },
  { label: '三年后', days: 1095 },
]

function load(r) {
  if (!r) return
  body.value = r.body || ''
  status.value = 'saved'
  savedAt.value = r.updated || 0
  covered.value = false
  sealing.value = null
  recipient.value = r.recipient || 'violet'
  pending = {}
  used.value = new Set()
  caret = null
  api.day(r.date).then((d) => {
    day.value = d
    listens.value = d.listens
  }).catch(() => {
    day.value = null
    listens.value = []
  })
  nextTick(grow)
}
watch(() => desk.writing?.id, () => load(desk.writing), { immediate: true })

function grow() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.max(el.scrollHeight, 34 * 12) + 'px'
}

// Typewriter scrolling: while writing at the end, keep the line being typed in the middle of the page.
function follow() {
  const el = textarea.value
  // Only once the writing has run past the blank lines of an empty sheet does the bottom equal the caret.
  if (!el || el.selectionEnd < body.value.length - 2 || el.scrollHeight <= 34 * 12 + 4) return
  const page = el.closest('.page')
  const rect = el.getBoundingClientRect()
  const caretY = rect.bottom - 40
  const target = page.clientHeight * 0.55
  if (caretY > target + 60) page.scrollBy({ top: caretY - target, behavior: 'smooth' })
}

function queue(fields, delay = 900) {
  Object.assign(pending, fields)
  status.value = 'dirty'
  clearTimeout(timer)
  timer = setTimeout(flush, delay)
}

async function flush() {
  clearTimeout(timer)
  if (!reply.value || !Object.keys(pending).length || composing.value) return
  const fields = pending
  pending = {}
  status.value = 'saving'
  try {
    const saved = await api.updateReply(reply.value.id, { ...fields, revision: reply.value.revision })
    desk.writing = { ...saved }
    savedAt.value = saved.updated
    status.value = Object.keys(pending).length ? 'dirty' : 'saved'
    if (status.value === 'dirty') queue({}, 300)
  } catch (e) {
    if (e.code === 'conflict' && e.current) {
      // Keep what was typed here; adopt the newer revision and save again.
      desk.writing = e.current
      pending = { ...fields, body: body.value }
      queue({}, 50)
      return
    }
    pending = { ...fields, ...pending }
    error.value = e.message
    status.value = 'error'
  }
}

function onInput() {
  grow()
  follow()
  queue({ body: body.value })
}

// 提笔话题 for an empty sheet; it follows the mood stamp once one is pressed on.
const promptTurn = ref(0)
const prompt = computed(() => promptFor(reply.value?.date || isoDate(), reply.value?.mood || '', promptTurn.value))
function usePrompt() {
  body.value = `${prompt.value}\n`
  onInput()
  nextTick(() => {
    textarea.value?.focus()
    textarea.value?.setSelectionRange(body.value.length, body.value.length)
  })
}

function onKey(event) {
  if (event.key.length === 1 || event.key === 'Enter' || event.key === 'Backspace') sound.key()
}

// 拾句: sentences gleaned from the day — what was delivered, what played, the season — ready to type in.
const WEATHER_LINES = { clear: '今天天气很好，阳光一直照到书桌上。', cloudy: '今天云很多，太阳时有时无。',
  overcast: '天阴了一整天。', rain: '外面一直在下雨。', snow: '下雪了。', wind: '今天风很大。', fog: '早上起了雾，远处都看不清。',
  storm: '傍晚打了雷。' }
const gleanings = computed(() => {
  const d = day.value
  const r = reply.value
  if (!d || !r || sealed.value) return []
  const out = []
  const season = d.almanac?.season
  if (d.almanac?.term) out.push(`今天是${d.almanac.term}。`)
  else if (season) out.push(`${season.term}${'一二三'[season.index]}候，书上说「${season.hou}」。`)
  for (const f of d.almanac?.festivals || []) out.push(`今天是${f}。`)
  if (r.weather && WEATHER_LINES[r.weather]) out.push(WEATHER_LINES[r.weather])
  const done = d.completed.map((c) => `「${c.title}」`)
  if (done.length) out.push(`${relativeDay(r.date) === '今天' ? '今天' : '那天'}办完了${done.slice(0, 3).join('、')}${done.length > 3 ? '，还有别的几件' : ''}。`)
  for (const a of d.appointments.slice(0, 2)) {
    out.push(a.kind === 'anniversary' ? `今天是「${a.title}」${a.years ? `，第 ${a.years} 年了` : ''}。` : `${a.start ? a.start + '，' : ''}${a.title}。`)
  }
  const top = d.listens[0]
  if (top) out.push(top.count >= 3 ? `《${top.title}》今天听了好几遍。` : `今天听了《${top.title}》。`)
  if (d.focus_seconds >= 600) out.push(`专心代笔了 ${Math.round(d.focus_seconds / 60)} 分钟。`)
  for (const p of (d.pressed || []).slice(0, 2)) out.push(p.note ? `把《${p.title}》压进了书里，${p.note}。` : `把《${p.title}》压进了书里。`)
  return out.filter((line) => !used.value.has(line) && !body.value.includes(line)).slice(0, 6)
})

async function glean(line) {
  const el = textarea.value
  if (!el || sealed.value) return
  used.value = new Set([...used.value, line])
  const at = caret ?? body.value.length
  el.focus({ preventScroll: true })
  el.selectionStart = el.selectionEnd = at
  sound.typing(Math.min(14, line.length), 0.05)
  await typeInto(el, line, (value) => {
    body.value = value
    grow()
  })
  caret = el.selectionEnd
  onInput()
}

function onBlur(event) {
  caret = event.target.selectionEnd
  flush()
}

function setStamp(kind, value) {
  if (sealed.value) return
  const next = reply.value[kind] === value ? null : value
  desk.writing = { ...reply.value, [kind]: next }
  queue({ [kind]: next }, 200)
  if (next) sound.stamp()
}

function clipSong(track) {
  if (sealed.value) return
  const song = track ? { id: track.track_id || track.id, title: track.title, artist: track.artist, album: track.album,
    has_cover: Boolean(track.has_cover) } : null
  desk.writing = { ...reply.value, song }
  queue({ song }, 200)
}

function toggleAttach() {
  const value = !reply.value.attach_commissions
  desk.writing = { ...reply.value, attach_commissions: value ? 1 : 0 }
  queue({ attach_commissions: value }, 200)
}

// Photos are shrunk in the page before upload: 1600 px on the long side is plenty for a letter.
async function addPhotos(files) {
  if (sealed.value) return
  const list = [...files].filter((f) => f.type.startsWith('image/')).slice(0, 12 - (reply.value.photos || []).length)
  if (!list.length) return toast('只能贴图片，一封信最多 12 张', 'warning')
  for (const file of list) {
    try {
      const { name } = await api.uploadPhoto(await shrinkImage(file))
      desk.writing = { ...reply.value, photos: [...(reply.value.photos || []), name] }
      queue({ photos: desk.writing.photos }, 100)
    } catch (e) {
      toast(e.message, 'error')
    }
  }
}

function removePhoto(name) {
  desk.writing = { ...reply.value, photos: reply.value.photos.filter((p) => p !== name) }
  queue({ photos: desk.writing.photos }, 100)
}

function onDrop(event) {
  dragging.value = false
  addPhotos(event.dataTransfer.files)
}

async function seal() {
  if (!body.value.trim()) return toast('信纸还是空的', 'warning')
  await flush()
  if (status.value === 'error') return toast('先让信收好，再封缄', 'warning')
  try {
    const result = await api.sealReply(reply.value.id, {
      recipient: recipient.value,
      deliver_on: recipient.value === 'future' ? deliverOn.value : null,
      revision: reply.value.revision,
      stationery: { ...set.value, signoff: signoff() },
    })
    sealing.value = 'folding'
    sound.seal()
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    setTimeout(() => {
      flyTo(document.querySelector('.fold-envelope') || { x: innerWidth / 2, y: innerHeight / 2 }, 'mailbox', 'letter')
      desk.writing = result
      sealing.value = null
      toast(recipient.value === 'future' ? `信已寄往 ${longDate(deliverOn.value)}，那天它会回到书桌上` : '回信已寄出，Violet 收到了', 'success', 6000)
      refresh()
      go('desk')
    }, reduced ? 0 : 1900)
  } catch (e) {
    toast(e.message, 'error', 6000)
  }
}

async function unseal() {
  try {
    desk.writing = await api.unsealReply(reply.value.id)
    load(desk.writing)
    refresh()
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function newSheet() {
  await flush()
  try {
    desk.writing = await api.createReply({ date: isoDate() })
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function leave() {
  await flush()
  refresh()
  go('desk')
}

const stopViewWatch = watch(() => store.view, (view, old) => {
  if (old === 'write' && view !== 'write') {
    flush()
    refresh()
  }
})
const onHide = () => document.visibilityState === 'hidden' && flush()
onMounted(() => {
  document.addEventListener('visibilitychange', onHide)
  window.addEventListener('beforeunload', flush)
  nextTick(() => textarea.value?.focus({ preventScroll: true }))
})
onBeforeUnmount(() => {
  flush()
  stopViewWatch()
  document.removeEventListener('visibilitychange', onHide)
  window.removeEventListener('beforeunload', flush)
})
</script>

<template>
  <div v-if="reply" class="write" :class="{ folding: sealing === 'folding' }">
    <div class="topbar">
      <button class="btn small ghost" @click="leave"><Icon name="chevron" :size="14" class="back" />回到书桌</button>
      <span class="status" :class="status" role="status">{{ statusText }}</span>
      <span class="faint small">{{ words }} 字</span>
      <button class="btn small ghost" :class="{ on: covered }" title="用泰尔西斯文字遮住字迹，旁人看不懂，你照样能写" @click="covered = !covered">
        <Icon name="cover" :size="15" />{{ covered ? '掀开' : '遮信' }}
      </button>
      <button v-if="sealed" class="btn small ghost" @click="newSheet"><Icon name="plus" :size="14" />再写一封</button>
    </div>

    <div class="room">
      <article class="paper letter-sheet daylight" :class="[{ dragging, sealed }, `ruling-${set.ruling}`, `paper-${set.paper}`]"
        :style="sheetVars" @dragover.prevent="dragging = !sealed" @dragleave="dragging = false" @drop.prevent="onDrop">
        <div v-if="set.letterhead !== 'none'" class="letterhead" aria-hidden="true">
          <img v-if="letterhead.url" :src="letterhead.url" alt="" />
          <span v-else class="post">C.H. POSTAL COMPANY<small>LEIDEN · AUTO MEMORY DOLL SERVICE</small></span>
        </div>
        <header class="paper-head">
          <div>
            <p class="to title-cn">致 {{ reply.recipient === 'future' && sealed ? '未来的我' : recipient === 'future' ? '未来的我' : 'Violet' }}：</p>
            <p class="dateline faint">{{ longDate(reply.date) }} · {{ relativeDay(reply.date) }}</p>
          </div>
          <div class="pinned">
            <MoodStamp v-if="reply.mood" :value="reply.mood" :size="52" :tilt="-5" />
            <MoodStamp v-if="reply.weather" kind="weather" :value="reply.weather" :size="46" :tilt="7" />
          </div>
        </header>

        <div v-if="!sealed && !body.trim()" class="prompt">
          <span class="prompt-text">{{ prompt }}</span>
          <button class="link" title="把这句写进信里，从它开始" @click="usePrompt">用这句开头</button>
          <button class="link" @click="promptTurn++">换一句</button>
        </div>
        <textarea ref="textarea" v-model="body" class="sheet-text selectable" :readonly="sealed"
          :placeholder="sealed ? '' : '从这里写起……'" spellcheck="false" aria-label="回信正文"
          @input="onInput" @keydown="onKey" @compositionstart="composing = true"
          @compositionend="composing = false; onInput()" @blur="onBlur" />

        <div v-if="reply.photos?.length" class="photos">
          <figure v-for="(name, i) in reply.photos" :key="name" class="polaroid" :style="{ '--tilt': (i % 2 ? 2.5 : -2) + 'deg' }">
            <img :src="photoUrl(name)" alt="夹在信里的照片" loading="lazy" />
            <button v-if="!sealed" class="icon-btn remove" title="取下这张照片" @click="removePhoto(name)"><Icon name="close" :size="13" /></button>
          </figure>
        </div>

        <div v-if="reply.song" class="song-ticket">
          <CoverArt :src="reply.song.has_cover ? libraryCoverUrl(reply.song.id) : ''" :size="42" :seed="reply.song.title" />
          <div>
            <p class="eyebrow small-eyebrow">今天的歌</p>
            <p class="title-text">{{ reply.song.title }}<span class="faint"> · {{ reply.song.artist || '佚名' }}</span></p>
          </div>
          <button v-if="!sealed" class="icon-btn" title="把歌取下来" @click="clipSong(null)"><Icon name="close" :size="14" /></button>
        </div>

        <footer class="sign">
          <span v-if="signed" class="signed">{{ signed }}</span>
          <span class="faint">—— {{ timeOfDay(reply.created) }}，写于书桌前</span>
          <Nunkish text="yours" :size="13" class="sig" />
        </footer>

        <CipherText v-if="textarea" :text="body" :veiled="covered" :target="textarea" :ruled="6" />
        <div v-if="dragging" class="drop-hint title-cn">松开，把照片夹进信里</div>
      </article>

      <aside class="kit" aria-label="邮票夹">
        <template v-if="!sealed">
          <section class="stationery">
            <button class="kit-title drawer" :aria-expanded="kitOpen" @click="kitOpen = !kitOpen">
              文具匣
              <span class="mini" aria-hidden="true">
                <span class="mini-paper" :style="{ backgroundImage: sheetVars['--paper-img'] }" />
                <SealImpression :color="set.seal_color" :motif="set.seal_motif" :initials="set.seal_initials" :size="24" />
              </span>
              <Icon name="chevron" :size="13" class="caret" :class="{ open: kitOpen }" />
            </button>
            <StationeryPicker v-if="kitOpen" v-model:tab="kitTab" :set="set" @change="setStationery" />
          </section>
          <section>
            <h3 class="kit-title">心情邮票</h3>
            <div class="stamps">
              <button v-for="(m, key) in MOODS" :key="key" class="stamp-btn" :class="{ on: reply.mood === key }"
                :aria-pressed="reply.mood === key" :title="m.label" @click="setStamp('mood', key)">
                <MoodStamp :value="key" :size="40" />
              </button>
            </div>
          </section>
          <section>
            <h3 class="kit-title">天气</h3>
            <div class="stamps">
              <button v-for="(w, key) in WEATHERS" :key="key" class="stamp-btn" :class="{ on: reply.weather === key }"
                :aria-pressed="reply.weather === key" :title="w.label" @click="setStamp('weather', key)">
                <MoodStamp kind="weather" :value="key" :size="34" />
              </button>
            </div>
          </section>
          <section v-if="gleanings.length">
            <h3 class="kit-title" title="从这一天的事里拾一句，点一下就打进信里">拾句</h3>
            <div class="gleanings">
              <button v-for="line in gleanings" :key="line" class="glean" @click="glean(line)">{{ line }}</button>
            </div>
          </section>
          <section>
            <h3 class="kit-title">一日一曲</h3>
            <button v-if="current && reply.song?.id !== current.id" class="song-option" @click="clipSong(current)">
              <Icon name="music" :size="14" /><span class="ellipsis">夹进正在听的「{{ current.title }}」</span>
            </button>
            <button v-for="t in listens.filter((l) => l.track_id !== reply.song?.id && l.track_id !== current?.id).slice(0, 4)"
              :key="t.track_id" class="song-option" @click="clipSong(t)">
              <Icon name="music" :size="14" /><span class="ellipsis">{{ t.title }}</span><span class="faint count">×{{ t.count }}</span>
            </button>
            <p v-if="!current && !listens.length" class="faint small">今天还没听歌。在书信匣里放一首，就能把它夹进信里。</p>
          </section>
          <section>
            <h3 class="kit-title">照片</h3>
            <button class="btn small" @click="fileInput.click()"><Icon name="photo" :size="14" />贴一张照片</button>
            <p class="faint small">也可以直接拖进信纸。</p>
            <input ref="fileInput" type="file" accept="image/*" multiple hidden @change="addPhotos($event.target.files); $event.target.value = ''" />
          </section>
          <section>
            <label class="attach">
              <input type="checkbox" :checked="Boolean(reply.attach_commissions)" @change="toggleAttach" />
              封缄时附上今天送达的委托
            </label>
          </section>
          <section class="seal-box">
            <template v-if="sealing === 'choose'">
              <h3 class="kit-title">寄给谁？</h3>
              <div class="chips">
                <button class="chip" :class="{ on: recipient === 'violet' }" @click="recipient = 'violet'">Violet</button>
                <button class="chip" :class="{ on: recipient === 'future' }" @click="recipient = 'future'">未来的我</button>
              </div>
              <template v-if="recipient === 'future'">
                <div class="chips">
                  <button v-for="f in FUTURE" :key="f.days" class="chip" :class="{ on: deliverOn === addDays(isoDate(), f.days) }"
                    @click="deliverOn = addDays(isoDate(), f.days)">{{ f.label }}</button>
                </div>
                <input v-model="deliverOn" class="field mono" type="date" :min="addDays(isoDate(), 1)" aria-label="投递日期" />
                <p class="faint small">那一天，它会作为来信回到书桌上。</p>
              </template>
              <div class="envelope-preview">
                <LetterEnvelope :stationery="{ ...set, signoff: signoff() }" side="front" :width="set.envelope === 'chinese' || set.envelope === 'pouch' ? 120 : 228"
                  :to="recipient === 'future' ? '未来的我' : 'Violet'"
                  :note="recipient === 'future' && deliverOn ? `${longDate(deliverOn)}启` : ''" />
                <button class="link" @click="kitOpen = true; kitTab = 'envelope'">换信封或邮票</button>
              </div>
              <div class="seal-actions">
                <button class="btn small ghost" @click="sealing = null">再想想</button>
                <button class="btn wax" @click="seal"><Icon name="send" :size="14" />盖上火漆</button>
              </div>
            </template>
            <button v-else class="btn wax big" :disabled="!body.trim()" @click="sealing = 'choose'">
              <Icon name="envelope" :size="16" />封缄寄出
            </button>
          </section>
        </template>
        <template v-else>
          <section class="sealed-note">
            <SealImpression :color="set.seal_color" :motif="set.seal_motif" :initials="set.seal_initials" :size="64" :tilt="-6" />
            <p class="title-cn">{{ reply.state === 'travelling' ? `这封信正寄往 ${longDate(reply.deliver_on)}` : '这封信已经封缄' }}</p>
            <p class="faint small">想改的话，可以拆开重写。</p>
            <button class="btn small" @click="unseal">拆开重写</button>
          </section>
          <section v-if="reply.commissions?.length">
            <h3 class="kit-title">附：那天送达的委托</h3>
            <ul class="done-list">
              <li v-for="c in reply.commissions" :key="c.id">{{ c.title }}</li>
            </ul>
          </section>
        </template>
      </aside>
    </div>

    <div v-if="sealing === 'folding'" class="fold-scene" aria-hidden="true">
      <div class="fold-envelope">
        <LetterEnvelope :stationery="set" side="back" :width="set.envelope === 'chinese' || set.envelope === 'pouch' ? 200 : 330"
          pressing />
      </div>
    </div>
  </div>
  <div v-else class="write-empty">
    <p class="faint">信纸还没铺开。</p>
    <button class="btn" @click="go('desk')">回到书桌</button>
  </div>
</template>

<style scoped>
.write {
  max-width: 1120px;
  margin: 0 auto;
}
.topbar {
  position: sticky;
  top: -34px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  margin-bottom: 8px;
  background: linear-gradient(var(--paper) 70%, transparent);
}
.back {
  transform: rotate(180deg);
}
.status {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--ink-faint);
}
.status.saving,
.status.dirty {
  color: var(--gold);
}
.status.error {
  color: var(--danger);
}
.small {
  font-size: 12.5px;
}
.btn.on {
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.room {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 28px;
  align-items: start;
}
/* The sheet of letter paper. */
.paper {
  position: relative;
  padding: 44px 56px 36px 64px;
  background: linear-gradient(90deg, transparent 40px, var(--letter-margin) 40px 41px, transparent 41px);
  box-shadow: var(--shadow-lift);
  border-radius: 2px;
  min-height: 70vh;
  transition: transform 0.6s var(--ease), box-shadow 0.3s;
}
.paper.dragging {
  box-shadow: 0 0 0 2px var(--violet-ink), var(--shadow-lift);
}
.paper-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 14px;
}
.paper-head p {
  margin: 0;
}
.to {
  font-size: 22px;
}
.dateline {
  font-size: 13px;
  margin-top: 4px !important;
}
.pinned {
  display: flex;
  gap: 6px;
  margin-top: -14px;
}
.sheet-text {
  display: block;
  width: 100%;
  border: 0;
  outline: none;
  resize: none;
  overflow: hidden;
  padding: 0;
  font-family: var(--letter-font);
  font-size: calc(17px * var(--letter-scale, 1));
  line-height: 34px;
  color: var(--letter-ink);
  background: repeating-linear-gradient(transparent 0 33px, var(--letter-rule) 33px 34px);
  background-attachment: local;
  caret-color: var(--letter-ink);
}
/* Rulings: lines (above), squares, a manuscript grid with one character to a box, or nothing at all. */
.ruling-grid .sheet-text {
  background:
    repeating-linear-gradient(transparent 0 33px, var(--letter-rule) 33px 34px),
    repeating-linear-gradient(90deg, transparent 0 33px, var(--letter-rule) 33px 34px);
  background-attachment: local;
}
.ruling-manuscript .sheet-text {
  font-size: 19px;
  letter-spacing: 15px;
  padding-left: 7.5px;
  background:
    repeating-linear-gradient(transparent 0 3px, var(--letter-rule) 3px 4px, transparent 4px 33px, var(--letter-rule) 33px 34px),
    repeating-linear-gradient(90deg, transparent 0 33px, var(--letter-rule) 33px 34px);
  background-attachment: local;
}
.ruling-blank .sheet-text {
  background: none;
}
.sign .signed {
  margin-right: auto;
  padding-left: 40%;
  font-family: var(--letter-font);
  font-size: calc(19px * var(--letter-scale, 1));
  color: var(--letter-ink);
}
.prompt {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 14px;
  margin: 0 0 4px;
  font-size: 13.5px;
  color: var(--ink-faint);
  animation: prompt-in 0.6s var(--ease) both;
}
.prompt-text {
  font-family: var(--font-title);
  font-size: 15px;
  color: var(--ink-soft);
}
.prompt .link {
  font-size: 12.5px;
}
@keyframes prompt-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
}
.sheet-text::placeholder {
  color: var(--ink-faint);
}
.photos {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin: 20px 0 6px;
}
.polaroid {
  position: relative;
  margin: 0;
  padding: 8px 8px 26px;
  background: #fffdf8;
  box-shadow: 0 6px 16px -8px rgba(40, 25, 15, 0.45);
  transform: rotate(var(--tilt));
}
.polaroid img {
  display: block;
  width: 160px;
  height: 130px;
  object-fit: cover;
}
.remove {
  position: absolute;
  top: -10px;
  right: -10px;
  width: 26px;
  height: 26px;
  background: var(--sheet-raised);
  box-shadow: var(--shadow-sheet);
}
.song-ticket {
  display: inline-grid;
  grid-template-columns: auto auto auto;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
  padding: 8px 14px 8px 8px;
  border: 1px dashed var(--rule-strong);
  border-radius: 4px;
  background: color-mix(in srgb, var(--gold) 6%, transparent);
}
.song-ticket p {
  margin: 0;
}
.small-eyebrow {
  font-size: 12px;
}
.sign {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-top: 24px;
  font-size: 13px;
}
.sig {
  color: var(--gold);
}
.drop-hint {
  position: absolute;
  inset: 12px;
  display: grid;
  place-items: center;
  border: 2px dashed var(--violet-ink);
  border-radius: 6px;
  color: var(--violet-ink);
  font-size: 20px;
  background: color-mix(in srgb, var(--sheet-raised) 80%, transparent);
  pointer-events: none;
}
/* The stamp drawer on the right. */
.kit {
  position: sticky;
  top: 40px;
  display: grid;
  gap: 18px;
  min-width: 0;
}
.kit > section {
  min-width: 0;
}
.kit-title {
  margin: 0 0 8px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 14px;
  color: var(--ink-soft);
  letter-spacing: 0.1em;
}
.kit p {
  margin: 6px 0 0;
}
.stamps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.stamp-btn {
  display: grid;
  place-items: center;
  padding: 3px 0;
  border-radius: 6px;
  opacity: 0.72;
  transition: all 0.2s var(--ease);
}
.stamp-btn:hover {
  opacity: 1;
  transform: translateY(-2px);
}
.stamp-btn.on {
  opacity: 1;
  background: var(--violet-wash-strong);
}
.song-option {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 5px 6px;
  border-radius: 4px;
  font-size: 13px;
  text-align: left;
  color: var(--ink-soft);
}
.song-option .ellipsis {
  flex: 1;
  min-width: 0;
}
.song-option .count {
  flex: none;
  font-size: 12px;
}
.song-option:hover {
  background: var(--violet-wash);
  color: var(--ink);
}
.attach {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-soft);
}
.attach input {
  accent-color: var(--violet-ink);
}
.stationery {
  display: grid;
  gap: 8px;
  padding-bottom: 14px;
  border-bottom: 1px dashed var(--rule-strong);
}
.drawer {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  margin: 0;
  text-align: left;
}
.mini {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}
.mini-paper {
  width: 18px;
  height: 23px;
  border-radius: 1px;
  background: #f6efe1 center / 80px;
  box-shadow: 0 0 0 1px var(--rule-strong);
}
.caret {
  transform: rotate(90deg);
  transition: transform 0.2s var(--ease);
}
.caret.open {
  transform: rotate(-90deg);
}
.envelope-preview {
  display: grid;
  justify-items: center;
  gap: 6px;
  padding: 6px 0;
}
.envelope-preview .link {
  font-size: 12.5px;
}
.seal-box {
  display: grid;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px dashed var(--rule-strong);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  border-color: var(--rule);
}
.seal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.big {
  height: 42px;
  font-size: 15px;
}
.sealed-note {
  display: grid;
  justify-items: center;
  gap: 8px;
  text-align: center;
}
.seal-v {
  font-size: 32px;
  transform: translate(1px, 3px);
}
.done-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13.5px;
  color: var(--ink-soft);
}
/* Sealing: the sheet folds away, an envelope takes its place, the wax lands. */
.folding .paper {
  transform: perspective(1200px) rotateX(70deg) scale(0.5) translateY(-200px);
  opacity: 0;
  transition: transform 0.8s var(--ease), opacity 0.8s 0.2s;
}
.fold-scene {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  pointer-events: none;
}
.fold-envelope {
  position: relative;
  animation: envelope-in 0.6s 0.5s var(--ease) both, fly-off 0.7s 1.35s cubic-bezier(0.5, 0, 0.8, 0.4) forwards;
}
/* The wax lands once the envelope has settled. */
.fold-envelope :deep(.seal.pressed) {
  animation-delay: 0.9s;
}
@keyframes envelope-in {
  from {
    opacity: 0;
    transform: scale(0.8) translateY(30px);
  }
}
@keyframes fly-off {
  to {
    opacity: 0;
    transform: translate(-40vw, -10vh) rotate(-18deg) scale(0.4);
  }
}
@keyframes press {
  0% {
    transform: scale(1.8) rotate(-18deg);
    opacity: 0;
  }
  60% {
    transform: scale(0.92) rotate(3deg);
    opacity: 1;
  }
  100% {
    transform: none;
  }
}
.write-empty {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 80px 0;
}
@media (max-width: 1100px) {
  .room {
    grid-template-columns: minmax(0, 1fr) 220px;
  }
  .paper {
    padding: 36px 32px 28px 52px;
  }
}
.gleanings {
  display: grid;
  gap: 4px;
}
.glean {
  position: relative;
  padding: 5px 10px 5px 18px;
  font-size: 13px;
  line-height: 1.55;
  text-align: left;
  color: var(--ink-soft);
  border-radius: var(--radius);
  transition: background 0.2s var(--ease), color 0.2s var(--ease), transform 0.25s var(--ease);
  animation: glean-in 0.5s var(--ease) backwards;
}
.glean:nth-child(2) {
  animation-delay: 0.06s;
}
.glean:nth-child(3) {
  animation-delay: 0.12s;
}
.glean:nth-child(4) {
  animation-delay: 0.18s;
}
.glean:nth-child(5) {
  animation-delay: 0.24s;
}
.glean::before {
  content: '❧';
  position: absolute;
  left: 3px;
  top: 5px;
  font-size: 11px;
  color: var(--gold);
}
.glean:hover {
  background: var(--violet-wash);
  color: var(--ink);
  transform: translateX(3px);
}
@keyframes glean-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
}
</style>
