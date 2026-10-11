<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { store, saveSettings, toast, confirm, requireKey } from '../store.js'
import { api } from '../api.js'
import { sound } from '../sound.js'
import PageHeader from '../components/PageHeader.vue'
import InkToggle from '../components/InkToggle.vue'
import Icon from '../components/Icon.vue'
import Nunkish from '../components/Nunkish.vue'
import HeroBackdrop from '../components/HeroBackdrop.vue'
import StationeryPicker from '../components/StationeryPicker.vue'
import LetterEnvelope from '../components/LetterEnvelope.vue'
import { defaults as stationery, paperVars, LETTERHEADS } from '../stationery.js'

const s = computed(() => store.settings)
const outDir = ref(store.settings?.out_dir || '')
const newDir = ref('')
const portraitPath = ref(store.settings?.portrait_path || '')
const keyInput = ref('')
const remember = ref(true)
const verifying = ref(false)
watch(
  () => store.settings?.out_dir,
  (v) => (outDir.value = v || ''),
)

const SOURCE = { env: '来自环境变量 CHKSZ_API_KEY', file: '已记住 · ~/.chksz_key', session: '仅本次启动有效' }
const THEMES = [
  { value: 'auto', label: '跟随系统', icon: 'auto' },
  { value: 'light', label: '信笺', icon: 'sun' },
  { value: 'dark', label: '烛光', icon: 'candle' },
]
const PLATFORM_NAMES = { netease: '网易云', qq: 'QQ 音乐', kugou: '酷狗' }

const set = (patch) => saveSettings(patch)

// ---- 每日来信的新歌
const charts = computed(() => {
  const groups = { netease: [], qq: [] }
  for (const [id, name] of Object.entries(store.chartCatalog)) groups[id.split(':')[0]]?.push({ id, name })
  return groups
})
const ticked = (id) => (s.value.letter_charts || []).includes(id)
function tickChart(id) {
  const list = s.value.letter_charts || []
  set({ letter_charts: ticked(id) ? list.filter((c) => c !== id) : [...list, id] })
}
const newPlaylist = ref('')
async function addPlaylist() {
  const link = newPlaylist.value.trim()
  if (!link) return
  if (await set({ letter_playlists: [...(s.value.letter_playlists || []), link] })) newPlaylist.value = ''
}
const removePlaylist = (link) => set({ letter_playlists: s.value.letter_playlists.filter((p) => p !== link) })
const noSource = computed(() => !(s.value.letter_charts || []).length && !s.value.letter_taste && !(s.value.letter_playlists || []).length)
const COUNT_WORDS = ['一', '二', '三', '四', '五']

// ---- 文具匣：默认的那一套
const boxTab = ref('paper')
const setDefault = (patch) => set({ stationery: { ...(s.value.stationery || {}), ...patch } })
const boxHead = computed(() => LETTERHEADS[stationery.value.letterhead] || LETTERHEADS.none)

// ---- 称呼与落款
const nickname = ref(store.settings?.nickname || '')
const signoffText = ref(store.settings?.signoff || '')
watch(() => store.settings?.nickname, (v) => (nickname.value = v || ''))
watch(() => store.settings?.signoff, (v) => (signoffText.value = v || ''))
function saveName(field, value) {
  if ((s.value[field] || '') !== value.trim()) set({ [field]: value.trim() })
}
const setQuality = (platform, value) => set({ qualities: { ...s.value.qualities, [platform]: value } })

async function saveOutDir() {
  const value = outDir.value.trim()
  if (!value || value === s.value.out_dir) return
  if (await set({ out_dir: value })) {
    store.library.stale = true
    toast('之后寄出的信会收进新的文件夹', 'success')
  } else outDir.value = s.value.out_dir
}

async function pickOutDir() {
  try {
    const { path } = await api.pickFolder(s.value.out_dir_abs)
    if (path) {
      outDir.value = path
      saveOutDir()
    }
  } catch (error) {
    toast(error.message, 'error')
  }
}

