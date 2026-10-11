<script setup>
// 驿路：鸿雁去取信的路。每条路通往一个学校网站的通知栏；可以开关、导入别人写好的驿路包。
// 带脚本的驿路盖着「含脚本」的封缄：展开能看到脚本全文，点「我信任它」才会启用。
import { computed, ref, watch } from 'vue'
import { api } from '../api.js'
import { geese, loadGeese, loadRoutes, setRoute, signIn, signOut } from '../geese.js'
import { confirm, toast } from '../store.js'
import { trapFocus } from '../dialog.js'
import Icon from './Icon.vue'

const box = ref(null)
const opened = ref('') // route id whose script is unfolded
const importing = ref(false)
const raw = ref('')
const preview = ref(null)
const previewError = ref('')
const trust = ref(new Set())
const busy = ref(false)
const fileInput = ref(null)

watch(
  () => geese.routesOpen,
  (open) => {
    if (open) loadRoutes()
    importing.value = false
    preview.value = null
    raw.value = ''
  },
)

const groups = computed(() => {
  const out = []
  for (const route of geese.roads) {
    let group = out.find((g) => g.pack === route.pack)
    if (!group) out.push((group = { pack: route.pack, name: route.pack_name, builtin: route.pack_builtin, routes: [] }))
    group.routes.push(route)
  }
  return out
})

function ago(ts) {
  if (!ts) return '还没去过'
  const minutes = Math.round((Date.now() / 1000 - ts) / 60)
  if (minutes < 1) return '刚刚取过信'
  if (minutes < 60) return `${minutes} 分钟前取过信`
  if (minutes < 1440) return `${Math.round(minutes / 60)} 小时前取过信`
  return `${Math.round(minutes / 1440)} 天前取过信`
}
function status(route) {
  if (!route.active) return { tone: 'off', text: route.why }
  if (route.error?.startsWith('login:')) return { tone: 'login', text: '需要登录门户' }
  if (route.error) return { tone: 'error', text: route.error.split(':').slice(1).join(':') || '取信失败' }
  return { tone: 'ok', text: ago(route.last_ok) }
}
const host = (url) => {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

async function trustRoute(route) {
  if (!(await confirm('信任这段脚本？', `「${route.name}」的脚本只会在沙盒里运行：不能联网、不能读写文件，也碰不到你的数据，只能把网页文字变成通知列表。看过脚本、觉得没问题再启用。`, '我信任它')))
    return
  await setRoute(route, { trusted: true })
  opened.value = ''
}

function pickFile() {
  fileInput.value?.click()
}
async function readFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (file.size > 512 * 1024) {
    toast('驿路包太大了（上限 512 KB）', 'error')
    return
  }
  raw.value = await file.text()
  look()
}
async function look() {
  if (!raw.value.trim()) return
  busy.value = true
  preview.value = null
  previewError.value = ''
  try {
    preview.value = await api.geesePreview(raw.value)
    trust.value = new Set()
  } catch (error) {
    previewError.value = error.message
  } finally {
    busy.value = false
  }
}
async function install() {
  busy.value = true
  try {
    const result = await api.geeseInstall(raw.value, [...trust.value])
    toast(`装上了驿路包「${result.pack.name}」`, 'success')
    importing.value = false
    preview.value = null
    raw.value = ''
    await loadRoutes()
    await loadGeese()
  } catch (error) {
    previewError.value = error.message
  } finally {
    busy.value = false
  }
}
async function removePack(group) {
  if (!(await confirm('移除这个驿路包？', `「${group.name}」的 ${group.routes.length} 条驿路和它们取回的信都会一起移除。`, '移除'))) return
  try {
    await api.geeseRemovePack(group.pack)
    await loadRoutes()
    await loadGeese()
  } catch (error) {
    toast(error.message, 'error')
  }
}
function toggleTrust(id) {
  const set = new Set(trust.value)
  set.has(id) ? set.delete(id) : set.add(id)
  trust.value = set
}

const close = () => (geese.routesOpen = false)
trapFocus(box, close)
</script>

