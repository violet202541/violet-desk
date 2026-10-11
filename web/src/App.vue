<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { store, boot, loadTodayLetter, go, VIEWS, MUSIC_VIEWS } from './store.js'
import { desk, loadDesk, startWriting } from './desk.js'
import { loadShelf } from './shelf.js'
import { loadGeese } from './geese.js'
import { player, toggle, seek, next, prev } from './player.js'
import { dialogOpen } from './dialog.js'
import { startDesktopLyrics } from './desktopLyrics.js'
import { isoDate } from './format.js'
import SideBar from './components/SideBar.vue'
import TitleBar from './components/TitleBar.vue'
import PlayerBar from './components/PlayerBar.vue'
import LyricsSheet from './components/LyricsSheet.vue'
import IntroOverlay from './components/IntroOverlay.vue'
import Overlays from './components/Overlays.vue'
import Nunkish from './components/Nunkish.vue'
import Wordmark from './components/Wordmark.vue'
import HeroBackdrop from './components/HeroBackdrop.vue'
import Ambience from './components/Ambience.vue'
import MusicTabs from './components/MusicTabs.vue'
import LetterOverlay from './components/LetterOverlay.vue'
import CommissionDrawer from './components/CommissionDrawer.vue'
import AppointmentDialog from './components/AppointmentDialog.vue'
import ReplyReader from './components/ReplyReader.vue'
import WeeklyDialog from './components/WeeklyDialog.vue'
import FocusOverlay from './components/FocusOverlay.vue'
import DeskView from './views/DeskView.vue'
import CommissionsView from './views/CommissionsView.vue'
import CalendarView from './views/CalendarView.vue'
import WriteView from './views/WriteView.vue'
import SearchView from './views/SearchView.vue'
import PlaylistView from './views/PlaylistView.vue'
import LibraryView from './views/LibraryView.vue'
import PostRoomView from './views/PostRoomView.vue'
import ShelfView from './views/ShelfView.vue'
import GeeseView from './views/GeeseView.vue'
import GooseReader from './components/GooseReader.vue'
import GeeseCard from './components/GeeseCard.vue'
import GeeseRoutes from './components/GeeseRoutes.vue'
import BundleMenu from './components/BundleMenu.vue'
import BundleDialog from './components/BundleDialog.vue'
import SendBackDialog from './components/SendBackDialog.vue'
import DuplicatesDialog from './components/DuplicatesDialog.vue'
import SettingsView from './views/SettingsView.vue'
import MailboxView from './views/MailboxView.vue'

// Alt+1…7 follow the sidebar from top to bottom.
const HOTKEYS = ['desk', 'commissions', 'calendar', 'mailbox', 'geese', 'music', 'settings']
const WATERMARK = { commissions: 'commissions', calendar: 'days', playlist: 'letters', library: 'memories', shelf: 'keepsakes',
  post: 'post office', mailbox: 'letters', settings: 'writing desk' }
const visited = reactive(new Set(['desk']))
const refs = reactive({})
const homeEmpty = computed(() => {
  const view = store.search
  return !view.songs.length && !view.loading && !view.error && !view.lastQuery
})
const backdrop = computed(() => {
  if (store.view === 'desk' || store.view === 'geese') return 'full'
  if (store.view === 'search' && homeEmpty.value) return 'soft'
  if (store.view === 'write') return 'whisper'
  return ''
})
const intro = ref(false)

// Turning pages: the old page lifts away while the new one settles, moving the way the bookmarks run.
const ORDER = ['desk', 'write', 'commissions', 'calendar', 'mailbox', 'geese', ...MUSIC_VIEWS, 'settings']
const turn = reactive({ leaving: '', entering: '', dir: 1, axis: 'y' })
// Only the page shown at start-up gets the gentle first fade; every later arrival uses the page turn.
const firstView = ref(store.view)
let turnTimer = null
const reload = () => window.location.reload()

// The full opening plays once a day (and can be switched off in settings).
function introDue() {
  try {
    const today = new Date().toDateString()
    if (localStorage.getItem('violet-intro-v5') === today) return false
    localStorage.setItem('violet-intro-v5', today)
  } catch {
    /* show it anyway */
  }
  return true
}

// Overlays outside the shell start below the custom title area, so the window stays movable.
watch(
  () => store.frame.frameless,
  (on) => document.documentElement.style.setProperty('--titlebar-h', on ? '38px' : '0px'),
)

