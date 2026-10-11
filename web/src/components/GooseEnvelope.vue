<script setup>
// 从信篮、信盒里摊开的一封信：信封正面。左上是驿路的邮戳，右上是邮票（急件换成「速达」戳），
// 中间是标题和「为什么拣给你」，信封脚写着截止日。拆过的褪了色，别着翡翠胸针的镶着翡翠绿。
import { computed } from 'vue'
import { leftLabel, makeCommission, openLetter, serial, updateLetter } from '../geese.js'
import ExpressStamp from './ExpressStamp.vue'
import Icon from './Icon.vue'

const props = defineProps({
  letter: { type: Object, required: true },
  sealed: { type: Boolean, default: false }, // in the drawer of letters that did not pass
  index: { type: Number, default: 0 },
})

const mark = computed(() => (props.letter.route_name || '').replace(/学院$/, '').slice(0, 4))
const day = computed(() => {
  const d = props.letter.published
  return d ? `${d.slice(5, 7)}·${d.slice(8, 10)}` : '—'
})
const left = computed(() => leftLabel(props.letter))
const reasons = computed(() => (props.letter.reasons || []).slice(0, 3))
const express = computed(() => props.letter.urgent && !props.letter.read_at && !props.sealed)
const tilt = computed(() => (Number(serial(props.letter)) % 7 - 3) * 0.25)
</script>

<template>
  <article class="envelope" :data-goose="letter.id" :style="{ '--i': index, '--tilt': tilt + 'deg' }"
    :class="{ read: letter.read_at, sealed, pinned: letter.pinned }">
    <button class="face" :title="letter.title" @click="openLetter(letter, $event.currentTarget)">
      <span class="top">
        <span class="postmark" aria-hidden="true">
          <span class="ring"><span class="who">{{ mark }}</span><span class="when mono">{{ day }}</span></span>
          <svg class="waves" viewBox="0 0 40 30"><path d="M0 6 q5 -4 10 0 t10 0 t10 0 t10 0M0 15 q5 -4 10 0 t10 0 t10 0 t10 0M0 24 q5 -4 10 0 t10 0 t10 0 t10 0" /></svg>
        </span>
        <ExpressStamp v-if="express" class="express" :size="70" :tilt="-11" />
        <span v-else class="postage" aria-hidden="true"><span><Icon name="goose" :size="15" /></span></span>
      </span>
      <span class="title title-text">
        <Icon v-if="letter.pinned" name="brooch" :size="14" class="pin-icon" />{{ letter.title }}
      </span>
      <span v-if="reasons.length" class="why">
        <span class="faint">{{ sealed ? '没拣它，因为' : '因为' }}</span>
        <span v-for="r in reasons" :key="r" class="reason">{{ r }}</span>
      </span>
      <span v-else-if="sealed" class="why faint">名片里没有提到和它有关的事</span>
      <span class="foot">
        <span v-if="letter.deadline" class="deadline" :class="{ soon: left && letter.days_left <= 3 }">
          <span class="mono">{{ letter.deadline.slice(5).replace('-', '/') }} 截止</span>
          <span v-if="left" class="left">{{ left }}</span>
        </span>
        <span v-else class="faint mono small">{{ letter.route_name }}</span>
        <span v-if="letter.commission_id" class="done-stamp">已成委托</span>
        <span v-else-if="letter.appointment_id" class="done-stamp">已写约定</span>
      </span>
    </button>
    <div class="tools">
      <button v-if="!letter.commission_id && !sealed" class="icon-btn" title="记成委托（带上截止日）" @click="makeCommission(letter)">
        <Icon name="commission" :size="15" />
      </button>
      <button v-if="!sealed" class="icon-btn" :class="{ on: letter.pinned }"
        :title="letter.pinned ? '取下胸针' : '别上翡翠胸针（不会被收进旧信）'" @click="updateLetter(letter, { pinned: !letter.pinned })">
        <Icon name="brooch" :size="15" />
      </button>
    </div>
  </article>
</template>

