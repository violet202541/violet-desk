<script setup>
const props = defineProps({ platform: { type: String, required: true }, small: Boolean })
const LABEL = { netease: '网易云', qq: 'QQ', kugou: '酷狗', all: '聚合' }
</script>

<template>
  <span class="pstamp" :class="[platform, { small }]">{{ LABEL[props.platform] || platform }}</span>
</template>

<style scoped>
.pstamp {
  display: inline-block;
  padding: 1px 8px 0;
  border: 1px dashed currentColor;
  border-radius: 3px;
  font-size: 12px;
  line-height: 20px;
  letter-spacing: 0.06em;
  white-space: nowrap;
}
.small {
  font-size: 11px;
  line-height: 17px;
  padding: 0 6px;
}
.netease {
  color: var(--p-netease);
}
.qq {
  color: var(--p-qq);
}
.kugou {
  color: var(--p-kugou);
}
.all {
  color: var(--violet-ink);
}
</style>
