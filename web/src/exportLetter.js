// 把一封回信存成一张 PNG：用这封信自己的信纸、抬头、格线、字和墨重新画一遍，
// 右上角贴邮票盖邮戳，右下角落款，火漆压在信尾。桌面窗口里弹另存为，浏览器里直接下载。
import { api, photoUrl } from './api.js'
import { store, toast } from './store.js'
import { resolve, PAPERS, LETTERHEADS, INKS, WAX, MOTIFS, stampImage, stampValue } from './stationery.js'
import { LETTER_FONTS, fontStack } from './fonts.js'
import { longDate, timeOfDay, isoDate } from './format.js'

const W = 1240
const PAD = 110

function load(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null)
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

// Wrap text to a width, keeping the writer's own line breaks.
function wrap(ctx, text, width) {
  const lines = []
  for (const para of String(text).split('\n')) {
    if (!para) {
      lines.push('')
      continue
    }
    let line = ''
    for (const ch of para) {
      const next = line + ch
      if (ctx.measureText(next).width > width && line) {
        lines.push(line)
        line = ch
      } else line = next
    }
    lines.push(line)
  }
  return lines
}

function polaroid(ctx, img, x, y, size, tilt) {
  ctx.save()
  ctx.translate(x + size / 2, y + size / 2)
  ctx.rotate(tilt)
  ctx.shadowColor = 'rgba(40, 25, 10, 0.28)'
  ctx.shadowBlur = 16
  ctx.shadowOffsetY = 6
  ctx.fillStyle = '#fffdf8'
  ctx.fillRect(-size / 2 - 12, -size / 2 - 12, size + 24, size + 52)
  ctx.shadowColor = 'transparent'
  const s = Math.min(img.width, img.height)
  ctx.drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, -size / 2, -size / 2, size, size)
  ctx.restore()
}

function postageStamp(ctx, img, x, y, w, value) {
  const h = w * 1.32
  ctx.save()
  ctx.shadowColor = 'rgba(50, 35, 20, 0.3)'
  ctx.shadowBlur = 8
  ctx.shadowOffsetY = 3
  ctx.fillStyle = '#fbf7ee'
  ctx.fillRect(x, y, w, h)
  ctx.shadowColor = 'transparent'
  // Perforations: bite small circles out of the edges.
  ctx.globalCompositeOperation = 'destination-out'
  const r = w * 0.031
  const step = w * 0.084
  for (let i = step / 2; i < w; i += step) {
    ctx.beginPath(); ctx.arc(x + i, y, r, 0, 7); ctx.arc(x + i, y + h, r, 0, 7); ctx.fill()
  }
  for (let i = step / 2; i < h; i += step) {
    ctx.beginPath(); ctx.arc(x, y + i, r, 0, 7); ctx.arc(x + w, y + i, r, 0, 7); ctx.fill()
  }
  ctx.globalCompositeOperation = 'source-over'
  const m = w * 0.09
  if (img) {
    const iw = w - m * 2
    const ih = h - m - w * 0.3
    const scale = Math.max(iw / img.width, ih / img.height)
    const sw = iw / scale
    const sh = ih / scale
    ctx.drawImage(img, (img.width - sw) / 2, (img.height - sh) / 2, sw, sh, x + m, y + m, iw, ih)
    ctx.strokeStyle = 'rgba(60, 40, 70, 0.35)'
    ctx.lineWidth = 1
    ctx.strokeRect(x + m, y + m, iw, ih)
  }
  ctx.fillStyle = '#4a3474'
  ctx.font = `600 ${w * 0.14}px 'Cormorant Garamond', serif`
  ctx.fillText(value, x + m * 1.2, y + h - w * 0.09)
  ctx.fillStyle = '#6e5a8f'
  ctx.font = `${w * 0.064}px 'Cutive Mono', monospace`
  ctx.textAlign = 'right'
  ctx.fillText('VIOLET POST', x + w - m * 1.2, y + h - w * 0.1)
  ctx.textAlign = 'left'
  ctx.restore()
}

function postmark(ctx, cx, cy, r, date) {
  ctx.save()
  ctx.strokeStyle = 'rgba(40, 30, 60, 0.6)'
  ctx.fillStyle = 'rgba(40, 30, 60, 0.7)'
  ctx.lineWidth = 2.2
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.stroke()
  ctx.lineWidth = 1
  ctx.beginPath(); ctx.arc(cx, cy, r * 0.8, 0, 7); ctx.stroke()
  ctx.textAlign = 'center'
  ctx.font = `${r * 0.26}px 'Cutive Mono', monospace`
  ctx.fillText('VIOLET POST', cx, cy - r * 0.12)
  ctx.font = `${r * 0.3}px 'Cutive Mono', monospace`
  ctx.fillText(date, cx, cy + r * 0.38)
  ctx.lineWidth = 2.2
  for (let k = -1; k <= 1; k++) {
    ctx.beginPath()
    for (let t = 0; t <= 1; t += 0.02) {
      const x = cx - r * 2.7 + t * r * 1.6
      const y = cy + k * r * 0.5 + Math.sin(t * Math.PI * 4) * r * 0.1
      t ? ctx.lineTo(x, y) : ctx.moveTo(x, y)
    }
    ctx.stroke()
  }
  ctx.restore()
}

