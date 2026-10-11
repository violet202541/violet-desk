// 书桌上方那句问候：一句中文、一句意思对应的英文，都很短。
// 三种口吻混着来——随时辰、节气、天气变的短句，古诗词半句，以及 Violet 的书信口吻。
// 同一天、同一个时辰里不变；节气当天先说节气。

const SLOTS = [
  [5, 'night'], [8, 'dawn'], [11, 'morning'], [14, 'noon'], [17, 'afternoon'], [19, 'dusk'], [23, 'evening'], [24, 'night'],
]

const TIME = {
  night: [
    ['夜深了，灯还亮着', 'The lamp is still lit'],
    ['墨水都睡了，你呢', 'Even the ink has gone to sleep'],
    ['星星在替夜色值班', 'The stars keep the night watch'],
    ['夜很静，适合写信', 'A quiet hour for letters'],
  ],
  dawn: [
    ['晨光落在窗台上', 'First light on the sill'],
    ['邮车已经出发了', 'The mail coach is on its way'],
    ['趁世界还没醒', 'Before the world wakes'],
  ],
  morning: [
    ['早安，今天的信到了', 'Good morning, your letter is here'],
    ['信和阳光一起到了', 'Your letter came with the sun'],
    ['新的一页，慢慢写', 'A fresh page, written slowly'],
  ],
  noon: [
    ['午安，歇一会儿也好', 'Good noon, rest a little'],
    ['日影正短，喝杯茶吧', 'Short shadows, a cup of tea'],
    ['一天过半，你做得很好', 'Halfway there, and doing well'],
  ],
  afternoon: [
    ['下午好，慢慢来', 'Good afternoon, take your time'],
    ['午后的光像蜂蜜', 'The light turns honey-gold'],
    ['日长，人也不必赶', 'Long days need no hurry'],
  ],
  dusk: [
    ['天边在用玫瑰色写字', 'The sky is writing in rose'],
    ['黄昏，邮差也回家了', 'Dusk, and the postman goes home'],
    ['街灯一盏盏亮了', 'Lamps lit along the street'],
  ],
  evening: [
    ['晚上好，写封回信吧', 'Good evening, write me back'],
    ['一天像信一样折好', 'The day folds like a letter'],
    ['说说今天吧', 'Tell me about today'],
  ],
}

const SEASON = {
  spring: { day: [['春风在敲窗', 'Spring wind at the window'], ['信封里落了花瓣', 'Petals in the envelope']],
    night: [['春夜，雨很轻', 'A spring night, soft rain']] },
  summer: { day: [['蝉声替你计时', 'The cicadas keep the time'], ['长夏，记得喝水', 'Long summer, stay cool']],
    night: [['窗外有萤火', 'Fireflies at the window']] },
  autumn: { day: [['枫叶可以当邮票', 'A maple leaf for a stamp'], ['秋高，天很远', 'High autumn, a far blue sky']],
    night: [['秋月下，给谁写信', 'Under the autumn moon, a letter']] },
  winter: { day: [['先暖暖手再写字', 'Warm your hands, then write'], ['雪光照着书桌', 'Snow light on the desk']],
    night: [['冬夜，灯下一杯茶', 'Winter night, tea by the lamp']] },
}

const TERMS = {
  立春: ['立春。冰在悄悄化', 'Spring begins, the ice lets go'],
  雨水: ['雨水。润物细无声', 'The rains return, softly'],
  惊蛰: ['惊蛰。春雷叫醒万物', 'Thunder wakes the earth'],
  春分: ['春分。昼夜平分', 'Day and night in balance'],
  清明: ['清明。风很干净', 'Clear and bright, a clean wind'],
  谷雨: ['谷雨。牡丹开了', 'Grain rain, the peonies open'],
  立夏: ['立夏。绿意正浓', 'Summer arrives in deep green'],
  小满: ['小满。未满，刚好', 'Not yet full, and that is fine'],
  芒种: ['芒种。忙着播种', 'A season for sowing'],
  夏至: ['夏至。白昼最长', 'The longest day of the year'],
  小暑: ['小暑。温风至', 'Warm winds rise'],
  大暑: ['大暑。慢一点，凉一点', 'High summer, slow and cool'],
  立秋: ['立秋。暑气渐收', 'Autumn begins, the heat ebbs'],
  处暑: ['处暑。热要走了', 'The heat is leaving'],
  白露: ['白露。草尖挂着露', 'White dew on the grass'],
  秋分: ['秋分。昼夜又平了', 'Autumn equinox, in balance again'],
  寒露: ['寒露。添件衣裳', 'Cold dew, bring a coat'],
  霜降: ['霜降。叶子红了', 'First frost, the leaves turn red'],
  立冬: ['立冬。万物收藏', 'Winter begins, all things rest'],
  小雪: ['小雪。等一场初雪', 'Waiting for the first snow'],
  大雪: ['大雪。围炉写信', 'Heavy snow, letters by the fire'],
  冬至: ['冬至。夜最长，灯最暖', 'The longest night, the warmest lamp'],
  小寒: ['小寒。梅花要开了', 'The plum is about to bloom'],
  大寒: ['大寒。春天不远了', 'Deep cold, spring is near'],
}

