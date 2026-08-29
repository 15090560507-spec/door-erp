import type { DoorCadFrameInput, DoorCadProjectMeta } from "@/lib/doorCadTypes";
import type { TaskItem } from "@/lib/types";

interface Props {
  inputs: DoorCadFrameInput;
  project: DoorCadProjectMeta;
  tasks: TaskItem[];
  onInputsChange: (value: DoorCadFrameInput) => void;
  onProjectChange: (value: DoorCadProjectMeta) => void;
}

const inputClass = "h-9 w-full border border-[#D1D1D6] bg-white px-2.5 text-[13px] text-[#1C1C1E] outline-none focus:border-[#007AFF]";
const labelClass = "space-y-1 text-[12px] text-[#636366]";

function NumberField({ label, value, onChange, step = 1, disabled = false }: { label: string; value: number; onChange: (value: number) => void; step?: number; disabled?: boolean }) {
  return (
    <label className={labelClass}>
      <span>{label}</span>
      <input className={inputClass} type="number" value={value} step={step} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex h-9 items-center gap-2 text-[13px] text-[#1C1C1E]">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 accent-[#007AFF]" />
      {label}
    </label>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-[#E5E5EA] pt-4 first:border-t-0 first:pt-0">
      <h3 className="mb-3 text-[13px] font-semibold text-[#1C1C1E]">{title}</h3>
      <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2">{children}</div>
    </section>
  );
}

export default function ParameterPanel({ inputs, project, tasks, onInputsChange, onProjectChange }: Props) {
  const setInput = <K extends keyof DoorCadFrameInput>(key: K, value: DoorCadFrameInput[K]) => {
    onInputsChange({ ...inputs, [key]: value });
  };

  return (
    <div className="space-y-5 border border-[#D1D1D6] bg-white p-4">
      <Section title="项目信息">
        <label className={labelClass}>
          <span>订单号</span>
          <input className={inputClass} value={project.orderNo} onChange={(event) => onProjectChange({ ...project, orderNo: event.target.value })} />
        </label>
        <label className={labelClass}>
          <span>项目名称</span>
          <input className={inputClass} value={project.projectName} onChange={(event) => onProjectChange({ ...project, projectName: event.target.value })} />
        </label>
        <label className={`${labelClass} min-[420px]:col-span-2`}>
          <span>关联终审任务</span>
          <select className={inputClass} value={project.taskId ?? ""} onChange={(event) => onProjectChange({ ...project, taskId: event.target.value || null })}>
            <option value="">不关联</option>
            {tasks.map((task) => <option key={task.id} value={task.id}>{task.customer || "未填写客户"} · {task.project || task.id} · {task.size}</option>)}
          </select>
        </label>
      </Section>

      <Section title="门洞尺寸">
        <NumberField label="门宽 (mm)" value={inputs.doorWidth} onChange={(value) => setInput("doorWidth", value)} />
        <NumberField label="门高 (mm)" value={inputs.doorHeight} onChange={(value) => setInput("doorHeight", value)} />
      </Section>

      <Section title="左右框规格">
        <NumberField label="外皮小边" value={inputs.outerSideShort} onChange={(value) => setInput("outerSideShort", value)} />
        <NumberField label="外皮大边" value={inputs.outerSideLong} onChange={(value) => setInput("outerSideLong", value)} />
        <div className="min-[420px]:col-span-2"><Toggle label="骨架尺寸随外皮自动联动（各减 3 mm）" checked={inputs.linkedSideSizes} onChange={(value) => setInput("linkedSideSizes", value)} /></div>
        <NumberField label="骨架小边" value={inputs.skeletonSideShort} disabled={inputs.linkedSideSizes} onChange={(value) => setInput("skeletonSideShort", value)} />
        <NumberField label="骨架大边" value={inputs.skeletonSideLong} disabled={inputs.linkedSideSizes} onChange={(value) => setInput("skeletonSideLong", value)} />
      </Section>

      <Section title="材料与压槽">
        <NumberField label="骨架厚度" value={inputs.skeletonThickness} step={0.1} onChange={(value) => setInput("skeletonThickness", value)} />
        <NumberField label="外皮厚度" value={inputs.skinThickness} step={0.1} onChange={(value) => setInput("skinThickness", value)} />
        <NumberField label="骨架槽深" value={inputs.skeletonGrooveDepth} step={0.1} onChange={(value) => setInput("skeletonGrooveDepth", value)} />
        <NumberField label="骨架槽宽" value={inputs.skeletonGrooveWidth} step={0.1} onChange={(value) => setInput("skeletonGrooveWidth", value)} />
        <NumberField label="外皮槽深" value={inputs.skinGrooveDepth} step={0.1} onChange={(value) => setInput("skinGrooveDepth", value)} />
        <NumberField label="外皮槽宽" value={inputs.skinGrooveWidth} step={0.1} onChange={(value) => setInput("skinGrooveWidth", value)} />
      </Section>

      <Section title="合页加工">
        <label className={labelClass}>
          <span>合页样式</span>
          <input className={inputClass} value={inputs.hingeStyle} onChange={(event) => setInput("hingeStyle", event.target.value)} />
        </label>
        <label className={labelClass}>
          <span>合页数量</span>
          <select className={inputClass} value={inputs.hingeCount} onChange={(event) => setInput("hingeCount", Number(event.target.value) as 3 | 4)}>
            <option value={3}>3</option><option value={4}>4</option>
          </select>
        </label>
        <label className={labelClass}>
          <span>位置模式</span>
          <select className={inputClass} value={inputs.hingeMode} onChange={(event) => setInput("hingeMode", event.target.value as "auto" | "custom")}>
            <option value="auto">自动</option><option value="custom">自定义</option>
          </select>
        </label>
        <NumberField label="骨架合页中心" value={inputs.hingeCenterSkeleton} step={0.1} onChange={(value) => setInput("hingeCenterSkeleton", value)} />
        <NumberField label="外皮合页中心" value={inputs.hingeCenterSkin} step={0.1} onChange={(value) => setInput("hingeCenterSkin", value)} />
        {inputs.hingeMode === "custom" && (
          <label className={`${labelClass} min-[420px]:col-span-2`}>
            <span>合页位置（逗号分隔，距底 mm）</span>
            <input
              className={inputClass}
              value={inputs.hingePositions.join(", ")}
              onChange={(event) => setInput("hingePositions", event.target.value.split(/[,，\s]+/).map(Number).filter(Number.isFinite))}
            />
          </label>
        )}
      </Section>

      <Section title="上下框规格">
        <NumberField label="上框小边" value={inputs.topShort} onChange={(value) => setInput("topShort", value)} />
        <NumberField label="上框大边" value={inputs.topLong} onChange={(value) => setInput("topLong", value)} />
        <div className="min-[420px]:col-span-2"><Toggle label="下框与上框相同" checked={inputs.sameTopBottom} onChange={(value) => setInput("sameTopBottom", value)} /></div>
        <NumberField label="下框小边" value={inputs.bottomShort} disabled={inputs.sameTopBottom} onChange={(value) => setInput("bottomShort", value)} />
        <NumberField label="下框大边" value={inputs.bottomLong} disabled={inputs.sameTopBottom} onChange={(value) => setInput("bottomLong", value)} />
        <Toggle label="上框带插脚" checked={inputs.topPin} onChange={(value) => setInput("topPin", value)} />
        <Toggle label="下框带插脚" checked={inputs.bottomPin} onChange={(value) => setInput("bottomPin", value)} />
      </Section>

      <Section title="生成零件">
        <Toggle label="左框" checked={inputs.includeLeft} onChange={(value) => setInput("includeLeft", value)} />
        <Toggle label="右框" checked={inputs.includeRight} onChange={(value) => setInput("includeRight", value)} />
        <Toggle label="上框" checked={inputs.includeTop} onChange={(value) => setInput("includeTop", value)} />
        <Toggle label="下框" checked={inputs.includeBottom} onChange={(value) => setInput("includeBottom", value)} />
      </Section>
    </div>
  );
}
