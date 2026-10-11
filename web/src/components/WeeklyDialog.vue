<script setup>
// 每周封存：把这一周送达的委托、心情邮票和听得最多的歌装进牛皮纸袋，写一句话，系上绳子。
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'
import { toast } from '../store.js'
import { desk, refresh } from '../desk.js'
import { sound } from '../sound.js'
import { flyTo } from '../motion.js'
import { trapFocus } from '../dialog.js'
import { hm, monthDay } from '../format.js'
import MoodStamp from './MoodStamp.vue'
import WaxSeal from './WaxSeal.vue'
import Icon from './Icon.vue'

const box = ref(null)
const note = ref('')
const tying = ref(false)
const week = computed(() => desk.weekly)
const s = computed(() => week.value?.summary || {})
const readOnly = computed(() => Boolean(week.value?.sealed_at))

watch(week, (w) => {
  note.value = w?.note || ''
  tying.value = false
})

async function seal() {
  try {
    const sealed = await api.sealWeek(week.value.week, note.value)
    tying.value = true
    sound.seal()
    setTimeout(() => {
      flyTo(box.value?.querySelector('.tie-seal') || box.value, 'mailbox', 'letter')
      desk.weekly = null
      toast(`${monthDay(sealed.start)} — ${monthDay(sealed.end)} 这一周封存好了，放进了信箱`, 'success', 6000)
      refresh()
    }, 1400)
  } catch (error) {
    toast(error.message, 'error')
  }
}

const close = () => (desk.weekly = null)
trapFocus(box, close)
</script>

<template>
  <Transition name="modal">
    <div v-if="week" class="backdrop" @mousedown.self="close">
      <div ref="box" class="packet" :class="{ tying }" role="dialog" aria-modal="true" aria-labelledby="weekly-title">
        <button class="icon-btn close" title="关上 (Esc)" @click="close"><Icon name="close" :size="16" /></button>
        <p class="eyebrow">Sealed week · {{ week.week }}</p>
        <h2 id="weekly-title" class="title-cn">{{ monthDay(week.start) }} — {{ monthDay(week.end) }}</h2>
        <div class="stats">
          <div><b class="mono">{{ s.done?.length || 0 }}</b><span>份委托送达</span></div>
          <div><b class="mono">{{ s.replies || 0 }}</b><span>封回信</span></div>
          <div><b class="mono">{{ s.listens || 0 }}</b><span>次聆听</span></div>
          <div><b class="mono small-b">{{ hm(s.focus_seconds) }}</b><span>代笔时间</span></div>
        </div>
        <div v-if="s.moods?.length" class="moods">
          <MoodStamp v-for="(m, i) in s.moods" :key="m.date" :value="m.mood || 'calm'" :size="38" :tilt="(i % 3) * 4 - 4"
            :title="m.date" />
        </div>
        <ul v-if="s.done?.length" class="done">
          <li v-for="(c, i) in s.done.slice(0, 8)" :key="i">{{ c.title }}</li>
          <li v-if="s.done.length > 8" class="faint">……还有 {{ s.done.length - 8 }} 份</li>
        </ul>
        <p v-if="s.songs?.length" class="songs">这一周的歌：<span v-for="t in s.songs" :key="t.track_id" class="song">「{{ t.title }}」</span></p>
        <p v-if="s.pressed?.length" class="songs">压下的花：<span v-for="t in s.pressed" :key="t.track_id" class="song">「{{ t.title }}」</span></p>
        <label class="note-label">
          <span class="caption">这一周，想留下一句什么？</span>
          <textarea v-model="note" rows="3" maxlength="2000" :readonly="readOnly" placeholder="比如：终于把拖了很久的事办完了。" />
        </label>
        <div class="actions">
          <button class="btn ghost" @click="close">{{ readOnly ? '收起' : '先放着' }}</button>
          <button v-if="!readOnly" class="btn wax" @click="seal"><Icon name="archive" :size="15" />系绳封存</button>
        </div>
        <span class="string" aria-hidden="true" />
        <WaxSeal v-if="tying" class="tie-seal" :size="60" tone="gold" pressed><span class="v">V</span></WaxSeal>
        <WaxSeal v-else-if="readOnly" class="corner-seal" :size="46" tone="gold"><span class="v small-v">V</span></WaxSeal>
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
.packet {
  position: relative;
  width: min(560px, calc(100vw - 48px));
  max-height: calc(100vh - 80px);
  overflow-y: auto;
  padding: 34px 36px 24px;
  display: grid;
  gap: 14px;
  color: #3b2f22;
  background:
    radial-gradient(120% 80% at 20% 0%, rgba(255, 255, 255, 0.25), transparent 60%),
    repeating-linear-gradient(95deg, transparent 0 3px, rgba(120, 85, 40, 0.04) 3px 4px),
    #d8c09a;
  border-radius: 4px;
  box-shadow: var(--shadow-lift);
}
.close {
  position: absolute;
  top: 10px;
  right: 10px;
  color: #5a4630;
}
.eyebrow {
  margin: 0;
  color: #7a5a2a;
}
h2 {
  margin: -6px 0 0;
  font-weight: 400;
  font-size: 24px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 12px 0;
  border-top: 1px dashed rgba(90, 60, 30, 0.35);
  border-bottom: 1px dashed rgba(90, 60, 30, 0.35);
}
.stats div {
  display: grid;
  justify-items: center;
  font-size: 12px;
}
.stats b {
  font-weight: 400;
  font-size: 26px;
  color: #5b3a8c;
}
.stats .small-b {
  font-size: 15px;
  line-height: 39px;
}
.moods {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.done {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
  line-height: 1.8;
}
.songs {
  margin: 0;
  font-size: 13.5px;
}
.note-label {
  display: grid;
  gap: 6px;
}
.caption {
  font-size: 12.5px;
  color: #6a5235;
}
textarea {
  padding: 10px 12px;
  border: 0;
  border-radius: 2px;
  background: #fbf7ee;
  color: #2a2238;
  font-size: 15px;
  line-height: 1.8;
  resize: vertical;
  outline: none;
  box-shadow: 0 1px 3px rgba(60, 40, 20, 0.2) inset;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.actions .ghost {
  color: #5a4630;
}
.string {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 2px;
  background: repeating-linear-gradient(0deg, #a0763c 0 6px, #8a6230 6px 9px);
  opacity: 0;
  transform: scaleY(0);
  transform-origin: top;
  pointer-events: none;
}
.tying .string {
  opacity: 0.8;
  transform: scaleY(1);
  transition: transform 0.6s var(--ease), opacity 0.3s;
}
.tie-seal {
  position: absolute;
  left: 50%;
  top: 50%;
  margin: -30px 0 0 -30px;
}
.corner-seal {
  position: absolute;
  top: 16px;
  right: 52px;
}
.small-v {
  font-size: 24px !important;
}
.v {
  font-size: 32px;
  transform: translate(1px, 3px);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s var(--ease);
}
</style>
