"use client";

import { useState, type KeyboardEvent, type ClipboardEvent, useRef, type DragEvent } from "react";

interface Props {
  onImage: (b64: string) => void;
  className?: string;
}

export default function ClipboardUpload({ onImage, className = "" }: Props) {
  const [hover, setHover] = useState(false);
  const [hasImage, setHasImage] = useState(false);
  const inputRef = useRef<HTMLDivElement>(null);

  const processFile = (file: File) => {
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = (reader.result as string).split(",")[1];
      onImage(b64);
      setHasImage(true);
    };
    reader.readAsDataURL(file);
  };

  const handlePaste = (e: ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        e.preventDefault();
        processFile(items[i].getAsFile()!);
        return;
      }
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setHover(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  return (
    <div
      ref={inputRef}
      tabIndex={0}
      onPaste={handlePaste}
      onDragOver={(e) => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.focus()}
      onKeyDown={(e: KeyboardEvent) => {
        if (e.ctrlKey && e.key === "v") return;
      }}
      className={`
        relative flex flex-col items-center justify-center
        min-h-[80px] rounded-lg border-2 border-dashed cursor-pointer
        transition-all duration-200 select-none
        ${hover ? "border-[#007AFF] bg-[#F0F8FF]" : "border-[#C7C7CC] bg-[#FAFAFC]"}
        ${className}
      `}
    >
      <input
        type="file"
        accept="image/*"
        onChange={handleFileInput}
        className="absolute inset-0 opacity-0 cursor-pointer"
        aria-label="上传图片"
      />
      <span className="text-[13px] font-medium text-[#8E8E93] pointer-events-none text-center px-4">
        {hasImage ? "图片已就绪，点击替换" : "点击框内后 Ctrl+V 粘贴 / 或拖拽图片"}
      </span>
    </div>
  );
}
