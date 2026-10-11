<script setup>
// 重读自己写过的信：回信，或者从过去寄来的那一封。用它封缄时的信纸、字和墨；可以存成一张图片。
import { computed, ref, watch } from 'vue'
import { signoff } from '../address.js'
import { resolve, paperVars, LETTERHEADS } from '../stationery.js'
import { exportLetter } from '../exportLetter.js'
import { api, photoUrl, libraryCoverUrl } from '../api.js'
import { store, toast, loadLibrary } from '../store.js'
import { desk, startWriting, refresh } from '../desk.js'
import { playList } from '../player.js'
import { trapFocus } from '../dialog.js'
import { daysBetween, isoDate, longDate, timeOfDay } from '../format.js'
import MoodStamp from './MoodStamp.vue'
import CoverArt from './CoverArt.vue'
import Icon from './Icon.vue'
import Nunkish from './Nunkish.vue'
import CipherText from './CipherText.vue'

const box = ref(null)
const reply = computed(() => desk.reading)
const fromPast = computed(() => reply.value?.recipient === 'future')
// 遮信 for this one letter; every letter opens plain.
const veiled = ref(false)
watch(() => reply.value?.id, () => (veiled.value = false))
const ago = computed(() => (reply.value ? daysBetween(reply.value.date, isoDate()) : 0))
const set = computed(() => resolve(reply.value?.stationery))
const letterhead = computed(() => LETTERHEADS[set.value.letterhead] || LETTERHEADS.none)
// Letters sealed before the stationery box keep today's sign-off; later ones keep their own.
const signed = computed(() => (reply.value?.stationery ? reply.value.stationery.signoff || '' : signoff()))
const exporting = ref(false)
async function saveImage() {
  exporting.value = true
  await exportLetter(reply.value)
  exporting.value = false
}

async function star() {
  try {
    desk.reading = await api.updateReply(reply.value.id, { starred: !reply.value.starred, revision: reply.value.revision })
    refresh()
  } catch (error) {
    toast(error.message, 'error')
  }
}

async function rewrite() {
  const item = reply.value
  desk.reading = null
  try {
    const opened = await api.unsealReply(item.id)
    startWriting(opened)
  } catch (error) {
    toast(error.message, 'error')
  }
}

async function play() {
  if (!store.library.loaded) await loadLibrary()
  const index = store.library.tracks.findIndex((t) => t.id === reply.value.song.id)
  if (index >= 0) playList(store.library.tracks, index)
  else toast('这首歌已经不在书信匣里了', 'warning')
}

const close = () => (desk.reading = null)
trapFocus(box, close)
</script>

