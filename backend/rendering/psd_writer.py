"""统一的 PSD 写入接口（服务器端）。

基于 psd-tools 输出普通透明像素层 + 图层组，支持中文图层名、透明度与
分辨率（DPI）元数据。第一版不强制智能对象，优先 Photoshop 兼容性与生成稳定性。

设计约定：
- 节点树以“视觉层叠顺序（上 → 下）”传入，写入时自动反转为 PSD 内部
  的“自下而上”追加顺序，保证最上层在 Photoshop 图层面板最顶部。
- 图层名通过 psd-tools 的 name 属性写入，中文字符会自动存入 Unicode
  图层名（luni）标签，兼容 Photoshop 中文界面。
- 每个像素层自动裁切到非透明内容包围盒（top/left 偏移 + 层尺寸），
  大幅减小 PSD 体积；全透明层保留为 1x1 占位，保持图层结构完整。
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from psd_tools.constants import Compression, Resource
from psd_tools.psd.image_resources import ImageResource, ResoulutionInfo


@dataclass
class PsdNode:
    """PSD 图层节点。

    - ``image`` 为 ``None`` 时表示图层组，其子节点放在 ``children``。
    - ``image`` 提供 RGBA 图片时表示普通透明像素层。
    """

    name: str
    image: Optional[Image.Image] = None
    children: List["PsdNode"] = field(default_factory=list)
    visible: bool = True
    opacity: int = 255


def _alpha_bbox(image: Image.Image) -> Optional[tuple[int, int, int, int]]:
    """返回非透明像素包围盒 (left, top, right, bottom)，全透明返回 None。"""
    arr = np.array(image)
    if arr.ndim != 3 or arr.shape[2] < 4:
        return (0, 0, image.width, image.height)
    alpha = arr[..., 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any() or not cols.any():
        return None
    top = int(np.argmax(rows))
    bottom = int(rows.shape[0] - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(cols.shape[0] - np.argmax(cols[::-1]))
    if bottom <= top or right <= left:
        return None
    return (left, top, right, bottom)


def _set_name(node, name: str) -> None:
    """通过属性写入图层名，让 psd-tools 正确生成 Unicode 图层名标签。"""
    node.name = name


def _append_node(parent, node: PsdNode, compression: Compression) -> None:
    if node.image is not None:
        bbox = _alpha_bbox(node.image)
        if bbox is None:
            # 全透明：保留 1x1 占位层，维持图层结构
            cropped = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            top, left = 0, 0
        else:
            left, top, right, bottom = bbox
            cropped = node.image.crop((left, top, right, bottom))
        layer = PixelLayer.frompil(cropped, parent, name="layer", top=top, left=left, compression=compression)
        _set_name(layer, node.name)
        layer.opacity = int(node.opacity)
        layer.visible = bool(node.visible)
        return
    group = Group.new(parent, name="group")
    _set_name(group, node.name)
    group.visible = bool(node.visible)
    group.opacity = int(node.opacity)
    # 子节点按“上 → 下”传入，反转为“下 → 上”追加，保持视觉顺序正确。
    for child in reversed(node.children):
        _append_node(group, child, compression)
    parent.append(group)


def write_psd(
    nodes: List[PsdNode],
    size: tuple[int, int],
    dpi: int = 300,
    compression: Compression = Compression.RLE,
) -> bytes:
    """将节点树序列化为 PSD 字节流。

    :param nodes: 顶层节点，按“视觉层叠顺序（上 → 下）”排列。
    :param size: 画布 (width, height) 像素尺寸。
    :param dpi: PSD 分辨率元数据（默认 300 DPI）。
    :param compression: 图层数据压缩（RLE 适合平整色块，ZIP 适合纹理图）。
    """
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise ValueError("PSD 画布尺寸必须为正整数")

    # 合成图（ImageData 段）用 ZIP 压缩：PSD 体积的大头是整幅合成预览图，
    # 默认 RAW 会原样写入（2600px 画布约 14MB），ZIP 可压到 1-2MB。
    psd = PSDImage.new("RGB", (width, height), depth=8, compression=Compression.ZIP)
    psd.image_resources[Resource.RESOLUTION_INFO] = ImageResource(
        key=Resource.RESOLUTION_INFO,
        data=ResoulutionInfo(
            horizontal=int(dpi),
            horizontal_unit=1,
            width_unit=1,
            vertical=int(dpi),
            vertical_unit=1,
            height_unit=1,
        ),
    )

    # 顶层节点按“上 → 下”传入，反转为“下 → 上”追加。
    for node in reversed(nodes):
        _append_node(psd, node, compression)

    buffer = io.BytesIO()
    psd.save(buffer)
    return buffer.getvalue()
