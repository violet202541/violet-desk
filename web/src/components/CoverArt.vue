<script setup>
// 封面：加载前显示信封纹样，失败时保留；首字母用泰尔西斯文字压印。
import { ref, watch } from 'vue'
import Nunkish from './Nunkish.vue'

const props = defineProps({
  src: { type: String, default: '' },
  size: { type: [Number, String], default: 48 },
  seed: { type: String, default: '' },
  radius: { type: Number, default: 4 },
})
const loaded = ref(false)
const failed = ref(false)
watch(
  () => props.src,
  () => {
    loaded.value = false
    failed.value = false
  },
)
const initial = () => (props.seed.match(/[a-z]/i)?.[0] || 'v').toLowerCase()
</script>

<template>
  <span class="cover" :style="{ width: typeof size === 'number' ? size + 'px' : size, borderRadius: radius + 'px' }">
    <span v-if="!loaded" class="placeholder">
      <Nunkish :text="initial()" :size="typeof size === 'number' ? Math.max(14, size * 0.42) : 40" :weight="5" />
    </span>
    <img v-if="src && !failed" :src="src" alt="" loading="lazy" decoding="async" :class="{ loaded }"
      @load="loaded = true" @error="failed = true" />
  </span>
</template>

<style scoped>
.cover {
  position: relative;
  display: block;
  flex: none;
  aspect-ratio: 1;
  overflow: hidden;
  background: linear-gradient(135deg, var(--paper-deep), var(--sheet));
  box-shadow: 0 0 0 1px var(--rule) inset;
}
.placeholder {
  position: absolute;
  inset: var(--cover-inset, 0);
  display: grid;
  place-items: center;
  color: var(--violet-ink);
  opacity: 0.4;
}
img {
  position: absolute;
  inset: var(--cover-inset, 0);
  width: calc(100% - 2 * var(--cover-inset, 0px));
  height: calc(100% - 2 * var(--cover-inset, 0px));
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.4s var(--ease);
}
img.loaded {
  opacity: 1;
}
</style>
