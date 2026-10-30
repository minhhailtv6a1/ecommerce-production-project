export const IMAGE_MAX_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/bmp",
] as const;

export function validateImageFile(file: File): string | null {
  if (!(ACCEPTED_IMAGE_TYPES as readonly string[]).includes(file.type)) {
    return "Định dạng chưa được hỗ trợ. Hãy chọn ảnh JPEG, PNG, WebP hoặc BMP.";
  }
  if (file.size === 0) return "Tệp ảnh đang trống.";
  if (file.size > IMAGE_MAX_BYTES) {
    return "Ảnh vượt quá giới hạn 10 MiB.";
  }
  return null;
}
