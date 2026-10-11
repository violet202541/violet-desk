<script setup>
// 扎一束信札：起个名字，写一句题记，挑一条缎带。右边是这束信札扎好后的样子。
import { computed, nextTick, ref, watch } from 'vue'
import { shelf, RIBBONS, saveBundle, openBundle } from '../shelf.js'
import { sendLetters, go } from '../store.js'
import { trapFocus } from '../dialog.js'
import BundleCard from './BundleCard.vue'
import Icon from './Icon.vue'

const box = ref(null)
const nameInput = ref(null)
const form = ref({ name: '', epigraph: '', ribbon: 'violet' })
const saving = ref(false)
const editing = computed(() => shelf.editing)
const count = computed(() => (editing.value?.trackIds?.length || 0) + (editing.value?.songs?.length || 0))
const IDEAS = ['雨天读的信', '写作业时', '深夜的灯', '想念一个人', '出门走走', '旧时光']

watch(editing, async (e) => {
  if (!e) return
  form.value = { name: e.name || '', epigraph: e.epigraph || '', ribbon: e.ribbon || 'violet' }
  saving.value = false
  await nextTick()
  nameInput.value?.focus()
})

async function tie() {
  const e = editing.value
  if (!form.value.name.trim() || saving.value) return
  saving.value = true
  const bundle = await saveBundle({ ...e, ...form.value })
  saving.value = false
  if (!bundle) return
  shelf.editing = null
  // Copying an online playlist: send only the songs the letter box does not have yet (the bundle's pending letters).
  if (e.download && e.downloadSongs?.length) {
    const norm = (text) => (text || '').toLowerCase().replace(/[\s\p{P}\p{S}]+/gu, '')
    const waiting = new Set((bundle.letters || []).filter((l) => l.state === 'pending').map((l) => norm(l.title) + '|' + norm(l.artist)))
    const missing = e.downloadSongs.filter((s) => waiting.has(norm(s.name) + '|' + norm(s.artist)))
    if (missing.length) await sendLetters(missing)
  }
  if (e.open) {
    go('shelf')
    openBundle(bundle.id)
  }
}

const close = () => (shelf.editing = null)
trapFocus(box, close)
</script>

<template>
  <Transition name="modal">
    <div v-if="editing" class="backdrop" @mousedown.self="close">
      <div ref="box" class="tie sheet" role="dialog" aria-modal="true" aria-labelledby="tie-title">
        <button class="icon-btn close" title="关上 (Esc)" @click="close"><Icon name="close" :size="16" /></button>
        <div class="form">
          <p class="eyebrow">{{ editing.id ? 'Retie the bundle' : 'Tie a bundle of letters' }}</p>
          <h2 id="tie-title" class="title-cn">{{ editing.id ? '重新扎这束信札' : '扎一束信札' }}</h2>
          <p class="faint small">信札就是你自己的歌单：想放在一起听的歌，用一条缎带扎起来。</p>

          <label class="field-label" for="tie-name">名字</label>
          <input id="tie-name" ref="nameInput" v-model="form.name" class="field" maxlength="40" placeholder="比如：雨天读的信"
            @keydown.enter.prevent="tie" />
          <div v-if="!editing.id && !form.name" class="ideas">
            <button v-for="idea in IDEAS" :key="idea" class="chip" @click="form.name = idea">{{ idea }}</button>
          </div>

          <label class="field-label" for="tie-epigraph">题记 <span class="faint">（写在最上面的一句话，可以不写）</span></label>
          <input id="tie-epigraph" v-model="form.epigraph" class="field" maxlength="80" placeholder="窗外在下雨，信纸有点潮" />

          <p class="field-label">缎带</p>
          <div class="ribbons" role="radiogroup" aria-label="缎带颜色">
            <button v-for="(r, key) in RIBBONS" :key="key" class="ribbon-pick" :class="{ on: form.ribbon === key }"
              role="radio" :aria-checked="form.ribbon === key" :title="r.label" :style="{ '--ribbon': r.hue }"
              @click="form.ribbon = key">
              <span class="swatch" /><span class="ribbon-name">{{ r.label }}</span>
            </button>
          </div>

          <p v-if="count" class="faint small tuck">
            <Icon name="envelope" :size="14" />扎好后会夹进 {{ count }} 封信<template v-if="editing.download">，书信匣里还没有的会顺便寄回来</template>
          </p>

          <div class="actions">
            <button class="btn ghost" @click="close">再想想</button>
            <button class="btn wax" :disabled="!form.name.trim() || saving" @click="tie">
              <Icon name="ribbon" :size="16" />{{ editing.id ? '重新系好' : '系上缎带' }}
            </button>
          </div>
        </div>
        <div class="preview" aria-hidden="true">
          <BundleCard :bundle="{ ...editing, ...form, name: form.name || '还没有名字', covers: editing.covers || [] }"
            preview :tilt="-3" />
          <p class="preview-name title-text">{{ form.name || '还没有名字' }}</p>
          <p v-if="form.epigraph" class="preview-epigraph">{{ form.epigraph }}</p>
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
.tie {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 250px;
  gap: 34px;
  width: min(760px, calc(100vw - 48px));
  max-height: calc(100vh - 80px);
  overflow-y: auto;
  padding: 32px 36px 26px;
}
.close {
  position: absolute;
  top: 12px;
  right: 12px;
}
.form {
  display: grid;
  align-content: start;
  gap: 6px;
}
.form h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 400;
}
.form p {
  margin: 0;
}
.small {
  font-size: 12.5px;
}
.field-label {
  margin-top: 14px !important;
  font-size: 13px;
  color: var(--ink-soft);
}
.field {
  height: 38px;
  font-size: 15px;
}
.ideas {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
.ribbons {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}
.ribbon-pick {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: var(--radius);
  font-size: 13px;
  color: var(--ink-soft);
  transition: border-color 0.2s var(--ease), background 0.2s var(--ease);
}
.ribbon-pick:hover {
  background: var(--violet-wash);
}
.ribbon-pick.on {
  border-color: var(--ribbon);
  color: var(--ink);
}
.swatch {
  width: 26px;
  height: 10px;
  border-radius: 2px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.25), transparent 45%, rgba(0, 0, 0, 0.18)), var(--ribbon);
  /* A ribbon end, cut on the bias. */
  clip-path: polygon(0 0, 100% 0, 86% 50%, 100% 100%, 0 100%);
}
.tuck {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 14px !important;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
.preview {
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 10px;
  padding: 10px 6px;
  border-left: 1px dashed var(--rule-strong);
  padding-left: 30px;
}
.preview :deep(.bundle) {
  width: 210px;
}
.preview-name {
  margin: 8px 0 0;
  font-size: 17px;
  text-align: center;
}
.preview-epigraph {
  margin: 0;
  font-size: 12.5px;
  font-style: italic;
  color: var(--ink-soft);
  text-align: center;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .tie {
  transform: translateY(14px) scale(0.98);
}
.modal-enter-active,
.modal-leave-active,
.modal-enter-active .tie {
  transition: all 0.3s var(--ease);
}
@media (max-width: 760px) {
  .tie {
    grid-template-columns: minmax(0, 1fr);
  }
  .preview {
    display: none;
  }
}
</style>