<style scoped>
.envelope {
  position: relative;
  transform: rotate(var(--tilt));
  animation: lay 0.55s var(--ease) both;
  animation-delay: calc(var(--i) * 45ms);
}
@keyframes lay {
  from {
    opacity: 0;
    transform: translateY(-18px) rotate(calc(var(--tilt) - 2deg));
  }
}
.face {
  position: relative;
  display: grid;
  grid-template-rows: auto 1fr auto auto;
  gap: 8px;
  width: 100%;
  min-height: 178px;
  padding: 12px 14px 12px 14px;
  border-radius: 3px;
  text-align: left;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.55), transparent 40%),
    linear-gradient(180deg, var(--env-a, #fffbf2), var(--env-b, #f4ead6));
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.8) inset,
    0 0 0 1px rgba(120, 90, 50, 0.1),
    0 12px 22px -16px rgba(70, 45, 20, 0.45),
    0 2px 3px -2px rgba(70, 45, 20, 0.25);
  color: var(--env-ink, #2a2238);
  transition: transform 0.3s var(--ease), box-shadow 0.3s var(--ease), opacity 0.3s var(--ease);
}
:root[data-theme='dark'] .face {
  --env-a: #ece2cd;
  --env-b: #ddd0b6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme='light']) .face {
    --env-a: #ece2cd;
    --env-b: #ddd0b6;
  }
}
.envelope:hover .face {
  transform: translateY(-3px) rotate(calc(var(--tilt) * -1));
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.8) inset,
    0 0 0 1px rgba(120, 90, 50, 0.12),
    0 22px 30px -18px rgba(70, 45, 20, 0.55);
}
.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  min-height: 52px;
}
.postmark {
  display: flex;
  align-items: center;
  color: #6e4fa3;
}
.ring {
  display: grid;
  place-items: center;
  align-content: center;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  box-shadow: inset 0 0 0 3px var(--env-a, #fffbf2), inset 0 0 0 4px currentColor;
  transform: rotate(-9deg);
  line-height: 1.1;
  opacity: 0.8;
}
.who {
  font-family: var(--font-title);
  font-size: 11.5px;
  letter-spacing: 0.04em;
}
.when {
  font-size: 10px;
}
.waves {
  width: 28px;
  height: 24px;
  margin-left: -6px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.2;
  opacity: 0.4;
}
.postage {
  display: grid;
  width: 34px;
  height: 40px;
  padding: 3px;
  background: #fffdf8;
  box-shadow: 0 1px 2px rgba(70, 45, 20, 0.3);
  transform: rotate(3deg);
  /* Perforated edges: little bites out of the paper all round. */
  -webkit-mask: radial-gradient(circle 2.2px at 50% 50%, transparent 95%, #000) -3px -3px / 6px 6px, linear-gradient(#000 0 0) 3px 3px / calc(100% - 6px) calc(100% - 6px) no-repeat;
  mask: radial-gradient(circle 2.2px at 50% 50%, transparent 95%, #000) -3px -3px / 6px 6px, linear-gradient(#000 0 0) 3px 3px / calc(100% - 6px) calc(100% - 6px) no-repeat;
}
.postage > span {
  display: grid;
  place-items: center;
  background: linear-gradient(160deg, #e9e0f4, #d6c6ec);
  color: #5e3f8f;
}
.pinned .postage > span {
  background: linear-gradient(160deg, #dcefe6, #bcdccd);
  color: #2e6b58;
}
.express {
  margin: -4px -6px 0 0;
}
.title {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 14.5px;
  line-height: 1.6;
  color: inherit;
}
.pin-icon {
  display: inline-block;
  vertical-align: -2px;
  margin-right: 4px;
  color: #2e6b58;
}
.why {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 3px 7px;
  font-size: 12px;
}
.why .faint {
  color: #6a5f73;
}
.reason {
  padding: 0 7px;
  border-radius: 9px;
  background: rgba(110, 79, 163, 0.1);
  color: #6e4fa3;
}
.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px dashed rgba(120, 90, 50, 0.22);
  font-size: 12px;
  color: #5b5068;
}
.small {
  font-size: 11.5px;
}
.deadline {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.deadline .left {
  font-family: var(--font-title);
  font-size: 13px;
}
/* A deadline that is close is ringed in red ink. */
.deadline.soon .left {
  position: relative;
  padding: 0 4px;
  color: #a4453a;
}
.deadline.soon .left::after {
  content: '';
  position: absolute;
  inset: -3px -5px;
  border: 1.5px solid currentColor;
  border-radius: 48% 52% 45% 55% / 60% 50% 50% 40%;
  transform: rotate(-4deg);
  opacity: 0.7;
}
.done-stamp {
  padding: 0 6px;
  border: 1.5px solid #2e6b58;
  border-radius: 3px;
  color: #2e6b58;
  font-family: var(--font-title);
  font-size: 11px;
  letter-spacing: 0.15em;
  transform: rotate(-6deg);
  opacity: 0.85;
}
/* Opened letters fade like paper left in the sun. */
.read .face {
  --env-a: #f7f2e8;
  --env-b: #ece4d4;
  color: #5b5068;
}
.read .ring,
.read .postage {
  opacity: 0.5;
}
/* Letters wearing the emerald brooch keep a thin emerald frame. */
.pinned .face {
  box-shadow:
    0 0 0 1px rgba(46, 107, 88, 0.55),
    0 0 0 4px rgba(46, 107, 88, 0.08),
    0 12px 22px -16px rgba(70, 45, 20, 0.45);
}
.sealed .face {
  min-height: 150px;
  background: transparent;
  box-shadow: none;
  border: 1px dashed var(--rule-strong);
  color: var(--ink);
}
.sealed .ring {
  box-shadow: none;
}
.sealed .foot {
  color: var(--ink-soft);
}
.tools {
  position: absolute;
  right: 6px;
  bottom: 40px;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.25s var(--ease);
}
.tools .icon-btn {
  color: #5b5068;
  background: color-mix(in srgb, #fffbf2 85%, transparent);
}
.tools .icon-btn.on {
  color: #2e6b58;
}
.envelope:hover .tools,
.envelope:focus-within .tools {
  opacity: 1;
}
@media (hover: none) {
  .tools {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .envelope {
    animation: none;
  }
}
</style>