async function addLibraryDir(path) {
  const value = (path ?? newDir.value).trim()
  if (!value) return
  if (await set({ library_dirs: [...s.value.library_dirs, value] })) {
    newDir.value = ''
    store.library.stale = true
  }
}

async function pickLibraryDir() {
  try {
    const { path } = await api.pickFolder('')
    if (path) addLibraryDir(path)
  } catch (error) {
    toast(error.message, 'error')
  }
}

async function removeLibraryDir(dir) {
  if (await set({ library_dirs: s.value.library_dirs.filter((d) => d !== dir) })) store.library.stale = true
}

async function saveKey() {
  try {
    store.key = await api.setKey(keyInput.value, remember.value)
    keyInput.value = ''
    toast(remember.value ? 'Key 已保存，下次启动自动使用' : 'Key 已设置，本次启动有效', 'success')
  } catch (error) {
    toast(error.message, 'error')
  }
}

async function verify() {
  if (!(await requireKey('验证需要先填写 Key'))) return
  verifying.value = true
  try {
    await api.verifyKey()
    toast('Key 可用，额度已刷新', 'success')
  } catch (error) {
    toast(error.message, 'error', 6000)
  } finally {
    verifying.value = false
  }
}

async function forget() {
  const remembered = store.key.remembered
  const ok = await confirm('忘记这把钥匙？', remembered ? '会删除 ~/.chksz_key，命令行工具也将无法自动读取它。' : '本次启动将不再使用这把 Key。', '忘记 Key')
  if (!ok) return
  try {
    store.key = await api.forgetKey()
    toast('已忘记 Key', 'info')
  } catch (error) {
    toast(error.message, 'error')
  }
}

const PORTRAITS = [
  { value: 'art', label: '水彩书桌', hint: '内置：她在窗边打字写信' },
  { value: 'custom', label: '自选图片', hint: '你喜欢的官方图、二创或生成图' },
  { value: 'off', label: '不显示', hint: '保持页面干净' },
]

// ---------------------------------------------------------------- backups
const backups = computed(() => store.backups)
const syncDir = ref(store.settings?.backup_dir || '')
const backingUp = ref(false)
watch(() => store.settings?.backup_dir, (v) => (syncDir.value = v || ''))

async function loadBackups() {
  try {
    store.backups = await api.backups()
  } catch (error) {
    toast(error.message, 'error')
  }
}

async function saveSyncDir(path) {
  const value = (path ?? syncDir.value).trim()
  if (value === (s.value.backup_dir || '')) return
  if (await set({ backup_dir: value })) {
    toast(value ? '之后每天的备份会多复制一份到这个文件夹' : '已停止复制到同步文件夹', 'success')
    loadBackups()
  }
}

async function pickSyncDir() {
  try {
    const { path } = await api.pickFolder(s.value.backup_dir || '')
    if (path) {
      syncDir.value = path
      saveSyncDir(path)
    }
  } catch (error) {
    toast(error.message, 'error')
  }
}

async function backupNow() {
  backingUp.value = true
  try {
    const result = await api.runBackup()
    toast(result.error || (result.sync ? '已备份，并复制到同步文件夹' : '已备份到本机'), result.error ? 'warning' : 'success', 6000)
    loadBackups()
  } catch (error) {
    toast(error.message, 'error')
  } finally {
    backingUp.value = false
  }
}

async function restore(item, where) {
  const ok = await confirm('从这份备份恢复？', `会先把现在的数据另存一份「恢复前」备份，再用 ${item.name} 替换委托、回信、来信与设置。`, '恢复')
  if (!ok) return
  try {
    await api.restoreBackup(item.name, where)
  } catch (error) {
    toast(error.message, 'error', 6000)
  }
}

