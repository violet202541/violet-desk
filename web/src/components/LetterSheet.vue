<script setup>
import { addressed } from '../address.js'
// 一封每日来信：寄语、三首新歌与一封旧信。
import { computed } from 'vue'
import { coverUrl, libraryCoverUrl } from '../api.js'
import { duration } from '../format.js'
import { store, sendLetters, updateLetter, runSearch, loadLibrary, go } from '../store.js'
import { playList } from '../player.js'
import CoverArt from './CoverArt.vue'
import Icon from './Icon.vue'
import Nunkish from './Nunkish.vue'
import PlatformStamp from './PlatformStamp.vue'
import Wordmark from './Wordmark.vue'
import { startWriting } from '../desk.js'
import { cnDay } from '../format.js'

const props = defineProps({ letter: { type: Object, required: true } })
const emit = defineEmits(['close'])

const dateText = computed(() => {
  const [y, m, d] = props.letter.date.split('-').map(Number)
  return `${y} 年 ${m} 月 ${d} 日`
})
const stampDigits = computed(() => props.letter.date.slice(5).replace('-', ''))
const old = computed(() => props.letter.old)
const oldNote = computed(() => {
  if (!old.value) return ''
  if (!old.value.last_played) return '它在书信匣里等了很久，还没被拆开过。'
  const days = Math.floor((Date.now() / 1000 - old.value.last_played) / 86400)
  return `上一次聆听，是 ${days} 天前。`
})
const quoteBy = computed(() => {
  const q = props.letter.quote || {}
  return [q.author, q.source].filter(Boolean).join(' ')
})

const songCount = computed(() => (props.letter.songs.length === 3 ? '三' : cnDay(props.letter.songs.length)))

function reply() {
  emit('close')
  startWriting()
}

function toGeese() {
  emit('close')
  go('geese')
}

// Not every song can be fetched from every shelf: look for the same one on the other platform.
const otherPlatform = (song) => ((song.platform || 'qq') === 'qq' ? 'netease' : 'qq')
function findElsewhere(song) {
  store.search.query = `${song.name} ${song.artist.split(',')[0]}`
  store.search.platform = otherPlatform(song)
  go('search')
  emit('close')
  runSearch()
}

async function playOld() {
  if (!store.library.loaded) await loadLibrary()
  const tracks = store.library.tracks
  const index = tracks.findIndex((t) => t.id === old.value.id)
  if (index < 0) return
  playList(tracks, index)
}
</script>

<template>
  <article class="letter">
    <header class="head">
      <div>
        <p class="eyebrow">A letter for {{ letter.weekday }}</p>
        <p class="date title-cn">{{ dateText }} · {{ letter.weekday }}</p>
      </div>
      <div class="postmark" aria-hidden="true">
        <Nunkish :text="stampDigits" :size="12" :weight="7" />
        <span class="mono">VIOLET POST</span>
      </div>
      <button class="icon-btn star" :class="{ on: letter.starred }" :title="letter.starred ? '取消收藏' : '收藏这封信'"
        @click="updateLetter(letter.date, { starred: !letter.starred })">
        <svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 4l2.4 5 5.4.6-4 3.7 1.1 5.4L12 16l-4.9 2.7 1.1-5.4-4-3.7 5.4-.6z" /></svg>
      </button>
    </header>

    <p class="greeting">{{ addressed(letter.greeting) }}</p>

    <blockquote class="quote">
      <p class="title-text">{{ letter.quote.text }}</p>
      <footer v-if="quoteBy">—— {{ quoteBy }}<span v-if="letter.quote.origin === 'hitokoto'" class="via">一言</span></footer>
    </blockquote>

    <section v-if="letter.songs.length" class="block">
      <p class="para">{{ letter.songs_intro || `今天从 QQ 音乐「${letter.chart}」里，替你挑了${songCount}首书信匣里还没有的歌：` }}</p>
      <ul class="songs">
        <li v-for="song in letter.songs" :key="song.id">
          <CoverArt :src="coverUrl(song, 120)" :size="46" :seed="song.name" />
          <div class="names">
            <span class="title-text ellipsis">{{ song.name }}</span>
            <span class="soft ellipsis small">{{ song.artist }} · {{ duration(song.duration) }}</span>
          </div>
          <PlatformStamp :platform="song.platform || 'qq'" small />
          <button class="btn small" :title="`去${otherPlatform(song) === 'qq' ? 'QQ 音乐' : '网易云'}找同一首`" @click="findElsewhere(song)">
            {{ otherPlatform(song) === 'qq' ? 'QQ 找找' : '网易云找找' }}
          </button>
          <button class="btn small wax" @click="sendLetters([song])"><Icon name="send" :size="14" />寄出</button>
        </li>
      </ul>
      <button v-if="letter.songs.length > 1" class="btn small ghost all" @click="sendLetters(letter.songs)">{{ songCount }}首都寄回来</button>
    </section>
    <p v-else-if="letter.songs_error" class="para faint">今天的榜单没能送到（{{ letter.songs_error }}），明天再给你挑。</p>
    <p v-else class="para faint">榜单上的歌，书信匣里都已经有了。今天就听听自己的收藏吧。</p>

    <section v-if="old" class="block">
      <p class="para">{{ old.pressed ? '书页间夹着一朵你压过的花，我替你取了出来。' : '还有一封旧信。' }}{{ oldNote }}</p>
      <div class="old">
        <CoverArt :src="old.has_cover ? libraryCoverUrl(old.id) : ''" :size="56" :seed="old.title" />
        <div class="names">
          <span class="title-text ellipsis">{{ old.title }}</span>
          <span class="soft ellipsis small">{{ old.artist || '佚名' }}<template v-if="old.album"> · {{ old.album }}</template></span>
        </div>
        <button class="play" title="重新拆开它" @click="playOld"><Icon name="play" :size="18" /></button>
      </div>
    </section>

    <section v-if="letter.geese?.text" class="block geese">
      <p class="para">{{ letter.geese.text }}</p>
      <button class="to-geese" @click="toGeese"><Icon name="goose" :size="15" />去信绳那儿看看</button>
    </section>

    <p class="closing">{{ letter.closing }}</p>
    <footer class="sign">
      <Wordmark :height="38" />
      <Nunkish text="auto memory doll" :size="10" class="sig-script" />
    </footer>
    <p v-for="(note, i) in letter.notes || []" :key="i" class="ps"><span class="ps-mark">{{ i ? '' : 'P.S.' }}</span>{{ note }}</p>
    <div class="reply-row">
      <button class="btn wax" @click="reply"><Icon name="quill" :size="15" />回信</button>
    </div>
  </article>