<template>
  <Transition name="letter-fade">
    <div v-if="reply" class="backdrop" @mousedown.self="close">
      <article ref="box" class="paper letter-sheet daylight" :class="`ruling-${set.ruling}`" :style="paperVars(set)" role="dialog"
        aria-modal="true" aria-label="重读回信">
        <div v-if="set.letterhead !== 'none'" class="letterhead" aria-hidden="true">
          <img v-if="letterhead.url" :src="letterhead.url" alt="" />
          <span v-else class="post">C.H. POSTAL COMPANY<small>LEIDEN · AUTO MEMORY DOLL SERVICE</small></span>
        </div>
        <button class="icon-btn close" title="收起 (Esc)" @click="close"><Icon name="close" :size="16" /></button>
        <p v-if="fromPast" class="eyebrow">A letter from {{ ago }} days ago · 来自 {{ longDate(reply.date) }} 的你</p>
        <header class="head">
          <div>
            <p class="to title-cn">致 {{ fromPast ? '未来的我' : 'Violet' }}：</p>
            <p class="faint small">{{ longDate(reply.date) }}</p>
          </div>
          <div class="pinned">
            <MoodStamp v-if="reply.mood" :value="reply.mood" :size="50" :tilt="-5" />
            <MoodStamp v-if="reply.weather" kind="weather" :value="reply.weather" :size="44" :tilt="7" />
          </div>
        </header>
        <CipherText class="body selectable" :text="reply.body || ''" :veiled="veiled" :ruled="6" />
        <div v-if="reply.photos?.length" class="photos">
          <figure v-for="(name, i) in reply.photos" :key="name" class="polaroid" :style="{ '--tilt': (i % 2 ? 2.5 : -2) + 'deg' }">
            <img :src="photoUrl(name)" alt="夹在信里的照片" loading="lazy" />
          </figure>
        </div>
        <button v-if="reply.song" class="song" title="放这首歌" @click="play">
          <CoverArt :src="reply.song.has_cover ? libraryCoverUrl(reply.song.id) : ''" :size="40" :seed="reply.song.title" />
          <span><span class="eyebrow tiny-eyebrow">那天的歌</span><br /><span class="title-text">{{ reply.song.title }}</span>
            <span class="faint"> · {{ reply.song.artist || '佚名' }}</span></span>
          <Icon name="play" :size="16" />
        </button>
        <section v-if="reply.commissions?.length" class="done">
          <p class="faint small">附：那天送达的委托</p>
          <ul>
            <li v-for="c in reply.commissions" :key="c.id">{{ c.title }}<span v-if="c.client" class="faint"> · {{ c.client }}</span></li>
          </ul>
        </section>
        <p v-if="signed" class="signed">{{ signed }}</p>
        <footer class="foot">
          <Nunkish text="yours" :size="12" class="sig" />
          <span class="faint small">封缄于 {{ longDate(isoDate(new Date(reply.sealed_at * 1000))) }} {{ timeOfDay(reply.sealed_at) }}</span>
          <span class="spacer" />
          <button class="btn small ghost" :class="{ on: veiled }" title="用泰尔西斯文字遮住字迹，旁人看不懂" @click="veiled = !veiled">
            <Icon name="cover" :size="14" />{{ veiled ? '掀开' : '遮信' }}
          </button>
          <button class="btn small ghost" :class="{ starred: reply.starred }" @click="star">
            <Icon name="star" :size="14" />{{ reply.starred ? '已收藏' : '收藏' }}
          </button>
          <button class="btn small ghost" :disabled="exporting" title="连同信纸、邮票和火漆存成一张 PNG，可以分享或打印" @click="saveImage">
            <Icon name="photo" :size="14" />{{ exporting ? '正在画…' : '存成图片' }}
          </button>
          <button v-if="!fromPast" class="btn small ghost" @click="rewrite"><Icon name="edit" :size="14" />拆开重写</button>
        </footer>
      </article>
    </div>
  </Transition>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: var(--titlebar-h, 0px) 0 0 0;
  z-index: 72;
  display: grid;
  place-items: center;
  padding: 40px 0;
  overflow-y: auto;
  background: color-mix(in srgb, var(--paper) 72%, rgba(30, 20, 40, 0.5));
  backdrop-filter: blur(6px);
}
.paper {
  position: relative;
  width: min(720px, calc(100vw - 80px));
  margin: auto;
  padding: 40px 52px 26px 60px;
  background: linear-gradient(90deg, transparent 38px, var(--letter-margin) 38px 39px, transparent 39px);
  box-shadow: var(--shadow-lift);
  animation: unfold 0.6s var(--ease) both;
}
.close {
  position: absolute;
  top: 10px;
  right: 10px;
}
.eyebrow {
  margin: 0 0 10px;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.head p {
  margin: 0;
}
.to {
  font-size: 22px;
}
.pinned {
  display: flex;
  gap: 6px;
}
.body {
  margin-top: 14px;
  white-space: pre-wrap;
  font-family: var(--letter-font);
  font-size: calc(17px * var(--letter-scale, 1));
  line-height: 34px;
  color: var(--letter-ink);
  background: repeating-linear-gradient(transparent 0 33px, var(--letter-rule) 33px 34px);
  min-height: 170px;
}
.ruling-grid .body {
  background:
    repeating-linear-gradient(transparent 0 33px, var(--letter-rule) 33px 34px),
    repeating-linear-gradient(90deg, transparent 0 33px, var(--letter-rule) 33px 34px);
}
.ruling-manuscript .body {
  font-size: 19px;
  letter-spacing: 15px;
  padding-left: 7.5px;
  background:
    repeating-linear-gradient(transparent 0 3px, var(--letter-rule) 3px 4px, transparent 4px 33px, var(--letter-rule) 33px 34px),
    repeating-linear-gradient(90deg, transparent 0 33px, var(--letter-rule) 33px 34px);
}
.ruling-blank .body {
  background: none;
}
.photos {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin: 20px 0 4px;
}
.polaroid {
  margin: 0;
  padding: 8px 8px 24px;
  background: #fffdf8;
  box-shadow: 0 6px 16px -8px rgba(40, 25, 15, 0.45);
  transform: rotate(var(--tilt));
}
.polaroid img {
  display: block;
  width: 180px;
  height: 140px;
  object-fit: cover;
}
.song {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
  padding: 8px 14px 8px 8px;
  border: 1px dashed var(--rule-strong);
  border-radius: 4px;
  text-align: left;
  line-height: 1.4;
  background: color-mix(in srgb, var(--gold) 6%, transparent);
}
.tiny-eyebrow {
  font-size: 12px;
}
.done {
  margin-top: 16px;
}
.done p {
  margin: 0 0 4px;
}
.done ul {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
  color: var(--ink-soft);
}
.small {
  font-size: 12.5px;
}
.signed {
  margin: 18px 0 0;
  text-align: right;
  font-family: var(--letter-font);
  font-size: calc(19px * var(--letter-scale, 1));
  color: var(--letter-ink);
}
.foot {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
  padding-top: 12px;
  border-top: 1px dashed var(--rule);
}
.sig {
  color: var(--gold);
}
.spacer {
  flex: 1;
}
.starred {
  color: var(--gold);
}
@keyframes unfold {
  from {
    opacity: 0;
    transform: translateY(40px) scaleY(0.92);
  }
}
.letter-fade-enter-active,
.letter-fade-leave-active {
  transition: opacity 0.4s var(--ease);
}
.letter-fade-enter-from,
.letter-fade-leave-to {
  opacity: 0;
}
</style>
