"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { TaskItem } from "@/lib/types";

interface Props {
  tasks: TaskItem[];
  value: string;
  onChange: (taskId: string) => void;
}

function taskLabel(task: TaskItem): string {
  return [
    task.customer || "未填客户",
    task.project || "未填项目",
    task.door_type || "",
    task.size || "",
  ].filter(Boolean).join(" / ");
}

function taskSearchText(task: TaskItem): string {
  return [
    task.id,
    task.customer,
    task.project,
    task.door_type,
    task.size,
    task.params?.ddh,
  ].filter(Boolean).join(" ").toLowerCase();
}

export default function TaskProjectCombobox({ tasks, value, onChange }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const selectedTask = tasks.find((task) => task.id === value);
  const [query, setQuery] = useState(selectedTask ? taskLabel(selectedTask) : "");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const task = tasks.find((item) => item.id === value);
    setQuery(task ? taskLabel(task) : "");
  }, [tasks, value]);

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (rootRef.current?.contains(event.target as Node)) return;
      setOpen(false);
      const task = tasks.find((item) => item.id === value);
      setQuery(task ? taskLabel(task) : "");
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [tasks, value]);

  const matches = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const source = normalized
      ? tasks.filter((task) => taskSearchText(task).includes(normalized))
      : tasks;
    return source.slice(0, 20);
  }, [query, tasks]);

  return (
    <div ref={rootRef} className="relative mt-1">
      <input
        type="text"
        value={query}
        placeholder="输入客户、项目、门型、尺寸或任务ID搜索"
        onFocus={() => {
          if (value) setQuery("");
          setOpen(true);
        }}
        onChange={(event) => {
          const nextQuery = event.target.value;
          setQuery(nextQuery);
          setOpen(true);
          if (!nextQuery.trim() && value) onChange("");
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setOpen(false);
            setQuery(selectedTask ? taskLabel(selectedTask) : "");
          }
        }}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        className="w-full rounded-lg border border-[#E5E5EA]/60 bg-white px-3 py-2 text-[13px] outline-none transition-colors focus:border-[#007AFF]"
      />

      {open && (
        <div
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-[#E5E5EA] bg-white p-1 shadow-lg"
        >
          {matches.length ? matches.map((task) => (
            <button
              key={task.id}
              type="button"
              role="option"
              aria-selected={task.id === value}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange(task.id);
                setQuery(taskLabel(task));
                setOpen(false);
              }}
              className={`block w-full rounded-md px-3 py-2 text-left text-[12px] transition-colors ${
                task.id === value
                  ? "bg-[#007AFF]/10 text-[#007AFF]"
                  : "text-[#1C1C1E] hover:bg-[#F2F2F7]"
              }`}
            >
              <span className="block font-medium">{taskLabel(task)}</span>
              <span className="mt-0.5 block text-[11px] text-[#8E8E93]">任务ID：{task.id}</span>
            </button>
          )) : (
            <div className="px-3 py-4 text-center text-[12px] text-[#8E8E93]">
              没有匹配的图纸项目
            </div>
          )}
        </div>
      )}
    </div>
  );
}
