<script setup>
import { computed, ref } from 'vue'
import { store, activeJobs, toast, TERMINAL, STATE_LABEL, requireKey, confirm } from '../store.js'
import { api, coverUrl } from '../api.js'
import { bytes, dayLabel, timeOfDay, postmarkDate } from '../format.js'
import PageHeader from '../components/PageHeader.vue'
import CoverArt from '../components/CoverArt.vue'
import PlatformStamp from '../components/PlatformStamp.vue'
import EmptyState from '../components/EmptyState.vue'
import WaxSeal from '../components/WaxSeal.vue'
import Nunkish from '../components/Nunkish.vue'
import Icon from '../components/Icon.vue'

const FILTERS = { all: '全部', done: '已送达', failed: '未送达', other: '已存在 / 撤回' }
const filter = ref('all')

const sessionFailed = computed(() => store.jobs.filter((j) => j.state === 'failed').length)
const sessionFinished = computed(() => store.jobs.filter((j) => TERMINAL.has(j.state)).length)
const doneCount = computed(() => store.history.filter((r) => r.state === 'done').length)

const groups = computed(() => {
  const list = store.history.filter((r) => {
    if (filter.value === 'all') return true
    if (filter.value === 'other') return r.state === 'skipped' || r.state === 'cancelled'
    return r.state === filter.value
  })
  const out = []
  for (const record of list) {
    const label = dayLabel(record.finished || record.created)
    if (!out.length || out[out.length - 1].label !== label) out.push({ label, items: [] })
    out[out.length - 1].items.push(record)
  }
  return out
})

