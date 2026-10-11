// 文具匣：信纸、格线、抬头、字与墨、火漆、邮票、信封。设置里挑默认的一套，写信时可以临时换；
// 每封信封缄时把用过的那套连同落款一起记下来，以后再打开还是那个样子。
import { computed } from 'vue'
import { store } from './store.js'
import { LETTER_FONTS, fontStack } from './fonts.js'

import parchment from './assets/stationery/paper/parchment.webp'
import lilacLaid from './assets/stationery/paper/lilac-laid.webp'
import kraft from './assets/stationery/paper/kraft.webp'
import pressedPetals from './assets/stationery/paper/pressed-petals.webp'
import violetsHead from './assets/stationery/letterhead/violets.webp'
import lilyHead from './assets/stationery/letterhead/lily-of-valley.webp'
import goldHead from './assets/stationery/letterhead/gold-flourish.webp'
import waxViolet from './assets/stationery/wax/violet.webp'
import waxWine from './assets/stationery/wax/wine.webp'
import waxEmerald from './assets/stationery/wax/emerald.webp'
import waxGold from './assets/stationery/wax/gold.webp'
import waxInk from './assets/stationery/wax/ink-blue.webp'
import waxCharcoal from './assets/stationery/wax/charcoal.webp'
import waxPearl from './assets/stationery/wax/pearl.webp'
import waxSakura from './assets/stationery/wax/sakura.webp'
import stampHarbor from './assets/stationery/stamps/harbor.webp'
import stampClock from './assets/stationery/stamps/clocktower.webp'
import stampPost from './assets/stationery/stamps/postoffice.webp'
import stampTram from './assets/stationery/stamps/tram.webp'
import stampField from './assets/stationery/stamps/flowerfield.webp'
import stampLight from './assets/stationery/stamps/lighthouse.webp'
import stampSnow from './assets/stationery/stamps/snowpeak.webp'
import stampSunset from './assets/stationery/stamps/sunset-sea.webp'
import { photoUrl } from './api.js'

export const PAPERS = {
  parchment: { label: '羊皮纸', url: parchment, ink: 'violet', rule: 'rgba(110, 79, 163, 0.16)', margin: 'rgba(164, 69, 58, 0.25)' },
  'lilac-laid': { label: '淡紫条纹纸', url: lilacLaid, ink: 'violet', rule: 'rgba(90, 62, 140, 0.18)', margin: 'rgba(120, 80, 170, 0.3)' },
  'pressed-petals': { label: '压花手工纸', url: pressedPetals, ink: 'blueblack', rule: 'rgba(90, 80, 120, 0.14)', margin: 'rgba(130, 100, 160, 0.25)' },
  kraft: { label: '牛皮纸', url: kraft, ink: 'sepia', rule: 'rgba(80, 50, 25, 0.2)', margin: 'rgba(120, 45, 30, 0.3)' },
  plain: { label: '素笺', url: '', ink: 'violet', rule: 'rgba(110, 79, 163, 0.13)', margin: 'rgba(164, 69, 58, 0.3)' },
}

export const RULINGS = {
  lines: { label: '横线' },
  grid: { label: '方格' },
  manuscript: { label: '稿纸格' },
  blank: { label: '空白' },
}

export const LETTERHEADS = {
  violets: { label: '紫罗兰', url: violetsHead },
  lily: { label: '铃兰', url: lilyHead },
  gold: { label: '金线花饰', url: goldHead },
  post: { label: '邮政公司抬头', url: '' },
  none: { label: '不要抬头', url: '' },
}

export const INKS = {
  violet: { label: '紫罗兰', color: '#4a3474' },
  blueblack: { label: '蓝黑', color: '#22304d' },
  sepia: { label: '深褐', color: '#5a3b26' },
  green: { label: '墨绿', color: '#2c4a3b' },
  black: { label: '炭黑', color: '#262326' },
}

