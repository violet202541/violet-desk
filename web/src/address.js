// 称呼与落款：Violet 来信怎么称呼你，你的回信怎么署名。改了以后，旧信也跟着改口。
import { store } from './store.js'

const FORMS = {
  '亲爱的你：': (n) => `亲爱的${n}：`,
  '见字如面：': (n) => `${n}，见字如面：`,
  '致今天的你：': (n) => `致今天的${n}：`,
  '展信佳：': (n) => `${n}，展信佳：`,
  '你好呀：': (n) => `${n}，你好呀：`,
}

export function addressed(greeting) {
  const name = store.settings?.nickname?.trim()
  return name && FORMS[greeting] ? FORMS[greeting](name) : greeting
}

export const signoff = () => store.settings?.signoff?.trim() || ''
