<script setup>
// 同一封信收到了好几份：并排比一比格式、码率和长短，留下最好的那份，其余的退回。
import { computed, ref } from 'vue'
import { sendBack, closeDuplicates, spareCopies, sendBackSpares } from '../sendback.js'
import { trapFocus } from '../dialog.js'
import { duration, bytes } from '../format.js'
import { coverOf } from '../player.js'
import CoverArt from './CoverArt.vue'
import InkLoader from './InkLoader.vue'
import Icon from './Icon.vue'

const box = ref(null)
const dupes = computed(() => sendBack.dupes)
const spares = computed(() => spareCopies())

function keep(group, id) {
  sendBack.dupes.keep = { ...sendBack.dupes.keep, [group.key]: id }
}

trapFocus(box, closeDuplicates)
</script>

<template>
  <Transition name="modal">
    <div v-if="dupes" class="backdrop" @mousedown.self="closeDuplicates">
      <div ref="box" class="twins sheet" role="dialog" aria-modal="true" aria-labelledby="twins-title">
        <button class="icon-btn close" title="关上 (Esc)" @click="closeDuplicates"><Icon name="close" :size="16" /></button>
        <p class="eyebrow">Duplicate letters</p>
        <h2 id="twins-title" class="title-cn">同一封信，收到了好几份</h2>
        <p class="faint small lead">每组留一份就好：默认留无损、码率高、更完整的那份。长短差得多的，可能是现场版或别的版本，先都留着。</p>

        <InkLoader v-if="dupes.loading" label="正在一封封比对…" script="sorting" />
        <p v-else-if="!dupes.groups.length" class="none title-cn">没有重复的信，书信匣很整齐。</p>
        <div v-else class="groups">
          <section v-for="g in dupes.groups" :key="g.key" class="group">
            <header class="group-head">
              <CoverArt :src="coverOf(g.copies[0])" :size="34" :seed="g.title" />
              <span class="names">
                <span class="title-text ellipsis">{{ g.title }}</span>
                <span class="faint small ellipsis">{{ g.artist || '佚名' }} · {{ g.copies.length }} 份</span>
              </span>
              <span v-if="g.versions" class="versions small">可能是不同版本</span>
              <button class="chip" :class="{ on: dupes.keep[g.key] === 'all' }" @click="keep(g, 'all')">都留着</button>
            </header>
            <label v-for="(c, i) in g.copies" :key="c.id" class="copy" :class="{ kept: dupes.keep[g.key] === c.id, all: dupes.keep[g.key] === 'all', leaving: dupes.keep[g.key] !== 'all' && dupes.keep[g.key] !== c.id }">
              <input type="radio" :name="g.key" :checked="dupes.keep[g.key] === c.id" @change="keep(g, c.id)" />
              <span class="fmt mono" :class="{ lossless: c.lossless }">{{ (c.ext || '').toUpperCase() }}</span>
              <span class="mono small">{{ c.kbps ? `${c.kbps} kbps` : '—' }}</span>
              <span class="mono small">{{ duration(c.duration) }}</span>
              <span class="mono small faint">{{ bytes(c.size) }}</span>
              <span class="faint small ellipsis" :title="c.folder">{{ c.folder === '.' ? '下载目录' : c.folder }}</span>
              <span class="tag small">
                <template v-if="dupes.keep[g.key] === c.id">留下</template>
                <template v-else-if="dupes.keep[g.key] !== 'all'">退回</template>
                <template v-else-if="i === 0">最好</template>
              </span>
            </label>
          </section>
        </div>

        <div class="buttons">
          <button class="btn ghost" @click="closeDuplicates">先不整理</button>
          <button class="btn wax red" :disabled="!spares.length" @click="sendBackSpares">
            <Icon name="sendback" :size="15" />{{ spares.length ? `退回 ${spares.length} 份多余的` : '没有要退回的' }}
          </button>
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
.twins {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(720px, calc(100vw - 48px));
  max-height: calc(100vh - 80px);
  padding: 28px 32px 22px;
}
.twins > * {
  flex: none;
}
.close {
  position: absolute;
  top: 12px;
  right: 12px;
}
.eyebrow {
  margin: 0;
}
h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 400;
}
.lead {
  margin: 6px 0 12px;
  line-height: 1.7;
}
.small {
  font-size: 12.5px;
}
.none {
  margin: 30px 0;
  text-align: center;
  color: var(--ink-soft);
}
.groups {
  flex: 0 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  gap: 14px;
  padding-right: 4px;
}
.group {
  border-top: 1px dashed var(--rule-strong);
  padding-top: 10px;
}
.group-head {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}
.names {
  display: grid;
  min-width: 0;
  line-height: 1.35;
}
.versions {
  color: var(--gold);
}
.copy {
  display: grid;
  grid-template-columns: 18px 52px 74px 48px 64px minmax(0, 1fr) 40px;
  align-items: center;
  gap: 10px;
  padding: 5px 8px 5px 46px;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.2s var(--ease), opacity 0.2s var(--ease);
}
.copy:hover {
  background: var(--violet-wash);
}
.copy input {
  accent-color: var(--violet-ink);
  margin: 0;
}
.copy.leaving {
  opacity: 0.62;
}
.copy.leaving .tag {
  color: var(--danger);
}
.copy.kept .tag {
  color: var(--violet-ink);
}
.tag {
  font-family: var(--font-title);
  text-align: right;
  color: var(--ink-faint);
}
.fmt {
  justify-self: start;
  font-size: 11px;
  padding: 0 5px;
  border: 1px solid var(--rule-strong);
  border-radius: 3px;
  color: var(--ink-soft);
  line-height: 18px;
}
.fmt.lossless {
  color: var(--gold);
  border-color: color-mix(in srgb, var(--gold) 50%, transparent);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .twins {
  transform: translateY(14px) scale(0.98);
}
.modal-enter-active,
.modal-leave-active,
.modal-enter-active .twins {
  transition: all 0.3s var(--ease);
}
</style>
