"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import BomTable from "@/components/door-cad/BomTable";
import NoticeDialog from "@/components/door-cad/NoticeDialog";
import Overview2D from "@/components/door-cad/Overview2D";
import ParameterPanel from "@/components/door-cad/ParameterPanel";
import PartDetail2D from "@/components/door-cad/PartDetail2D";
import ProductionValidation from "@/components/door-cad/ProductionValidation";
import ProjectActions from "@/components/door-cad/ProjectActions";
import { getTasks } from "@/lib/api";
import {
  calculateDoorFrame,
  createDoorCadProject,
  doorCadErrorMessage,
  downloadDoorCadBlob,
  exportDoorCadBom,
  exportDoorCadDxf,
  exportDoorCadJson,
  getDoorCadProject,
  listDoorCadProjects,
  updateDoorCadProject,
} from "@/lib/doorCadApi";
import {
  DEFAULT_DOOR_CAD_INPUT,
  DEFAULT_DOOR_CAD_PROJECT,
  type DoorCadGeometry,
  type DoorCadProjectRequest,
  type DoorCadProjectSummary,
} from "@/lib/doorCadTypes";
import type { TaskItem } from "@/lib/types";

type ViewTab = "overview" | "part" | "bom";
type ExportKind = "dxf" | "bom" | "json";

interface DialogState {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelable?: boolean;
}