watch(
  () => store.view,
  (view, old) => {
    visited.add(view)
    if (old && !window.matchMedia('(prefers-reduced-motion: reduce)').matches && store.settings?.ambient !== false) {
      clearTimeout(turnTimer)
      turn.dir = ORDER.indexOf(view) >= ORDER.indexOf(old) ? 1 : -1
      turn.axis = MUSIC_VIEWS.includes(view) && MUSIC_VIEWS.includes(old) ? 'x' : 'y'
      turn.leaving = old
      turn.entering = view
      // Clear only after the slowest animation (0.1 s delay + 0.6 s) has finished.
      turnTimer = setTimeout(() => {
        turn.leaving = ''
        turn.entering = ''
      }, 760)
    }
    player.sheet = false
    if (location.hash.slice(1) !== view) history.replaceState(null, '', `#${view}`)
  },
)

function typing(target) {
  const tag = target?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable
}

function onKey(event) {
  if (store.keyDialog || store.confirmDialog) {
    if (event.key === 'Escape') {
      const dialog = store.confirmDialog || store.keyDialog
      dialog.resolve(false)
      if (dialog === store.confirmDialog) store.confirmDialog = null
      else store.keyDialog = null
    }
    return
  }
  // A dialog that traps focus handles its own keys.
  if (intro.value || dialogOpen() || store.letters.envelope) return
  const inField = typing(event.target)
  const ctrl = event.ctrlKey || event.metaKey
  if (event.altKey && /^[1-7]$/.test(event.key)) {
    event.preventDefault()
    go(HOTKEYS[Number(event.key) - 1])
    return
  }
  if (event.key === 'Escape' && player.sheet) {
    player.sheet = false
    return
  }
  if (ctrl && event.key.toLowerCase() === 'n' && !event.shiftKey) {
    event.preventDefault()
    desk.editing = { due_date: isoDate() }
    return
  }
  if ((ctrl && (event.key === 'k' || event.key === 'f')) || (!inField && event.key === '/')) {
    event.preventDefault()
    if (store.view !== 'playlist') go('search')
    setTimeout(() => refs[store.view]?.focus?.(), 30)
    return
  }
  if (ctrl && event.key.toLowerCase() === 'd' && MUSIC_VIEWS.includes(store.view)) {
    event.preventDefault()
    refs[store.view]?.sendSelected?.()
    return
  }
  if (inField) return
  if (ctrl && event.key.toLowerCase() === 'a' && (store.view === 'search' || store.view === 'playlist')) {
    event.preventDefault()
    refs[store.view]?.selectVisible?.()
  } else if (event.key === ' ' && event.target.tagName !== 'BUTTON' && !event.target.closest('[role="listbox"]')) {
    event.preventDefault()
    toggle()
  } else if (ctrl && event.key === 'ArrowRight') next(true)
  else if (ctrl && event.key === 'ArrowLeft') prev()
  else if (event.shiftKey && event.key === 'ArrowRight') seek(player.time + 10)
  else if (event.shiftKey && event.key === 'ArrowLeft') seek(player.time - 10)
}

function followHash() {
  const view = location.hash.slice(1)
  if (view === 'write') startWriting()
  else if (VIEWS.includes(view)) go(view)
}

