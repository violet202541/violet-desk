import { createApp } from 'vue'
import '@fontsource/cormorant-garamond/400.css'
import '@fontsource/cormorant-garamond/400-italic.css'
import '@fontsource/cormorant-garamond/500-italic.css'
import '@fontsource/cormorant-garamond/600.css'
import '@fontsource/cutive-mono/400.css'
import '@fontsource/pinyon-script/400.css'
import 'lxgw-wenkai-screen-webfont/lxgwwenkaigbscreen.css'
import './styles/huiwen.css'
import './styles/base.css'
import './fonts.js'
import App from './App.vue'
import DesktopLyrics from './components/DesktopLyrics.vue'

// The same page serves the floating lyrics strip, opened with ?view=lyrics.
const view = new URLSearchParams(location.search).get('view')
createApp(view === 'lyrics' ? DesktopLyrics : App).mount('#app')