// Wax: the blank seal images and how a pressed motif reads on each (relief shadow and light).
export const WAX = {
  violet: { label: '紫罗兰紫', url: waxViolet, deep: 'rgba(20, 8, 40, 0.55)', light: 'rgba(225, 205, 255, 0.4)' },
  wine: { label: '酒红', url: waxWine, deep: 'rgba(40, 0, 6, 0.55)', light: 'rgba(255, 200, 200, 0.38)' },
  emerald: { label: '祖母绿', url: waxEmerald, deep: 'rgba(0, 25, 15, 0.55)', light: 'rgba(200, 255, 225, 0.35)' },
  gold: { label: '古金', url: waxGold, deep: 'rgba(70, 40, 0, 0.5)', light: 'rgba(255, 245, 200, 0.55)' },
  ink: { label: '墨蓝', url: waxInk, deep: 'rgba(0, 5, 30, 0.6)', light: 'rgba(200, 215, 255, 0.35)' },
  charcoal: { label: '炭黑', url: waxCharcoal, deep: 'rgba(0, 0, 0, 0.7)', light: 'rgba(255, 255, 255, 0.28)' },
  pearl: { label: '珍珠白', url: waxPearl, deep: 'rgba(90, 75, 70, 0.4)', light: 'rgba(255, 255, 255, 0.85)' },
  sakura: { label: '樱粉', url: waxSakura, deep: 'rgba(110, 40, 60, 0.4)', light: 'rgba(255, 240, 245, 0.7)' },
}