onMounted(async () => {
  // Drop the first-fade class once it has played, so no later class change can restart it.
  setTimeout(() => (firstView.value = ''), 900)
  followHash()
  window.addEventListener('hashchange', followHash)
  await boot()
  if (store.ready) {
    if (store.settings?.intro !== false && introDue()) intro.value = true
    loadTodayLetter()
    loadDesk()
    loadShelf() // the library cards and the player bar show which songs are pressed
    loadGeese() // the sidebar counts unopened school letters; the desk has a letter rack
    startDesktopLyrics()
  }
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div v-if="store.bootError" class="fatal">
    <Wordmark :height="80" />
    <p class="title-cn">Violet 的本地服务没有回应</p>
    <p class="faint">{{ store.bootError }}</p>
    <button class="btn" @click="reload">重新连接</button>
  </div>

  <div v-else class="shell" :class="{ ready: store.ready, frameless: store.frame.frameless }">
    <SideBar />
    <TitleBar />
    <main class="main">
      <Transition name="fade">
        <HeroBackdrop v-if="store.ready && backdrop" :strength="backdrop" :scene="store.view === 'geese' ? 'postal' : 'desk'" />
      </Transition>
      <Transition name="fade">
        <Ambience v-if="store.ready && backdrop" :strength="backdrop" />
      </Transition>
      <Nunkish v-if="WATERMARK[store.view]" class="watermark" :text="WATERMARK[store.view]" :size="120" :weight="2.4" />
      <template v-if="store.ready">
        <div v-for="id in VIEWS" v-show="store.view === id || turn.leaving === id" :key="id" class="page" :data-view="id"
          :class="{ leaving: turn.leaving === id, entering: turn.entering === id, [`axis-${turn.axis}`]: true }"
          :style="{ '--dir': turn.dir }" :inert="turn.leaving === id || undefined">
          <div v-if="visited.has(id)" class="page-inner" :class="{ first: id === firstView }">
            <MusicTabs v-if="MUSIC_VIEWS.includes(id)" />
            <DeskView v-if="id === 'desk'" />
            <CommissionsView v-else-if="id === 'commissions'" />
            <CalendarView v-else-if="id === 'calendar'" />
            <MailboxView v-else-if="id === 'mailbox'" />
            <GeeseView v-else-if="id === 'geese'" />
            <WriteView v-else-if="id === 'write'" />
            <SearchView v-else-if="id === 'search'" :ref="(el) => (refs.search = el)" />
            <PlaylistView v-else-if="id === 'playlist'" :ref="(el) => (refs.playlist = el)" />
            <LibraryView v-else-if="id === 'library'" />
            <PostRoomView v-else-if="id === 'post'" />
            <ShelfView v-else-if="id === 'shelf'" />
            <SettingsView v-else-if="id === 'settings'" />
          </div>
        </div>
      </template>
      <LyricsSheet />
    </main>
    <PlayerBar />
  </div>

  <LetterOverlay :ready="!intro && store.ready" />
  <CommissionDrawer />
  <AppointmentDialog />
  <ReplyReader />
  <WeeklyDialog />
  <FocusOverlay />
  <BundleDialog />
  <BundleMenu />
  <DuplicatesDialog />
  <SendBackDialog />
  <GooseReader />
  <GeeseCard />
  <GeeseRoutes />
  <Overlays />
  <IntroOverlay v-if="intro" @done="intro = false" />
</template>

<style>
.shell {
  --titlebar: 0px;
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: var(--sidebar) 1fr;
  grid-template-rows: var(--titlebar) minmax(0, 1fr) var(--player);
  height: 100vh;
}
.shell.frameless {
  --titlebar: 38px;
}
.shell > .sidebar {
  grid-row: 1 / 3;
}
.shell > .titlebar {
  grid-column: 2;
  grid-row: 1;
}
.shell > .main {
  grid-column: 2;
  grid-row: 2;
}
.shell > .player {
  grid-column: 1 / -1;
  grid-row: 3;
}
.frameless .page-inner {
  padding-top: 10px;
}
.main {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.page {
  position: absolute;
  inset: 0;
  z-index: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
}
.page-inner {
  position: relative;
  max-width: 1240px;
  margin: 0 auto;
  padding: 34px 48px 48px;
}
/* The very first page fades in once. It is keyed to a class that never comes back,
   so removing the turning classes afterwards cannot replay it (that replay was the flash). */
.page-inner.first {
  animation: page-in 0.5s var(--ease);
}
@keyframes page-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
}
/* The page being put away lifts off and fades; the new one slides in from the side the bookmarks point to. */
.page.leaving {
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}
.page.leaving > .page-inner {
  animation: page-away 0.22s cubic-bezier(0.4, 0, 1, 1) forwards;
}
.page.entering > .page-inner {
  animation: page-turn 0.6s cubic-bezier(0.2, 0.8, 0.25, 1) 0.1s both;
}
@keyframes page-away {
  to {
    opacity: 0;
    transform: translate3d(0, calc(var(--dir) * -18px), 0) scale(0.985);
    filter: blur(2px);
  }
}
@keyframes page-turn {
  from {
    opacity: 0;
    transform: translate3d(0, calc(var(--dir) * 26px), 0) rotate(calc(var(--dir) * 0.4deg));
    filter: blur(3px);
  }
  55% {
    filter: blur(0);
  }
}
/* Between the music tabs only the sheet under the tabs slides sideways; the tabs stay put. */
.page.axis-x.leaving > .page-inner,
.page.axis-x.entering > .page-inner {
  animation: none;
}
.page.axis-x.leaving .music-tabs {
  visibility: hidden;
}
.page.axis-x.leaving > .page-inner > :not(.music-tabs) {
  animation: page-away-x 0.2s cubic-bezier(0.4, 0, 1, 1) forwards;
}
.page.axis-x.entering > .page-inner > :not(.music-tabs) {
  animation: page-turn-x 0.5s cubic-bezier(0.2, 0.8, 0.25, 1) 0.08s both;
}
@keyframes page-away-x {
  to {
    opacity: 0;
    transform: translate3d(calc(var(--dir) * -30px), 0, 0);
  }
}
@keyframes page-turn-x {
  from {
    opacity: 0;
    transform: translate3d(calc(var(--dir) * 40px), 0, 0);
  }
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.6s var(--ease);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.watermark {
  position: absolute;
  left: 24px;
  bottom: 10px;
  color: var(--violet-ink);
  opacity: 0.045;
  pointer-events: none;
  transform: rotate(-6deg);
}
.fatal {
  height: 100vh;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 10px;
  text-align: center;
}
.fatal p {
  margin: 0;
}
.fatal .title-cn {
  font-size: 22px;
  margin-top: 12px;
}
</style>
