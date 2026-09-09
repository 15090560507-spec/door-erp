"use client";

import { X } from "lucide-react";
import { useEffect, useId, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type ViewportDialogProps = {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "small" | "medium" | "large" | "wide";
  closeOnBackdrop?: boolean;
  onClose: () => void;
};

export default function ViewportDialog({
  open,
  title,
  description,
  children,
  footer,
  size = "medium",
  closeOnBackdrop = true,
  onClose,
}: ViewportDialogProps) {
  const [mounted, setMounted] = useState(false);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!mounted || !open) return null;
  return createPortal(
    <div
      className="viewport-dialog-backdrop"
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className={`viewport-dialog viewport-dialog--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
      >
        <header className="viewport-dialog__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p id={descriptionId}>{description}</p>}
          </div>
          <button type="button" className="viewport-dialog__close" onClick={onClose} aria-label="关闭弹窗" title="关闭">
            <X size={18} strokeWidth={1.8} />
          </button>
        </header>
        <div className="viewport-dialog__body">{children}</div>
        {footer && <footer className="viewport-dialog__footer">{footer}</footer>}
      </section>
    </div>,
    document.body,
  );
}