function safeFilename(value: string, fallback: string) {
  return (value || fallback).replace(/[<>:"/\\|?*\x00-\x1f]/g, "_").trim() || fallback;
}

export default function DoorCadFramePage() {
  const [inputs, setInputs] = useState(() => ({ ...DEFAULT_DOOR_CAD_INPUT }));
  const [project, setProject] = useState(() => ({ ...DEFAULT_DOOR_CAD_PROJECT }));
  const [geometry, setGeometry] = useState<DoorCadGeometry | null>(null);
  const [projects, setProjects] = useState<DoorCadProjectSummary[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [savedProjectId, setSavedProjectId] = useState("");
  const [selectedPartId, setSelectedPartId] = useState("");
  const [tab, setTab] = useState<ViewTab>("overview");
  const [calculating, setCalculating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const calculationSequence = useRef(0);
  const confirmedAction = useRef<(() => void) | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);

  const request = useMemo<DoorCadProjectRequest>(() => ({ inputs, project }), [inputs, project]);
  const selectedPart = geometry?.parts.find((part) => part.partId === selectedPartId) ?? geometry?.parts[0] ?? null;
  const canExport = Boolean(geometry && geometry.validation.status !== "ERROR");

  const refreshProjects = useCallback(async () => {
    try { setProjects(await listDoorCadProjects()); } catch (error) { setErrorMessage(doorCadErrorMessage(error, "加载项目失败")); }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshProjects();
      void getTasks({ limit: 200, offset: 0 }).then((result) => setTasks(result.tasks)).catch(() => setTasks([]));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshProjects]);

  useEffect(() => {
    const sequence = ++calculationSequence.current;
    const timer = window.setTimeout(() => {
      setCalculating(true);
      void calculateDoorFrame(request)
        .then((result) => {
          if (sequence !== calculationSequence.current) return;
          setGeometry(result);
          setErrorMessage("");
          setSelectedPartId((current) => result.parts.some((part) => part.partId === current) ? current : result.parts[0]?.partId ?? "");
        })
        .catch((error) => {
          if (sequence !== calculationSequence.current) return;
          setGeometry(null);
          setErrorMessage(doorCadErrorMessage(error, "参数计算失败"));
        })
        .finally(() => { if (sequence === calculationSequence.current) setCalculating(false); });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [request]);

  const loadProject = async (projectId: string) => {
    setSavedProjectId(projectId);
    setSuccessMessage("");
    if (!projectId) {
      setInputs({ ...DEFAULT_DOOR_CAD_INPUT });
      setProject({ ...DEFAULT_DOOR_CAD_PROJECT });
      return;
    }
    setBusy(true);
    try {
      const record = await getDoorCadProject(projectId);
      setInputs(record.inputs);
      setProject(record.geometry.project);
      setGeometry(record.geometry);
      setSelectedPartId(record.geometry.parts[0]?.partId ?? "");
      setSuccessMessage("项目已加载");
    } catch (error) {
      setDialog({ title: "加载失败", message: doorCadErrorMessage(error, "项目加载失败") });
    } finally { setBusy(false); }
  };

  const saveProject = async () => {
    if (!canExport) return;
    setBusy(true);
    try {
      const record = savedProjectId
        ? await updateDoorCadProject(savedProjectId, request)
        : await createDoorCadProject(request);
      setSavedProjectId(record.id);
      setGeometry(record.geometry);
      await refreshProjects();
      setSuccessMessage(savedProjectId ? "项目修改已保存" : "项目已创建");
      setDialog({ title: "保存成功", message: savedProjectId ? "当前项目已覆盖保存。" : "下料项目已创建，可继续导出。" });
    } catch (error) {
      setDialog({ title: "保存失败", message: doorCadErrorMessage(error, "项目保存失败") });
    } finally { setBusy(false); }
  };

  const executeExport = async (kind: ExportKind, acknowledgeWarnings: boolean) => {
    setBusy(true);
    try {
      const body = { inputs, project, acknowledgeWarnings };
      const projectName = safeFilename(project.projectName, "未命名项目");
      const orderNo = safeFilename(project.orderNo, "无订单号");
      const blob = kind === "dxf"
        ? await exportDoorCadDxf(body)
        : kind === "bom"
          ? await exportDoorCadBom(body)
          : await exportDoorCadJson(body);
      const suffix = kind === "dxf" ? "门框下料图.dxf" : kind === "bom" ? "门框BOM.xlsx" : "门框下料项目.json";
      downloadDoorCadBlob(blob, `${orderNo}-${projectName}-${suffix}`);
      setSuccessMessage(`${suffix} 已开始下载`);
    } catch (error) {
      setDialog({ title: "导出失败", message: doorCadErrorMessage(error, "文件导出失败") });
    } finally { setBusy(false); }
  };

  const requestExport = (kind: ExportKind) => {
    if (!geometry || geometry.validation.status === "ERROR") return;
    if (geometry.validation.warnings.length > 0) {
      confirmedAction.current = () => { void executeExport(kind, true); };
      setDialog({
        title: "确认生产警告",
        message: geometry.validation.warnings.map((warning) => `• ${warning.message}`).join("\n"),
        confirmLabel: "确认并导出",
        cancelable: true,
      });
      return;
    }
    void executeExport(kind, false);
  };

  const importProject = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text()) as DoorCadGeometry;
      if (parsed.schemaVersion !== "1.0" || parsed.ruleVersion !== "frame-new-v1.4.3" || !parsed.inputs || !parsed.project) {
        throw new Error("项目文件版本不兼容");
      }
      setSavedProjectId("");
      setInputs(parsed.inputs);
      setProject(parsed.project);
      setSuccessMessage("项目 JSON 已导入并重新计算");
    } catch (error) {
      setDialog({ title: "导入失败", message: doorCadErrorMessage(error, "项目 JSON 无法读取") });
    }
  };

  const tabs: Array<{ id: ViewTab; label: string }> = [
    { id: "overview", label: "装配总览" },
    { id: "part", label: "零件展开" },
    { id: "bom", label: "BOM" },
  ];

  return (
    <main className="mx-auto max-w-[1600px] px-3 py-4 sm:px-5 sm:py-5">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-[#1C1C1E]">门框下料</h1>
          <p className="mt-1 text-[13px] text-[#636366]">新工艺门框 · 8 个标准零件 · SVG / DXF / BOM 共用同一几何数据</p>
        </div>
        <div className="flex w-full flex-wrap items-end gap-2 sm:w-auto">
          <label className="min-w-0 flex-1 space-y-1 text-[12px] text-[#636366] sm:flex-none">
            <span>已保存项目</span>
            <select className="block h-9 w-full min-w-0 border border-[#D1D1D6] bg-white px-2 text-[13px] sm:w-72" value={savedProjectId} onChange={(event) => void loadProject(event.target.value)}>
              <option value="">新建项目</option>
              {projects.map((item) => <option key={item.id} value={item.id}>{item.orderNo || "无订单号"} · {item.projectName || "未命名"}</option>)}
            </select>
          </label>
          <input ref={importInputRef} type="file" accept="application/json,.json" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importProject(file); event.currentTarget.value = ""; }} />
          <button type="button" onClick={() => importInputRef.current?.click()} className="h-9 border border-[#D1D1D6] bg-white px-3 text-[13px] hover:bg-[#F2F2F7]">导入 JSON</button>
        </div>
      </header>

      {(errorMessage || successMessage) && (
        <div className={`mb-4 border px-4 py-2 text-[13px] ${errorMessage ? "border-[#FF3B30]/30 bg-[#FF3B30]/6 text-[#C5221F]" : "border-[#34C759]/30 bg-[#34C759]/7 text-[#248A3D]"}`}>
          {errorMessage || successMessage}
        </div>
      )}

      <div className="grid items-start gap-4 xl:grid-cols-[390px_minmax(0,1fr)]">
        <ParameterPanel inputs={inputs} project={project} tasks={tasks} onInputsChange={setInputs} onProjectChange={setProject} />
        <div className="min-w-0 space-y-4">
          <ProjectActions
            busy={busy}
            canExport={canExport}
            onSave={() => void saveProject()}
            onExportDxf={() => requestExport("dxf")}
            onExportBom={() => requestExport("bom")}
            onExportJson={() => requestExport("json")}
          />
          <ProductionValidation geometry={geometry} />
          <section className="border border-[#D1D1D6] bg-white">
            <div className="flex flex-wrap items-center border-b border-[#D1D1D6] bg-[#FAFAFA]">
              <div className="flex min-w-0 overflow-x-auto">
                {tabs.map((item) => (
                  <button key={item.id} type="button" onClick={() => setTab(item.id)} className={`h-10 shrink-0 border-r border-[#D1D1D6] px-4 text-[13px] font-medium sm:px-5 ${tab === item.id ? "bg-white text-[#007AFF]" : "text-[#636366] hover:bg-white"}`}>
                    {item.label}
                  </button>
                ))}
              </div>
              <span className="ml-auto px-3 text-xs text-[#8E8E93] sm:px-4">{calculating ? "正在计算..." : geometry ? `${geometry.parts.length} 个零件` : "等待有效参数"}</span>
            </div>
            <div className="p-3">
              {tab === "overview" && <Overview2D geometry={geometry} />}
              {tab === "part" && (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {geometry?.parts.map((part) => (
                      <button key={part.partId} type="button" onClick={() => setSelectedPartId(part.partId)} className={`h-8 border px-3 text-[12px] ${selectedPart?.partId === part.partId ? "border-[#007AFF] bg-[#007AFF] text-white" : "border-[#D1D1D6] bg-white text-[#3C3C43]"}`}>
                        {part.partId} {part.name}
                      </button>
                    ))}
                  </div>
                  <PartDetail2D part={selectedPart} />
                  {selectedPart && (
                    <div className="grid gap-3 border border-[#D1D1D6] bg-[#FAFAFA] p-3 text-[13px] sm:grid-cols-4">
                      <span>长度：{selectedPart.length} mm</span><span>展开宽：{selectedPart.flatWidth} mm</span><span>厚度：{selectedPart.thickness} mm</span><span>镜像：{selectedPart.process.mirrored ? "是" : "否"}</span>
                    </div>
                  )}
                </div>
              )}
              {tab === "bom" && <BomTable parts={geometry?.parts ?? []} />}
            </div>
          </section>
        </div>
      </div>

      {dialog && (
        <NoticeDialog
          title={dialog.title}
          message={dialog.message}
          confirmLabel={dialog.confirmLabel}
          onCancel={dialog.cancelable ? () => { confirmedAction.current = null; setDialog(null); } : undefined}
          onConfirm={() => {
            const action = confirmedAction.current;
            confirmedAction.current = null;
            setDialog(null);
            action?.();
          }}
        />
      )}
    </main>
  );
}