// Seal motifs on a 48×48 face: line drawings that are pressed into the wax (see SealImpression).
export const MOTIFS = {
  monogram: { label: 'V 字', family: '字母', text: 'V' },
  initials: { label: '我的字母', family: '字母', text: '' },
  violet: {
    label: '紫罗兰', family: '花与植物',
    d: ['M24 23c-3-1.5-6.5-5-6-9s4.5-4.5 6 0c1.5-4.5 6.5-4.5 6 0s-3 7.5-6 9z',
      'M23 25c-3-2-8-2-10.5 1s1 6 5 4.5 5.5-3.5 5.5-5.5z', 'M25 25c3-2 8-2 10.5 1s-1 6-5 4.5-5.5-3.5-5.5-5.5z',
      'M24 26c-3.5 1-6 5-4.5 8.5s7.5 3.5 9 0-1-7.5-4.5-8.5z', 'M24 23.5v4M22.4 31.5l1.6-3 1.6 3'],
  },
  lily: {
    label: '铃兰', family: '花与植物',
    d: ['M14 39c2-11 8-20 16-23 3-1 6-1 8 0', 'M13 40c-4-9-2-19 6-24 0 9-2 17-6 24z',
      'M16.6 30c0-4.5 1.6-6 3.4-6s3.4 1.5 3.4 6l.6.6h-8z', 'M20 24c0-1.2.4-2 1-2.6',
      'M23.6 25c0-4.5 1.6-6 3.4-6s3.4 1.5 3.4 6l.6.6h-8z', 'M27 19v-1.6',
      'M31.2 23.6c0-3.8 1.3-5 2.8-5s2.8 1.2 2.8 5l.5.5h-6.6z', 'M34 18.6v-2.4'],
  },
  wheat: {
    label: '麦穗', family: '花与植物',
    d: ['M24 41V9', 'M24 13c-3-1-4.5-3.5-4-6 3 .5 4.5 3 4 6zM24 13c3-1 4.5-3.5 4-6-3 .5-4.5 3-4 6z',
      'M24 19c-3.5-.8-5.5-3.5-5-6.5 3.5.6 5.5 3.3 5 6.5zM24 19c3.5-.8 5.5-3.5 5-6.5-3.5.6-5.5 3.3-5 6.5z',
      'M24 25.5c-3.8-.8-6-3.6-5.5-6.8 3.8.6 6 3.5 5.5 6.8zM24 25.5c3.8-.8 6-3.6 5.5-6.8-3.8.6-6 3.5-5.5 6.8z',
      'M24 32c-4-.8-6.3-3.7-5.8-7 4 .6 6.3 3.6 5.8 7zM24 32c4-.8 6.3-3.7 5.8-7-4 .6-6.3 3.6-5.8 7z'],
  },
  olive: {
    label: '橄榄枝', family: '花与植物',
    d: ['M11 38c6-6 13-13 26-25', 'M17 32c-3-1-5-4-4-7 3 .8 5 3.8 4 7zM17 32c1-3 4-5 7-4-.8 3-3.8 5-7 4z',
      'M24.5 24.5c-3-1-5-4-4-7 3 .8 5 3.8 4 7zM24.5 24.5c1-3 4-5 7-4-.8 3-3.8 5-7 4z',
      'M31.5 18c-2.5-1-4-3.5-3.2-6 2.5.7 4 3.2 3.2 6zM31.5 18c1-2.5 3.5-4 6-3.2-.7 2.5-3.2 4-6 3.2z',
      'M19.5 36.5a2.2 2.6 -30 1 0 .1 0zM27.5 29a2.2 2.6 -30 1 0 .1 0z'],
  },
  quill: {
    label: '羽毛笔', family: '代笔的器物',
    d: ['M36 8C26 10 17 20 14 34c6-2 11-6 15-11-3 .2-5 0-6-.8 3-1 6-2.8 8-5.2-2 .2-3.6 0-4.4-.6C31 13 34 10.5 36 8z',
      'M14 34l-3 6', 'M15.5 31.5C21 23 28 15 36 8'],
  },
  key: {
    label: '钥匙', family: '代笔的器物',
    d: ['M17 11.5a6 6 0 1 0 .1 0z', 'M17 15a2.4 2.4 0 1 0 .1 0z', 'M21.3 21.3L37 37', 'M31 31l3.2-3.2M34 34l2.4-2.4M28.5 28.5l2-2'],
  },
  bell: {
    label: '铃铛', family: '代笔的器物',
    d: ['M15 32c1-3 1.5-6 1.5-9.5 0-5 3.4-8.5 7.5-8.5s7.5 3.5 7.5 8.5c0 3.5.5 6.5 1.5 9.5l2 2.5H13z',
      'M24 9.5a2.4 2.4 0 1 0 .1 0z', 'M21.5 35c0 1.6 1.1 2.8 2.5 2.8s2.5-1.2 2.5-2.8', 'M19 20c.8-1.6 2.2-2.6 3.8-2.8'],
  },
  brooch: {
    label: '胸针', family: '代笔的器物',
    d: ['M24 10c6.6 0 11 6.3 11 14s-4.4 14-11 14-11-6.3-11-14 4.4-14 11-14z',
      'M24 15.5c3.9 0 6.3 3.8 6.3 8.5s-2.4 8.5-6.3 8.5-6.3-3.8-6.3-8.5 2.4-8.5 6.3-8.5z',
      'M24 15.5l4.4 5v7L24 32.5l-4.4-5v-7z', 'M24 6.5v2M24 39.5v2M9.5 24h2M36.5 24h2'],
  },
  opener: {
    label: '拆信刀', family: '代笔的器物',
    d: ['M24 6l3.6 22h-7.2z', 'M16 28h16', 'M22.4 28.2v9h3.2v-9', 'M24 37.2a2.2 2.2 0 1 0 .1 4.4 2.2 2.2 0 0 0-.1-4.4z', 'M24 10v15'],
  },
  goose: {
    label: '鸿雁', family: '天空与飞鸟',
    d: ['M9 29c6 .5 12-.5 17-3 3.5-1.7 7-4 10.5-4.5l3 .5-2.7 1.6c-3 .4-5.5 2.4-8 4.6-4 3.4-10 4.6-19.8.8z',
      'M21 27.5c-1-6 2-12.5 8-17-1 5 0 9.5 2.6 13', 'M18.5 28c-2.5-4-2.8-8.5-.8-12.5 1.7 3.8 3.8 6.7 6.8 9',
      'M9 29l-3 1.8M9 29l-3-1'],
  },
  moon: {
    label: '月与星', family: '天空与飞鸟',
    d: ['M27 10a14 14 0 1 0 9.5 23.5A11.5 11.5 0 0 1 27 10z',
      'M33 12.5l1 2.6 2.6 1-2.6 1-1 2.6-1-2.6-2.6-1 2.6-1zM38 23l.6 1.5 1.5.6-1.5.6-.6 1.5-.6-1.5-1.5-.6 1.5-.6z'],
  },
  sun: {
    label: '太阳', family: '天空与飞鸟',
    d: ['M24 16.5a7.5 7.5 0 1 0 .1 0z',
      'M24 8v4M24 36v4M8 24h4M36 24h4M12.7 12.7l2.8 2.8M32.5 32.5l2.8 2.8M12.7 35.3l2.8-2.8M32.5 15.5l2.8-2.8'],
  },
  cloud: {
    label: '云', family: '天空与飞鸟',
    d: ['M14.5 31.5a5.5 5.5 0 0 1 .9-10.9 8 8 0 0 1 15.3-2 6 6 0 0 1 2.8 11.5 3.6 3.6 0 0 1-2.5 1.4z',
      'M17 37.5h14M20.5 41h7'],
  },
}

