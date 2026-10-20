"""Compare actual internal and editable DXF sheets in the same plot window."""

import io
import json
import os
import sys
import time
from pathlib import Path

import ezdxf
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from cad_download import editable_sheet_dxf
from rendering.cad_sheet_jpg import _order_form_bbox, _plot


def verify(folder):
    reports = []
    for index in range(4):
        source = (folder / f'adaptive-{index}.dxf').read_bytes()
        original = ezdxf.read(io.StringIO(source.decode('utf-8')))
        bounds = _order_form_bbox(original)
        assert bounds is not None
        started = time.perf_counter()
        converted = editable_sheet_dxf(source)
        elapsed = time.perf_counter() - started
        download = ezdxf.read(io.StringIO(converted.decode('utf-8')))
        assert _order_form_bbox(download) is None
        assert not download.audit().has_errors
        original_image = _plot(original, bounds, (1782, 1260))
        download_image = _plot(download, bounds, (1782, 1260))
        (folder / f'download-{index}.jpg').write_bytes(download_image)
        a = np.asarray(Image.open(io.BytesIO(original_image)), dtype=np.int16)
        b = np.asarray(Image.open(io.BytesIO(download_image)), dtype=np.int16)
        difference = np.abs(a - b)
        changed = float(np.mean(np.max(difference, axis=2) > 12))
        assert changed < 0.01, f'Sheet {index} changed {changed:.2%} of rendered pixels'
        reports.append({'sample': index, 'conversionSeconds': round(elapsed, 3),
                        'sourceBytes': len(source), 'downloadBytes': len(converted),
                        'changedPixelFraction': round(changed, 8),
                        'meanPixelDifference': round(float(np.mean(difference)), 6)})
    (folder / 'download-verification.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    verify(Path(os.environ.get('CAD_LAYOUT_ARTIFACT_DIR', 'F:/codex/cad-editable-sheet-verification')))
