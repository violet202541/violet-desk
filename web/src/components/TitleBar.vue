<script setup>
// 自绘标题区：按下即交给系统移动 / 缩放（保留贴边分屏），双击最大化。
import { computed } from 'vue'
import { store } from '../store.js'
import { startDrag as onDragDown, windowAction as act } from '../windowFrame.js'

const frame = computed(() => store.frame || {})
const EDGES = ['top', 'bottom', 'left', 'right', 'topleft', 'topright', 'bottomleft', 'bottomright']

function onEdgeDown(event, edge) {
  if (event.button === 0) act('begin', edge)
}
</script>

<template>
  <template v-if="frame.frameless">
    <div class="titlebar" @pointerdown="onDragDown">
      <div class="caption">
        <slot />
      </div>
      <div class="controls">
        <button class="ctl" title="最小化" @click="act('minimize')">
          <svg viewBox="0 0 12 12"><path d="M2 6.5h8" /></svg>
        </button>
        <button class="ctl" :title="frame.maximized ? '还原' : '最大化'" @click="act('toggle')">
          <svg v-if="frame.maximized" viewBox="0 0 12 12"><path d="M3.5 4.5h5v5h-5z M5 4.5V3h4.5v4.5H8.5" /></svg>
          <svg v-else viewBox="0 0 12 12"><path d="M2.5 2.5h7v7h-7z" /></svg>
        </button>
        <button class="ctl close" title="关闭" @click="act('close')">
          <svg viewBox="0 0 12 12"><path d="M2.5 2.5l7 7M9.5 2.5l-7 7" /></svg>
        </button>
      </div>
    </div>
    <template v-if="!frame.maximized">
      <div v-for="edge in EDGES" :key="edge" class="edge" :class="edge" @pointerdown="onEdgeDown($event, edge)" />
    </template>
  </template>
</template>

<style scoped>
.titlebar {
  position: relative;
  z-index: 30;
  display: flex;
  align-items: stretch;
  height: var(--titlebar);
  user-select: none;
}
.caption {
  flex: 1;
  display: flex;
  align-items: center;
  padding-left: 20px;
  min-width: 0;
  color: var(--ink-faint);
}
.controls {
  display: flex;
}
.ctl {
  width: 46px;
  display: grid;
  place-items: center;
  color: var(--ink-soft);
  transition: background 0.15s ease, color 0.15s ease;
}
.ctl svg {
  width: 12px;
  height: 12px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.1;
}
.ctl:hover {
  background: var(--violet-wash-strong);
  color: var(--ink);
}
.ctl.close:hover {
  background: #a33a32;
  color: #fff;
}
.edge {
  position: fixed;
  z-index: 200;
}
.top,
.bottom {
  left: 10px;
  right: 10px;
  height: 5px;
  cursor: ns-resize;
}
.top {
  top: 0;
}
.bottom {
  bottom: 0;
}
.left,
.right {
  top: 10px;
  bottom: 10px;
  width: 5px;
  cursor: ew-resize;
}
.left {
  left: 0;
}
.right {
  right: 0;
}
.topleft,
.topright,
.bottomleft,
.bottomright {
  width: 10px;
  height: 10px;
}
.topleft {
  top: 0;
  left: 0;
  cursor: nwse-resize;
}
.bottomright {
  bottom: 0;
  right: 0;
  cursor: nwse-resize;
}
.topright {
  top: 0;
  right: 0;
  cursor: nesw-resize;
}
.bottomleft {
  bottom: 0;
  left: 0;
  cursor: nesw-resize;
}
</style>
