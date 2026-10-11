<script setup>
// 约定与纪念日：约定是某天某时要去的事；纪念日每年都会回来，可以按农历过。
import { computed, reactive, ref, watch } from 'vue'
import { desk, saveAppointment, removeAppointment } from '../desk.js'
import { trapFocus } from '../dialog.js'
import { longDate } from '../format.js'
import Icon from './Icon.vue'
import WaxSeal from './WaxSeal.vue'

const box = ref(null)
const form = reactive({})
const open = computed(() => Boolean(desk.appointment))
const isNew = computed(() => open.value && !desk.appointment.id)
const anniversary = computed(() => form.kind === 'anniversary')
const REMIND = [
  { value: null, label: '不提醒' },
  { value: 0, label: '准时' },
  { value: 15, label: '提前 15 分' },
  { value: 60, label: '提前 1 小时' },
  { value: 1440, label: '提前 1 天' },
  { value: 4320, label: '提前 3 天' },
]

watch(
  () => desk.appointment,
  (item) => {
    for (const key of Object.keys(form)) delete form[key]
    if (!item) return
    Object.assign(form, { kind: 'appointment', title: '', place: '', note: '', start: '', end: '', remind: null, lunar: false },
      JSON.parse(JSON.stringify(item)))
    // An occurrence of an anniversary edits the original record and its original date.
    form.start = form.start || ''
    form.end = form.end || ''
    form.lunar = Boolean(form.lunar)
  },
  { immediate: true },
)

async function save() {
  if (!form.title?.trim()) return
  const data = {
    kind: form.kind,
    title: form.title,
    date: form.date,
    place: form.place,
    note: form.note,
    start: anniversary.value ? null : form.start || null,
    end: anniversary.value ? null : form.end || null,
    remind: form.remind,
    lunar: anniversary.value && form.lunar,
  }
  if (form.id) Object.assign(data, { id: form.id, revision: form.revision })
  const after = desk.appointment?._after // e.g. a school notice that asked to be written into the stamp book
  const item = await saveAppointment(data)
  if (item) {
    after?.(item)
    desk.appointment = null
  }
}

async function remove() {
  await removeAppointment(desk.appointment)
  desk.appointment = null
}

const close = () => (desk.appointment = null)
trapFocus(box, close)
</script>

<template>
  <Transition name="modal">
    <div v-if="open" class="backdrop" @mousedown.self="close">
      <form ref="box" class="dialog sheet" role="dialog" aria-modal="true" aria-labelledby="appointment-title" @submit.prevent="save">
        <WaxSeal class="seal" :size="54" :tone="anniversary ? 'danger' : 'violet'">
          <Icon :name="anniversary ? 'cake' : 'calendar'" :size="20" />
        </WaxSeal>
        <div class="kinds">
          <button type="button" class="chip" :class="{ on: !anniversary }" @click="form.kind = 'appointment'">约定</button>
          <button type="button" class="chip" :class="{ on: anniversary }" @click="form.kind = 'anniversary'">纪念日</button>
        </div>
        <h2 id="appointment-title" class="title-cn">{{ isNew ? (anniversary ? '记下一个纪念日' : '记下一个约定') : anniversary ? '纪念日' : '约定' }}</h2>
        <input v-model="form.title" class="field big" maxlength="200" autofocus
          :placeholder="anniversary ? '妈妈的生日、相识纪念日……' : '和谁、做什么'" />
        <label class="row">
          <span class="caption">{{ anniversary ? '那一天（最初的日期）' : '日期' }}</span>
          <input v-model="form.date" class="field mono" type="date" required />
        </label>
        <template v-if="!anniversary">
          <div class="row">
            <span class="caption">时间</span>
            <input v-model="form.start" class="field mono" type="time" aria-label="开始" />
            <span class="faint">—</span>
            <input v-model="form.end" class="field mono" type="time" aria-label="结束" />
            <span class="faint tiny">留空就是全天</span>
          </div>
          <label class="row">
            <span class="caption"><Icon name="pin" :size="13" />地点</span>
            <input v-model="form.place" class="field" maxlength="200" placeholder="可不填" />
          </label>
        </template>
        <label v-else class="lunar">
          <input v-model="form.lunar" type="checkbox" />
          按农历过（生日常这样）
        </label>
        <div class="row wrap">
          <span class="caption"><Icon name="bell" :size="13" />提醒</span>
          <button v-for="r in REMIND" :key="String(r.value)" type="button" class="chip" :class="{ on: form.remind === r.value }"
            @click="form.remind = r.value">{{ r.label }}</button>
        </div>
        <p v-if="form.remind !== null && (anniversary || !form.start)" class="faint tiny">没写时间时，按当天 09:00 提醒。</p>
        <textarea v-model="form.note" class="note" rows="2" placeholder="附注" />
        <p v-if="desk.appointment.on && desk.appointment.on !== desk.appointment.date" class="faint tiny">
          这是 {{ longDate(desk.appointment.on) }} 的那一次；修改会作用于每一年。
        </p>
        <div class="buttons">
          <button v-if="!isNew" type="button" class="btn small ghost danger" @click="remove"><Icon name="trash" :size="14" />划掉</button>
          <span class="spacer" />
          <button type="button" class="btn ghost" @click="close">取消</button>
          <button class="btn wax" type="submit" :disabled="!form.title?.trim() || !form.date">记下</button>
        </div>
      </form>
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
  width: min(480px, calc(100vw - 48px));
  padding: 40px 30px 22px;
  display: grid;
  gap: 12px;
  background: var(--sheet-raised);
  box-shadow: var(--shadow-lift);
}
.seal {
  position: absolute;
  top: -27px;
  left: 50%;
  margin-left: -27px;
}
.kinds {
  display: flex;
  justify-content: center;
  gap: 6px;
}
h2 {
  margin: 0;
  text-align: center;
  font-weight: 400;
  font-size: 22px;
}
.big {
  font-size: 19px;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.row.wrap {
  flex-wrap: wrap;
  gap: 6px;
}
.row .field {
  height: 34px;
}
.row .field:not(.mono) {
  flex: 1;
}
.caption {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 64px;
  font-size: 12.5px;
  color: var(--ink-faint);
}
.chip {
  border-color: var(--rule);
}
.lunar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--ink-soft);
}
.lunar input {
  accent-color: var(--violet-ink);
}
.note {
  border: 1px solid var(--rule);
  border-radius: 4px;
  background: transparent;
  padding: 8px 10px;
  resize: vertical;
  outline: none;
  font-size: 14px;
}
.note:focus {
  border-color: var(--violet-ink);
}
.tiny {
  font-size: 12px;
  margin: 0;
}
.buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.spacer {
  flex: 1;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .dialog,
.modal-leave-to .dialog {
  transform: translateY(16px) scale(0.98);
}
.modal-enter-active,
.modal-leave-active,
.modal-enter-active .dialog,
.modal-leave-active .dialog {
  transition: all 0.3s var(--ease);
}
</style>
