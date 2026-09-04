import type { ComposerAttachmentView } from "@/contracts/composer";

const MAX_ATTACHMENTS = 8;
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export async function filesToComposerAttachments(
  files: File[],
  currentCount: number,
): Promise<ComposerAttachmentView[]> {
  const remaining = MAX_ATTACHMENTS - currentCount;
  const slice = files.slice(0, Math.max(0, remaining));
  const out: ComposerAttachmentView[] = [];

  for (const file of slice) {
    if (file.type.startsWith("image/") && file.size > MAX_IMAGE_BYTES) {
      continue;
    }
    const preview_url = file.type.startsWith("image/")
      ? await readFileAsDataUrl(file)
      : URL.createObjectURL(file);

    out.push({
      id: crypto.randomUUID(),
      name: file.name,
      mime_type: file.type || "application/octet-stream",
      preview_url,
      size_bytes: file.size,
    });
  }

  return out;
}

export function revokeComposerAttachmentUrl(attachment: ComposerAttachmentView): void {
  if (attachment.preview_url.startsWith("blob:")) {
    URL.revokeObjectURL(attachment.preview_url);
  }
}

export function revokeComposerAttachmentUrls(attachments: ComposerAttachmentView[]): void {
  attachments.forEach(revokeComposerAttachmentUrl);
}
