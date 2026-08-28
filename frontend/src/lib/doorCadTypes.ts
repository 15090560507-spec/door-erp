export interface DoorCadFrameInput {
  doorWidth: number;
  doorHeight: number;
  linkedSideSizes: boolean;
  outerSideShort: number;
  outerSideLong: number;
  skeletonSideShort: number;
  skeletonSideLong: number;
  skeletonThickness: number;
  skeletonGrooveDepth: number;
  skeletonGrooveWidth: number;
  skinThickness: number;
  skinGrooveDepth: number;
  skinGrooveWidth: number;
  hingeStyle: string;
  hingeCount: 3 | 4;
  hingeMode: "auto" | "custom";
  hingeCenterSkeleton: number;
  hingeCenterSkin: number;
  hingePositions: number[];
  includeLeft: boolean;
  includeRight: boolean;
  includeTop: boolean;
  includeBottom: boolean;
  sameTopBottom: boolean;
  topShort: number;
  topLong: number;
  bottomShort: number;
  bottomLong: number;
  topPin: boolean;
  bottomPin: boolean;
}

export interface DoorCadProjectMeta {
  orderNo: string;
  projectName: string;
  taskId: string | null;
}

export interface DoorCadPoint {
  x: number;
  y: number;
}

export interface DoorCadSegment {
  start: DoorCadPoint;
  end: DoorCadPoint;
}

export interface DoorCadPolyline {
  points: DoorCadPoint[];
  closed: boolean;
}

export interface DoorCadShape {
  shapeId: string;
  kind: "circle" | "rectangle" | "obround" | "polyline";
  center: DoorCadPoint | null;
  width: number | null;
  height: number | null;
  diameter: number | null;
  points: DoorCadPoint[];
  layer: string;
}

export interface DoorCadGroove {
  grooveId: string;
  face: "inner" | "outer";
  segments: DoorCadSegment[];
  depth: number;
  width: number;
  layer: string;
}

export interface DoorCadDimension {
  dimensionId: string;
  label: string;
  start: DoorCadPoint;
  end: DoorCadPoint;
  offset: number;
  orientation: "horizontal" | "vertical" | "aligned";
  value: number | null;
}

export interface DoorCadFoldNode {
  x: number;
  angle: number;
  direction: "up" | "down" | "none";
}

export interface DoorCadPart {
  partId: string;
  name: string;
  position: "left" | "right" | "top" | "bottom";
  materialType: "skeleton" | "skin";
  length: number;
  thickness: number;
  flatWidth: number;
  cutOuter: DoorCadPolyline;
  holes: DoorCadShape[];
  grooves: DoorCadGroove[];
  foldSection: DoorCadPolyline;
  flatSection: DoorCadPolyline;
  dimensions: DoorCadDimension[];
  process: {
    sourceRule: string;
    sourceTemplate: string | null;
    mirrored: boolean;
    grooveFaces: Array<"inner" | "outer">;
    foldNodes: DoorCadFoldNode[];
    notes: string[];
  };
}

export interface DoorCadPlacement {
  partId: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DoorCadValidationIssue {
  code: string;
  message: string;
  field: string | null;
  severity: "error" | "warning";
}

export interface DoorCadGeometry {
  schemaVersion: "1.0";
  ruleVersion: "frame-new-v1.4.3";
  project: DoorCadProjectMeta;
  inputs: DoorCadFrameInput;
  assembly: {
    width: number;
    height: number;
    placements: DoorCadPlacement[];
  };
  parts: DoorCadPart[];
  validation: {
    status: "PASSED" | "WARNING" | "ERROR";
    errors: DoorCadValidationIssue[];
    warnings: DoorCadValidationIssue[];
  };
}

export interface DoorCadProjectRequest {
  inputs: DoorCadFrameInput;
  project: DoorCadProjectMeta;
}

export interface DoorCadProjectRecord {
  id: string;
  schemaVersion: "1.0";
  ruleVersion: "frame-new-v1.4.3";
  createdAt: string;
  updatedAt: string;
  createdBy: string;
  updatedBy: string;
  inputs: DoorCadFrameInput;
  geometry: DoorCadGeometry;
}

export interface DoorCadProjectSummary {
  id: string;
  orderNo: string;
  projectName: string;
  taskId: string | null;
  status: "PASSED" | "WARNING" | "ERROR";
  updatedAt: string;
  updatedBy: string;
}

export interface DoorCadDomainError {
  code: string;
  message: string;
  field?: string | null;
  severity?: string;
}

export const DEFAULT_DOOR_CAD_INPUT: DoorCadFrameInput = {
  doorWidth: 1800,
  doorHeight: 2700,
  linkedSideSizes: true,
  outerSideShort: 55,
  outerSideLong: 62,
  skeletonSideShort: 52,
  skeletonSideLong: 59,
  skeletonThickness: 2,
  skeletonGrooveDepth: 1,
  skeletonGrooveWidth: 2,
  skinThickness: 0.8,
  skinGrooveDepth: 0.3,
  skinGrooveWidth: 0.6,
  hingeStyle: "可拆卸合页",
  hingeCount: 3,
  hingeMode: "auto",
  hingeCenterSkeleton: 97,
  hingeCenterSkin: 98.5,
  hingePositions: [],
  includeLeft: true,
  includeRight: true,
  includeTop: true,
  includeBottom: true,
  sameTopBottom: true,
  topShort: 55,
  topLong: 75,
  bottomShort: 55,
  bottomLong: 75,
  topPin: true,
  bottomPin: true,
};

export const DEFAULT_DOOR_CAD_PROJECT: DoorCadProjectMeta = {
  orderNo: "",
  projectName: "",
  taskId: null,
};
