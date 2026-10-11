<script setup>
// 信封：西式三角封口、航空信封、中式竖封、驿站公文袋。正面贴邮票、写收信人，背面是封口和火漆。
// 纸面用这封信的信纸纹理（公文袋总是牛皮纸）。尺寸跟着 width 走，里面的东西都按 em 排。
import { computed } from 'vue'
import { PAPERS, paperVars } from '../stationery.js'
import SealImpression from './SealImpression.vue'
import PostageStamp from './PostageStamp.vue'

const props = defineProps({
  stationery: { type: Object, required: true }, // a resolved set (see stationery.resolve)
  side: { type: String, default: 'back' }, // back | front
  width: { type: Number, default: 260 },
  to: { type: String, default: 'Violet' },
  note: { type: String, default: '' }, // under the address: "2027 年 10 月 11 日启" …
  postmark: { type: String, default: '' },
  pressing: { type: Boolean, default: false }, // the seal lands with a flourish
})
const kind = computed(() => props.stationery.envelope || 'western')
const portrait = computed(() => kind.value === 'chinese' || kind.value === 'pouch')
const height = computed(() => Math.round(props.width * (portrait.value ? 1.55 : 0.64)))
const texture = computed(() => {
  if (kind.value === 'pouch') return PAPERS.kraft.url
  return (PAPERS[props.stationery.paper] || PAPERS.parchment).url
})
const vars = computed(() => ({
  ...paperVars(props.stationery),
  '--tex': texture.value ? `url(${texture.value})` : 'none',
  width: props.width + 'px',
  height: height.value + 'px',
  fontSize: (portrait.value ? props.width / 9.5 : props.width / 17) + 'px',
}))
const s = computed(() => props.stationery)
const sealSize = computed(() => Math.round(props.width * (portrait.value ? 0.34 : 0.24)))
const stampWidth = computed(() => Math.round(props.width * (portrait.value ? 0.28 : 0.17)))
</script>

<template>
  <div class="envelope" :class="[kind, side]" :style="vars">
    <!-- ---------------------------------------------------------------- back: the flap and its seal -->
    <template v-if="side === 'back'">
      <span v-if="kind === 'airmail'" class="stripes" />
      <span class="fold left" />
      <span class="fold right" />
      <span class="flap" />
      <template v-if="kind === 'pouch'">
        <span class="button top" /><span class="button low" />
        <svg class="string" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path d="M50 30c-9 4-9 10 0 14s9 10 0 14c-8 4-8 9 0 12 8-3 8-8 0-12-9-4-9-10 0-14s9-10 0-14" />
        </svg>
      </template>
      <span class="seal-spot">
        <SealImpression :color="s.seal_color" :motif="s.seal_motif" :initials="s.seal_initials" :size="sealSize"
          :pressed="pressing" :tilt="-8" />
      </span>
    </template>

    <!-- ---------------------------------------------------------------- front: stamp and address -->
    <template v-else>
      <span v-if="kind === 'airmail'" class="stripes" />
      <span v-if="kind === 'airmail'" class="avion">PAR AVION<br /><b>航空</b></span>
      <span v-if="kind === 'chinese'" class="zip"><i v-for="n in 6" :key="n" /></span>
      <span v-if="kind === 'pouch'" class="pouch-head">驿站公文 · VIOLET POST</span>
      <PostageStamp class="stamp" :stamp="s.stamp" :tone="s.stamp_tone" :width="stampWidth" :tilt="3" />
      <!-- The postmark lands half on the stamp, half on the envelope, the way a clerk's hand would put it. -->
      <svg v-if="postmark" class="postmark" viewBox="0 0 120 50" aria-hidden="true">
        <path d="M2 14c7-4 12 4 19 0s12 4 19 0M2 25c7-4 12 4 19 0s12 4 19 0M2 36c7-4 12 4 19 0s12 4 19 0" />
        <circle cx="72" cy="25" r="21" />
        <circle cx="72" cy="25" r="16.5" stroke-width="0.7" />
        <text x="72" y="21.5" text-anchor="middle" class="pm-top">VIOLET POST</text>
        <text x="72" y="31.5" text-anchor="middle" class="pm-date">{{ postmark }}</text>
      </svg>
      <div class="address">
        <span class="to">{{ kind === 'chinese' ? `${to} 亲启` : `致 ${to}` }}</span>
        <span v-if="kind !== 'chinese'" class="line">{{ to === 'Violet' ? '莱顿 · C.H. 邮政公司' : '书桌的抽屉里' }}</span>
        <span v-if="note && kind !== 'chinese'" class="line note">{{ note }}</span>
      </div>
      <span v-if="note && kind === 'chinese'" class="side-note">{{ note }}</span>
      <span v-if="s.signoff" class="from">{{ kind === 'chinese' ? `${s.signoff} 缄` : `—— ${s.signoff}` }}</span>
    </template>
  </div>
