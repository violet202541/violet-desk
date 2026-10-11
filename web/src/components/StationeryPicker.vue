<script setup>
// 文具匣的抽屉：信纸、字与墨、火漆、邮票、信封五格。写信时在右边的工具栏里用，设置里挑默认的也用它。
// 只负责挑：选中了什么就 emit('change', 改动)，由用的地方决定存到这封信还是存成默认。
import { computed, ref } from 'vue'
import { api } from '../api.js'
import { store, saveSettings, toast } from '../store.js'
import { shrinkImage } from '../images.js'
import { PAPERS, RULINGS, LETTERHEADS, INKS, WAX, MOTIFS, STAMPS, STAMP_TONES, ENVELOPES, LETTER_FONTS } from '../stationery.js'
import { fontStack } from '../fonts.js'
import SealImpression from './SealImpression.vue'
import PostageStamp from './PostageStamp.vue'
import LetterEnvelope from './LetterEnvelope.vue'
import Icon from './Icon.vue'

const props = defineProps({
  set: { type: Object, required: true }, // the resolved stationery being chosen for
  tab: { type: String, default: 'paper' },
  roomy: { type: Boolean, default: false }, // the wider layout in settings
})
const emit = defineEmits(['change', 'update:tab'])
const TABS = { paper: '信纸', ink: '字与墨', seal: '火漆', stamp: '邮票', envelope: '信封' }
const pick = (patch) => emit('change', patch)

const motifGroups = computed(() => {
  const groups = {}
  for (const [id, m] of Object.entries(MOTIFS)) (groups[m.family] ||= []).push(id)
  return groups
})
const initials = ref(props.set.seal_initials || '')
function saveInitials() {
  const value = initials.value.trim().slice(0, 3)
  pick({ seal_initials: value, seal_motif: value ? 'initials' : props.set.seal_motif })
}

const photoStamps = computed(() => store.settings?.photo_stamps || [])
const fileInput = ref(null)
const uploading = ref(false)
async function addPhotoStamp(file) {
  if (!file) return
  uploading.value = true
  try {
    const { name } = await api.uploadPhoto(await shrinkImage(file, 900))
    if (await saveSettings({ photo_stamps: [name, ...photoStamps.value].slice(0, 24) })) pick({ stamp: `photo:${name}` })
  } catch (error) {
    toast(error.message, 'error')
  } finally {
    uploading.value = false
  }
}
const removePhotoStamp = (name) => saveSettings({ photo_stamps: photoStamps.value.filter((p) => p !== name) })
</script>

