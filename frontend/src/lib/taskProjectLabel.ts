import type { TaskItem } from "./types";
import { calculateDoorAreas } from "./doorAreas";

export function taskProjectLabel(task: TaskItem): string {
  const parts = [task.customer || "未填客户", task.project || "未填项目", task.door_type || "", task.size || ""];
  if (task.params && (Number(task.params.dw) > 0 || (task.params.use_light_size && Number(task.params.light_w) > 0)) &&
      (Number(task.params.dh) > 0 || (task.params.use_light_size && Number(task.params.light_h) > 0))) {
    const metrics = calculateDoorAreas(task.params);
    if ((metrics.hasFrontOuter || metrics.hasInnerTrim) &&
        (metrics.outerWidth !== metrics.frameWidth || metrics.outerHeight !== metrics.frameHeight)) {
      parts.push(`${Number(metrics.outerWidth.toFixed(3))} × ${Number(metrics.outerHeight.toFixed(3))} (外围)`);
    }
  }
  return parts.filter(Boolean).join(" / ");
}
