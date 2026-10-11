<script setup>
// 退回的确认：一张退信单，盖着红色「退回」戳。写明每首歌夹在哪些信札里、是不是干花、进过几封回信。
import { computed, ref } from 'vue'
import { sendBack, cancelSendBack, confirmSendBack } from '../sendback.js'
import { trapFocus } from '../dialog.js'
import { duration } from '../format.js'
import Icon from './Icon.vue'

const box = ref(null)
const asking = computed(() => sendBack.asking)
const tracks = computed(() => asking.value?.tracks || [])
const single = computed(() => tracks.value.length === 1)

function notes(t) {
  const r = asking.value?.refs?.[t.id]
  if (!r) return []
  const out = []
  if (r.bundles.length) out.push({ icon: 'bundle', text: `夹在${r.bundles.map((b) => `《${b}》`).join('')}信札里` })
  if (r.pressed) out.push({ icon: 'heart', text: '压成了干花' })
  if (r.replies) out.push({ icon: 'quill', text: `夹进过 ${r.replies} 封回信` })
  return out
}
const anyTwin = computed(() => tracks.value.some((t) => asking.value?.refs?.[t.id]?.twin))
const anyKept = computed(() => tracks.value.some((t) => notes(t).length))

trapFocus(box, cancelSendBack)
</script>

<template>
  <Transition name="modal">
    <div v-if="asking" class="backdrop" @mousedown.self="cancelSendBack">
      <div ref="box" class="slip sheet" role="alertdialog" aria-modal="true" aria-labelledby="sendback-title">
        <span class="return-stamp" aria-hidden="true"><span>退 回</span><small>RETURN TO SENDER</small></span>
        <p class="eyebrow">Return to sender</p>
        <h2 id="sendback-title" class="title-cn">
          {{ single ? `把「${tracks[0].title}」退回去？` : `把这 ${tracks.length} 首歌退回去？` }}
        </h2>

        <ol class="songs" :class="{ one: single }">
          <li v-for="t in tracks" :key="t.id" class="song">
            <span class="names">
              <span class="title-text ellipsis">{{ t.title }}</span>
              <span class="faint small ellipsis">{{ t.artist || '佚名' }}<template v-if="t.ext"> · {{ t.ext.toUpperCase() }}</template><template v-if="t.duration"> · {{ duration(t.duration) }}</template></span>
            </span>
            <span v-if="asking.loading" class="faint small">…</span>
            <span v-else class="refs">
              <span v-for="n in notes(t)" :key="n.text" class="ref"><Icon :name="n.icon" :size="12" />{{ n.text }}</span>
            </span>
          </li>
        </ol>

        <p class="fine soft small">
          文件会连同同名歌词一起移进 Windows 回收站，想找回可以去回收站还原。
          <template v-if="anyKept">它会从信札和干花里取下；旧回信里还留着歌名，只是不能再放了。</template>
          <template v-if="anyTwin">书信匣里另有一份的，干花和信札会改夹在那一份上。</template>
        </p>

        <div class="buttons">
          <button class="btn ghost" autofocus @click="cancelSendBack">再想想</button>
          <button class="btn wax red" :disabled="asking.busy || asking.loading" @click="confirmSendBack">
            <Icon name="sendback" :size="15" />{{ asking.busy ? '正在退回…' : single ? '退回' : `退回 ${tracks.length} 首` }}
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
  z-index: 85;
  display: grid;
  place-items: center;
  background: rgba(30, 22, 40, 0.38);
  backdrop-filter: blur(3px);
}
.slip {
  position: relative;
  display: grid;
  gap: 6px;
  width: min(520px, calc(100vw - 48px));
  max-height: calc(100vh - 80px);
  padding: 28px 32px 22px;
  overflow: hidden;
}
.eyebrow {
  margin: 0;
}
h2 {
  margin: 0 96px 6px 0;
  font-size: 21px;
  font-weight: 400;
  line-height: 1.45;
}
/* A red rubber stamp, a little crooked, ink thinner at the edges. */
.return-stamp {
  position: absolute;
  top: 22px;
  right: 22px;
  display: grid;
  justify-items: center;
  padding: 5px 10px 4px;
  border: 2px solid var(--danger);
  border-radius: 4px;
  color: var(--danger);
  font-family: var(--font-title);
  transform: rotate(-11deg);
  opacity: 0.82;
  box-shadow: inset 0 0 0 2px var(--sheet), inset 0 0 0 3px var(--danger);
  mask-image: radial-gradient(circle at 30% 40%, #000 55%, rgba(0, 0, 0, 0.7) 75%, rgba(0, 0, 0, 0.85));
}
.return-stamp span {
  font-size: 19px;
  letter-spacing: 0.3em;
  margin-right: -0.3em;
  line-height: 1.2;
}
.return-stamp small {
  font-family: var(--font-mono);
  font-size: 7.5px;
  letter-spacing: 0.12em;
}
.songs {
  display: grid;
  gap: 0;
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
  max-height: 46vh;
  overflow-y: auto;
  border-top: 1px dashed var(--rule-strong);
}
.song {
  display: grid;
  gap: 4px;
  padding: 9px 2px;
  border-bottom: 1px dashed var(--rule-strong);
}
.names {
  display: grid;
  min-width: 0;
  line-height: 1.4;
}
.refs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
}
.refs:empty {
  display: none;
}
.ref {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--danger);
}
.small {
  font-size: 12.5px;
}
.fine {
  margin: 10px 0 0;
  line-height: 1.7;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .slip {
  transform: translateY(14px) scale(0.98);
}
.modal-enter-from .return-stamp {
  transform: rotate(-30deg) scale(1.8);
  opacity: 0;
}
.modal-enter-active,
.modal-leave-active,
.modal-enter-active .slip {
  transition: all 0.3s var(--ease);
}
.modal-enter-active .return-stamp {
  transition: all 0.45s cubic-bezier(0.2, 1.4, 0.4, 1) 0.15s;
}
</style>
