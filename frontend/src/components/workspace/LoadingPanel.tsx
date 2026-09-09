export default function LoadingPanel({ rows = 5, label = "正在加载" }: { rows?: number; label?: string }) {
  return (
    <div className="workspace-loading" role="status" aria-live="polite" aria-label={label}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, index) => (
        <div className="workspace-loading__row" key={index} aria-hidden="true">
          <i />
          <span><b /><b /></span>
          <em />
        </div>
      ))}
    </div>
  );
}
