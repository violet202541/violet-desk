// 退回：把下错的、不要的歌移进 Windows 回收站（连同同名歌词），从信札和压花里取下。
// 先问清它夹在哪儿，再退；退回后旧回信里还留着歌名，只是不能再放了。
import { reactive } from 'vue'
import { api } from './api.js'
import { store, toast } from './store.js'
import { release, forgetTracks } from './player.js'
import { loadShelf, shelf } from './shelf.js'
import { sound } from './sound.js'

export const sendBack = reactive({
  asking: null, // { tracks, refs, loading, busy } — the confirmation
  picking: false, // 整理 mode in the letter box
  picked: new Set(),
  dupes: null, // { loading, groups, keep: { key: id | 'all' } }
})

export function startPicking() {
  sendBack.picking = true
  sendBack.picked = new Set()
}

export function stopPicking() {
  sendBack.picking = false
  sendBack.picked = new Set()
}

export function togglePick(id) {
  const next = new Set(sendBack.picked)
  next.has(id) ? next.delete(id) : next.add(id)
  sendBack.picked = next
}

export async function askSendBack(tracks) {
  if (!tracks?.length) return false
  const asking = reactive({ tracks, refs: {}, loading: true, busy: false, resolve: null })
  sendBack.asking = asking
  const answer = new Promise((resolve) => (asking.resolve = resolve))
  try {
    const { items } = await api.references(tracks.map((t) => t.id))
    asking.refs = Object.fromEntries(items.map((r) => [r.id, r]))
  } catch (error) {
    toast(error.message, 'error', 6000)
  } finally {
    asking.loading = false
  }
  return answer
}

export function cancelSendBack() {
  sendBack.asking?.resolve(false)
  sendBack.asking = null
}

export async function confirmSendBack() {
  const asking = sendBack.asking
  if (!asking || asking.busy) return
  asking.busy = true
  const ids = asking.tracks.map((t) => t.id)
  const held = release(ids)
  let result = { removed: [], failed: [] }
  try {
    result = await api.sendBack(ids)
  } catch (error) {
    toast(error.message, 'error', 6000)
  }
  forgetTracks(result.removed, held)
  const gone = new Set(result.removed)
  store.library.tracks = store.library.tracks.filter((t) => !gone.has(t.id))
  sendBack.picked = new Set([...sendBack.picked].filter((id) => !gone.has(id)))
  if (gone.size) {
    sound.stamp()
    if (shelf.loaded) loadShelf()
    toast(gone.size === 1 ? `「${asking.tracks.find((t) => gone.has(t.id)).title}」退回了，在回收站里还能找回来`
      : `${gone.size} 首歌退回了，在回收站里还能找回来`, 'success')
  }
  if (result.failed.length) {
    const first = result.failed[0]
    toast(`${result.failed.length} 首没能退回${first.title ? `（「${first.title}」：${first.error}）` : `：${first.error}`}`, 'error', 8000)
  }
  asking.resolve(gone.size > 0)
  sendBack.asking = null
  if (sendBack.picking && !sendBack.picked.size && gone.size) stopPicking()
}

// ---------------------------------------------------------------- the same song, more than once

export async function openDuplicates() {
  sendBack.dupes = { loading: true, groups: [], keep: {} }
  try {
    const { groups } = await api.duplicates()
    if (!sendBack.dupes) return
    sendBack.dupes.groups = groups
    // Copies of very different length are probably different versions: keep them all unless told otherwise.
    sendBack.dupes.keep = Object.fromEntries(groups.map((g) => [g.key, g.versions ? 'all' : g.copies[0].id]))
  } catch (error) {
    toast(error.message, 'error', 6000)
    sendBack.dupes = null
    return
  }
  sendBack.dupes.loading = false
}

export function closeDuplicates() {
  sendBack.dupes = null
}

export function spareCopies() {
  const d = sendBack.dupes
  if (!d) return []
  return d.groups.flatMap((g) => (d.keep[g.key] === 'all' ? [] : g.copies.filter((c) => c.id !== d.keep[g.key])))
}

export async function sendBackSpares() {
  const spares = spareCopies()
  const byId = new Map(store.library.tracks.map((t) => [t.id, t]))
  const tracks = spares.map((c) => byId.get(c.id) || c)
  if (await askSendBack(tracks)) await openDuplicates()
}
