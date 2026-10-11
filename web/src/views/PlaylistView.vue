<script setup>
import { ref } from 'vue'
import { store, loadPlaylist, songKey } from '../store.js'
import { shelf } from '../shelf.js'
import { coverUrl } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import StampPicker from '../components/StampPicker.vue'
import CatalogResults from '../components/CatalogResults.vue'
import InkLoader from '../components/InkLoader.vue'
import EmptyState from '../components/EmptyState.vue'
import CoverArt from '../components/CoverArt.vue'
import PlatformStamp from '../components/PlatformStamp.vue'
import Icon from '../components/Icon.vue'

const view = store.playlist
const input = ref(null)
const results = ref(null)
const PLATFORMS = [
  { value: 'qq', label: 'QQ音乐', sub: '公开歌单 · 无需 Key' },
  { value: 'netease', label: '网易云', sub: '需要 API Key' },
]

// 抄成信札: copy the online playlist (or just the ticked songs) into a bundle of your own.
// Songs already in the letter box are tucked in at once; the rest travel there as they are downloaded.
function copyToBundle() {
  const picked = view.songs.filter((s) => view.selected.has(songKey(s)))
  const songs = picked.length ? picked : view.songs
  shelf.editing = {
    name: (view.info?.title || '').slice(0, 40),
    epigraph: picked.length ? '' : `抄自${view.info?.platform === 'netease' ? '网易云' : ' QQ 音乐'}的歌单`,
    songs: songs.map((s) => ({ title: s.name, artist: s.artist, album: s.album })),
    download: true,
    downloadSongs: songs,
    open: true,
  }
}

defineExpose({
  focus: () => input.value?.focus(),
  sendSelected: () => results.value?.sendSelected(),
  selectVisible: () => results.value?.selectVisible(),
})
</script>

<template>
  <div>
    <PageHeader eyebrow="Music · Collections" title="歌单" script="letters"
      subtitle="粘贴 QQ 音乐或网易云的公开歌单链接，整本信札一次展开。" />

    <form class="compose" @submit.prevent="loadPlaylist">
      <label class="line">
        <Icon name="link" :size="20" class="nib" />
        <input ref="input" v-model="view.source" class="field source"
          placeholder="https://y.qq.com/n/ryqq/playlist/…  或  music.163.com/#/playlist?id=…  或纯数字 ID"
          autocomplete="off" spellcheck="false" />
      </label>
      <StampPicker v-model="view.platform" :options="PLATFORMS" compact />
      <button class="btn wax" type="submit" :disabled="view.loading">{{ view.loading ? '展开中' : '展开歌单' }}</button>
    </form>
    <p class="note faint">完整链接会自动识别平台；纯数字 ID 按所选邮票处理。</p>

    <InkLoader v-if="view.loading && !view.songs.length" label="正在拆开这叠信…" script="opening" />
    <EmptyState v-else-if="view.error && !view.songs.length" script="sorry" title="歌单没能展开" :hint="view.error" />
    <template v-else-if="view.songs.length">
      <p v-if="view.error" class="inline-error">{{ view.error }} · 下面仍是上一次的歌单</p>
      <article class="folio sheet">
        <CoverArt class="folio-cover stamp-edge" :src="coverUrl({ picUrl: view.info?.cover }, 300)" :size="112"
          :seed="view.info?.title || ''" :radius="0" />
        <div class="folio-text">
          <p class="eyebrow">A bundle of letters</p>
          <h2 class="title-text">{{ view.info?.title }}</h2>
          <p class="meta">
            <PlatformStamp :platform="view.info?.platform || view.platform" />
            <span class="mono">{{ view.songs.length }} 首</span>
            <span class="mono faint">#{{ view.info?.id }}</span>
          </p>
          <button class="btn small copy" :title="view.selected.size ? '把勾选的歌扎成一束信札，没有的顺便寄回来' : '把整张歌单扎成一束信札，没有的顺便寄回来'"
            @click="copyToBundle">
            <Icon name="ribbon" :size="15" />{{ view.selected.size ? `把勾选的 ${view.selected.size} 首抄成信札` : '整张抄成一束信札' }}
          </button>
        </div>
      </article>
      <CatalogResults ref="results" :view="view" :show-platform="false" />
    </template>
    <EmptyState v-else script="your letters" title="还没有展开任何歌单"
      hint="QQ 音乐公开歌单不需要 Key 就能浏览；下载每首歌时才会使用你的 API Key。" />
  </div>
</template>

<style scoped>
.compose {
  display: flex;
  align-items: flex-end;
  gap: 22px;
}
.line {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.nib {
  color: var(--violet-ink);
  flex: none;
}
.source {
  flex: 1;
  min-width: 0;
  height: 44px;
  font-size: 16px;
}
.note {
  font-size: 12.5px;
  margin: 10px 0 0 32px;
}
.inline-error {
  color: var(--danger);
  font-size: 13px;
}
.folio {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 22px 26px;
  margin-top: 30px;
}
.folio-cover {
  box-shadow: none;
}
.folio-text h2 {
  margin: 0;
  font-size: 26px;
  line-height: 1.3;
}
.folio-text .eyebrow {
  margin: 0;
}
.meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--ink-soft);
}
.copy {
  margin-top: 10px;
}
</style>