function eta(job) {
  if (!job.total_bytes || !job.speed || job.done_bytes >= job.total_bytes) return ''
  const s = Math.round((job.total_bytes - job.done_bytes) / job.speed)
  return ` · 剩 ${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

async function run(action, success) {
  try {
    const result = await action()
    if (success) toast(success(result), 'success')
  } catch (error) {
    toast(error.message, 'error', 6000)
    if (error.code === 'no_key') requireKey(error.message)
  }
}

const cancelAll = () => run(() => api.cancel(), (r) => `已撤回 ${r.cancelled} 封信`)
const cancelOne = (id) => run(() => api.cancel(id))
const retryAll = async () => {
  if (!(await requireKey('重试需要 API Key'))) return
  run(() => api.retry(), (r) => `已重新寄出 ${r.retried} 封`)
}
const retryRecord = async (id) => {
  if (!(await requireKey('重试需要 API Key'))) return
  run(() => api.retryRecord(id), (r) => (r.retried ? '已重新交给邮差' : '这封信已经在路上了'))
}
const reveal = (id) => run(() => api.reveal({ record: id }))
const removeRecord = (id) => run(() => api.removeHistory([id]))
const clearSession = () => run(() => api.clearFinished())
async function clearHistory() {
  if (await confirm('清空往来书信？', '只会清除记录，已下载的歌曲文件不受影响。', '清空记录')) {
    run(() => api.clearHistory(), () => '往来书信已清空')
  }
}

const SEAL = { done: 'emerald', skipped: 'gold', failed: 'danger', cancelled: 'violet' }
const SEAL_ICON = { done: 'check', skipped: 'box', failed: 'close', cancelled: 'retry' }
</script>

<template>
  <div>
    <PageHeader eyebrow="Music · The Post Room" title="寄信室" script="post"
      :subtitle="`${activeJobs.length} 封在路上 · 历来已送达 ${doneCount} 封 · 最多同时寄送 4 封`">
      <button v-if="sessionFailed" class="btn small" @click="retryAll"><Icon name="retry" :size="15" />重试未送达 · {{ sessionFailed }}</button>
      <button v-if="activeJobs.length" class="btn small danger" @click="cancelAll"><Icon name="stop" :size="14" />全部撤回</button>
      <button v-if="sessionFinished && !activeJobs.length" class="btn small ghost" @click="clearSession">收起本次队列</button>
    </PageHeader>

    <section v-if="activeJobs.length" class="transit">
      <h2 class="section-title"><span class="eyebrow">In transit</span> 在路上</h2>
      <TransitionGroup name="envelope" tag="div" class="envelopes">
        <article v-for="job in activeJobs" :key="job.id" class="envelope sheet" :class="job.state">
          <CoverArt class="stamp stamp-edge" :src="coverUrl(job.song, 120)" :size="66" :seed="job.song.name" :radius="0" />
          <div class="body">
            <div class="who">
              <span class="title-text ellipsis name">{{ job.song.name }}</span>
              <PlatformStamp :platform="job.song.platform" small />
            </div>
            <p class="soft ellipsis small">{{ job.song.artist || '佚名' }}</p>
            <div class="track">
              <span class="ink" :style="{ width: (job.state === 'downloading' || job.state === 'finishing' ? job.pct : 4) + '%' }" />
              <span v-if="job.state === 'resolving' || job.state === 'queued'" class="writing" />
            </div>
            <p class="status">
              <span class="state">{{ STATE_LABEL[job.state] }}</span>
              <span class="faint">{{ job.detail }}</span>
              <span v-if="job.state === 'downloading'" class="mono faint stats">
                {{ bytes(job.done_bytes) }}{{ job.total_bytes ? ' / ' + bytes(job.total_bytes) : '' }} · {{ bytes(job.speed) }}/s{{ eta(job) }}
              </span>
            </p>
          </div>
          <button class="icon-btn" title="撤回这封信" :disabled="job.state === 'finishing' || job.state === 'cancelling'"
            @click="cancelOne(job.id)"><Icon name="close" :size="16" /></button>
        </article>
      </TransitionGroup>
    </section>

    <section class="archive">
      <div class="archive-head">
        <h2 class="section-title"><span class="eyebrow">Correspondence</span> 往来书信</h2>
        <div class="filters">
          <button v-for="(label, key) in FILTERS" :key="key" class="chip" :class="{ on: filter === key }" @click="filter = key">{{ label }}</button>
        </div>
        <button class="btn small ghost" :disabled="!store.history.length" @click="clearHistory"><Icon name="trash" :size="15" />清空记录</button>
      </div>

      <EmptyState v-if="!store.history.length && !activeJobs.length" script="no letters" title="还没有寄出过信"
        hint="在搜索或歌单里选中歌曲，点「寄出所选」，它们就会出现在这里。" />
      <p v-else-if="!groups.length" class="faint none">这一类里还没有信。</p>

      <div v-for="group in groups" :key="group.label" class="day">
        <h3 class="day-label">{{ group.label }}</h3>
        <TransitionGroup name="row" tag="div">
          <div v-for="r in group.items" :key="r.id" class="record" :class="r.state">
            <CoverArt class="stamp stamp-edge" :src="coverUrl(r.song, 80)" :size="42" :seed="r.song.name" :radius="0" />
            <div class="names">
              <span class="title-text ellipsis">{{ r.song.name }}</span>
              <span class="soft ellipsis small">{{ r.song.artist || '佚名' }}<template v-if="r.song.album"> · {{ r.song.album }}</template></span>
            </div>
            <div class="detail small">
              <span class="state-label">{{ STATE_LABEL[r.state] }}</span>
              <span class="faint ellipsis">{{ r.state === 'done' ? [store.qualityLabels[r.level] || r.level, ...(r.flags || '').split('+').map((f) => f.trim())].filter(Boolean).join(' · ') : r.detail }}</span>
            </div>
            <div class="postmark" :title="postmarkDate(r.finished || r.created)">
              <WaxSeal v-if="r.state !== 'done'" :size="30" :tone="SEAL[r.state]"><Icon :name="SEAL_ICON[r.state]" :size="13" /></WaxSeal>
              <span v-else class="mark">
                <Nunkish :text="postmarkDate(r.finished || r.created).replace(/\./g, '')" :size="9" :weight="7" />
              </span>
            </div>
            <span class="mono faint small time">{{ timeOfDay(r.finished || r.created) }}</span>
            <div class="row-actions">
              <button v-if="r.path && (r.state === 'done' || r.state === 'skipped')" class="icon-btn" title="在文件夹中显示" @click="reveal(r.id)"><Icon name="folder" :size="16" /></button>
              <button v-if="r.state === 'failed' || r.state === 'cancelled'" class="icon-btn" title="重新寄出" @click="retryRecord(r.id)"><Icon name="retry" :size="16" /></button>
              <button class="icon-btn" title="移除这条记录" @click="removeRecord(r.id)"><Icon name="close" :size="15" /></button>
            </div>
          </div>
        </TransitionGroup>
      </div>
    </section>
  </div>
</template>

<style scoped>
.section-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 14px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 20px;
}
.small {
  font-size: 13px;
}
.transit {
  margin-bottom: 36px;
}
.envelopes {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 16px;
}
.envelope {
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: start;
  padding: 16px 14px 14px 16px;
  overflow: hidden;
  /* Airmail border. */
  border-image: repeating-linear-gradient(135deg, var(--p-netease) 0 10px, transparent 10px 20px, var(--p-kugou) 20px 30px, transparent 30px 40px) 4;
  border-width: 3px;
  border-style: solid;
}
.stamp {
  background: var(--sheet-raised);
  padding: 4px;
}
.body {
  min-width: 0;
}
.who {
  display: flex;
  align-items: center;
  gap: 10px;
}
.name {
  font-size: 17px;
}
.body p {
  margin: 0;
}
.track {
  position: relative;
  height: 2px;
  margin: 12px 0 8px;
  background: var(--rule);
  border-radius: 2px;
}
.ink {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  background: var(--violet-ink);
  border-radius: 2px;
  transition: width 0.4s var(--ease);
}
.ink::after {
  content: '';
  position: absolute;
  right: -3px;
  top: -3px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--violet-ink);
  box-shadow: 0 0 0 3px var(--violet-wash-strong);
}
.writing {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--violet-ink), transparent) 0 0 / 30% 100% no-repeat;
  animation: sweep 1.4s ease-in-out infinite;
}
@keyframes sweep {
  from {
    background-position: -40% 0;
  }
  to {
    background-position: 140% 0;
  }
}
.status {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12.5px;
}
.state {
  color: var(--violet-ink);
}
.stats {
  width: 100%;
}
.envelope-enter-from,
.envelope-leave-to {
  opacity: 0;
  transform: translateY(10px) rotate(-1deg);
}
.envelope-enter-active,
.envelope-leave-active {
  transition: all 0.45s var(--ease);
}

.archive-head {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 4px;
}
.archive-head .section-title {
  margin: 0;
}
.filters {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.chip {
  padding: 3px 12px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--ink-faint);
}
.chip.on {
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.none {
  text-align: center;
  padding: 40px 0;
}
.day-label {
  margin: 24px 0 6px;
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 500;
  font-size: 16px;
  color: var(--gold);
}
.record {
  display: grid;
  grid-template-columns: 50px minmax(180px, 1.3fr) minmax(160px, 1fr) 46px 48px 112px;
  align-items: center;
  gap: 14px;
  min-height: 62px;
  padding: 6px 10px;
  border-bottom: 1px dashed var(--rule);
}
.record:hover {
  background: var(--violet-wash);
}
.record .stamp {
  padding: 3px;
}
.names,
.detail {
  display: grid;
  min-width: 0;
  line-height: 1.4;
}
.state-label {
  color: var(--emerald);
}
.failed .state-label {
  color: var(--danger);
}
.skipped .state-label,
.cancelled .state-label {
  color: var(--ink-soft);
}
.postmark {
  display: grid;
  place-items: center;
}
.mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 1.5px solid var(--emerald);
  border-radius: 50%;
  color: var(--emerald);
  opacity: 0.75;
  transform: rotate(-12deg);
  box-shadow: 0 0 0 3px var(--paper), 0 0 0 4px color-mix(in srgb, var(--emerald) 40%, transparent);
}
.time {
  text-align: right;
}
.row-actions {
  display: flex;
  justify-content: flex-end;
  opacity: 0.35;
  transition: opacity 0.2s var(--ease);
}
.record:hover .row-actions,
.record:focus-within .row-actions {
  opacity: 1;
}
.row-leave-to {
  opacity: 0;
  transform: translateX(16px);
}
.row-leave-active {
  transition: all 0.3s var(--ease);
}
</style>
