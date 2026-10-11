// 书桌的状态：委托、约定、回信、邮戳簿与代笔时间。与音乐部分（store.js）分开，各管各的。
import { reactive } from 'vue'
import { api } from './api.js'
import { store, toast, go, on, loadTodayLetter } from './store.js'
import { sound } from './sound.js'
import { flyTo, petals } from './motion.js'
import { isoDate, monthDay, relativeDay } from './format.js'

export const desk = reactive({
  today: null,
  loading: false,
  error: '',
  commissions: [],
  clients: [],
  loaded: false,
  filter: 'today', // today | upcoming | all | someday | done
  client: '',
  editing: null, // a commission open in the drawer ({} for a new one)
  replies: [],
  weeks: [],
  repliesLoaded: false,
  month: '',
  days: [],
  selected: '',
  detail: null,
  calendarLoading: false,
  appointment: null, // an appointment / anniversary open in the dialog
  writing: null, // the reply on the typewriter
  focus: null, // { commission, started, target }
  weekly: null, // the weekly packet being sealed
  reading: null, // one of your own letters, open for rereading
  finished: 0, // when the day's last commission was delivered (the desk shows 今日事毕)
})

function fail(error) {
  toast(error.message, 'error', 6000)
}

// Reload whatever is on screen after a change, quietly.
export async function refresh() {
  const jobs = [loadDesk(true)]
  if (desk.loaded) jobs.push(loadCommissions())
  if (desk.month) jobs.push(loadCalendar(desk.month, true))
  if (desk.repliesLoaded) jobs.push(loadReplies())
  await Promise.allSettled(jobs)
}

export async function loadDesk(quiet = false) {
  if (!quiet) desk.loading = true
  try {
    desk.today = await api.deskToday()
    desk.error = ''
  } catch (error) {
    desk.error = error.message
  } finally {
    desk.loading = false
  }
}

// ---------------------------------------------------------------- commissions

export async function loadCommissions() {
  try {
    const result = await api.commissions()
    desk.commissions = result.commissions
    desk.clients = result.clients
    desk.loaded = true
  } catch (error) {
    fail(error)
  }
}

function replaceLocal(item) {
  const index = desk.commissions.findIndex((c) => c.id === item.id)
  if (index >= 0) desk.commissions[index] = item
  else desk.commissions.push(item)
}

export async function saveCommission(data) {
  try {
    const item = data.id ? await api.updateCommission(data.id, data) : await api.createCommission(data)
    replaceLocal(item)
    refresh()
    return item
  } catch (error) {
    if (error.code === 'conflict' && error.current) {
      replaceLocal(error.current)
      toast('这份委托刚在别处改过，已换成最新的内容', 'warning', 6000)
      return error.current
    }
    fail(error)
    return null
  }
}

export async function postponeCommission(item, on) {
  const before = item.due_date
  const saved = await saveCommission({ id: item.id, due_date: on, revision: item.revision })
  if (saved && saved.due_date === on) {
    toast(`「${item.title}」推到了${relativeDay(on)}`, 'success', 5000, {
      label: '撤销',
      run: () => saveCommission({ id: saved.id, due_date: before, revision: saved.revision }),
    })
  }
}

// `from` is the row on screen: the delivered slip flies into the stamp book.
export async function completeCommission(item, done = true, from = null) {
  try {
    const wasOpen = desk.today?.commissions?.some((c) => c.id === item.id)
    const result = await api.completeCommission(item.id, done)
    replaceLocal(result.commission)
    if (done) {
      sound.stamp()
      if (from) flyTo(from, 'calendar', 'stamp')
      const next = result.spawned
      toast(next ? `已送达 · 下一份「${next.title}」排在${relativeDay(next.due_date)}` : `「${item.title}」已送达`,
        'success', 5000, { label: '撤销', run: () => completeCommission(result.commission, false) })
    }
    await refresh()
    // The last of today's commissions: the whole day gets its seal.
    if (done && wasOpen && !desk.today?.commissions?.length) {
      desk.finished = Date.now()
      if (from) petals(from, 18)
      sound.seal()
    }
    return result.commission
  } catch (error) {
    fail(error)
    return null
  }
}

export async function tearCommission(item) {
  try {
    await api.remove('commissions', item.id)
    desk.commissions = desk.commissions.filter((c) => c.id !== item.id)
    if (desk.editing?.id === item.id) desk.editing = null
    toast(`撕掉了委托「${item.title}」`, 'info', 7000, {
      label: '撤销',
      run: async () => {
        await api.restore('commissions', item.id)
        refresh()
      },
    })
    refresh()
  } catch (error) {
    fail(error)
  }
}

