"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { TaskItem } from "@/lib/types";

interface Props {
  tasks: TaskItem[];
  value: string;
  onChange: (taskId: string) => void;
  searchTasks?: (query: string) => Promise<TaskItem[]>;
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

export default function TaskProjectCombobox({ tasks, value, onChange, searchTasks }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchRequestRef = useRef(0);
  const listboxId = useId();
  const selectedTask = tasks.find((task) => task.id === value);
  const [inputQuery, setInputQuery] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [remoteMatches, setRemoteMatches] = useState<TaskItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const query = inputQuery ?? (selectedTask ? taskLabel(selectedTask) : "");

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (rootRef.current?.contains(event.target as Node)) return;
      setOpen(false);
      setRemoteMatches(null);
      setInputQuery(null);
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  useEffect(() => () => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchRequestRef.current += 1;
  }, []);

  const scheduleRemoteSearch = (nextQuery: string) => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    const normalized = nextQuery.trim();
    if (!searchTasks || !normalized) {
      searchRequestRef.current += 1;
      setRemoteMatches(null);
      setSearching(false);
      return;
    }

    const requestId = ++searchRequestRef.current;
    setRemoteMatches(null);
    setSearching(true);
    searchTimerRef.current = setTimeout(async () => {
      try {
        const result = await searchTasks(normalized);
        if (searchRequestRef.current === requestId) setRemoteMatches(result);
      } catch (error) {
        console.warn("search drawing tasks failed:", error);
        if (searchRequestRef.current === requestId) setRemoteMatches([]);
      } finally {
        if (searchRequestRef.current === requestId) setSearching(false);
      }
    }, 250);
  };

  const matches = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const source = remoteMatches ?? (normalized
      ? tasks.filter((task) => taskSearchText(task).includes(normalized))
      : tasks);
    return source.slice(0, 20);
  }, [query, remoteMatches, tasks]);

  return (
    <div ref={rootRef} className="relative mt-1">
      <input
        type="text"
        value={query}
        placeholder="输入客户、项目、门型、尺寸或任务ID搜索"
        onFocus={() => {
          if (value) {
            setInputQuery("");
            setRemoteMatches(null);
          }
          setOpen(true);
        }}
        onChange={(event) => {
          const nextQuery = event.target.value;
          setInputQuery(nextQuery);
          setOpen(true);
          scheduleRemoteSearch(nextQuery);
          if (!nextQuery.trim() && value) onChange("");
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setOpen(false);
            setInputQuery(null);
          }
        }}
        role="combobox"
        aria-controls={listboxId}
        aria-expanded={open}
        aria-autocomplete="list"
        className="w-full rounded-lg border border-[#E5E5EA]/60 bg-white px-3 py-2 text-[13px] outline-none transition-colors focus:border-[#007AFF]"
      />

      {open && (
        <div
          id={listboxId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-[#E5E5EA] bg-white p-1 shadow-lg"
        >
          {searching ? (
            <div className="px-3 py-4 text-center text-[12px] text-[#8E8E93]">
              正在搜索全部图纸项目...
            </div>
          ) : matches.length ? matches.map((task) => (
            <button
              key={task.id}
              type="button"
              role="option"
              aria-selected={task.id === value}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange(task.id);
                setInputQuery(null);
                setRemoteMatches(null);
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