</template>

<style scoped>
.envelope {
  position: relative;
  flex: none;
  overflow: hidden;
  border-radius: 3px;
  background: var(--tex) center / 300px, #f3ead8;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.5) inset, 0 10px 24px -14px rgba(50, 30, 20, 0.55), 0 0 0 1px rgba(90, 70, 50, 0.16);
  font-family: var(--letter-font);
  color: var(--letter-ink);
}
.pouch {
  border-radius: 2px;
}
/* ---- back */
.fold {
  position: absolute;
  bottom: 0;
  width: 50%;
  height: 62%;
  background: linear-gradient(var(--fold-dir, to top right), transparent calc(50% - 0.6px), rgba(80, 60, 40, 0.18) 50%, transparent calc(50% + 0.8px));
}
.fold.left {
  left: 0;
}
.fold.right {
  right: 0;
  --fold-dir: to top left;
}
.flap {
  position: absolute;
  inset: 0 0 auto 0;
  height: 58%;
  background: var(--tex) center / 300px, #f1e7d3;
  clip-path: polygon(0 0, 100% 0, 50% 100%);
  filter: drop-shadow(0 2px 2px rgba(60, 40, 20, 0.22)) brightness(0.97);
}
.seal-spot {
  position: absolute;
  left: 50%;
  top: 58%;
  display: grid;
  transform: translate(-50%, -50%);
}
.chinese .fold,
.pouch .fold {
  display: none;
}
.chinese .flap {
  height: 22%;
  clip-path: polygon(0 0, 100% 0, 92% 100%, 8% 100%);
}
.chinese .seal-spot {
  top: 22%;
}
.pouch .flap {
  height: 40%;
  clip-path: polygon(0 0, 100% 0, 50% 100%);
}
.button {
  position: absolute;
  left: 50%;
  width: 1.1em;
  height: 1.1em;
  margin-left: -0.55em;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #c9a37a, #7c5532);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
}
.button.top {
  top: 22%;
}
.button.low {
  top: 66%;
}
.string {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  fill: none;
  stroke: #e9dcc4;
  stroke-width: 0.8;
  filter: drop-shadow(0 0.5px 0.5px rgba(0, 0, 0, 0.4));
}
.pouch .seal-spot {
  top: 46%;
  left: 76%;
}
/* Air mail: the red and blue barber-pole border. */
.stripes {
  position: absolute;
  inset: 0;
  --b: max(5px, 0.5em);
  background: repeating-linear-gradient(-45deg, #b23a3a 0 10px, transparent 10px 16px, #2d4e8a 16px 26px, transparent 26px 32px);
  -webkit-mask: linear-gradient(#000 0 0) top / 100% var(--b) no-repeat, linear-gradient(#000 0 0) bottom / 100% var(--b) no-repeat,
    linear-gradient(#000 0 0) left / var(--b) 100% no-repeat, linear-gradient(#000 0 0) right / var(--b) 100% no-repeat;
  opacity: 0.82;
}
/* ---- front */
.stamp {
  position: absolute;
  top: 9%;
  right: 6%;
}
.address {
  position: absolute;
  left: 12%;
  right: 30%;
  top: 40%;
  display: grid;
  gap: 0.35em;
}
.address > span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.postmark {
  position: absolute;
  top: calc(9% + var(--pm-drop, 2.2em));
  right: 2%;
  width: 7.4em;
  fill: none;
  stroke: rgba(40, 30, 60, 0.6);
  stroke-width: 1.3;
  transform: rotate(-8deg);
  pointer-events: none;
}
.postmark text {
  stroke: none;
  fill: rgba(40, 30, 60, 0.7);
  font-family: 'Cutive Mono', monospace;
}
.pm-top {
  font-size: 6px;
  letter-spacing: 0.08em;
}
.pm-date {
  font-size: 7px;
}
.chinese .postmark,
.pouch .postmark {
  --pm-drop: 2.6em;
  width: 5.4em;
}
.to {
  font-size: calc(1.6em * var(--letter-scale, 1));
  line-height: 1.2;
  border-bottom: 1px solid var(--letter-rule);
  padding-bottom: 0.15em;
}
.line {
  font-size: 0.82em;
  opacity: 0.78;
  border-bottom: 1px solid var(--letter-rule);
  padding-bottom: 0.25em;
}
.note {
  font-family: var(--font-title);
}
.from {
  position: absolute;
  right: 7%;
  bottom: 8%;
  font-size: 0.8em;
  opacity: 0.8;
}
.avion {
  position: absolute;
  top: 12%;
  left: 7%;
  padding: 0.25em 0.6em;
  border: 1.5px solid #2d4e8a;
  border-radius: 2px;
  color: #2d4e8a;
  font-family: 'Cutive Mono', monospace;
  font-size: 0.62em;
  line-height: 1.3;
  text-align: center;
  letter-spacing: 0.06em;
}
.avion b {
  font-family: var(--font-title);
  font-weight: 400;
  letter-spacing: 0.3em;
}
/* Chinese envelope: postcode boxes, a red-framed address column written top to bottom. */
.chinese .zip {
  position: absolute;
  top: 6%;
  left: 7%;
  display: flex;
  gap: 0.18em;
}
.chinese .zip i {
  width: 0.62em;
  height: 0.72em;
  border: 1px solid #b8473b;
}
.chinese .stamp {
  top: 5%;
  right: 7%;
}
.chinese .address {
  left: 50%;
  right: auto;
  top: 30%;
  bottom: 22%;
  transform: translateX(-50%);
  padding: 0.5em 0.35em;
  border: 1.5px solid #b8473b;
  border-width: 0 1.5px;
  writing-mode: vertical-rl;
  display: block;
}
.chinese .to {
  border: 0;
  font-size: calc(1.15em * var(--letter-scale, 1));
  letter-spacing: 0.25em;
}
.side-note {
  position: absolute;
  left: 12%;
  top: 34%;
  writing-mode: vertical-rl;
  font-family: var(--font-title);
  font-size: 0.5em;
  letter-spacing: 0.1em;
  opacity: 0.75;
}
.chinese .from {
  left: auto;
  right: 9%;
  bottom: 6%;
  writing-mode: vertical-rl;
  font-size: 0.6em;
}
/* The post-station pouch: a printed header and kraft paper. */
.pouch .pouch-head {
  position: absolute;
  top: 8%;
  left: 8%;
  font-family: var(--font-title);
  font-size: 0.58em;
  letter-spacing: 0.12em;
  color: #6b3a24;
  border: 1px solid rgba(107, 58, 36, 0.6);
  padding: 0.2em 0.5em;
}
.pouch .stamp {
  top: 18%;
}
.pouch .address {
  left: 10%;
  right: 10%;
  top: 56%;
}
.pouch .to {
  font-size: calc(1.05em * var(--letter-scale, 1));
}
.pouch .line {
  font-size: 0.56em;
}
.pouch .from {
  font-size: 0.56em;
}
:root[data-theme='dark'] .envelope {
  filter: brightness(0.86);
}
</style>