<template>
  <Transition name="modal">
    <div v-if="geese.routesOpen" class="backdrop" @mousedown.self="close">
      <div ref="box" class="dialog sheet" role="dialog" aria-modal="true" aria-labelledby="routes-title">
        <button class="icon-btn close" title="关上 (Esc)" @click="close"><Icon name="close" :size="16" /></button>
        <p class="eyebrow">Post roads</p>
        <h2 id="routes-title" class="title-cn">驿路</h2>
        <p class="faint small intro">鸿雁沿着这些路去取信。每条路通往一个网站的通知栏；同一个网站的路一次只走一条，中间歇一歇，不给学校添麻烦。</p>

        <section v-for="group in groups" :key="group.pack" class="group">
          <header class="group-head">
            <span class="title-cn">{{ group.name }}</span>
            <span class="faint small">{{ group.routes.filter((r) => r.active).length }} / {{ group.routes.length }} 条在用</span>
            <button v-if="!group.builtin" class="link danger" @click="removePack(group)">移除这个包</button>
          </header>
          <ul class="routes">
            <li v-for="route in group.routes" :key="route.id" class="route" :class="status(route).tone">
              <span class="dot" :title="status(route).text" />
              <div class="info">
                <p class="name">
                  <span class="title-text">{{ route.name }}</span><span v-if="route.column" class="faint"> · {{ route.column }}</span>
                  <button v-if="route.script" class="seal-chip" :class="{ trusted: route.trusted }" @click="opened = opened === route.id ? '' : route.id">
                    <Icon name="seal" :size="12" />{{ route.trusted ? '含脚本 · 已信任' : '含脚本' }}
                  </button>
                </p>
                <p class="meta faint small">
                  <a :href="route.url" target="_blank" rel="noreferrer">{{ host(route.url) }}</a>
                  <span> · {{ status(route).text }}</span>
                  <span v-if="route.active"> · 每 {{ route.interval >= 60 ? `${Math.round(route.interval / 60)} 小时` : `${route.interval} 分钟` }}</span>
                </p>
                <div v-if="route.portal" class="portal">
                  <template v-if="route.portal.signed_in">
                    <span class="small"><Icon name="key" :size="13" />已登录{{ route.portal.name }}（只在本机保存会话，不保存密码）</span>
                    <button class="link" @click="signOut(route.login)">退出</button>
                  </template>
                  <button v-else class="btn small" @click="signIn(route.login)"><Icon name="key" :size="14" />登录{{ route.portal.name }}</button>
                </div>
                <div v-if="opened === route.id" class="script">
                  <pre class="mono">{{ route.script }}</pre>
                  <button v-if="!route.trusted" class="btn small wax" @click="trustRoute(route)">我看过了，信任它</button>
                  <button v-else class="btn small" @click="setRoute(route, { trusted: false })">收回信任</button>
                </div>
              </div>
              <button class="switch" role="switch" :aria-checked="route.enabled" :title="route.enabled ? '关掉这条驿路' : '打开这条驿路'"
                @click="setRoute(route, { enabled: !route.enabled })"><span class="knob" /></button>
            </li>
          </ul>
        </section>

        <section class="import">
          <button v-if="!importing" class="btn" @click="importing = true"><Icon name="plus" :size="15" />导入驿路包</button>
          <template v-else>
            <p class="title-cn import-title">导入驿路包</p>
            <p class="faint small">驿路包是一个 .json 文件，别人写好了可以直接分享给你。装之前会先试着取一次，让你看看取回来的是什么。</p>
            <div class="import-row">
              <button class="btn small" @click="pickFile"><Icon name="folder" :size="14" />选一个文件</button>
              <span class="faint small">或者把内容粘贴在下面</span>
              <input ref="fileInput" type="file" accept=".json,application/json" hidden @change="readFile" />
            </div>
            <textarea v-model="raw" class="field paste mono" rows="6" placeholder='{"format": "violet-routes/1", "id": "...", "routes": [...]}' />
            <div class="import-row">
              <button class="btn ghost small" @click="importing = false">算了</button>
              <button class="btn small" :disabled="!raw.trim() || busy" @click="look">看看内容</button>
            </div>
            <p v-if="previewError" class="error small">{{ previewError }}</p>
            <div v-if="preview" class="preview">
              <p><span class="title-cn">{{ preview.pack.name }}</span>
                <span v-if="preview.pack.author" class="faint small"> · {{ preview.pack.author }}</span>
                <span v-if="preview.exists" class="faint small"> · 已经装过，会更新</span></p>
              <p v-if="preview.pack.note" class="faint small">{{ preview.pack.note }}</p>
              <ul class="preview-routes">
                <li v-for="r in preview.routes" :key="r.id">
                  <span>{{ r.name }}<span v-if="r.column" class="faint"> · {{ r.column }}</span></span>
                  <span class="faint small">{{ host(r.url) }}</span>
                  <label v-if="r.script" class="trust">
                    <input type="checkbox" :checked="trust.has(r.id)" @change="toggleTrust(r.id)" />含脚本，信任它
                  </label>
                  <details v-if="r.script" class="peek"><summary class="small">看脚本</summary><pre class="mono">{{ r.script }}</pre></details>
                </li>
              </ul>
              <p v-if="preview.sample.length" class="small">试着取了「{{ preview.sample_route }}」，拿到这些：</p>
              <ul v-if="preview.sample.length" class="sample">
                <li v-for="s in preview.sample" :key="s.link"><span class="mono faint">{{ (s.published || '').slice(5) }}</span> {{ s.title }}</li>
              </ul>
              <p v-else-if="preview.error" class="error small">试取没有成功：{{ preview.error }}</p>
              <button class="btn wax" :disabled="busy" @click="install"><Icon name="route" :size="15" />装上这些驿路</button>
            </div>
          </template>
        </section>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
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
  width: min(760px, calc(100vw - 48px));
  max-height: calc(100vh - var(--titlebar-h, 0px) - 48px);
  overflow-y: auto;
  padding: 28px 32px 24px;
}
.close {
  position: absolute;
  top: 12px;
  right: 12px;
}
h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 400;
}
.eyebrow {
  margin: 0;
}
.small {
  font-size: 12.5px;
}
.intro {
  margin: 4px 0 10px;
}
.group {
  margin-top: 14px;
}
.group-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--rule);
}
.group-head .title-cn {
  font-size: 17px;
}
.link {
  font-size: 12.5px;
  color: var(--violet-ink);
}
.link:hover {
  text-decoration: underline;
}
.link.danger {
  margin-left: auto;
  color: var(--danger);
}
.routes {
  margin: 0;
  padding: 0;
  list-style: none;
}
.route {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 10px 2px;
  border-bottom: 1px dashed var(--rule);
}
.route.off .info {
  opacity: 0.6;
}
.dot {
  width: 9px;
  height: 9px;
  margin-top: 7px;
  border-radius: 50%;
  background: var(--emerald);
  box-shadow: 0 0 0 3px var(--emerald-wash);
}
.route.off .dot {
  background: var(--ink-ghost);
  box-shadow: none;
}
.route.error .dot,
.route.login .dot {
  background: var(--danger);
  box-shadow: 0 0 0 3px var(--danger-wash);
}
.info p {
  margin: 0;
}
.name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
}
.meta a {
  color: inherit;
}
.seal-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 0 8px;
  border-radius: 10px;
  border: 1px solid var(--danger);
  color: var(--danger);
  font-size: 11.5px;
}
.seal-chip.trusted {
  border-color: var(--emerald);
  color: var(--emerald);
}
.portal {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
}
.portal .small {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--emerald);
}
.script {
  margin-top: 8px;
}
pre {
  max-height: 220px;
  overflow: auto;
  margin: 0 0 8px;
  padding: 10px;
  border-radius: var(--radius);
  background: var(--paper);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}
