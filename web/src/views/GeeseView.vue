<script setup>
// 鸿雁：学校的通知。背景是邮局的分拣室；窗前拉着几根信绳（每根一项关心的事，信夹在上面），
// 也可以看一张打字机打的收信清单。两种看法，右上角切换，记住上次用的。
import { computed, onMounted, ref, watch } from 'vue'
import { store } from '../store.js'
import { fetchNow, geese, loadGeese, openDrawer, setLook } from '../geese.js'
import PageHeader from '../components/PageHeader.vue'
import GeeseLines from '../components/GeeseLines.vue'
import GeeseList from '../components/GeeseList.vue'
import GooseEnvelope from '../components/GooseEnvelope.vue'
import GooseFigure from '../components/GooseFigure.vue'
import PostmanRide from '../components/PostmanRide.vue'
import EmptySatchel from '../components/EmptySatchel.vue'
import InkLoader from '../components/InkLoader.vue'
import Icon from '../components/Icon.vue'

onMounted(() => {
  if (!geese.loaded) loadGeese()
})
// Coming back to the page: a quiet refresh, so letters that arrived meanwhile are in their cubbies.
watch(
  () => store.view,
  (view) => view === 'geese' && geese.loaded && loadGeese(),
)

const school = computed(() => geese.schools.find((s) => s.id === geese.card?.school))
const subtitle = computed(() => {
  if (!geese.card) return '学校的通知，替你取回来、拣出来'
  const parts = [school.value?.short || '鸿雁', `${geese.routes.length} 条驿路`]
  parts.push(geese.card.mode === 'morning' ? '每天早上取一次' : '随到随取')
  if (geese.lastFetch) parts.push(ago(geese.lastFetch))
  return parts.join(' · ')
})
function ago(ts) {
  const minutes = Math.round((Date.now() / 1000 - ts) / 60)
  if (minutes < 1) return '刚刚取过信'
  if (minutes < 60) return `${minutes} 分钟前取过信`
  if (minutes < 1440) return `${Math.round(minutes / 60)} 小时前取过信`
  return `${Math.round(minutes / 1440)} 天前取过信`
}
const broken = computed(() => geese.routes.filter((r) => r.error))
const progressText = computed(() => {
  const p = geese.progress
  if (!p) return '鸿雁出发了…'
  return `${p.route || '出发'} · ${p.done}/${p.total}`
})

const query = ref('')
let searchTimer = null
watch(query, (q) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => openDrawer('archive', q.trim()), 300)
})
function toggleDrawer(box) {
  if (geese.drawer?.box === box) geese.drawer = null
  else {
    query.value = ''
    openDrawer(box)
  }
}
</script>

<template>
  <section class="geese-view">
    <PageHeader eyebrow="Wild geese · letters from school" title="鸿雁" script="wild geese" :subtitle="subtitle">
      <template v-if="geese.card">
        <div class="look" role="radiogroup" aria-label="怎么看这些信">
          <button class="look-btn" role="radio" :aria-checked="geese.look === 'lines'" :class="{ on: geese.look === 'lines' }"
            @click="setLook('lines')"><Icon name="ribbon" :size="15" />信绳</button>
          <button class="look-btn" role="radio" :aria-checked="geese.look === 'list'" :class="{ on: geese.look === 'list' }"
            @click="setLook('list')"><Icon name="list" :size="15" />清单</button>
        </div>
        <button class="btn" :disabled="geese.running" @click="fetchNow">
          <Icon name="refresh" :size="15" :class="{ spin: geese.running }" />{{ geese.running ? '正在取信' : '现在就去取' }}
        </button>
        <button class="btn ghost" title="鸿雁去取信的路" @click="geese.routesOpen = true"><Icon name="route" :size="15" />驿路</button>
        <button class="btn ghost" title="收件人名片：你是谁、关心什么" @click="geese.carding = true"><Icon name="user" :size="15" />名片</button>
      </template>
    </PageHeader>

    <InkLoader v-if="!geese.loaded && geese.loading" label="鸿雁在整理羽毛…" script="wild geese" />
    <p v-else-if="geese.error && !geese.loaded" class="faint">鸿雁没能飞起来：{{ geese.error }}</p>

    <!-- Before the card: the sorting room is empty and a V of geese passes the window. -->
    <div v-else-if="geese.loaded && !geese.card" class="welcome">
      <div class="invite">
        <p class="eyebrow">Wild Geese Post</p>
        <p class="title-cn big">鸿雁传书</p>
        <p class="lede">
          写一张收件人名片，告诉鸿雁你是谁、关心什么。它会沿着驿路去学校各处取信，
          只把和你有关的夹在窗前的信绳上；其余的放进「未拆的信」，想翻随时能翻。
        </p>
        <p class="faint small">
          现在认识的学校：{{ geese.schools.map((s) => s.name).join('、') || '还没有' }}。别的学校，可以导入别人写好的驿路包。
        </p>
        <div class="invite-actions">
          <button class="btn wax" @click="geese.carding = true"><Icon name="goose" :size="16" />写一张名片</button>
          <button class="btn ghost" @click="geese.routesOpen = true"><Icon name="route" :size="15" />看看驿路</button>
        </div>
      </div>
      <div class="sky" aria-hidden="true">
        <GooseFigure v-for="i in 5" :key="i" class="v-goose" :size="i === 3 ? 62 : 48" :delay="i * 0.09" :letter="i === 3"
          :style="{ '--k': Math.abs(i - 3), '--side': i < 3 ? -1 : 1 }" />
      </div>
    </div>

    <template v-else-if="geese.loaded">
      <p v-if="broken.length" class="broken faint small">
        <Icon name="route" :size="13" />
        {{ broken.map((r) => r.name + (r.column ? '·' + r.column : '')).join('、') }} 这次没取到信。
        <button class="link" @click="geese.routesOpen = true">看看驿路</button>
      </p>

      <Transition name="ride">
        <PostmanRide v-if="geese.running" :label="progressText" />
      </Transition>

      <Transition name="swap" mode="out-in">
        <!-- ---------------------------------------------------- the lines before the window -->
        <div v-if="geese.look === 'lines'" key="lines" class="wall">
          <GeeseLines :drawer="geese.drawer?.box || ''" @drawer="toggleDrawer" />

          <section v-if="geese.drawer" class="laid">
            <header class="laid-head">
              <h3 class="title-cn">{{ geese.drawer.box === 'unopened' ? '未拆的信' : '旧信' }}</h3>
              <p class="faint small">
                {{ geese.drawer.box === 'unopened'
                  ? '鸿雁没拣出来的信，30 天后自动清掉。哪封其实有用，拆开后点「这封对我有用」，它就会教给名片。'
                  : '截止日期过了、或者送来两周的信，会收到这里，留一年。' }}
              </p>
              <input v-if="geese.drawer.box === 'archive'" v-model="query" class="field search" placeholder="搜旧信：标题、正文、驿路" aria-label="搜旧信" />
            </header>
            <InkLoader v-if="geese.drawer.loading && !geese.drawer.letters.length" label="翻信篮…" script="letters" />
            <div v-else-if="geese.drawer.letters.length" :key="geese.drawer.box + geese.drawer.q" class="spread">
              <GooseEnvelope v-for="(l, i) in geese.drawer.letters" :key="l.id" :letter="l" :index="i"
                :sealed="geese.drawer.box === 'unopened'" />
            </div>
            <EmptySatchel v-else :title="geese.drawer.box === 'unopened' ? '信篮是空的' : query ? '没有搜到' : '还没有旧信'" />
          </section>
        </div>

        <!-- ---------------------------------------------------- the typed list -->
        <GeeseList v-else key="list" />
      </Transition>
    </template>
  </section>
