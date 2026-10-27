"use client";

import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";

type Choice = { id: number; name: string; detail: string; search: string };

export default function PurchaseCatalogInput({ label, value, choices, disabled, onChange, onSelect }: {
  label: string; value: string; choices: Choice[]; disabled?: boolean;
  onChange: (value: string) => void; onSelect: (id: number) => void;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [showAll, setShowAll] = useState(false);
  const needle = showAll ? "" : value.trim().toLocaleLowerCase();
  const matches = choices.filter(choice => choice.search.toLocaleLowerCase().includes(needle));
  const choose = (choice: Choice) => { onSelect(choice.id); setOpen(false); setActive(-1); };

  return <div className="relative min-w-0" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <div className="flex h-10 border border-[#C7C7CC] bg-white">
      <input aria-label={label} role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={id}
        aria-activedescendant={open && active >= 0 ? `${id}-${active}` : undefined}
        disabled={disabled} value={value} placeholder="搜索或输入新名称" className="min-w-0 flex-1 px-3 text-sm outline-none"
        onFocus={() => { setOpen(true); setShowAll(false); }}
        onChange={event => { onChange(event.target.value); setOpen(true); setShowAll(false); setActive(-1); }}
        onKeyDown={event => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault(); setOpen(true);
            setActive(index => matches.length ? Math.max(0, Math.min(matches.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))) : -1);
          } else if (event.key === "Enter" && open && active >= 0 && matches[active]) {
            event.preventDefault(); choose(matches[active]);
          } else if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); }
        }} />
      <button type="button" disabled={disabled} aria-label={`${label}下拉选择`} title={`${label}下拉选择`}
        className="w-9 shrink-0" onClick={() => { setShowAll(true); setOpen(!open); setActive(-1); }}><ChevronDown size={15} className="mx-auto" /></button>
    </div>
    {open && <div id={id} role="listbox" aria-label={`${label}候选`} className="absolute inset-x-0 top-full z-30 max-h-56 overflow-y-auto border border-[#C7C7CC] bg-white shadow-md">
      {matches.map((choice, index) => <button type="button" role="option" aria-selected={active === index} id={`${id}-${index}`} key={choice.id}
        className={`block w-full px-3 py-2 text-left text-sm hover:bg-[#EDF3FF] ${active === index ? "bg-[#EDF3FF]" : ""}`}
        onMouseDown={event => event.preventDefault()} onClick={() => choose(choice)}>
        <span className="block break-words font-medium">{choice.name}</span><span className="block break-words text-xs text-[#636366]">{choice.detail}</span>
      </button>)}
      {!matches.length && <div className="px-3 py-2 text-xs text-[#636366]">无匹配资料</div>}
    </div>}
  </div>;
}
