// 信里的字：文具匣里可选的几款字体。都是 SIL OFL 开源字体，随安装包附带，
// 切成按需加载的小块，只有信纸上真的用到哪款、哪些字，才会读进来。
import '@fontsource/ma-shan-zheng/400.css'
import '@fontsource/zhi-mang-xing/400.css'
import '@fontsource/long-cang/400.css'
import '@fontsource/zcool-xiaowei/400.css'
import '@chinese-fonts/xiaolai/dist/Xiaolai/result.css'

export const LETTER_FONTS = {
  wenkai: { label: '文楷', hint: '霞鹜文楷 · 端正的钢笔楷书', family: "'LXGW WenKai Screen'", scale: 1 },
  xiaolai: { label: '小赖', hint: '小赖字体 · 圆润随手的字', family: "'Xiaolai SC'", scale: 1 },
  mincho: { label: '明朝', hint: '汇文明朝 · 正式的信函', family: "'Huiwen Mincho'", scale: 1 },
  xiaowei: { label: '小薇', hint: '站酷小薇 · 清秀的宋体', family: "'ZCOOL XiaoWei'", scale: 1 },
  mashan: { label: '楷书', hint: '马善政楷书 · 毛笔小楷', family: "'Ma Shan Zheng'", scale: 1.12 },
  zhimang: { label: '行书', hint: '志莽行书 · 流动的行书', family: "'Zhi Mang Xing'", scale: 1.2 },
  longcang: { label: '手札', hint: '龙藏体 · 潦草的手写', family: "'Long Cang'", scale: 1.32 },
}

export function fontStack(id) {
  const font = LETTER_FONTS[id] || LETTER_FONTS.wenkai
  return `${font.family}, 'LXGW WenKai Screen', 'Microsoft YaHei UI', sans-serif`
}
