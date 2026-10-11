// 泰尔西斯密写：每个汉字固定写成两三个泰尔西斯字母，两个字连成一个「词」。
// 只是遮给旁人看的装饰，不是加密：同一个字永远是同一个词，所以重复的字会形成看得出的「词」。
import { GLYPHS } from './assets/nunkish.js'

// Weighted the way the letters in the anime fall: small round bowls everywhere (u, c, q are circles in Telsis),
// broken up by tall loops and boxes (p, h, b, d) and the odd descender (y, g).
const CONSONANTS = 'hpyvnlkdbtiqh'
const VOWELS = 'uuucaaxeo'

function hash(code) {
  let h = Math.imul(code ^ 0x9e3779b9, 0x85ebca6b)
  h ^= h >>> 13
  h = Math.imul(h, 0xc2b2ae35)
  return (h ^ (h >>> 16)) >>> 0
}

const cache = new Map()
// The fixed letters for one Han character. A two-character word reads like three or four letters:
// the first character opens it with a syllable, the second closes it, usually with one letter.
export function wordFor(char, role = 'solo') {
  const key = char + role
  let word = cache.get(key)
  if (word) return word
  const h = hash(char.codePointAt(0))
  const c1 = CONSONANTS[h % CONSONANTS.length]
  const v = VOWELS[(h >>> 5) % VOWELS.length]
  const c2 = CONSONANTS[(h >>> 9) % CONSONANTS.length]
  const v2 = VOWELS[(h >>> 19) % VOWELS.length]
  const roll = (h >>> 14) % 20
  // Two characters make a word of three to six small letters.
  if (role === 'end') word = roll < 9 ? v + c2 : roll < 15 ? c2 + v2 : v + c2 + v2
  else if (role === 'start') word = roll < 8 ? c1 + v : roll < 14 ? c1 + v + c2 : v + c1
  else word = roll < 10 ? c1 + v + c2 : roll < 16 ? c1 + v + c2 + v2 : v + c2 + v2
  cache.set(key, word)
  return word
}

const HAN = /[㐀-鿿豈-﫿\u{20000}-\u{2fa1f}]/u
const MARKS = {
  '，': ',', '、': ',', '；': ',', ';': ',', ',': ',',
  '。': '.', '.': '.', '…': '.',
  '！': '!', '!': '!', '？': '!', '?': '!',
  '：': ':', ':': ':',
  '—': '-', '－': '-', '-': '-', '–': '-', '~': '-', '～': '-',
}
const QUOTES = '「」『』“”‘’"\'《》〈〉（）()[]【】'

// What to draw in one character's box: letters (a word piece), a mark, or nothing.
export function pieceFor(char, role = 'solo') {
  if (HAN.test(char)) return { letters: wordFor(char, role), han: true }
  const lower = char.toLowerCase()
  if (GLYPHS[lower] && /[a-z0-9]/.test(lower)) return { letters: lower }
  if (MARKS[char]) return { mark: MARKS[char] }
  if (QUOTES.includes(char)) return { mark: 'tick' }
  if (/\s/.test(char)) return null
  return { mark: '.' }
}

// ---------------------------------------------------------------- strokes

const paths = new Map()
let ruler = null
// Each pen stroke as a Path2D with its length, measured once.
function strokesOf(key) {
  let found = paths.get(key)
  if (found) return found
  const glyph = key === ':' ? { w: 20, d: [], dots: [[10, 50], [10, 76]] }
    : key === 'tick' ? { w: 16, d: ['M10 30 L6 46'] }
      : GLYPHS[key]
  if (!ruler) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.style.cssText = 'position:absolute;width:0;height:0;visibility:hidden'
    ruler = document.createElementNS('http://www.w3.org/2000/svg', 'path')
    svg.appendChild(ruler)
    document.body.appendChild(svg)
  }
  const strokes = glyph.d.map((d) => {
    ruler.setAttribute('d', d)
    return { path: new Path2D(d), length: ruler.getTotalLength() || 1 }
  })
  for (const [cx, cy] of glyph.dots || []) strokes.push({ dot: [cx, cy], length: 6 })
  found = { w: glyph.w, strokes }
  paths.set(key, found)
  return found
}

// ---------------------------------------------------------------- a line of handwriting

const SLANT = 0.07 // a near-upright hand, as in the letters on screen
const TIGHT = 7 // letters stand close, not joined (units)

function kindOf(char) {
  if (HAN.test(char)) return 'han'
  if (/[a-z0-9]/i.test(char) && GLYPHS[char.toLowerCase()]) return 'latin'
  if (/\s/.test(char)) return 'space'
  return 'mark'
}

// Turn one visual line of the original into words of pen letters.
// chars: [{ char, index }] in reading order. Two Han characters make one word; a Latin run is its own word;
// punctuation hangs on the word before it; spaces only break words.
function wordsOf(chars) {
  const words = []
  let word = null
  let run = 0
  const close = () => {
    if (word && (word.keys.length || word.marks.length)) words.push(word)
    word = null
  }
  const ensure = () => {
    if (!word) word = { keys: [], indexes: [], marks: [] }
    return word
  }
  chars.forEach((c, i) => {
    const kind = kindOf(c.char)
    if (kind === 'space') {
      close()
      run = 0
      return
    }
    if (kind === 'mark') {
      const p = pieceFor(c.char)
      if (!p) return
      // Punctuation hangs on the word just written.
      const last = word || words[words.length - 1]
      if (last) last.marks.push({ key: p.mark, after: last.keys.length, index: c.index })
      else ensure().marks.push({ key: p.mark, after: 0, index: c.index })
      close()
      run = 0
      return
    }
    if (kind === 'latin') {
      if (run) close()
      run = 0
      ensure().keys.push(c.char.toLowerCase())
      word.indexes.push(c.index)
      if (kindOf(chars[i + 1]?.char || ' ') !== 'latin') close()
      return
    }
    // A Han character: the first of a pair opens a word, the second closes it.
    const next = chars[i + 1]
    const opens = run % 2 === 0
    const role = opens ? (next && kindOf(next.char) === 'han' ? 'start' : 'solo') : 'end'
    if (opens) close()
    const w = ensure()
    for (const k of wordFor(c.char, role)) {
      w.keys.push(k)
      w.indexes.push(c.index)
    }
    run++
    if (role !== 'start') close()
  })
  close()
  return words
}