</template>

<style scoped>
.geese-view {
  display: grid;
  gap: 18px;
}
.geese-view > :deep(.page-header) {
  margin-bottom: 0;
}
.spin {
  animation: spin 1.1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.small {
  font-size: 12.5px;
}
.link {
  font-size: 12.5px;
  color: var(--violet-ink);
}
.link:hover {
  text-decoration: underline;
}
/* ---------------------------------------------------------- welcome */
.welcome {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1fr);
  gap: 30px;
  align-items: center;
  min-height: 460px;
}
.invite {
  padding: 28px 30px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--sheet) 82%, transparent);
  backdrop-filter: blur(2px);
  box-shadow: var(--shadow-sheet);
}
.invite p {
  margin: 0 0 10px;
}
.big {
  font-size: 34px;
  letter-spacing: 0.14em;
}
.lede {
  font-size: 15.5px;
  line-height: 1.9;
  color: var(--ink-soft);
}
.invite-actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}
.sky {
  position: relative;
  height: 300px;
}
.v-goose {
  position: absolute;
  left: calc(46% - 30px + var(--side) * var(--k) * 48px);
  top: calc(6px + var(--k) * 22px);
  --goose-ink: var(--ink-faint);
  opacity: 0.6;
  animation: glide 6s ease-in-out infinite alternate;
  animation-delay: calc(var(--k) * -0.7s);
}
@keyframes glide {
  from {
    transform: translate(-12px, 6px);
  }
  to {
    transform: translate(14px, -8px);
  }
}
/* ---------------------------------------------------------- the page */
.broken {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -6px 0 0;
}
.look {
  display: inline-flex;
  margin-right: 6px;
  padding: 3px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--sheet) 80%, transparent);
  box-shadow: inset 0 0 0 1px var(--rule);
  backdrop-filter: blur(2px);
}
.look-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border-radius: 16px;
  font-size: 13px;
  color: var(--ink-soft);
  transition: background 0.25s var(--ease), color 0.25s var(--ease);
}
.look-btn.on {
  background: var(--sheet-raised);
  color: var(--violet-ink);
  box-shadow: 0 1px 3px rgba(60, 40, 20, 0.15);
}
.wall {
  display: grid;
  gap: 22px;
}
.shelf-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 15px;
  color: var(--emerald);
}
.laid {
  padding: 4px 0 0;
}
.laid-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 14px;
  margin-bottom: 14px;
}
.laid-head h3,
.laid-head p {
  margin: 0;
}
.laid-head h3 {
  font-size: 20px;
  font-weight: 400;
  letter-spacing: 0.12em;
}
.laid-head .search {
  flex-basis: 100%;
  max-width: 320px;
}
.urgent {
  color: var(--danger);
}
/* Envelopes laid out in front of the wall. */
.spread {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(232px, 1fr));
  gap: 18px 16px;
}
.spread.slim {
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}
/* The header's buttons sit over the painting's window: give them a little paper behind. */
.geese-view > :deep(.page-header .btn) {
  background: color-mix(in srgb, var(--sheet) 78%, transparent);
  backdrop-filter: blur(3px);
}
.ride-enter-from,
.ride-leave-to {
  opacity: 0;
  height: 0;
}
.ride-enter-active,
.ride-leave-active {
  transition: all 0.4s var(--ease);
  overflow: hidden;
}
.swap-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.swap-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
.swap-enter-active,
.swap-leave-active {
  transition: all 0.3s var(--ease);
}
@media (max-width: 900px) {
  .welcome {
    grid-template-columns: minmax(0, 1fr);
  }
  .sky {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .v-goose,
  .spin {
    animation: none;
  }
}
</style>
