import type {
  RenderReferenceRole,
  RenderSegmentation,
  RenderTask,
  RenderTaskFile,
} from "@/lib/renderApi";

const REFERENCE_ROLES: RenderReferenceRole[] = ["panel", "trim", "frame", "glass", "hardware"];
const REFERENCE_GUIDANCE_MARKER = "\n\n本次参考素材使用规则：";
const SYSTEM_POLICY_MARKER = "\n输出清晰、真实的门类产品效果图；";

export interface RestoredReferenceGroup {
  role: RenderReferenceRole;
  assetIds: string[];
  persistedFiles: RenderTaskFile[];
}

export interface RestoredRenderHistory {
  configId: string;
  prompt: string;
  size: string;
  sourceType: RenderTask["sourceType"];
  sourceSide: RenderTask["sourceSide"];
  sourceTaskId: string;
  lineArtFile?: RenderTaskFile;
  referenceGroups: RestoredReferenceGroup[];
  segmentation: RenderSegmentation | null;
}

export function restoreRenderHistory(task: RenderTask): RestoredRenderHistory {
  const taskFiles = Array.isArray(task.files) ? task.files : [];
  const lineArtFile = taskFiles.find((file) => file.role === "line_art");

  return {
    configId: task.modelConfigId || "",
    prompt: editablePrompt(task.prompt || ""),
    size: task.size || "auto",
    sourceType: task.sourceType || "image",
    sourceSide: task.sourceSide || "front",
    sourceTaskId: task.sourceTaskId || "",
    lineArtFile,
    referenceGroups: REFERENCE_ROLES.map((role) => {
      const binding = task.referenceBindings?.[role];
      const boundFiles = Array.isArray(binding?.files) ? binding.files : [];
      const fallbackFiles = taskFiles.filter((file) => (
        file.targetRole === role
        && ["component_reference", "style_reference", "temp_asset"].includes(file.role || "")
      ));
      return {
        role,
        assetIds: Array.from(new Set(binding?.assetIds || [])),
        persistedFiles: deduplicateFiles([...boundFiles, ...fallbackFiles]),
      };
    }),
    segmentation: isRenderSegmentation(task.segmentation) ? task.segmentation : null,
  };
}

function editablePrompt(value: string): string {
  const withoutPolicy = value.split(SYSTEM_POLICY_MARKER, 1)[0];
  return withoutPolicy.split(REFERENCE_GUIDANCE_MARKER, 1)[0].trim();
}

function deduplicateFiles(files: RenderTaskFile[]): RenderTaskFile[] {
  const seen = new Set<string>();
  return files.filter((file) => {
    const key = file.url || file.filePath || file.id || `${file.originalName || "file"}:${file.targetRole || ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function isRenderSegmentation(value: RenderTask["segmentation"]): value is RenderSegmentation {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<RenderSegmentation>;
  return Boolean(candidate.id && candidate.source && candidate.masks);
}
