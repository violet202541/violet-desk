<script setup>
// 一束信札：几封叠在一起的信，用缎带十字扎好，打个蝴蝶结。最上面那封贴着歌的封面当邮票。
import { computed } from 'vue'
import { RIBBONS } from '../shelf.js'
import { libraryCoverUrl } from '../api.js'
import { duration } from '../format.js'

const props = defineProps({
  bundle: { type: Object, required: true },
  preview: { type: Boolean, default: false }, // in the tie dialog: no counts, just the look
  tilt: { type: Number, default: 0 },
})
const hue = computed(() => (RIBBONS[props.bundle.ribbon] || RIBBONS.violet).hue)
const meta = computed(() => {
  const b = props.bundle
  const parts = [`${b.count || 0} 封`]
  if (b.duration) parts.push(duration(b.duration))
  return parts.join(' · ')
})
</script>

<template>
  <div class="bundle" :style="{ '--ribbon': hue, '--tilt': tilt + 'deg' }">
    <div class="stack">
      <span class="env back2" />
      <span class="env back1" />
      <span class="env top">
        <span class="flap" />
        <span class="stamps">
          <span v-for="(id, i) in bundle.covers || []" :key="id" class="stamp stamp-edge" :style="{ '--r': (i - 1) * 7 + 'deg' }">
            <img :src="libraryCoverUrl(id)" alt="" draggable="false" />
          </span>
          <span v-if="!(bundle.covers || []).length" class="stamp stamp-edge blank"><span>V</span></span>
        </span>
        <span class="to title-text">{{ bundle.name || '还没有名字' }}</span>
      </span>
      <span class="ribbon-v" />
      <span class="ribbon-h" />
      <svg class="bow" viewBox="0 0 60 44" aria-hidden="true">
        <path class="loop" d="M30 20 C 20 4, 4 6, 6 18 C 8 28, 22 26, 30 20 Z" />
        <path class="loop" d="M30 20 C 40 4, 56 6, 54 18 C 52 28, 38 26, 30 20 Z" />
        <path class="tail" d="M28 22 L 18 42 L 24 39 L 27 43 L 31 23 Z" />
        <path class="tail" d="M32 22 L 42 42 L 36 39 L 33 43 L 29 23 Z" />
        <ellipse class="knot" cx="30" cy="20.5" rx="4.5" ry="4" />
        <path class="shine" d="M12 14 C 16 10, 22 12, 25 16 M48 14 C 44 10, 38 12, 35 16" />
      </svg>
    </div>
    <div v-if="!preview" class="caption">
      <p class="name title-text">{{ bundle.name }}</p>
      <p v-if="bundle.epigraph" class="epigraph">{{ bundle.epigraph }}</p>
      <p class="meta mono">{{ meta }}<span v-if="bundle.pending" class="pending">· {{ bundle.pending }} 封在路上</span>
        <span v-if="bundle.lost" class="lost">· {{ bundle.lost }} 封遗失</span></p>
    </div>
  </div>
</template>

<style scoped>
.bundle {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.stack {
  position: relative;
  aspect-ratio: 16 / 10.5;
  transform: rotate(var(--tilt));
  transition: transform 0.45s var(--ease);
}
.env {
  position: absolute;
  inset: 0;
  border-radius: 4px;
  border: 1px solid var(--rule-strong);
  background: linear-gradient(160deg, var(--sheet-raised), var(--paper-deep));
  box-shadow: var(--shadow-sheet);
  transition: transform 0.45s var(--ease);
}
.back2 {
  transform: rotate(-4deg) translate(-6px, 6px);
  filter: brightness(0.96);
}
.back1 {
  transform: rotate(2.5deg) translate(5px, 3px);
  filter: brightness(0.98);
}
.top {
  overflow: hidden;
}
.flap {
  position: absolute;
  inset: 0 0 auto 0;
  height: 52%;
  background: linear-gradient(170deg, var(--sheet-raised), var(--paper-deep));
  clip-path: polygon(0 0, 100% 0, 50% 100%);
  filter: drop-shadow(0 1px 1px rgba(60, 40, 20, 0.15));
}
.stamps {
  position: absolute;
  top: 10%;
  right: 7%;
  display: flex;
}
.stamps {
  filter: drop-shadow(0 1px 2px rgba(40, 20, 50, 0.3));
}
/* Covers become postage stamps: perforated only round the edge (the shared .stamp-edge mask). */
.stamp {
  --hole: 2px;
  display: block;
  width: 34px;
  height: 40px;
  margin-left: -10px;
  transform: rotate(var(--r, 0deg));
}
.stamp:first-child {
  margin-left: 0;
}
.stamp img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.stamp.blank span {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  font-family: var(--font-script);
  font-size: 22px;
  color: var(--wax-text);
  background: var(--ribbon);
}
.to {
  position: absolute;
  left: 9%;
  bottom: 14%;
  max-width: 48%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  color: var(--ink);
  border-bottom: 1px solid var(--rule-strong);
  padding-bottom: 2px;
}
/* The ribbon crosses the bundle both ways and is tied off-centre. */
.ribbon-v,
.ribbon-h {
  position: absolute;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.18), transparent 40%, rgba(0, 0, 0, 0.15)),
    var(--ribbon);
  box-shadow: 0 1px 2px rgba(30, 10, 40, 0.3);
}
.ribbon-v {
  top: -3px;
  bottom: -3px;
  left: 63%;
  width: 9px;
}
.ribbon-h {
  left: -3px;
  right: -3px;
  top: 58%;
  height: 9px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.18), transparent 40%, rgba(0, 0, 0, 0.15)),
    var(--ribbon);
}
.bow {
  position: absolute;
  left: calc(63% + 4.5px);
  top: calc(58% + 4.5px);
  width: 64px;
  transform: translate(-50%, -46%);
  overflow: visible;
  filter: drop-shadow(0 2px 2px rgba(30, 10, 40, 0.3));
  transition: transform 0.5s cubic-bezier(0.3, 1.5, 0.5, 1);
}
.loop,
.tail {
  fill: var(--ribbon);
}
.loop {
  stroke: rgba(0, 0, 0, 0.18);
  stroke-width: 0.8;
}
.tail {
  filter: brightness(0.88);
}
.knot {
  fill: var(--ribbon);
  stroke: rgba(0, 0, 0, 0.2);
  stroke-width: 0.8;
}
.shine {
  fill: none;
  stroke: rgba(255, 255, 255, 0.35);
  stroke-width: 1.4;
  stroke-linecap: round;
}
/* Picking it up: the letters fan a little and the bow perks up. */
.bundle:hover .stack,
:focus-visible > .bundle .stack {
  transform: rotate(0deg) translateY(-4px);
}
.bundle:hover .back2 {
  transform: rotate(-7deg) translate(-12px, 8px);
}
.bundle:hover .back1 {
  transform: rotate(5deg) translate(10px, 2px);
}
.bundle:hover .bow {
  transform: translate(-50%, -46%) rotate(-6deg) scale(1.06);
}
.caption {
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 0 4px;
}
.caption p {
  margin: 0;
}
.name {
  font-size: 16px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.epigraph {
  font-size: 12.5px;
  color: var(--ink-soft);
  font-style: italic;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta {
  font-size: 11.5px;
  color: var(--ink-faint);
}
.pending {
  margin-left: 4px;
  color: var(--gold);
}
.lost {
  margin-left: 4px;
  color: var(--danger);
}
</style>
