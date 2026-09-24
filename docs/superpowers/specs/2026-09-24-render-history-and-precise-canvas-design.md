# Render History And Precise Canvas Fix

## Goal

Fix two related rendering defects:

1. Opening a history item must restore the line-art source, selected side, prompt, model, output size, component references, and confirmed segmentation used by that task.
2. Precise rendering must generate and compose one selected door face in one shared coordinate system. Front/back CAD views and stray accessory helper geometry must not enlarge or shift the output canvas.

## History Restoration

The task record remains the source of truth. Selecting a history item hydrates the editor from its persisted snapshot rather than only replacing the result preview.

- Restore model configuration, prompt, size, source type, source side, and linked drawing task.
- Restore library references from `referenceBindings[*].assetIds`.
- Restore uploaded component references from persisted file URLs and names.
- Restore the saved line-art file and confirmed segmentation for image-based tasks.
- For drawing-task sources, reload the task line-art extraction so both front and back previews are visible.
- If an old task lacks part of the snapshot, restore every available field and show a non-blocking message for missing data.
- Restoring a history item must not mutate or delete the original task.

New tasks continue to persist all input files in the task record. The frontend task types will describe these files explicitly so restoration does not depend on `unknown` casts.

## Precise Single-Face Canvas

DXF precise rendering will isolate the selected face before any AI material call.

1. Split structural primitives into front and back using the existing view-title logic.
2. Build the selected face envelope from panel, frame, trim, and glass geometry.
3. Apply a small proportional margin around that structural envelope.
4. Keep hardware geometry only where it intersects the expanded structural envelope. Far-away helper lines, insertion leaders, and block artifacts cannot expand the canvas.
5. Crop the selected face's flat structural input and all role masks with the same pixel rectangle.
6. Run each referenced material operation against that same face-local input size.
7. Composite seam, trim, frame, panel, glass, hardware, and lighting layers without any later independent resize or reposition.

The existing dual-face rendering path remains available for legacy PSD generation and tests. The precise task path passes the selected side explicitly and receives face-local image and layer outputs.

## Geometry Rules

- Panel, frame, trim, and glass define the authoritative door envelope.
- Hardware can extend slightly outside that envelope but cannot determine the overall canvas size.
- Every generated role layer must have exactly the same width and height as the selected face canvas.
- The final image does not include the CAD line layer.
- Real structural seams remain black and are generated from the shared masks.
- If no structural envelope can be found, the task fails with a clear geometry error instead of returning a malformed image.

## Error Handling

- History restoration reports unavailable legacy files without clearing the currently displayed result.
- Failed remote-file restoration identifies the affected component role.
- Precise rendering rejects an invalid or empty selected face before calling the image provider.
- Provider failures continue to fall back to flat material for the affected role while preserving geometry.

## Verification

- Frontend test or extracted helper test verifies a history task reconstructs line art and all reference groups.
- Backend test uses a two-face DXF and asserts the provider receives only the selected face canvas.
- Backend test adds a far-away accessory helper primitive and asserts output bounds remain tied to structural geometry.
- Existing precise-render, layered-render, and frontend production builds must pass.
- The established CAD baseline may retain its existing nine unrelated failures, but no new failures are accepted.
