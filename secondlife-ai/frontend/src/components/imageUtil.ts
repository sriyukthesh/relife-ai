/** Downscale a photo in the browser before upload (phone photos are often 5 MB+). */
export async function shrinkImage(file: File, maxSide = 1600, quality = 0.88): Promise<File> {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
    if (scale === 1 && file.size < 1_500_000 && file.type === "image/jpeg") { bmp.close(); return file; }
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * scale); c.height = Math.round(bmp.height * scale);
    c.getContext("2d")?.drawImage(bmp, 0, 0, c.width, c.height);
    bmp.close();
    const blob = await new Promise<Blob | null>((res) => c.toBlob(res, "image/jpeg", quality));
    return blob ? new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file; // let the server decide (it re-validates and resizes)
  }
}
