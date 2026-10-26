export function clipboardImageFiles(data: Pick<DataTransfer, "files" | "items">): File[] {
  const files = Array.from(data.files || []).filter(file => file.type.startsWith("image/"));
  if (files.length) return files;
  return Array.from(data.items || [])
    .filter(item => item.kind === "file" && item.type.startsWith("image/"))
    .map(item => item.getAsFile())
    .filter((file): file is File => Boolean(file));
}

export function isClipboardTextTarget(target: EventTarget | null): boolean {
  const element = target as Element | null;
  return typeof element?.closest === "function" && Boolean(
    element.closest("input, textarea, [contenteditable]:not([contenteditable='false'])"),
  );
}
