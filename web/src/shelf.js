// 信札与压花。压花 = 收藏：喜欢的歌像花一样压进书页，可以写一句压花笺。
// 信札 = 自己的歌单：一束用缎带扎起来的信，有名字、题记和缎带的颜色。
import { reactive, watch } from 'vue'
import { api } from './api.js'
import { store, toast } from './store.js'
import { sound } from './sound.js'
import { flyTo, petals } from './motion.js'
import { player, playList } from './player.js'

export const RIBBONS = {
  violet: { label: '紫罗兰', hue: '#6e4fa3' },
  wine: { label: '酒红', hue: '#8a2b36' },
  prussian: { label: '普鲁士蓝', hue: '#2a4a72' },
  moss: { label: '苔绿', hue: '#5c7a4a' },
  gold: { label: '旧金', hue: '#a67c2e' },
  rose: { label: '灰玫瑰', hue: '#b0707c' },
}

export const shelf = reactive({
  loaded: false,
  loading: false,
  pressed: [],
  pressedIds: new Set(),
  bundles: [],
  memberships: {}, // track id → bundle ids
  open: '', // '' | 'pressed' | a bundle id
  detail: null,
  menu: null, // { tracks, x, y } — the 夹进信札 popover
  editing: null, // a bundle being tied or retied
  focusNote: '', // a pressed song whose note should open for writing
})

function fail(error) {
  toast(error.message, 'error', 6000)
}

export async function loadShelf() {
  shelf.loading = true
  try {
    const data = await api.shelf()
    shelf.pressed = data.pressed
    shelf.pressedIds = new Set(data.pressed.map((p) => p.track_id))
    shelf.bundles = data.bundles
    shelf.memberships = data.memberships
    shelf.loaded = true
    if (shelf.open && shelf.open !== 'pressed') await openBundle(shelf.open, true)
  } catch (error) {
    fail(error)
  } finally {
    shelf.loading = false
  }
}

// Songs arriving in the letter box may be the ones a bundle was waiting for.
watch(() => store.library.tracks, () => shelf.loaded && loadShelf())

// The 信札 index tab on whichever music page is showing, or the music bookmark.
function shelfTarget() {
  return [...document.querySelectorAll('.music-tabs [data-tab="shelf"]')].find((el) => el.offsetParent) || 'music'
}

// ---------------------------------------------------------------- 压花

export const isPressed = (track) => Boolean(track && shelf.pressedIds.has(track.id))

export async function togglePress(track, from = null) {
  if (!track) return
  const pressing = !isPressed(track)
  // Answer at once; the server confirms a moment later.
  const ids = new Set(shelf.pressedIds)
  if (pressing) ids.add(track.id)
  else ids.delete(track.id)
  shelf.pressedIds = ids
  try {
    await api.press(track.id, pressing)
    if (pressing) {
      sound.stamp()
      if (from) petals(from, 9)
      toast(`把「${track.title}」压进了书里`, 'success', 4500, {
        label: '写一句压花笺',
        run: () => openPressed(track.id),
      })
    } else {
      toast(`把「${track.title}」从书页间取了出来`, 'info', 6000, { label: '放回去', run: () => togglePress(track) })
    }
    loadShelf()
  } catch (error) {
    loadShelf()
    fail(error)
  }
}

export async function setNote(trackId, note) {
  try {
    await api.press(trackId, true, note)
    const item = shelf.pressed.find((p) => p.track_id === trackId)
    if (item) item.note = note
  } catch (error) {
    fail(error)
  }
}

export function openPressed(trackId = '') {
  shelf.open = 'pressed'
  shelf.detail = null
  shelf.focusNote = trackId
  store.musicTab = 'shelf'
  store.view = 'shelf'
}

// ---------------------------------------------------------------- 信札

export async function openBundle(id, quiet = false) {
  shelf.open = id
  if (!quiet) shelf.detail = null
  try {
    const detail = await api.bundle(id)
    if (shelf.open === id) shelf.detail = detail
  } catch (error) {
    if (shelf.open === id) shelf.open = ''
    fail(error)
  }
}

