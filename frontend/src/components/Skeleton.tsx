"use client";

export function TaskCardSkeleton() {
  return (
    <div className="flex items-stretch gap-1 mb-2 animate-pulse">
      <div className="flex-1 bg-white border border-[#E5E5EA] rounded-[10px] px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="h-4 w-40 bg-[#E5E5EA] rounded" />
          <div className="h-5 w-14 bg-[#E5E5EA] rounded-full" />
        </div>
        <div className="h-3 w-64 bg-[#E5E5EA] rounded mt-2" />
      </div>
    </div>
  );
}

export function TaskListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <TaskCardSkeleton key={i} />
      ))}
    </>
  );
}
