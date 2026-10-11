// 打字机音效：全部用 WebAudio 合成，不带音频文件。默认关闭；播放音乐时自动静音。

let ctx = null
let enabled = false
let musicPlaying = () => false

function audio() {
  if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)()
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

function allowed() {
  return enabled && !musicPlaying()
}

function noiseBurst(time, duration, frequency, gain) {
  const c = audio()
  const buffer = c.createBuffer(1, Math.ceil(c.sampleRate * duration), c.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 3)
  const source = c.createBufferSource()
  source.buffer = buffer
  const filter = c.createBiquadFilter()
  filter.type = 'bandpass'
  filter.frequency.value = frequency
  filter.Q.value = 1.4
  const amp = c.createGain()
  amp.gain.value = gain
  source.connect(filter).connect(amp).connect(c.destination)
  source.start(time)
}

function tone(time, frequency, duration, gain) {
  const c = audio()
  const osc = c.createOscillator()
  const amp = c.createGain()
  osc.type = 'sine'
  osc.frequency.value = frequency
  amp.gain.setValueAtTime(gain, time)
  amp.gain.exponentialRampToValueAtTime(0.0001, time + duration)
  osc.connect(amp).connect(c.destination)
  osc.start(time)
  osc.stop(time + duration)
}

export const sound = {
  setEnabled(value) {
    enabled = value
  },
  bindMusic(fn) {
    musicPlaying = fn
  },
  key() {
    if (!allowed()) return
    const c = audio()
    noiseBurst(c.currentTime, 0.035, 2400 + Math.random() * 900, 0.5)
    noiseBurst(c.currentTime + 0.012, 0.05, 700, 0.25)
  },
  typing(count = 8, gap = 0.075) {
    if (!allowed()) return
    const c = audio()
    for (let i = 0; i < count; i++) {
      const t = c.currentTime + i * gap + Math.random() * 0.02
      noiseBurst(t, 0.035, 2200 + Math.random() * 1200, 0.45)
    }
  },
  carriage() {
    if (!allowed()) return
    const c = audio()
    noiseBurst(c.currentTime, 0.22, 900, 0.18)
    tone(c.currentTime + 0.2, 2093, 0.9, 0.08)
  },
  // A rubber postmark landing on paper.
  stamp() {
    if (!allowed()) return
    const c = audio()
    noiseBurst(c.currentTime, 0.09, 260, 0.9)
    noiseBurst(c.currentTime + 0.01, 0.05, 1400, 0.25)
  },
  // Wax pressed, then the envelope slides away.
  seal() {
    if (!allowed()) return
    const c = audio()
    noiseBurst(c.currentTime, 0.12, 320, 0.7)
    noiseBurst(c.currentTime + 0.35, 0.4, 1800, 0.08)
  },
  // A goose arriving: three soft wingbeats.
  wings() {
    if (!allowed()) return
    const c = audio()
    for (let i = 0; i < 3; i++) noiseBurst(c.currentTime + i * 0.17, 0.14, 380 + i * 60, 0.22 - i * 0.04)
  },
  bell() {
    if (!allowed()) return
    const c = audio()
    tone(c.currentTime, 2637, 1.2, 0.07)
    tone(c.currentTime, 3951, 0.6, 0.03)
  },
}