export function closeBundle() {
  shelf.open = ''
  shelf.detail = null
}

export async function saveBundle(data) {
  try {
    if (data.id) {
      const bundle = await api.updateBundle(data.id, { name: data.name, epigraph: data.epigraph, ribbon: data.ribbon,
        revision: data.revision })
      toast(`信札「${bundle.name}」重新扎好了`, 'success')
      await loadShelf()
      return bundle
    }
    const bundle = await api.createBundle({ name: data.name, epigraph: data.epigraph, ribbon: data.ribbon,
      track_ids: data.trackIds || [], songs: data.songs || [] })
    sound.seal()
    const extra = bundle.pending ? `，${bundle.pending} 封还在路上，寄到书信匣就会自动收进来` : ''
    toast(`扎好了一束信札「${bundle.name}」${bundle.count ? `，夹着 ${bundle.count} 封信` : ''}${extra}`, 'success', 6500)
    await loadShelf()
    return bundle
  } catch (error) {
    if (error.code === 'conflict') {
      toast('这束信札刚在别处改过，已换成最新的样子', 'warning')
      loadShelf()
    } else fail(error)
    return null
  }
}

export async function addToBundle(bundle, { trackIds = [], songs = [] } = {}, from = null) {
  try {
    const result = await api.addToBundle(bundle.id, { track_ids: trackIds, songs })
    if (result.added) {
      sound.key()
      flyTo(from, shelfTarget(), 'letter')
      toast(result.duplicates ? `夹进了「${bundle.name}」· ${result.duplicates} 封原本就在里面` : `夹进了「${bundle.name}」`,
        'success')
    } else {
      toast(`这些信已经在「${bundle.name}」里了`, 'info')
    }
    if (shelf.open === bundle.id) shelf.detail = result.bundle
    loadShelf()
    return result
  } catch (error) {
    fail(error)
    return null
  }
}

export async function removeLetters(bundle, letters) {
  try {
    const result = await api.removeFromBundle(bundle.id, letters.map((l) => l.id))
    if (shelf.open === bundle.id) shelf.detail = result.bundle
    const name = letters.length === 1 ? `「${letters[0].title}」` : `${letters.length} 封信`
    toast(`把${name}从「${bundle.name}」里抽了出来`, 'info', 7000, {
      label: '放回去',
      run: () => addToBundle(bundle, { songs: result.removed }),
    })
    loadShelf()
  } catch (error) {
    fail(error)
  }
}

export async function reorderLetters(bundle, ids) {
  try {
    const detail = await api.orderBundle(bundle.id, ids)
    if (shelf.open === bundle.id) shelf.detail = detail
  } catch (error) {
    fail(error)
    openBundle(bundle.id, true)
  }
}

export async function untieBundle(bundle) {
  try {
    await api.remove('bundles', bundle.id)
    if (shelf.open === bundle.id) closeBundle()
    toast(`拆散了信札「${bundle.name}」。里面的歌都还在书信匣里`, 'info', 8000, {
      label: '重新扎起',
      run: async () => {
        await api.restore('bundles', bundle.id)
        loadShelf()
      },
    })
    loadShelf()
  } catch (error) {
    fail(error)
  }
}

export function playLetters(letters, shuffle = false) {
  const tracks = letters.filter((l) => l.state === 'here').map((l) => l.track)
  if (!tracks.length) return toast('这里的信还没寄到书信匣', 'info')
  player.mode = shuffle ? 'shuffle' : player.mode === 'shuffle' ? 'order' : player.mode
  playList(tracks, shuffle ? Math.floor(Math.random() * tracks.length) : 0)
}

// The 夹进信札 popover, anchored under whatever was clicked.
export function openMenu(tracks, event) {
  const rect = event.currentTarget.getBoundingClientRect()
  shelf.menu = { tracks: tracks.filter(Boolean), x: rect.left + rect.width / 2, y: rect.bottom + 6, top: rect.top - 6,
    from: event.currentTarget }
  if (!shelf.loaded) loadShelf()
}