// The weather stamp on today's reply.
const WEATHER = {
  clear: [['晴天，适合寄信', 'A clear day for the post']],
  cloudy: [['云慢慢走', 'The clouds take their time']],
  overcast: [['阴天，适合想念', 'A grey day for missing someone']],
  rain: [['听雨，也是一种休息', 'Listening to the rain is rest'], ['雨天，信纸有点潮', 'Rain, and the paper feels damp']],
  snow: [['落雪了，信走得慢些', 'Snow falls, the post goes slow']],
  wind: [['风会把信送到', 'The wind will carry it']],
  fog: [['雾里，一切都很温柔', 'Everything is gentle in the fog']],
  storm: [['雷声远远的，别怕', 'Thunder far away, no need to fear']],
}

// Half-lines of classical poetry; `season` and `when` say when they fit.
const CLASSIC = [
  { cn: '春风又绿江南岸', en: 'Spring wind greens the south again', season: 'spring' },
  { cn: '春眠不觉晓', en: 'Spring sleep knows no dawn', season: 'spring', when: ['dawn', 'morning'] },
  { cn: '好雨知时节', en: 'Good rain knows its season', season: 'spring' },
  { cn: '接天莲叶无穷碧', en: 'Lotus leaves meet the sky', season: 'summer' },
  { cn: '小荷才露尖尖角', en: 'A young lotus shows its tip', season: 'summer', when: ['dawn', 'morning'] },
  { cn: '稻花香里说丰年', en: 'Rice in bloom, talk of harvest', season: 'summer', when: ['evening', 'night'] },
  { cn: '晴空一鹤排云上', en: 'A crane climbs the clear sky', season: 'autumn' },
  { cn: '停车坐爱枫林晚', en: 'I stop for the maples at dusk', season: 'autumn', when: ['afternoon', 'dusk'] },
  { cn: '天阶夜色凉如水', en: 'The night is cool as water', season: 'autumn', when: ['evening', 'night'] },
  { cn: '月是故乡明', en: 'The moon is brightest at home', season: 'autumn', when: ['evening', 'night'] },
  { cn: '晚来天欲雪', en: 'Snow is coming this evening', season: 'winter', when: ['dusk', 'evening'] },
  { cn: '能饮一杯无', en: 'Will you share a cup with me?', season: 'winter', when: ['dusk', 'evening', 'night'] },
  { cn: '墙角数枝梅', en: 'Plum blossoms by the wall', season: 'winter' },
  { cn: '云中谁寄锦书来', en: 'Who sends a letter from the clouds?' },
  { cn: '海内存知己', en: 'A friend anywhere in the world' },
  { cn: '但愿人长久', en: 'May those we love live long', when: ['evening', 'night'] },
  { cn: '见字如面', en: 'As if we met in these words' },
]

const VIOLET = [
  ['今天也为你代笔', 'Writing for you again today'],
  ['信纸已经铺好了', 'The paper is ready'],
  ['每一封信都会抵达', 'Every letter arrives'],
  ['说不出的话，我替你写', 'I will write what you cannot say'],
  ['你的话，值得被写下', 'Your words deserve to be written'],
]

const SEASON_OF = {
  spring: ['立春', '雨水', '惊蛰', '春分', '清明', '谷雨'],
  summer: ['立夏', '小满', '芒种', '夏至', '小暑', '大暑'],
  autumn: ['立秋', '处暑', '白露', '秋分', '寒露', '霜降'],
  winter: ['立冬', '小雪', '大雪', '冬至', '小寒', '大寒'],
}

function seasonOf(term, month) {
  for (const [name, terms] of Object.entries(SEASON_OF)) if (terms.includes(term)) return name
  return ['winter', 'winter', 'spring', 'spring', 'spring', 'summer', 'summer', 'summer', 'autumn', 'autumn', 'autumn', 'winter'][month - 1]
}

function hash(text) {
  let h = 2166136261
  for (const ch of text) h = Math.imul(h ^ ch.codePointAt(0), 16777619)
  return h >>> 0
}

/** [english, chinese] for the desk: `term` is today's solar term (if today is one), `period` the term we are in. */
export function greetingFor({ date, hour = new Date().getHours(), term = '', period = '', weather = '' }) {
  const slot = SLOTS.find(([until]) => hour < until)[1]
  const dark = slot === 'night' || slot === 'evening'
  // On the day of a solar term, the morning and afternoon belong to it.
  if (term && TERMS[term] && !dark) return [TERMS[term][1], TERMS[term][0]]
  const season = seasonOf(period, Number((date || '').slice(5, 7)) || new Date().getMonth() + 1)
  const pool = [
    ...TIME[slot],
    ...TIME[slot],
    ...SEASON[season][dark ? 'night' : 'day'],
    ...(WEATHER[weather] || []).flatMap((w) => [w, w]),
    ...CLASSIC.filter((c) => (!c.season || c.season === season) && (!c.when || c.when.includes(slot))).map((c) => [c.cn, c.en]),
    ...VIOLET,
  ]
  const [cn, en] = pool[hash(`${date}|${slot}`) % pool.length]
  return [en, cn]
}