<template>
  <div class="picker" :class="{ roomy }">
    <div class="tabs" role="tablist">
      <button v-for="(label, id) in TABS" :key="id" class="tab" :class="{ on: tab === id }" role="tab" :aria-selected="tab === id"
        @click="emit('update:tab', id)">{{ label }}</button>
    </div>

    <!-- ---------------------------------------------------------------- 信纸 -->
    <div v-if="tab === 'paper'" class="pane">
      <div class="swatches papers">
        <button v-for="(p, id) in PAPERS" :key="id" class="swatch" :class="{ on: set.paper === id }" :title="p.label" @click="pick({ paper: id })">
          <span class="sheet" :style="{ backgroundImage: p.url ? `url(${p.url})` : 'none' }" />
          <span class="name">{{ p.label }}</span>
        </button>
      </div>
      <p class="label">格线</p>
      <div class="chips">
        <button v-for="(r, id) in RULINGS" :key="id" class="chip" :class="{ on: set.ruling === id }" @click="pick({ ruling: id })">{{ r.label }}</button>
      </div>
      <p class="label">抬头与花边</p>
      <div class="swatches heads">
        <button v-for="(h, id) in LETTERHEADS" :key="id" class="swatch head" :class="{ on: set.letterhead === id }" :title="h.label"
          @click="pick({ letterhead: id })">
          <img v-if="h.url" :src="h.url" alt="" />
          <span v-else-if="id === 'post'" class="post-head">C.H. POSTAL COMPANY</span>
          <span v-else class="none">—</span>
          <span class="name">{{ h.label }}</span>
        </button>
      </div>
    </div>

    <!-- ---------------------------------------------------------------- 字与墨 -->
    <div v-else-if="tab === 'ink'" class="pane">
      <div class="fonts">
        <button v-for="(f, id) in LETTER_FONTS" :key="id" class="font" :class="{ on: set.font === id }" :title="f.hint" @click="pick({ font: id })">
          <span class="sample" :style="{ fontFamily: fontStack(id), fontSize: 17 * f.scale + 'px' }">见字如面</span>
          <span class="name">{{ f.label }}</span>
        </button>
      </div>
      <p class="label">墨水</p>
      <div class="inks">
        <button v-for="(ink, id) in INKS" :key="id" class="ink" :class="{ on: set.ink === id }" :title="ink.label" @click="pick({ ink: id })">
          <span class="drop" :style="{ background: ink.color }" /><span class="name">{{ ink.label }}</span>
        </button>
      </div>
    </div>

    <!-- ---------------------------------------------------------------- 火漆 -->
    <div v-else-if="tab === 'seal'" class="pane">
      <div class="waxes">
        <button v-for="(w, id) in WAX" :key="id" class="wax" :class="{ on: set.seal_color === id }" :title="w.label" @click="pick({ seal_color: id })">
          <img :src="w.url" alt="" />
        </button>
      </div>
      <template v-for="(ids, family) in motifGroups" :key="family">
        <p class="label">{{ family }}</p>
        <div class="motifs">
          <button v-for="id in ids" :key="id" class="motif" :class="{ on: set.seal_motif === id }" :title="MOTIFS[id].label"
            @click="id === 'initials' && !set.seal_initials ? null : pick({ seal_motif: id })">
            <SealImpression :color="set.seal_color" :motif="id" :initials="set.seal_initials || 'AB'" :size="roomy ? 54 : 44" />
          </button>
        </div>
        <div v-if="family === '字母'" class="initials">
          <input v-model="initials" class="field" maxlength="3" placeholder="1–3 个字母或一个字" aria-label="印章上的字母"
            @keydown.enter="saveInitials" @blur="saveInitials" />
        </div>
      </template>
    </div>

    <!-- ---------------------------------------------------------------- 邮票 -->
    <div v-else-if="tab === 'stamp'" class="pane">
      <div class="stamps">
        <button v-for="(st, id) in STAMPS" :key="id" class="stamp" :class="{ on: set.stamp === id }" :title="st.label" @click="pick({ stamp: id })">
          <PostageStamp :stamp="id" :tone="set.stamp_tone" :width="roomy ? 62 : 50" />
        </button>
        <span v-for="name in photoStamps" :key="name" class="stamp photo" :class="{ on: set.stamp === `photo:${name}` }">
          <button :title="'用这张照片做的邮票'" @click="pick({ stamp: `photo:${name}` })">
            <PostageStamp :stamp="`photo:${name}`" :tone="set.stamp_tone" :width="roomy ? 62 : 50" />
          </button>
          <button class="drop-photo" title="不要这枚了" @click="removePhotoStamp(name)"><Icon name="close" :size="10" /></button>
        </span>
        <button class="stamp add" :disabled="uploading" title="选一张照片，裁成一枚带齿孔的邮票" @click="fileInput.click()">
          <Icon name="photo" :size="18" /><span>{{ uploading ? '在做…' : '照片邮票' }}</span>
        </button>
        <input ref="fileInput" type="file" accept="image/*" hidden @change="addPhotoStamp($event.target.files[0]); $event.target.value = ''" />
      </div>
      <p class="label">色调</p>
      <div class="chips">
        <button v-for="(label, id) in STAMP_TONES" :key="id" class="chip" :class="{ on: set.stamp_tone === id }" @click="pick({ stamp_tone: id })">{{ label }}</button>
      </div>
    </div>

    <!-- ---------------------------------------------------------------- 信封 -->
    <div v-else class="pane envelopes">
      <button v-for="(e, id) in ENVELOPES" :key="id" class="envelope-pick" :class="{ on: set.envelope === id }" @click="pick({ envelope: id })">
        <LetterEnvelope :stationery="{ ...set, envelope: id }" side="back"
          :width="id === 'chinese' || id === 'pouch' ? (roomy ? 70 : 54) : roomy ? 130 : 104" />
        <span class="name">{{ e.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.picker {
  display: grid;
  align-content: start;
  gap: 10px;
  min-width: 0;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  border-bottom: 1px solid var(--rule);
}
.tab {
  padding: 4px 9px 6px;
  font-size: 13px;
  color: var(--ink-faint);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tab.on {
  color: var(--violet-ink);
  border-bottom-color: var(--violet-ink);
}
.pane {
  display: grid;
  gap: 8px;
  min-width: 0;
}
.label {
  margin: 4px 0 0 !important;
  font-size: 12px;
  color: var(--ink-faint);
  letter-spacing: 0.08em;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.name {
  font-size: 11.5px;
  color: var(--ink-soft);
  white-space: nowrap;
}
button.on .name {
  color: var(--violet-ink);
}
.swatches {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(62px, 1fr));
  gap: 8px;
}
.swatch {
  display: grid;
  justify-items: center;
  gap: 3px;
}
.sheet {
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 2px;
  background: #f6efe1 center / 140px;
  box-shadow: 0 0 0 1px var(--rule), 0 3px 6px -3px rgba(40, 20, 10, 0.35);
  transition: transform 0.2s var(--ease), box-shadow 0.2s;
}
.swatch.on .sheet {
  box-shadow: 0 0 0 2px var(--violet-ink), 0 4px 8px -3px rgba(40, 20, 10, 0.4);
  transform: translateY(-2px);
}
.heads {
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
}
.head img,
.head .post-head,
.head .none {
  display: grid;
  place-items: center;
  width: 100%;
  height: 34px;
  object-fit: contain;
  border-radius: 3px;
  background: #f6efe1;
  box-shadow: 0 0 0 1px var(--rule);
}
.post-head {
  font-family: 'Cutive Mono', monospace;
  font-size: 7.5px;
  letter-spacing: 0.08em;
  color: #4a3474;
}
.none {
  color: var(--ink-faint);
}
.head.on img,
.head.on .post-head,
.head.on .none {
  box-shadow: 0 0 0 2px var(--violet-ink);
}
.fonts {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 6px;
}
.font {
  display: grid;
  gap: 2px;
  padding: 6px 8px;
  border-radius: var(--radius);
  text-align: left;
  background: #f6efe1;
  color: #3b2a5c;
  box-shadow: 0 0 0 1px var(--rule);
}
.font .name {
  color: #7a6a8f;
}
.font.on {
  box-shadow: 0 0 0 2px var(--violet-ink);
}
.sample {
  line-height: 1.4;
  white-space: nowrap;
}
.inks {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.ink {
  display: grid;
  justify-items: center;
  gap: 3px;
}
.drop {
  width: 22px;
  height: 22px;
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg);
  box-shadow: 0 0 0 2px var(--sheet-raised), 0 0 0 3px transparent;
}
.ink.on .drop {
  box-shadow: 0 0 0 2px var(--sheet-raised), 0 0 0 3.5px var(--violet-ink);
}
.waxes {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 54px));
  gap: 4px;
}
.wax {
  padding: 2px;
  border-radius: 50%;
}
.wax img {
  width: 100%;
  display: block;
  transition: transform 0.2s var(--ease);
}
.wax.on {
  box-shadow: 0 0 0 2px var(--violet-ink);
}
.wax:hover img {
  transform: scale(1.08) rotate(-6deg);
}
.motifs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.motif {
  padding: 3px;
  border-radius: 50%;
  transition: background 0.2s;
}
.motif:hover {
  background: var(--violet-wash);
}
.motif.on {
  background: var(--violet-wash-strong);
  box-shadow: 0 0 0 1.5px var(--violet-ink);
}
.initials .field {
  width: 100%;
  height: 32px;
  font-size: 14px;
}
.stamps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-start;
}
.stamp {
  position: relative;
  padding: 3px;
  border-radius: 4px;
}
.stamp.on {
  background: var(--violet-wash-strong);
  box-shadow: 0 0 0 1.5px var(--violet-ink);
}
.stamp.add {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 4px;
  width: 56px;
  height: 74px;
  border: 1.5px dashed var(--rule-strong);
  font-size: 11px;
  color: var(--ink-faint);
}
.roomy .stamp.add {
  width: 68px;
  height: 88px;
}
.drop-photo {
  position: absolute;
  top: -4px;
  right: -4px;
  display: none;
  place-items: center;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: var(--sheet-raised);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  color: var(--ink-soft);
}
.stamp.photo:hover .drop-photo {
  display: grid;
}
.envelopes {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: end;
  gap: 12px 8px;
}
.envelope-pick {
  display: grid;
  justify-items: center;
  gap: 4px;
  padding: 6px 4px;
  border-radius: var(--radius);
}
.envelope-pick.on {
  background: var(--violet-wash-strong);
  box-shadow: 0 0 0 1.5px var(--violet-ink);
}
.roomy .envelopes {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
</style>
