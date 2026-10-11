// 贴进信里的照片先缩一缩：长边不超过 1600px，存成 JPEG。
export async function shrinkImage(file, longest = 1600) {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, longest / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.86))
}
