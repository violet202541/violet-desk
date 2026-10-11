<script setup>
// 打字机打出一行字：一个字一个字落下，打完后光标再闪几下就隐去。
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { calm } from '../motion.js'

const props = defineProps({
  text: { type: String, required: true },
  delay: { type: Number, default: 300 },
  speed: { type: Number, default: 55 },
})
const shown = ref('')
const typing = ref(false)
const resting = ref(false)
let timer = null

function run() {
  clearTimeout(timer)
  if (calm()) {
    shown.value = props.text
    resting.value = true
    return
  }
  shown.value = ''
  typing.value = true
  resting.value = false
  let i = 0
  const step = () => {
    i += 1
    shown.value = props.text.slice(0, i)
    if (i < props.text.length) {
      // A little hesitation after punctuation, like a hand reaching for the next key.
      const pause = /[，。、·,.]/.test(props.text[i - 1]) ? 220 : 0
      timer = setTimeout(step, props.speed + Math.random() * 45 + pause)
    } else {
      typing.value = false
      timer = setTimeout(() => (resting.value = true), 1800)
    }
  }
  timer = setTimeout(step, props.delay)
}

onMounted(run)
watch(() => props.text, (now, before) => {
  // Later changes (the hour turns) simply swap the words.
  if (before) shown.value = now
})
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <span class="type-line" :aria-label="text">
    <span aria-hidden="true">{{ shown }}</span><span class="caret" :class="{ typing, resting }" aria-hidden="true" />
    <span class="ghost" aria-hidden="true">{{ text.slice(shown.length) }}</span>
  </span>
</template>

<style scoped>
.type-line {
  position: relative;
  white-space: pre;
}
/* Keeps the line its full width while it is being typed, so nothing around it shifts. */
.ghost {
  visibility: hidden;
}
.caret {
  display: inline-block;
  width: 0.5em;
  height: 2px;
  margin-left: 1px;
  vertical-align: -0.1em;
  background: currentColor;
  animation: blink 1s steps(1) infinite;
}
.caret.typing {
  animation: none;
}
.caret.resting {
  opacity: 0;
  transition: opacity 0.8s;
  animation: none;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
