function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("image load failed"));
    };
    img.src = url;
  });
}

/** Downscales a photo to maxSide px and re-encodes it as JPEG; `square` crops the centre. */
export async function compressImage(file: File, maxSide = 1600, quality = 0.8, square = false): Promise<File> {
  const img = await loadImage(file);
  const side = Math.min(img.naturalWidth, img.naturalHeight);
  const cw = square ? side : img.naturalWidth;
  const ch = square ? side : img.naturalHeight;
  const sx = square ? (img.naturalWidth - side) / 2 : 0;
  const sy = square ? (img.naturalHeight - side) / 2 : 0;

  const scale = Math.min(1, maxSide / Math.max(cw, ch));
  const width = Math.max(1, Math.round(cw * scale));
  const height = Math.max(1, Math.round(ch * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas unavailable");
  ctx.drawImage(img, sx, sy, cw, ch, 0, 0, width, height);

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
  if (!blob) throw new Error("compress failed");
  return new File([blob], "photo.jpg", { type: "image/jpeg" });
}
