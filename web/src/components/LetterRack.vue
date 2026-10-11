<script setup>
// 书桌边上的小信插：插着今天最相关、还没拆的一两封学校的信。没有新信时，它就不在桌上。
import { computed } from 'vue'
import { go } from '../store.js'
import { geese, leftLabel, openLetter, shortTitle } from '../geese.js'
import Icon from './Icon.vue'
import ExpressStamp from './ExpressStamp.vue'

const picks = computed(() =>
  geese.letters
    .filter((l) => !l.read_at)
    .sort((a, b) => Number(b.urgent) - Number(a.urgent) || b.score - a.score)
    .slice(0, 3),
)
const more = computed(() => geese.letters.filter((l) => !l.read_at).length - picks.value.length)
</script>

<template>
  <section v-if="picks.length" class="card rack-card" aria-labelledby="desk-rack">
    <h2 id="desk-rack" class="card-title">
      <Icon name="goose" :size="17" />鸿雁 · 信插
      <button class="link" @click="go('geese')">去信绳那儿</button>
    </h2>
    <div class="rack">
      <div class="slots">
        <button v-for="(l, i) in picks" :key="l.id" class="slip" :class="{ urgent: l.urgent }" :data-goose="l.id"
          :style="{ '--i': i }" :title="l.title" @click="openLetter(l, $event.currentTarget)">
          <span class="from">{{ l.route_name }}</span>
          <span class="title title-text">{{ shortTitle(l.title, 30) }}</span>
          <span v-if="leftLabel(l)" class="left" :class="{ soon: l.days_left <= 3 }">{{ leftLabel(l) }}</span>
          <ExpressStamp v-if="l.urgent" class="express" :size="50" :tilt="-12" />
        </button>
      </div>
      <span class="bar" aria-hidden="true" />
    </div>
    <p v-if="more > 0" class="faint small more">信绳上还有 {{ more }} 封没拆。</p>
  </section>
</template>

<style scoped>
.rack-card {
  position: relative;
  padding: 18px 22px 22px;
  background: color-mix(in srgb, var(--sheet) 90%, transparent);
  backdrop-filter: blur(3px);
  border: 1px solid var(--rule);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sheet);
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-family: var(--font-title);
  font-weight: 400;
  font-size: 17px;
  color: var(--ink);
}
.card-title :deep(svg) {
  color: var(--violet-ink);
}
.link {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--violet-ink);
  font-family: var(--font-body);
}
.link:hover {
  text-decoration: underline;
}
.rack {
  position: relative;
  padding: 0 6px;
}
.slots {
  display: grid;
  gap: 0;
}
/* Letters standing in a wall rack: each one peeks out above the wooden bar, a little askew. */
.slip {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas: 'from left' 'title title';
  gap: 2px 8px;
  margin-top: -6px;
  padding: 10px 14px 18px;
  border-radius: 3px 3px 0 0;
  background: linear-gradient(180deg, var(--sheet-raised), color-mix(in srgb, var(--sheet) 80%, var(--paper-deep)));
  box-shadow: 0 -1px 0 var(--rule), 0 -6px 12px -10px rgba(40, 20, 5, 0.35);
  text-align: left;
  transform: rotate(calc((var(--i) - 1) * 0.8deg));
  transition: transform 0.35s var(--ease);
}
.slip:first-child {
  margin-top: 0;
}
.slip:hover {
  transform: translateY(-4px) rotate(0deg);
  z-index: 1;
}
.express {
  position: absolute;
  right: 10px;
  bottom: 16px;
}
.slip.urgent .title {
  padding-right: 54px;
}
.from {
  grid-area: from;
  font-size: 11.5px;
  color: var(--violet-ink);
  letter-spacing: 0.05em;
}
.title {
  grid-area: title;
  font-size: 14.5px;
  color: var(--ink);
}
.left {
  grid-area: left;
  font-size: 12px;
  color: var(--ink-faint);
  font-family: var(--font-title);
}
.left.soon {
  color: var(--danger);
}
/* The pale oak bar of the rack, with a brass rail along its top — the same wood as the sorting wall. */
.bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -4px;
  height: 22px;
  border-radius: 3px;
  background:
    linear-gradient(180deg, var(--brass-hi), var(--brass)) top / 100% 3px no-repeat,
    repeating-linear-gradient(90deg, rgba(120, 80, 30, 0.04) 0 1px, transparent 1px 9px),
    linear-gradient(180deg, var(--oak-hi), var(--oak-mid));
  box-shadow: 0 8px 12px -8px var(--oak-shade), inset 0 -2px 0 color-mix(in srgb, var(--oak-edge) 30%, transparent);
  pointer-events: none;
}
.more {
  margin: 14px 0 0;
}
.small {
  font-size: 12.5px;
}
</style>