// Lay out every line: letters at their own widths, words evenly spaced, wrapped lines filled to the measure.
// lines: [{ chars, top, height, width, last, n }] in px. ruled: px from the line's bottom to sit the letters on.
export function plan(lines, { fontSize, ruled = 0 }) {
  const unit = fontSize * 0.0112 // small letters with plenty of air between the lines
  const space = fontSize * 0.62
  const laid = []
  for (const line of lines) {
    const words = wordsOf(line.chars)
    if (!words.length) continue
    for (const w of words) {
      let ox = 0
      w.parts = []
      const marksAfter = (n) => {
        for (const m of w.marks.filter((m) => m.after === n)) {
          const mg = strokesOf(m.key)
          ox += 3
          w.parts.push({ g: mg, ox, mark: true, index: m.index })
          ox += mg.w
        }
      }
      marksAfter(0)
      w.keys.forEach((k, i) => {
        const g = strokesOf(k)
        w.parts.push({ g, ox, index: w.indexes[i] })
        ox += g.w - TIGHT
        marksAfter(i + 1)
      })
      w.units = Math.max(ox + TIGHT, 12)
    }
    laid.push({ line, words, natural: words.reduce((sum, w) => sum + w.units * unit, 0) })
  }
  // One hand writes the whole page at one size: if any line is too long for the measure,
  // every letter narrows by the same amount rather than just that line's.
  const squeeze = laid.reduce((k, { line, words, natural }) => {
    const room = line.width - 2 - (words.length - 1) * space * 0.6
    return natural > room ? Math.min(k, Math.max(0.62, room / natural)) : k
  }, 1)
  const out = []
  for (const { line, words } of laid) {
    const gaps = words.length - 1
    const room = line.width - 2
    const natural = words.reduce((sum, w) => sum + w.units * unit * squeeze, 0)
    // Ragged on the right like any letter: word spaces stay as they are unless the line would overrun.
    const gap = natural + gaps * space > room && gaps ? Math.max(space * 0.6, (room - natural) / gaps) : space
    // Sit on the ruling when the paper is ruled; otherwise a little below the middle of the line.
    const base = ruled ? line.top + line.height - ruled : line.top + line.height * 0.68
    // No hand keeps a line dead level: each one drifts a little up or down as it goes.
    const drift = ((hash(line.n * 31 + 7) % 9) - 4) * fontSize * 0.022
    let x = 0
    for (const w of words) {
      const sx = unit * squeeze
      const first = w.indexes[0] ?? w.marks[0]?.index ?? 0
      const wobble = ((hash(first + 11) % 5) - 2) * fontSize * 0.008
      out.push({
        parts: w.parts,
        x0: x,
        sx,
        sy: unit,
        top: base - 80 * unit + wobble + drift * (x / Math.max(1, room)),
        indexes: [...w.indexes, ...w.marks.map((m) => m.index)],
        ink: 0.86 + (hash(first * 7 + 3) % 14) / 100,
        line: line.n,
      })
      x += w.units * sx + gap
    }
  }
  return out
}

// Draw the planned words with an even, fine pen line. born(word) says when its pen starts (ms);
// letters still being written show partly. Returns true while anything is unfinished.
export function draw(ctx, words, { color, dpr = 1, at = Infinity, speed = 70, born = () => 0, weight = 1 }) {
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  let busy = false
  for (const w of words) {
    const elapsed = at === Infinity ? Infinity : at - born(w)
    if (elapsed <= 0) {
      busy = true
      continue
    }
    ctx.globalAlpha = w.ink
    const line = (1.2 * weight) / w.sy // the pen, in glyph units
    w.parts.forEach((part, i) => {
      // Each letter takes `speed` ms; the word is written left to right.
      let p = elapsed === Infinity ? 1 : (elapsed - i * speed) / speed
      if (p <= 0) {
        busy = true
        return
      }
      if (p < 1) busy = true
      p = Math.min(1, p)
      ctx.setTransform(w.sx * dpr, 0, -SLANT * w.sy * dpr, w.sy * dpr, (w.x0 + part.ox * w.sx + SLANT * w.sy * 80) * dpr, w.top * dpr)
      ctx.lineWidth = line
      const total = part.g.strokes.reduce((s, k) => s + k.length, 0)
      let budget = p * total
      for (const k of part.g.strokes) {
        if (budget <= 0) break
        const share = Math.min(1, budget / k.length)
        budget -= k.length
        if (k.dot) {
          if (share >= 1) {
            ctx.beginPath()
            ctx.arc(k.dot[0], k.dot[1], line * 0.85, 0, Math.PI * 2)
            ctx.fill()
          }
          continue
        }
        if (share < 1) ctx.setLineDash([k.length * share, k.length * 2])
        ctx.stroke(k.path)
        if (share < 1) ctx.setLineDash([])
      }
    })
  }
  ctx.globalAlpha = 1
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  return busy
}

export function escapeHtml(char) {
  return char === '<' ? '&lt;' : char === '>' ? '&gt;' : char === '&' ? '&amp;' : char
}
