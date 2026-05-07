"use client";

import { useEffect, useCallback, useState } from "react";

interface ImageModalProps {
  src: string;
  onClose: () => void;
  alt?: string;
}

export default function ImageModal({ src, onClose, alt = "" }: ImageModalProps) {
  const handleKey = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
    };
  }, [handleKey]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-w-[95vw] max-h-[95vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          className="max-w-[95vw] max-h-[95vh] object-contain rounded-lg shadow-2xl"
        />
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 w-8 h-8 flex items-center justify-center rounded-full bg-white/90 text-[#8E8E93] hover:text-[#1C1C1E] shadow-lg transition-colors text-lg leading-none"
        >
          x
        </button>
      </div>
    </div>
  );
}

/** 缩略图组件：使用 React state 管理全屏预览，避免 DOM 泄漏 */
export function Thumbnail({
  b64,
  alt = "",
  width = 250,
}: {
  b64: string;
  alt?: string;
  width?: number;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const src = `data:image/png;base64,${b64}`;

  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        width={width}
        onClick={() => setModalOpen(true)}
        className="rounded-lg border border-[#E5E5EA] cursor-pointer transition-all duration-200 hover:shadow-md hover:scale-[1.02]"
      />

      {modalOpen && (
        <ImageModal src={src} alt={alt} onClose={() => setModalOpen(false)} />
      )}
    </>
  );
}
