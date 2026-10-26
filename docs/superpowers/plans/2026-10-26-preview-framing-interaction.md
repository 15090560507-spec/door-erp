# Preview Framing and Interaction

**Goal:** Fit only door views and dimensions, dock after half the large canvas enters the viewport, and support local pan/zoom.

**Architecture:** Keep the existing generated SVG and serial preview queue. Filter order-form descendants and non-dimension text only in grouped previews. Use a stable lower canvas target for docking. Manipulate SVG viewBox locally with uniform scaling.

**Constraints:** No DXF geometry changes, no paid AI calls, no extra CAD requests for navigation, preserve floating size/position and selected side.

- [x] Add regression coverage for nearby order-form notes and inherited dimension layers; fix grouped renderer and invalidate its SVG cache.
- [x] Measure a stable lower canvas; switch when its midpoint reaches the viewport bottom.
- [x] Add left-drag pan, right-drag anchored zoom, capture/cancel handling and fit reset.
- [x] Run unit, backend, type and browser checks with generated SVGs; inspect screenshots.
- [x] Prepare scoped delivery and Tencent Cloud commands. Git push status is confirmed separately in the delivery message.
