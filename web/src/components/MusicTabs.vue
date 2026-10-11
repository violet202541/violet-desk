<script setup>
// 音乐的五个分页，像文件夹上的索引签。诗意的名字下面写着白话。
import { store, activeJobs, go } from '../store.js'

const TABS = [
  { id: 'search', label: '寻歌', hint: '搜索与下载' },
  { id: 'playlist', label: '歌单', hint: '导入整张歌单' },
  { id: 'library', label: '书信匣', hint: '本地曲库' },
  { id: 'shelf', label: '信札', hint: '收藏与我的歌单' },
  { id: 'post', label: '寄信室', hint: '下载队列与记录' },
]
</script>

<template>
  <div class="music-tabs" role="tablist" aria-label="音乐">
    <button v-for="tab in TABS" :key="tab.id" class="tab" :class="{ on: store.view === tab.id }" role="tab"
      :data-tab="tab.id" :aria-selected="store.view === tab.id" @click="go(tab.id)">
      <span class="label title-cn">{{ tab.label }}</span>
      <span class="hint">{{ tab.hint }}</span>
      <span v-if="tab.id === 'post' && activeJobs.length" class="count mono">{{ activeJobs.length }}</span>
    </button>
  </div>
</template>

<style scoped>
.music-tabs {
  display: flex;
  gap: 4px;
  margin: -6px 0 26px;
  border-bottom: 1px solid var(--rule-strong);
}
.tab {
  position: relative;
  display: grid;
  justify-items: start;
  padding: 7px 18px 6px;
  border: 1px solid transparent;
  border-bottom: 0;
  border-radius: 8px 8px 0 0;
  margin-bottom: -1px;
  color: var(--ink-faint);
  line-height: 1.3;
  transition: color 0.2s var(--ease), background 0.2s var(--ease);
}
.tab:hover {
  color: var(--ink);
  background: var(--violet-wash);
}
.tab.on {
  color: var(--ink);
  background: var(--sheet);
  border-color: var(--rule-strong);
}
.tab.on::before {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  top: -1px;
  height: 2px;
  border-radius: 2px;
  background: var(--violet-ink);
}
.label {
  font-size: 16px;
  letter-spacing: 0.08em;
}
.hint {
  font-size: 11.5px;
  color: var(--ink-faint);
}
.count {
  position: absolute;
  top: 4px;
  right: 6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--gold);
  color: #fff;
  font-size: 10.5px;
  line-height: 16px;
  text-align: center;
}
/* A song tucked into a bundle lands on this tab. */
.tab.caught {
  animation: tab-catch 0.8s cubic-bezier(0.3, 1.6, 0.5, 1);
}
@keyframes tab-catch {
  30% {
    transform: translateY(-4px);
    color: var(--gold);
  }
}
</style>
