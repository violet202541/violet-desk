<script setup>
// 便笺式提示、Key 弹窗与确认弹窗。
import { nextTick, ref, watch } from 'vue'
import { store, dismissToast } from '../store.js'
import { api } from '../api.js'
import Icon from './Icon.vue'
import InkToggle from './InkToggle.vue'
import WaxSeal from './WaxSeal.vue'
import { trapFocus } from '../dialog.js'

const keyValue = ref('')
const remember = ref(true)
const keyError = ref('')
const saving = ref(false)
const keyInput = ref(null)
const keyBox = ref(null)
const confirmBox = ref(null)

watch(
  () => store.keyDialog,
  (dialog) => {
    if (dialog) {
      keyValue.value = ''
      keyError.value = ''
      nextTick(() => keyInput.value?.focus())
    }
  },
)

function closeKey(result) {
  store.keyDialog?.resolve(result)
  store.keyDialog = null
}

async function submitKey() {
  saving.value = true
  keyError.value = ''
  try {
    store.key = await api.setKey(keyValue.value, remember.value)
    closeKey(true)
  } catch (error) {
    keyError.value = error.message
  } finally {
    saving.value = false
  }
}

function closeConfirm(result) {
  store.confirmDialog?.resolve(result)
  store.confirmDialog = null
}

const ICON = { success: 'check', error: 'close', warning: 'sparkle', info: 'envelope' }

function act(t) {
  dismissToast(t.id)
  t.action.run()
}

trapFocus(keyBox, () => closeKey(false))
trapFocus(confirmBox, () => closeConfirm(false))
</script>

<template>
  <div class="toasts" aria-live="polite">
    <TransitionGroup name="slip">
      <div v-for="t in store.toasts" :key="t.id" class="slip" :class="t.level" @click="dismissToast(t.id)">
        <Icon :name="ICON[t.level] || 'envelope'" :size="16" />
        <span>{{ t.text }}</span>
        <button v-if="t.action" class="slip-action" @click.stop="act(t)">{{ t.action.label }}</button>
      </div>
    </TransitionGroup>
  </div>

  <Transition name="modal">
    <div v-if="store.keyDialog" class="backdrop" @mousedown.self="closeKey(false)" @keydown.esc="closeKey(false)">
      <form ref="keyBox" class="dialog sheet" role="dialog" aria-modal="true" aria-labelledby="key-title" @submit.prevent="submitKey">
        <WaxSeal class="seal" :size="58"><Icon name="key" :size="22" /></WaxSeal>
        <p class="eyebrow">A key for the post office</p>
        <h2 id="key-title" class="title-cn">请交给我一把钥匙</h2>
        <p class="soft">{{ store.keyDialog.reason || '搜索与下载需要 ChKSz API Key。' }}</p>
        <input ref="keyInput" v-model="keyValue" class="field mono" type="password" placeholder="chksz_…" autocomplete="off" spellcheck="false" />
        <p v-if="keyError" class="error">{{ keyError }}</p>
        <InkToggle v-model="remember" label="记住它" hint="保存到 ~/.chksz_key，命令行工具也能使用" />
        <div class="buttons">
          <a class="small" href="https://api.chksz.com/#apis" target="_blank" rel="noreferrer">还没有 Key？</a>
          <button class="btn ghost" type="button" @click="closeKey(false)">稍后</button>
          <button class="btn wax" type="submit" :disabled="saving || !keyValue.trim()">交给 Violet</button>
        </div>
      </form>
    </div>
  </Transition>

  <Transition name="modal">
    <div v-if="store.confirmDialog" class="backdrop" @mousedown.self="closeConfirm(false)" @keydown.esc="closeConfirm(false)">
      <div ref="confirmBox" class="dialog sheet small-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title" class="title-cn">{{ store.confirmDialog.title }}</h2>
        <p class="soft">{{ store.confirmDialog.text }}</p>
        <div class="buttons">
          <button class="btn ghost" autofocus @click="closeConfirm(false)">取消</button>
          <button class="btn wax" @click="closeConfirm(true)">{{ store.confirmDialog.ok }}</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.toasts {
  position: fixed;
  right: 24px;
  bottom: calc(var(--player) + 18px);
  z-index: 60;
  display: grid;
  gap: 10px;
  justify-items: end;
  pointer-events: none;
}
.slip {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 420px;
  padding: 11px 16px 11px 14px;
  background: var(--sheet-raised);
  border: 1px solid var(--rule);
  border-left: 3px solid var(--violet-ink);
  border-radius: 3px;
  box-shadow: var(--shadow-lift);
  font-size: 14px;
  line-height: 1.5;
  cursor: pointer;
}
.slip :deep(svg) {
  flex: none;
  margin-top: 3px;
  color: var(--violet-ink);
}
.slip.success {
  border-left-color: var(--emerald);
}
.slip.success :deep(svg) {
  color: var(--emerald);
}
.slip.error {
  border-left-color: var(--danger);
}
.slip.error :deep(svg) {
  color: var(--danger);
}
.slip.warning {
  border-left-color: var(--gold);
}
.slip.warning :deep(svg) {
  color: var(--gold);
}
.slip-action {
  flex: none;
  margin-left: 6px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--violet-ink);
  border: 1px solid color-mix(in srgb, var(--violet-ink) 40%, transparent);
}
.slip-action:hover {
  background: var(--violet-wash);
}
.slip-enter-from {
  opacity: 0;
  transform: translateY(12px) rotate(1.5deg);
}
.slip-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
.slip-enter-active,
.slip-leave-active {
  transition: all 0.4s var(--ease);
}

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
  width: min(460px, calc(100vw - 48px));
  padding: 44px 34px 26px;
  display: grid;
  gap: 10px;
  background: var(--sheet-raised);
  box-shadow: var(--shadow-lift);
}
.seal {
  position: absolute;
  top: -29px;
  left: 50%;
  margin-left: -29px;
}
.dialog h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 400;
}
.dialog .eyebrow,
.dialog p {
  margin: 0;
}
.dialog .field {
  margin-top: 6px;
}
.error {
  color: var(--danger);
  font-size: 13px;
}
.buttons {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}
.buttons .small {
  margin-right: auto;
  font-size: 13px;
}
.small-dialog {
  padding-top: 28px;
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