function seal(ctx, img, set, cx, cy, size) {
  if (!img) return
  const wax = WAX[set.seal_color] || WAX.violet
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate(-0.12)
  ctx.shadowColor = 'rgba(40, 20, 40, 0.35)'
  ctx.shadowBlur = 10
  ctx.shadowOffsetY = 4
  const scale = size / Math.max(img.width, img.height)
  ctx.drawImage(img, (-img.width * scale) / 2, (-img.height * scale) / 2, img.width * scale, img.height * scale)
  ctx.shadowColor = 'transparent'
  // The motif, in relief: shadow down-right, light up-left (same as SealImpression).
  const face = size * 0.56
  const unit = face / 48
  const motif = MOTIFS[set.seal_motif] || MOTIFS.monogram
  const text = set.seal_motif === 'initials' ? (set.seal_initials || 'V').slice(0, 3) : motif.text
  for (const [colour, off] of [[wax.deep, 0.7], [wax.light, -0.7], ['rgba(0,0,0,0.1)', 0]]) {
    ctx.save()
    ctx.translate(-face / 2 + off * unit, -face / 2 + off * 1.1 * unit)
    ctx.scale(unit, unit)
    ctx.strokeStyle = colour
    ctx.fillStyle = colour
    ctx.lineWidth = 1.45
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    if (text) {
      const mono = set.seal_motif === 'monogram'
      ctx.font = mono ? 'italic 500 34px "Cormorant Garamond", serif' : `600 ${text.length > 2 ? 15 : text.length === 2 ? 19 : 26}px "Cormorant Garamond", "Huiwen Mincho", serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(text, 24, mono ? 25.5 : 24)
    }
    for (const d of motif.d || []) ctx.stroke(new Path2D(d))
    ctx.restore()
  }
  ctx.restore()
}

export async function renderLetter(reply) {
  const set = resolve(reply.stationery)
  const paper = PAPERS[set.paper] || PAPERS.parchment
  const font = LETTER_FONTS[set.font] || LETTER_FONTS.wenkai
  const ink = (INKS[set.ink] || INKS.violet).color
  const head = LETTERHEADS[set.letterhead] || LETTERHEADS.none
  const family = fontStack(set.font)
  const size = Math.round(31 * font.scale)
  const manuscript = set.ruling === 'manuscript'
  const lineH = 62
  await Promise.all([
    document.fonts.load(`${size}px ${family}`, (reply.body || '见') + (reply.stationery?.signoff || store.settings?.signoff || '')),
    // Huiwen Mincho comes in slices by character: ask for exactly the ones about to be drawn.
    document.fonts.load(`40px 'Huiwen Mincho'`, `致未来的我 Violet：${longDate(reply.date)}那天的歌·「」—${reply.song?.title || ''}${reply.song?.artist || ''}写于书桌前0123456789:，`),
    document.fonts.load(`20px 'Cutive Mono'`, 'VIOLET'),
    document.fonts.load(`italic 500 34px 'Cormorant Garamond'`, 'V'),
  ]).catch(() => {})
  const [texture, headImg, waxImg, stampImg, ...photos] = await Promise.all([
    load(paper.url), load(head.url), load((WAX[set.seal_color] || WAX.violet).url), load(stampImage(set.stamp)),
    ...(reply.photos || []).slice(0, 3).map((p) => load(photoUrl(p))),
  ])

  // Measure first, then paint at the height the letter needs.
  const probe = document.createElement('canvas').getContext('2d')
  probe.font = `${manuscript ? 34 : size}px ${family}`
  const bodyWidth = W - PAD * 2
  // On manuscript paper every character takes one box, whatever its width.
  const perRow = Math.floor(bodyWidth / lineH)
  const lines = manuscript
    ? String(reply.body || '').split('\n').flatMap((para) => {
        const chars = [...para]
        if (!chars.length) return ['']
        const rows = []
        for (let i = 0; i < chars.length; i += perRow) rows.push(chars.slice(i, i + perRow).join(''))
        return rows
      })
    : wrap(probe, reply.body || '', bodyWidth)
  const headH = set.letterhead === 'none' ? 0 : head.url ? 200 : 110
  const photosH = photos.filter(Boolean).length ? 330 : 0
  const songH = reply.song ? 90 : 0
  // As tall as the letter needs, but never shorter than a sheet of writing paper turned a little square.
  const H = Math.max(Math.round(W * 1.15), PAD - 30 + headH + 150 + (lines.length + 2) * lineH + 30 + photosH + songH + 250)

  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#f7f0e2'
  ctx.fillRect(0, 0, W, H)
  if (texture) {
    const pattern = ctx.createPattern(texture, 'repeat')
    pattern.setTransform(new DOMMatrix().scale(1.15))
    ctx.fillStyle = pattern
    ctx.fillRect(0, 0, W, H)
  }
  let y = PAD - 30
  if (headImg) {
    const w = W * 0.56
    ctx.globalAlpha = 0.94
    ctx.drawImage(headImg, (W - w) / 2, y - 30, w, (w * headImg.height) / headImg.width)
    ctx.globalAlpha = 1
    y += headH
  } else if (set.letterhead === 'post') {
    ctx.fillStyle = ink
    ctx.globalAlpha = 0.8
    ctx.textAlign = 'center'
    ctx.font = `22px 'Cutive Mono', monospace`
    ctx.fillText('C . H .   P O S T A L   C O M P A N Y', W / 2, y + 30)
    ctx.font = `15px 'Cutive Mono', monospace`
    ctx.fillText('L E I D E N  ·  A U T O  M E M O R Y  D O L L  S E R V I C E', W / 2, y + 58)
    ctx.fillRect(W * 0.18, y + 74, W * 0.64, 1.2)
    ctx.fillRect(W * 0.18, y + 78, W * 0.64, 1.2)
    ctx.globalAlpha = 1
    ctx.textAlign = 'left'
    y += headH
  }
  // The stamp, top right, cancelled with the date it was sealed.
  const sealedOn = reply.sealed_at ? isoDate(new Date(reply.sealed_at * 1000)) : reply.date
  postageStamp(ctx, stampImg, W - PAD - 96, PAD - 50, 104, set.stamp?.startsWith('photo:') ? '30' : stampValue(set.stamp))
  postmark(ctx, W - PAD - 70, PAD + 92, 44, sealedOn.replaceAll('-', '·'))

  ctx.fillStyle = ink
  ctx.font = `42px 'Huiwen Mincho', serif`
  ctx.fillText(`致 ${reply.recipient === 'future' ? '未来的我' : 'Violet'}：`, PAD, y + 50)
  ctx.globalAlpha = 0.7
  ctx.font = `22px 'Huiwen Mincho', serif`
  ctx.fillText(longDate(reply.date), PAD, y + 92)
  ctx.globalAlpha = 1
  y += 150

  // Ruling and the margin line.
  const top = y
  const rows = lines.length + 2
  ctx.strokeStyle = paper.rule
  ctx.lineWidth = 1.5
  if (set.ruling !== 'blank') {
    for (let i = 1; i <= rows; i++) {
      ctx.beginPath(); ctx.moveTo(PAD - 20, top + i * lineH); ctx.lineTo(W - PAD + 20, top + i * lineH); ctx.stroke()
    }
    if (set.ruling === 'grid' || manuscript) {
      for (let x = PAD; x <= W - PAD; x += lineH) {
        ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + rows * lineH); ctx.stroke()
      }
    }
    ctx.strokeStyle = paper.margin
    ctx.beginPath(); ctx.moveTo(PAD - 36, 0); ctx.lineTo(PAD - 36, H); ctx.stroke()
  }
  ctx.fillStyle = ink
  ctx.font = `${manuscript ? 34 : size}px ${family}`
  lines.forEach((line, i) => {
    const base = top + (i + 1) * lineH - 16
    if (manuscript) [...line].forEach((ch, k) => ctx.fillText(ch, PAD + k * lineH + 13, base))
    else ctx.fillText(line, PAD, base)
  })
  y = top + rows * lineH + 30

  const shots = photos.filter(Boolean)
  shots.forEach((img, i) => polaroid(ctx, img, PAD + 10 + i * 330, y + 20, 250, [-0.04, 0.035, -0.02][i]))
  y += photosH
  if (reply.song) {
    ctx.fillStyle = ink
    ctx.globalAlpha = 0.75
    ctx.font = `22px 'Huiwen Mincho', serif`
    ctx.fillText(`那天的歌 ·「${reply.song.title}」${reply.song.artist ? ' — ' + reply.song.artist : ''}`, PAD, y + 40)
    ctx.globalAlpha = 1
    y += songH
  }
  const signed = reply.stationery?.signoff || (reply.sealed_at ? '' : store.settings?.signoff) || ''
  ctx.textAlign = 'right'
  if (signed) {
    ctx.font = `${Math.round(36 * font.scale)}px ${family}`
    ctx.fillText(signed, W - PAD, y + 50)
  }
  ctx.globalAlpha = 0.7
  ctx.font = `21px 'Huiwen Mincho', serif`
  ctx.fillText(`—— ${timeOfDay(reply.sealed_at || reply.created)}，写于书桌前`, W - PAD, y + 92)
  ctx.globalAlpha = 1
  ctx.textAlign = 'left'
  seal(ctx, waxImg, set, PAD + 60, Math.min(H - 120, y + 120), 140)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
}

export async function exportLetter(reply) {
  try {
    const blob = await renderLetter(reply)
    const name = `${reply.recipient === 'future' ? '写给未来的我' : '写给 Violet'} ${reply.date}.png`
    if (store.windowed) {
      const { path } = await api.exportImage(blob, name)
      if (path) toast(`存好了：${path}`, 'success', 6000)
      return
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = name
    a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 4000)
  } catch (error) {
    toast(`没能存成图片：${error.message}`, 'error', 6000)
  }
}