export const STAMPS = {
  harbor: { label: '港口', url: stampHarbor, value: '30' },
  clocktower: { label: '钟楼广场', url: stampClock, value: '25' },
  postoffice: { label: '邮政公司', url: stampPost, value: '50' },
  tram: { label: '绿色电车', url: stampTram, value: '20' },
  flowerfield: { label: '花田', url: stampField, value: '15' },
  lighthouse: { label: '灯塔', url: stampLight, value: '40' },
  snowpeak: { label: '雪山', url: stampSnow, value: '60' },
  'sunset-sea': { label: '夕阳海', url: stampSunset, value: '35' },
}
export const STAMP_TONES = { color: '原色', sepia: '旧照片', engraved: '雕刻版' }

export const ENVELOPES = {
  western: { label: '西式信封' },
  airmail: { label: '航空信封' },
  chinese: { label: '中式竖封' },
  pouch: { label: '驿站公文袋' },
}

export const DEFAULT = {
  paper: 'parchment', ruling: 'lines', letterhead: 'violets', font: 'wenkai', ink: 'violet', seal_color: 'violet',
  seal_motif: 'monogram', seal_initials: '', stamp: 'harbor', stamp_tone: 'color', envelope: 'western', signoff: '',
}

/** The full set for a letter: its own choices over the defaults chosen in settings. */
export function resolve(own) {
  return { ...DEFAULT, ...(store.settings?.stationery || {}), ...(own || {}) }
}
export const defaults = computed(() => resolve(null))

export function stampImage(id) {
  if (id?.startsWith('photo:')) return photoUrl(id.slice(6))
  return (STAMPS[id] || STAMPS.harbor).url
}
export const stampValue = (id) => STAMPS[id]?.value || '30'

/** CSS variables for a sheet of paper in this stationery. */
export function paperVars(s) {
  const paper = PAPERS[s.paper] || PAPERS.parchment
  const font = LETTER_FONTS[s.font] || LETTER_FONTS.wenkai
  return {
    '--paper-img': paper.url ? `url(${paper.url})` : 'none',
    '--letter-ink': (INKS[s.ink] || INKS.violet).color,
    '--letter-rule': paper.rule,
    '--letter-margin': paper.margin,
    '--letter-font': fontStack(s.font),
    '--letter-scale': font.scale,
  }
}

export { LETTER_FONTS }
