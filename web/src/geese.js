// 鸿雁：学校的通知。驿路取信，按收件人名片拣信，夹在窗前的信绳上。
import { computed, reactive } from 'vue'
import { api } from './api.js'
import { go, on, toast } from './store.js'
import { desk } from './desk.js'
import { sound } from './sound.js'
import { flyTo } from './motion.js'
import { isoDate } from './format.js'

export const geese = reactive({
  loaded: false,
  loading: false,
  error: '',
  card: null,
  cubbies: [],
  letters: [],
  unopened: 0,
  archived: 0,
  routes: [], // the active routes, in brief (for the page)
  roads: [], // every route in full (for the routes dialog)
  lastFetch: null,
  running: false,
  progress: null, // { done, total, route } while the geese are out
  presets: [],
  portals: {},
  schools: [],
  selected: '', // the category open in the list ('all' for everything)
  look: savedLook(), // 'lines' | 'list': the lines before the window, or the typed list
  reading: null, // a letter open on the reading desk (full text)
  readingLoading: false,
  drawer: null, // { box: 'unopened' | 'archive', letters, q, loading }
  carding: false, // the card dialog
  routesOpen: false, // the routes dialog
  arrival: 0, // bumps when new letters come in: the goose flies over the cabinet
  arrivedIds: [],
})

function savedLook() {
  try {
    return ['list', 'ledger'].includes(localStorage.getItem('violet-geese-look')) ? 'list' : 'lines'
  } catch {
    return 'lines'
  }
}
export function setLook(look) {
  geese.look = look
  try {
    localStorage.setItem('violet-geese-look', look)
  } catch {
    /* remembered for this session only */
  }
}

export const unread = computed(() => geese.letters.filter((l) => !l.read_at).length)
export const urgentCount = computed(() => geese.letters.filter((l) => l.urgent && !l.read_at).length)

export function shortTitle(title, limit = 24) {
  let core = (title || '').replace(/^关于(?:做好|开展|举办|组织|启动)?/, '').replace(/的(?:通知|公告|公示)$/, '').trim() || title || ''
  return core.length <= limit ? core : core.slice(0, limit - 1) + '…'
}

// A letter's number in the register: three typed digits, steady for the same letter.
export function serial(letter) {
  let h = 0
  for (const c of String(letter?.id ?? '')) h = (h * 31 + c.charCodeAt(0)) >>> 0
  return String(h % 1000).padStart(3, '0')
}

export function leftLabel(letter) {
  const left = letter?.days_left
  if (left == null || left < 0) return ''
  if (left === 0) return '今天截止'
  if (left === 1) return '明天截止'
  if (left === 2) return '后天截止'
  return `还剩 ${left} 天`
}

function fail(error) {
  toast(error.message, 'error', 6000)
}

function apply(data) {
  geese.card = data.card
  geese.cubbies = data.cubbies
  geese.letters = data.letters
  geese.unopened = data.unopened
  geese.archived = data.archived
  geese.routes = data.routes
  geese.lastFetch = data.last_fetch
  geese.running = data.running
  geese.progress = data.progress
  geese.presets = data.presets
  geese.portals = data.portals
  geese.schools = data.schools || []
  if (!geese.selected || (geese.selected !== 'all' && !geese.cubbies.some((c) => c.id === geese.selected))) {
    const first = geese.cubbies.find((c) => c.unread) || geese.cubbies.find((c) => c.count) || geese.cubbies[0]
    geese.selected = first?.id || ''
  }
  geese.loaded = true
}

export async function loadGeese() {
  geese.loading = !geese.loaded
  try {
    apply(await api.geese())
    geese.error = ''
  } catch (error) {
    geese.error = error.message
  } finally {
    geese.loading = false
  }
}

export async function fetchNow() {
  if (geese.running) return
  geese.running = true
  try {
    const result = await api.geeseFetch()
    await loadGeese()
    if (!result.new) toast('鸿雁跑了一圈，各处都没有新信', 'info')
  } catch (error) {
    fail(error)
  } finally {
    geese.running = false
    geese.progress = null
  }
}

export async function openLetter(letter, from = null) {
  geese.reading = { ...letter, content: null }
  geese.readingLoading = true
  try {
    const full = await api.geeseLetter(letter.id)
    if (geese.reading?.id === letter.id) geese.reading = full
    patchLocal(full)
  } catch (error) {
    fail(error)
  } finally {
    geese.readingLoading = false
  }
  if (from) from.blur?.()
}

function patchLocal(item) {
  const index = geese.letters.findIndex((l) => l.id === item.id)
  if (index >= 0) geese.letters[index] = { ...geese.letters[index], ...item, content: undefined, body: undefined }
  if (geese.drawer) {
    const i = geese.drawer.letters.findIndex((l) => l.id === item.id)
    if (i >= 0) geese.drawer.letters[i] = { ...geese.drawer.letters[i], ...item }
  }
}

