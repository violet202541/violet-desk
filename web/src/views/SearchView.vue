<script setup>
import { computed, ref, onMounted } from 'vue'
import { store, runSearch, loadMore } from '../store.js'
import { sound } from '../sound.js'
import Wordmark from '../components/Wordmark.vue'
import Nunkish from '../components/Nunkish.vue'
import StampPicker from '../components/StampPicker.vue'
import CatalogResults from '../components/CatalogResults.vue'
import InkLoader from '../components/InkLoader.vue'
import EmptyState from '../components/EmptyState.vue'
import Icon from '../components/Icon.vue'

const view = store.search
const input = ref(null)
const results = ref(null)
const compact = computed(() => Boolean(view.songs.length || view.loading || view.error || view.lastQuery))
const PLATFORMS = [
  { value: 'netease', label: '网易云', sub: 'NetEase' },
  { value: 'qq', label: 'QQ音乐', sub: 'Tencent' },
  { value: 'kugou', label: '酷狗', sub: 'Kugou' },
  { value: 'all', label: '聚合', sub: 'All three' },
]

function submit() {
  sound.key()
  runSearch()
}

function focus() {
  input.value?.focus()
  input.value?.select()
}

onMounted(() => {
  if (!view.songs.length) setTimeout(() => input.value?.focus(), 400)
})

defineExpose({
  focus,
  sendSelected: () => results.value?.sendSelected(),
  selectVisible: () => results.value?.selectVisible(),
})
</script>

<template>
  <div class="search" :class="{ compact }">
    <header class="hero">
      <p class="eyebrow">Auto Memory Doll · 代笔寻歌</p>
      <Wordmark class="mark" :height="compact ? 52 : 118" />
      <div class="signature">
        <span class="rule" />
        <Nunkish text="violet evergarden" :size="compact ? 14 : 22" :weight="4.2" />
        <span class="rule" />
      </div>
      <p class="tagline title-cn">写下想听的歌，我替你把它寄回来。</p>
    </header>

    <form class="compose" @submit.prevent="submit">
      <label class="line">
        <Icon name="quill" :size="22" class="nib" />
        <input ref="input" v-model="view.query" class="query" placeholder="歌名、歌手，或记得的一句歌词…"
          autocomplete="off" spellcheck="false" />
        <button class="btn wax go" type="submit" :disabled="view.loading">
          {{ view.loading ? '寻找中' : '寻找' }}
        </button>
      </label>
      <StampPicker v-model="view.platform" :options="PLATFORMS" :compact="compact" />
    </form>
    <div v-if="!compact" class="hints faint">
      <span><kbd>Enter</kbd> 寻找</span>
      <span><kbd>Ctrl</kbd> + <kbd>D</kbd> 寄出所选</span>
      <span><kbd>/</kbd> 回到搜索</span>
      <span><kbd>Space</kbd> 播放 / 暂停</span>
    </div>

    <InkLoader v-if="view.loading && !view.songs.length" label="正在替你翻找…" script="searching" />
    <EmptyState v-else-if="view.error && !view.songs.length" script="sorry" title="这封信没能寄出" :hint="view.error">
      <button class="btn" @click="submit">再试一次</button>
    </EmptyState>
    <EmptyState v-else-if="view.lastQuery && !view.songs.length" script="nothing" title="没有找到这首歌"
      hint="换个关键词，或换一个平台试试。" />
    <template v-else-if="view.songs.length">
      <p v-if="view.error" class="inline-error">刚才的寻找失败了：{{ view.error }} · 下面仍是上一次的结果</p>
      <CatalogResults ref="results" :view="view" :show-platform="view.lastPlatform === 'all'" :more="view.hasMore"
        :loading-more="view.loadingMore" @more="loadMore" />
    </template>
  </div>
</template>

<style scoped>
.search {
  padding-top: 6vh;
}
.hero {
  display: grid;
  justify-items: center;
  text-align: center;
}
.mark {
  margin: 6px 0 2px;
  transition: height 0.5s var(--ease), width 0.5s var(--ease);
}
.signature {
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--gold);
  opacity: 0.85;
}
.rule {
  width: 72px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold-soft));
}
.rule:last-child {
  transform: scaleX(-1);
}
.tagline {
  margin: 14px 0 0;
  color: var(--ink-soft);
  font-size: 17px;
  letter-spacing: 0.12em;
}
.compose {
  display: grid;
  justify-items: center;
  gap: 26px;
  margin: 38px auto 0;
  max-width: 760px;
}
.line {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 4px 10px;
  border-bottom: 1.5px solid var(--rule-strong);
  background-image: linear-gradient(var(--violet-ink), var(--violet-ink));
  background-size: 0 1.5px;
  background-repeat: no-repeat;
  background-position: left bottom;
  transition: background-size 0.6s var(--ease);
}
.line:focus-within {
  background-size: 100% 1.5px;
}
.nib {
  color: var(--violet-ink);
  flex: none;
}
.query {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  font-family: var(--font-title);
  font-size: 26px;
  letter-spacing: 0.03em;
  color: var(--ink);
}
.query::placeholder {
  color: var(--ink-faint);
  opacity: 0.8;
}
.go {
  height: 40px;
  padding: 0 24px;
  font-size: 15px;
}
.hints {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px 26px;
  margin-top: 48px;
  font-size: 13px;
}
kbd {
  font-family: var(--font-mono);
  font-size: 12px;
  padding: 1px 6px;
  border: 1px solid var(--rule-strong);
  border-bottom-width: 2px;
  border-radius: 4px;
  color: var(--ink-soft);
}
.inline-error {
  color: var(--danger);
  font-size: 13px;
  margin: 16px 14px 0;
}

/* Compact header once there is something to show. */
.compact {
  padding-top: 0;
}
.compact .hero {
  grid-template-columns: auto auto;
  justify-content: start;
  align-items: end;
  column-gap: 18px;
  text-align: left;
}
.compact .eyebrow,
.compact .tagline {
  display: none;
}
.compact .signature {
  padding-bottom: 10px;
}
.compact .rule:first-child {
  display: none;
}
.compact .compose {
  grid-template-columns: 1fr auto;
  align-items: end;
  max-width: none;
  margin-top: 18px;
  gap: 28px;
}
.compact .query {
  font-size: 21px;
}
</style>