// Quick add from the desk: "整理照片" lands on today unless a day is given.
export async function quickCommission(title, extra = {}) {
  title = title.trim()
  if (!title) return null
  const item = await saveCommission({ title, due_date: isoDate(), ...extra })
  if (item) sound.key()
  return item
}

// ---------------------------------------------------------------- appointments

export async function saveAppointment(data) {
  try {
    const item = data.id ? await api.updateAppointment(data.id, data) : await api.createAppointment(data)
    flyTo(document.activeElement, 'calendar', 'letter')
    toast(item.kind === 'anniversary' ? `记下了「${item.title}」，每年都会提醒你` : `约定「${item.title}」已记在${monthDay(item.date)}`, 'success')
    refresh()
    return item
  } catch (error) {
    if (error.code === 'conflict') toast('这个约定刚在别处改过，请重新打开', 'warning')
    else fail(error)
    return null
  }
}

export async function removeAppointment(item) {
  try {
    await api.remove('appointments', item.id)
    toast(`划掉了「${item.title}」`, 'info', 7000, {
      label: '撤销',
      run: async () => {
        await api.restore('appointments', item.id)
        refresh()
      },
    })
    refresh()
  } catch (error) {
    fail(error)
  }
}

// ---------------------------------------------------------------- the stamp book

export async function loadCalendar(month, quiet = false) {
  if (!quiet) desk.calendarLoading = true
  try {
    const result = await api.calendar(month)
    desk.month = result.month
    desk.days = result.days
  } catch (error) {
    fail(error)
  } finally {
    desk.calendarLoading = false
  }
  if (desk.selected) selectDay(desk.selected, true)
}

export async function selectDay(date, quiet = false) {
  desk.selected = date
  if (!quiet) desk.detail = null
  try {
    const detail = await api.day(date)
    if (desk.selected === date) desk.detail = detail
  } catch (error) {
    fail(error)
  }
}

// ---------------------------------------------------------------- replies (the diary)

export async function loadReplies() {
  try {
    const result = await api.replies()
    desk.replies = result.replies
    desk.weeks = result.weeks
    desk.repliesLoaded = true
  } catch (error) {
    fail(error)
  }
}

// Sit down at the typewriter: today's unfinished draft, a given reply, or a fresh sheet.
export async function startWriting(reply = null) {
  try {
    if (!reply) {
      if (!desk.today) await loadDesk(true)
      const current = desk.today?.reply
      reply = current && !current.sealed_at ? current : await api.createReply({ date: isoDate() })
    } else if (typeof reply === 'string') {
      reply = await api.reply(reply)
    }
    desk.writing = reply
    go('write')
  } catch (error) {
    fail(error)
  }
}

// Clip a song into today's reply from anywhere (the player, the desk); a draft is started if needed.
export async function clipToReply(track, from = null) {
  if (!track) return
  try {
    if (!desk.today) await loadDesk(true)
    let reply = desk.today?.reply
    if (reply?.sealed_at) {
      toast('今天的回信已经封缄了。明天再把歌夹进去吧', 'info')
      return
    }
    if (!reply) reply = await api.createReply({ date: isoDate() })
    const song = { id: track.track_id || track.id, title: track.title, artist: track.artist, album: track.album,
      has_cover: Boolean(track.has_cover) }
    const saved = await api.updateReply(reply.id, { song, revision: reply.revision })
    if (desk.writing?.id === saved.id) desk.writing = saved
    flyTo(from, 'desk', 'note')
    sound.stamp()
    toast(`把「${track.title}」夹进了今天的回信`, 'success', 5000, { label: '去写信', run: () => startWriting(saved) })
    refresh()
  } catch (error) {
    fail(error)
  }
}

// ---------------------------------------------------------------- 代笔时间 (focus)

export function startFocus(commission = null, target = 25 * 60) {
  desk.focus = { commission, started: Date.now(), target }
}

export async function endFocus(seconds, { complete = false } = {}) {
  const focus = desk.focus
  desk.focus = null
  if (!focus || seconds < 30) return
  try {
    await api.focus(focus.commission?.id, Math.round(seconds), focus.started / 1000)
    if (complete && focus.commission) await completeCommission(focus.commission, true, { x: innerWidth / 2, y: innerHeight / 2 })
    else toast(`代笔了 ${Math.round(seconds / 60)} 分钟，已记在委托单上`, 'success')
    refresh()
  } catch (error) {
    fail(error)
  }
}

on('reminder', () => refresh())
on('write', () => startWriting())

// Reopen the desk when the date rolls over while Violet stays open overnight.
let lastDay = isoDate()
setInterval(() => {
  const day = isoDate()
  if (day !== lastDay) {
    lastDay = day
    store.today = day
    refresh()
    loadTodayLetter()
  }
}, 60000)