export async function updateLetter(letter, patch, quiet = false) {
  try {
    const item = await api.geeseUpdate(letter.id, patch)
    patchLocal(item)
    if (geese.reading?.id === item.id) Object.assign(geese.reading, item)
    if ('pinned' in patch || 'archived' in patch) await loadGeese()
    if (!quiet && 'pinned' in patch)
      toast(patch.pinned ? `给《${shortTitle(item.title, 18)}》别上了翡翠胸针，它不会被收进旧信` : '胸针取下来了', 'success')
    return item
  } catch (error) {
    fail(error)
    return null
  }
}

export async function openDrawer(box, q = '') {
  geese.drawer = { box, q, letters: geese.drawer?.box === box ? geese.drawer.letters : [], loading: true }
  try {
    const { letters } = await api.geeseDrawer(box, q)
    if (geese.drawer?.box === box) Object.assign(geese.drawer, { letters, loading: false })
  } catch (error) {
    fail(error)
    if (geese.drawer) geese.drawer.loading = false
  }
}

export async function teach(letter, data) {
  try {
    const item = await api.geeseTeach(letter.id, data)
    await loadGeese()
    if (geese.drawer) openDrawer(geese.drawer.box, geese.drawer.q)
    if (geese.reading?.id === item.id) Object.assign(geese.reading, item)
    const words = data.words?.length ? `「${data.words.join('、')}」` : ''
    if (data.kind === 'useful') {
      const cubby = geese.cubbies.find((c) => c.id === item.cubby)
      toast(words ? `记下了${words}，以后这类信会夹在「${cubby?.name || '杂信'}」那根绳上` : '这封信夹上信绳了', 'success', 6000)
    } else {
      toast(words ? `记下了${words}，以后这类信放进未拆的信` : '这封信放回未拆的信了', 'success', 6000)
    }
    return item
  } catch (error) {
    fail(error)
    return null
  }
}

export async function saveCard(card) {
  try {
    const saved = await api.geeseCard(card)
    geese.card = saved
    geese.selected = '' // the cubbies changed: open the first one with letters waiting
    await loadGeese()
    return saved
  } catch (error) {
    fail(error)
    return null
  }
}

// A deadline clause like 「报名截止日期：10月11日晚20:00」 gives the commission its hour too.
function deadlineTime(letter) {
  const match = (letter.deadline_text || '').match(/(\d{1,2})\s*[:：]\s*(\d{2})/)
  if (!match) return ''
  const h = Number(match[1])
  return h < 24 ? `${String(h).padStart(2, '0')}:${match[2]}` : ''
}

export function makeCommission(letter) {
  const note = [letter.title, letter.deadline_text ? `「${letter.deadline_text}」` : '', letter.link].filter(Boolean).join('\n')
  const time = letter.deadline ? deadlineTime(letter) : ''
  geese.reading = null // the slip opens on its own; the letter goes back into its cubby
  desk.editing = {
    title: shortTitle(letter.title, 60),
    client: letter.route_name,
    note,
    due_date: letter.deadline || '',
    due_time: time,
    remind: letter.deadline ? 1440 : null, // the slip's own choices: a day ahead
    _after: async (item) => {
      await updateLetter(letter, { commission_id: item.id }, true)
      const row = document.querySelector(`[data-goose="${letter.id}"]`)
      if (row) flyTo(row, 'commissions', 'letter')
    },
  }
}

export function makeAppointment(letter) {
  geese.reading = null
  desk.appointment = {
    kind: 'appointment',
    title: shortTitle(letter.title, 60),
    date: letter.deadline || isoDate(),
    note: [letter.title, letter.link].join('\n'),
    _after: (item) => updateLetter(letter, { appointment_id: item.id }, true),
  }
}

export async function loadRoutes() {
  try {
    const data = await api.geeseRoutes()
    geese.roads = data.routes
    geese.portals = data.portals
    return data
  } catch (error) {
    fail(error)
    return null
  }
}

export async function setRoute(route, patch) {
  try {
    const item = await api.geeseRoute(route.id, patch)
    const all = await loadRoutes()
    await loadGeese()
    return item || all
  } catch (error) {
    fail(error)
    return null
  }
}

export async function signIn(portalId) {
  try {
    await api.geeseLogin(portalId)
    toast('登录好了，鸿雁这就去门户取信', 'success')
    await loadRoutes()
    fetchNow()
  } catch (error) {
    fail(error)
  }
}

export async function signOut(portalId) {
  try {
    await api.geeseLogout(portalId)
    toast('已退出门户，本机不再保存它的登录', 'success')
    await loadRoutes()
  } catch (error) {
    fail(error)
  }
}

// ---------------------------------------------------------------- server events

on('geese', async (data) => {
  await loadGeese()
  if (data.new) {
    geese.arrivedIds = data.ids || []
    geese.arrival++
    sound.wings()
    if (data.alert) {
      sound.bell()
      toast(`${data.alert.title} · ${data.alert.text}`, 'warning', 12000, { label: '拆开看看', run: () => go('geese') })
    }
  }
})
on('geese-progress', (data) => {
  geese.progress = data
  geese.running = true
})
on('geese-login', (data) => {
  if (data.signed_in) return
  const portal = geese.portals[data.portal]
  toast(`${portal?.name || '门户'}的登录过期了，鸿雁进不去`, 'warning', 12000, {
    label: '重新登录',
    run: () => signIn(data.portal),
  })
})