.switch {
  position: relative;
  width: 38px;
  height: 22px;
  margin-top: 2px;
  border-radius: 11px;
  background: var(--rule-strong);
  transition: background 0.2s var(--ease);
}
.switch .knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--sheet-raised);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
  transition: transform 0.25s var(--ease);
}
.switch[aria-checked='true'] {
  background: var(--violet-ink);
}
.switch[aria-checked='true'] .knob {
  transform: translateX(16px);
}
.import {
  margin-top: 18px;
}
.import-title {
  margin: 0;
  font-size: 17px;
}
.import p {
  margin: 4px 0;
}
.import-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}
.paste {
  width: 100%;
  height: auto;
  padding: 8px 10px;
  font-size: 12.5px;
  resize: vertical;
}
.error {
  color: var(--danger);
}
.preview {
  margin-top: 10px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--paper);
}
.preview-routes,
.sample {
  margin: 6px 0;
  padding: 0;
  list-style: none;
}
.preview-routes li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 12px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--rule);
}
.trust {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--danger);
  font-size: 12.5px;
}
.peek {
  flex-basis: 100%;
}
.sample li {
  font-size: 13px;
  padding: 2px 0;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .dialog {
  transform: translateY(14px) scale(0.98);
}
.modal-enter-active,
.modal-leave-active,
.modal-enter-active .dialog {
  transition: all 0.3s var(--ease);
}
</style>