function backupTime(item) {
  const d = new Date(item.time * 1000)
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(loadBackups)

async function savePortraitPath(path) {
  const value = (path ?? portraitPath.value).trim()
  if (!value) return
  if (!/\.(png|jpe?g|webp|gif|bmp)$/i.test(value)) {
    toast('请选择 png / jpg / webp 图片', 'warning')
    return
  }
  portraitPath.value = value
  if (await set({ portrait: 'custom', portrait_path: value })) toast('背景画已更换', 'success')
}

async function pickPortrait() {
  try {
    const { path } = await api.pickImage()
    if (path) savePortraitPath(path)
  } catch (error) {
    toast(error.message, 'error')
  }
}

function setSound(on) {
  set({ sound: on })
  sound.setEnabled(on)
  if (on) setTimeout(() => sound.typing(6), 60)
}

const quotaText = computed(() => {
  const q = store.quota || {}
  if (q.free === undefined && q.paid === undefined) return '尚未获取 · 下一次请求后更新'
  return [q.free !== undefined && `免费 ${q.free}`, q.paid !== undefined && `付费 ${q.paid}`].filter(Boolean).join(' · ')
})
</script>

<template>
  <div v-if="s">
    <PageHeader eyebrow="Chapter V · Settings" title="设置" script="settings"
      subtitle="钥匙、歌寄往何处、灯光、开场，以及把这一切好好备份。" />

    <div class="desk">
      <section class="card sheet key">
        <h2><Icon name="key" :size="18" />通行钥匙 · API Key</h2>
        <div class="key-status">
          <span class="dot" :class="{ on: store.key.has_key }" />
          <div>
            <p class="mono">{{ store.key.has_key ? store.key.masked : '尚未配置' }}</p>
            <p class="faint small">{{ store.key.has_key ? SOURCE[store.key.source] : '搜索和下载需要 ChKSz API Key' }}</p>
          </div>
          <div class="quota">
            <span class="eyebrow">Quota</span>
            <span class="mono small">{{ quotaText }}</span>
          </div>
        </div>
        <form class="key-form" @submit.prevent="saveKey">
          <input v-model="keyInput" class="field mono" type="password" placeholder="chksz_…" autocomplete="off" spellcheck="false" />
          <button class="btn" type="submit" :disabled="!keyInput.trim()">{{ store.key.has_key ? '更换' : '保存' }}</button>
        </form>
        <InkToggle v-model="remember" label="记住这把 Key" hint="写入 ~/.chksz_key，与命令行工具共用；不记住则仅本次启动有效。" />
        <div class="row-buttons">
          <button class="btn small" :disabled="verifying || !store.key.has_key" @click="verify">
            <Icon name="refresh" :size="14" />{{ verifying ? '验证中…' : '验证并刷新额度' }}
          </button>
          <button class="btn small ghost danger" :disabled="!store.key.has_key || store.key.source === 'env'" @click="forget">忘记 Key</button>
          <a class="small upstream" href="https://api.chksz.com/#apis" target="_blank" rel="noreferrer">获取 Key · api.chksz.com</a>
        </div>
        <p class="faint small">验证会发起一次搜索请求，消耗 1 次额度。</p>
      </section>

      <section class="card sheet">
        <h2><Icon name="folder" :size="18" />寄往何处</h2>
        <div class="path-row">
          <input v-model="outDir" class="field path mono" spellcheck="false" @blur="saveOutDir" @keydown.enter="saveOutDir" />
          <button v-if="store.windowed" class="btn small" @click="pickOutDir">选择…</button>
          <button class="icon-btn" title="打开文件夹" @click="api.reveal({ folder: 'out' }).catch((e) => toast(e.message, 'error'))">
            <Icon name="folder" :size="17" />
          </button>
        </div>
        <p class="faint small resolved">{{ s.out_dir_abs }}</p>
        <InkToggle :model-value="s.subfolders" label="按歌手分文件夹" hint="music/歌手/歌手 - 歌名.flac" @update:model-value="(v) => set({ subfolders: v })" />
        <InkToggle :model-value="s.ios" label="手机版整理" hint="music/歌手/专辑/，并额外写同名 .lrc，方便只认旁车歌词的播放器" @update:model-value="(v) => set({ ios: v })" />
      </section>

      <section class="card sheet">
        <h2><Icon name="sparkle" :size="18" />首选音质</h2>
        <p class="faint small">没有所选音质时逐档降级；鉴权、额度、限流等错误不会被当作音质问题反复尝试。</p>
        <div v-for="(levels, platform) in store.qualities" :key="platform" class="quality">
          <span class="title-cn">{{ PLATFORM_NAMES[platform] }}</span>
          <div class="levels">
            <button v-for="level in levels" :key="level" class="level" :class="{ on: s.qualities[platform] === level }"
              @click="setQuality(platform, level)">{{ store.qualityLabels[level] || level }}</button>
          </div>
        </div>
      </section>

      <section class="card sheet">
        <h2><Icon name="envelope" :size="18" />封缄</h2>
        <InkToggle :model-value="s.lyric" label="内嵌歌词" hint="写入音频标签；网易云会附上翻译" @update:model-value="(v) => set({ lyric: v })" />
        <InkToggle :model-value="s.cover" label="内嵌封面" @update:model-value="(v) => set({ cover: v })" />
        <p class="faint small">两项都关闭时，仍会写入歌名、歌手和专辑。本地已有同名文件时直接跳过，从不覆盖。</p>
      </section>

      <section class="card sheet">
        <h2><Icon name="box" :size="18" />书信匣的来源</h2>
        <p class="faint small">下载文件夹总会被收录。可以再添加其他存放音乐的文件夹，只读取，不修改；只有你亲手退回的歌才会移进回收站。</p>
        <ul class="dirs">
          <li class="mono small"><Icon name="folder" :size="15" /><span class="ellipsis">{{ s.out_dir_abs }}</span><span class="faint">下载</span></li>
          <li v-for="dir in s.library_dirs" :key="dir" class="mono small">
            <Icon name="folder" :size="15" /><span class="ellipsis">{{ dir }}</span>
            <button class="icon-btn" title="移除" @click="removeLibraryDir(dir)"><Icon name="close" :size="14" /></button>
          </li>
        </ul>
        <div class="path-row">
          <input v-model="newDir" class="field path mono" placeholder="D:\Music" spellcheck="false" @keydown.enter="addLibraryDir()" />
          <button class="btn small" :disabled="!newDir.trim()" @click="addLibraryDir()">添加</button>
          <button v-if="store.windowed" class="btn small" @click="pickLibraryDir">选择…</button>
        </div>
      </section>

      <section class="card sheet box">
        <h2><Icon name="seal" :size="18" />文具匣</h2>
        <p class="faint small">新信纸默认用这一套。写信时右边的「文具匣」可以临时换；每封信封缄时会记住自己用的那套。</p>
        <div class="box-grid">
          <StationeryPicker v-model:tab="boxTab" :set="stationery" roomy @change="setDefault" />
          <div class="box-preview" aria-hidden="true">
            <div class="mini-sheet letter-sheet daylight" :class="`ruling-${stationery.ruling}`" :style="paperVars(stationery)">
              <img v-if="boxHead.url" class="mini-head" :src="boxHead.url" alt="" />
              <span v-else-if="stationery.letterhead === 'post'" class="mini-post">C.H. POSTAL COMPANY</span>
              <p class="mini-to">致 Violet：</p>
              <p class="mini-body">见字如面。今天的风很轻，窗台上的紫罗兰开了第二朵，想写信告诉你。</p>
              <p v-if="s.signoff" class="mini-sign">{{ s.signoff }}</p>
            </div>
            <LetterEnvelope :stationery="{ ...stationery, signoff: s.signoff }" side="front"
              :width="['chinese', 'pouch'].includes(stationery.envelope) ? 110 : 220" postmark="2026·10·11" />
            <LetterEnvelope :stationery="stationery" side="back" :width="['chinese', 'pouch'].includes(stationery.envelope) ? 110 : 220" />
          </div>
        </div>
      </section>

      <section class="card sheet">
        <h2><Icon name="quill" :size="18" />称呼与落款</h2>
        <label class="small soft" for="nickname">Violet 怎么称呼你</label>
        <input id="nickname" v-model="nickname" class="field" maxlength="12" placeholder="留空就是「亲爱的你」"
          @blur="saveName('nickname', nickname)" @keydown.enter="$event.target.blur()" />
        <p class="faint small">来信抬头会写成「亲爱的{{ nickname.trim() || '你' }}：」「{{ nickname.trim() || '你' }}，见字如面：」，旧信也跟着改口。</p>
        <label class="small soft" for="signoff">你的回信怎么落款</label>
        <input id="signoff" v-model="signoffText" class="field" maxlength="16" placeholder="比如：你的小满"
          @blur="saveName('signoff', signoffText)" @keydown.enter="$event.target.blur()" />
        <p class="faint small">写在每封回信的右下角；留空就不署名。</p>
      </section>

      <section class="card sheet sources">
        <h2><Icon name="music" :size="18" />每日来信的新歌</h2>
        <p class="faint small">Violet 每天从勾上的地方挑书信匣里还没有的歌，一天最多用其中两处。都走公开接口，不用登录，也不花 Key 的额度。</p>
        <div class="count-row">
          <span class="small soft">每天挑</span>
          <div class="levels">
            <button v-for="n in 5" :key="n" class="level" :class="{ on: (s.letter_count || 3) === n }" @click="set({ letter_count: n })">{{ COUNT_WORDS[n - 1] }}首</button>
          </div>
        </div>
        <div v-for="(list, platform) in charts" :key="platform" class="chart-row">
          <span class="small soft platform-name">{{ PLATFORM_NAMES[platform] }}</span>
          <div class="levels">
            <button v-for="c in list" :key="c.id" class="level" :class="{ on: ticked(c.id) }" :aria-pressed="ticked(c.id)"
              @click="tickChart(c.id)">{{ c.name }}</button>
          </div>
        </div>
        <InkToggle :model-value="s.letter_taste" label="按我的口味" hint="从书信匣里常听的歌手出发，找他们你还没有的歌（网易云公开资料）。"
          @update:model-value="(v) => set({ letter_taste: v })" />
        <p class="small soft playlists-title">自己留的歌单</p>
        <ul v-if="s.letter_playlists?.length" class="dirs">
          <li v-for="link in s.letter_playlists" :key="link" class="mono small">
            <Icon name="link" :size="15" /><span class="ellipsis" :title="link">{{ link }}</span>
            <button class="icon-btn" title="移除" @click="removePlaylist(link)"><Icon name="close" :size="14" /></button>
          </li>
        </ul>
        <div class="path-row">
          <input v-model="newPlaylist" class="field path mono" placeholder="粘贴网易云或 QQ 音乐的公开歌单链接" spellcheck="false"
            @keydown.enter="addPlaylist" />
          <button class="btn small" :disabled="!newPlaylist.trim()" @click="addPlaylist">添加</button>
        </div>
        <p v-if="noSource" class="warn small">一处都没勾的话，来信里就不会有新歌了。</p>
      </section>

      <section class="card sheet">
        <h2><Icon name="candle" :size="18" />灯光与声音</h2>
        <div class="themes">
          <button v-for="t in THEMES" :key="t.value" class="theme" :class="[t.value, { on: s.theme === t.value }]" @click="set({ theme: t.value })">
            <span class="swatch"><Icon :name="t.icon" :size="18" /></span>
            <span>{{ t.label }}</span>
          </button>
        </div>
        <InkToggle :model-value="s.sound" label="打字机音效" hint="寄出时的滑轨声、送达时的铃声。播放音乐时自动静音。" @update:model-value="setSound" />
        <InkToggle :model-value="s.ambient !== false" label="光影与动效"
          hint="窗光随时辰变色、浮尘与萤火、跟着回信天气下雨落雪，以及翻页和信件飞行。关掉后只留静态的光。"
          @update:model-value="(v) => set({ ambient: v })" />
      </section>

      <section class="card sheet">
        <h2><Icon name="bell" :size="18" />开场与托盘</h2>
        <InkToggle :model-value="s.intro" label="每天第一次打开时播放开场" hint="水彩晕开、钢笔写下 Violet。当天再打开就直接进书桌。"
          @update:model-value="(v) => set({ intro: v })" />
        <InkToggle :model-value="s.tray" label="关掉窗口时退到托盘" hint="委托与约定的提醒照常送达（系统通知）。右键托盘图标可以彻底退出。"
          @update:model-value="(v) => set({ tray: v })" />
        <p v-if="!store.tray" class="faint small">托盘只在桌面窗口里可用；浏览器模式下关掉页面就是退出。</p>
      </section>

      <section class="card sheet backup">
        <h2><Icon name="archive" :size="18" />备份</h2>
        <p class="faint small">委托、回信、来信、照片与设置都存在下面这个文件夹。每天第一次打开和退出时自动备份；API Key 不在其中。</p>
        <div class="path-row">
          <span class="mono path-text ellipsis" :title="s.data_dir">{{ s.data_dir }}</span>
          <button class="icon-btn" title="打开数据文件夹" @click="api.reveal({ folder: 'data' }).catch((e) => toast(e.message, 'error'))">
            <Icon name="folder" :size="17" />
          </button>
        </div>
        <p class="sub-title">同步文件夹（例如百度网盘客户端的「同步空间」）</p>
        <div class="path-row">
          <input v-model="syncDir" class="field path mono" placeholder="D:\百度网盘同步空间\Violet" spellcheck="false"
            @blur="saveSyncDir()" @keydown.enter="saveSyncDir()" />
          <button v-if="store.windowed" class="btn small" @click="pickSyncDir">选择…</button>
        </div>
        <p class="faint small">设置后，每份备份会再复制一份到这里，保留最近 30 份，由网盘客户端负责上传；本机另存最近 7 份。</p>
        <div class="row-buttons">
          <button class="btn small" :disabled="backingUp || backups?.running" @click="backupNow">
            <Icon name="archive" :size="14" />{{ backingUp ? '正在备份…' : '立即备份' }}
          </button>
          <span v-if="backups?.error" class="small danger-text">{{ backups.error }}</span>
        </div>
        <details v-if="backups" class="history">
          <summary class="small">从备份恢复（{{ backups.local.length + backups.sync.length }} 份）</summary>
          <ul>
            <li v-for="b in backups.local" :key="'l' + b.name">
              <span class="mono small">{{ backupTime(b) }}</span><span class="faint small">本机</span>
              <button class="btn small ghost" @click="restore(b, 'local')">恢复</button>
            </li>
            <li v-for="b in backups.sync" :key="'s' + b.name">
              <span class="mono small">{{ backupTime(b) }}</span><span class="faint small">同步文件夹</span>
              <button class="btn small ghost" @click="restore(b, 'sync')">恢复</button>
            </li>
          </ul>
        </details>
      </section>

      <section class="card sheet">
        <h2><Icon name="sparkle" :size="18" />背景画</h2>
        <div class="portraits">
          <button v-for="p in PORTRAITS" :key="p.value" class="portrait-opt" :class="{ on: s.portrait === p.value }"
            :disabled="p.value === 'custom' && !s.portrait_path && !portraitPath"
            @click="set({ portrait: p.value })">
            <span class="title-cn">{{ p.label }}</span>
            <span class="faint small">{{ p.hint }}</span>
          </button>
        </div>
        <div class="path-row">
          <input v-model="portraitPath" class="field path mono" placeholder="D:\Pictures\violet.png" spellcheck="false"
            @keydown.enter="savePortraitPath()" />
          <button class="btn small" :disabled="!portraitPath.trim()" @click="savePortraitPath()">使用</button>
          <button v-if="store.windowed" class="btn small" @click="pickPortrait">选择图片…</button>
        </div>
        <p class="faint small">自选图片只在本机读取，不会复制进程序目录；左侧会自动淡出给文字留位置，横幅、人物在右侧的图效果最好。</p>
        <div v-if="s.portrait !== 'off'" class="portrait-preview"><HeroBackdrop strength="full" /></div>
      </section>

      <section class="card sheet about">
        <Nunkish text="violet evergarden" :size="20" class="sig" />
        <p class="title-cn">Violet · v{{ store.version }}</p>
        <p class="faint small">
          搜索、解析与下载由 <a href="https://api.chksz.com/#apis" target="_blank" rel="noreferrer">ChKSz API</a> 提供。
          字体：汇文明朝体（TerryWang，免费商用）、霞鹜文楷屏幕阅读版（OFL）、Cormorant Garamond、Cutive Mono、Pinyon Script（OFL）。
          图标与侧栏的紫罗兰取自 Mary Vaux Walcott 的植物水彩（Smithsonian，CC0）；书桌水彩与日历、日记、委托三幅插图为原创生成图。泰尔西斯文字参照 NunkishPixies 重绘，仅作装饰，相关权利归《紫罗兰永恒花园》版权方所有。每日寄语部分来自「一言」；农历与节气按天文算法推算。
        </p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.desk {
  columns: 2;
  column-gap: 22px;
  padding-bottom: 24px;
}
.card {
  break-inside: avoid;
  margin-bottom: 22px;
  padding: 22px 24px 18px;
}
h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 14px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 19px;
  color: var(--ink);
}
h2 :deep(svg) {
  color: var(--violet-ink);
}
p {
  margin: 0;
}
.small {
  font-size: 12.5px;
}
.key-status {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--violet-wash);
  margin-bottom: 14px;
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--danger);
  box-shadow: 0 0 0 4px var(--danger-wash);
}
.dot.on {
  background: var(--emerald);
  box-shadow: 0 0 0 4px var(--emerald-wash);
}
.quota {
  margin-left: auto;
  display: grid;
  text-align: right;
}
.quota .eyebrow {
  font-size: 13px;
}
.key-form {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 6px;
}
.key-form .field {
  flex: 1;
}
.row-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 10px 0 8px;
}
.upstream {
  margin-left: auto;
}
.path-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.path {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
}
.resolved {
  margin: 4px 0 8px;
  word-break: break-all;
}
.quality {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 12px;
  align-items: start;
  padding: 12px 0 2px;
}
.quality .title-cn {
  padding-top: 3px;
}
.levels {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.level {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12.5px;
  border: 1px solid var(--rule);
  color: var(--ink-soft);
  transition: all 0.2s var(--ease);
}
.level:hover {
  border-color: var(--ink-faint);
}
.level.on {
  border-color: var(--violet-ink);
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.box {
  column-span: all;
  margin-bottom: 22px;
}
.box-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 28px;
  margin-top: 12px;
}
.box-preview {
  display: grid;
  justify-items: center;
  align-content: start;
  gap: 16px;
  padding-left: 24px;
  border-left: 1px dashed var(--rule-strong);
}
.mini-sheet {
  width: 240px;
  padding: 16px 18px 18px 26px;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent 16px, var(--letter-margin) 16px 17px, transparent 17px);
  box-shadow: var(--shadow-sheet);
  transform: rotate(-1.5deg);
}
.mini-head {
  display: block;
  width: 62%;
  margin: -8px auto 2px;
}
.mini-post {
  display: block;
  text-align: center;
  font-family: 'Cutive Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.2em;
  color: var(--letter-ink);
  border-bottom: 1px double var(--letter-ink);
  padding-bottom: 3px;
  margin-bottom: 6px;
}
.mini-to {
  margin: 0;
  font-family: var(--font-title);
  font-size: 13px;
}
.mini-body {
  margin: 4px 0 0;
  font-family: var(--letter-font);
  font-size: calc(12.5px * var(--letter-scale, 1));
  line-height: 24px;
  color: var(--letter-ink);
  background: repeating-linear-gradient(transparent 0 23px, var(--letter-rule) 23px 24px);
}
.ruling-blank .mini-body {
  background: none;
}
.ruling-grid .mini-body,
.ruling-manuscript .mini-body {
  background:
    repeating-linear-gradient(transparent 0 23px, var(--letter-rule) 23px 24px),
    repeating-linear-gradient(90deg, transparent 0 23px, var(--letter-rule) 23px 24px);
}
.mini-sign {
  margin: 6px 0 0;
  text-align: right;
  font-family: var(--letter-font);
  font-size: 13px;
  color: var(--letter-ink);
}
@media (max-width: 1100px) {
  .box-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .box-preview {
    border-left: 0;
    padding-left: 0;
    grid-template-columns: repeat(3, auto);
    justify-content: center;
  }
}
.count-row,
.chart-row {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  margin: 10px 0;
}
.platform-name,
.count-row > .small {
  padding-top: 3px;
}
.playlists-title {
  margin: 14px 0 0;
}
.sources .dirs {
  margin: 6px 0 8px;
}
.warn {
  margin: 10px 0 0;
  color: var(--danger);
}
.dirs {
  list-style: none;
  padding: 0;
  margin: 12px 0;
  display: grid;
  gap: 4px;
}
.dirs li {
  display: grid;
  grid-template-columns: 18px 1fr auto;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  color: var(--ink-soft);
}
.themes {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}
.theme {
  display: grid;
  justify-items: center;
  gap: 6px;
  padding: 12px 0 10px;
  border-radius: var(--radius);
  border: 1px solid var(--rule);
  font-size: 13.5px;
  color: var(--ink-soft);
  transition: all 0.2s var(--ease);
}
.theme.on {
  border-color: var(--violet-ink);
  color: var(--violet-ink);
  background: var(--violet-wash);
}
.swatch {
  display: grid;
  place-items: center;
  width: 44px;
  height: 30px;
  border-radius: 4px;
  border: 1px solid var(--rule-strong);
}
.light .swatch {
  background: #f3ecdf;
  color: #5e3f8f;
}
.dark .swatch {
  background: #1c1825;
  color: #e1ba6a;
}
.auto .swatch {
  background: linear-gradient(135deg, #f3ecdf 50%, #1c1825 50%);
  color: #8f8597;
}
.portraits {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.portrait-opt {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--rule);
  text-align: left;
  line-height: 1.4;
  transition: all 0.2s var(--ease);
}
.portrait-opt.on {
  border-color: var(--violet-ink);
  background: var(--violet-wash);
  color: var(--violet-ink);
}
.portrait-opt:disabled {
  opacity: 0.45;
}
.portrait-preview {
  position: relative;
  height: 150px;
  margin: 12px 0 0;
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--paper);
  border: 1px solid var(--rule);
}
.path-text {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--ink-soft);
}
.sub-title {
  margin: 14px 0 2px;
  font-size: 13.5px;
  color: var(--ink-soft);
}
.danger-text {
  color: var(--danger);
}
.history summary {
  cursor: pointer;
  color: var(--violet-ink);
}
.history ul {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: grid;
  gap: 2px;
  max-height: 220px;
  overflow-y: auto;
}
.history li {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 10px;
}
.about {
  column-span: all;
  display: grid;
  justify-items: center;
  text-align: center;
  gap: 6px;
}
.about .sig {
  color: var(--gold);
}
.about .faint {
  max-width: 720px;
  line-height: 1.7;
}
@media (max-width: 1100px) {
  .desk {
    columns: 1;
  }
}
</style>