</template>

<style scoped>
.letter {
  position: relative;
  padding: 40px 48px 34px;
  background:
    linear-gradient(90deg, transparent 30px, color-mix(in srgb, var(--violet-ink) 22%, transparent) 30px 31px, transparent 31px),
    var(--sheet-raised);
  box-shadow: var(--shadow-lift);
  border-radius: 2px;
  font-size: 15.5px;
  line-height: 2.2;
}
.head {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.head > div:first-child {
  flex: 1;
}
.eyebrow,
.date {
  margin: 0;
  line-height: 1.5;
}
.date {
  font-size: 18px;
}
.postmark {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 2px;
  width: 74px;
  height: 74px;
  border: 1.5px solid var(--violet-ink);
  border-radius: 50%;
  color: var(--violet-ink);
  opacity: 0.7;
  transform: rotate(-12deg);
  line-height: 1;
}
.postmark .mono {
  font-size: 8px;
  letter-spacing: 0.12em;
}
.star svg {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linejoin: round;
}
.star.on {
  color: var(--gold);
}
.star.on svg {
  fill: currentColor;
}
.greeting {
  margin: 22px 0 6px;
  font-size: 17px;
}
.quote {
  margin: 8px 0 14px;
  padding: 14px 0 6px 22px;
  border-left: 2px solid var(--gold-soft);
}
.quote p {
  margin: 0;
  font-size: 23px;
  line-height: 1.75;
  color: var(--violet-ink);
}
.quote footer {
  margin-top: 6px;
  text-align: right;
  color: var(--ink-soft);
  font-size: 14px;
  line-height: 1.6;
}
.via {
  margin-left: 8px;
  padding: 0 6px;
  border: 1px solid var(--rule-strong);
  border-radius: 3px;
  font-size: 11px;
}
.para {
  margin: 4px 0;
}
.block {
  margin-top: 6px;
}
.songs {
  list-style: none;
  margin: 4px 0 2px;
  padding: 0;
  display: grid;
  gap: 8px;
}
.songs li,
.old {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto auto;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border-radius: var(--radius);
  background: var(--violet-wash);
  line-height: 1.4;
}
.old {
  grid-template-columns: auto minmax(0, 1fr) auto;
  background: color-mix(in srgb, var(--gold) 9%, transparent);
}
.names {
  display: grid;
  min-width: 0;
}
.small {
  font-size: 12.5px;
}
.all {
  margin-top: 4px;
}
.play {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  color: var(--wax-text);
  background: radial-gradient(120% 140% at 30% 20%, var(--wax-a), var(--wax-b));
}
.closing {
  margin: 14px 0 0;
}
.sign {
  display: grid;
  justify-items: end;
  margin-top: 4px;
}
.sig-script {
  color: var(--gold);
  margin-top: -4px;
}
.to-geese {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
  color: var(--violet-ink);
  font-size: 13.5px;
}
.to-geese:hover {
  text-decoration: underline;
}
.ps {
  display: grid;
  grid-template-columns: 36px 1fr;
  margin: 0;
  font-size: 14.5px;
  line-height: 1.9;
  color: var(--ink-soft);
}
.ps-mark {
  font-family: var(--font-display);
  font-style: italic;
  color: var(--gold);
}
.reply-row {
  display: flex;
  justify-content: center;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed var(--rule);
}
</style>
