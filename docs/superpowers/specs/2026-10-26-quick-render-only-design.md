# Quick Render Only

The user requests removing precise/segmented generation from the render page and retaining one-click quick generation. Keep the existing layout, model configuration, line-art sources/crop, component reference uploads, and history restoration.

- One primary action: `一键生成效果图`, always submitting `renderMode: quick` and one image. Automatic resolution means 2K; explicit 1K/2K/4K remains available.
- Remove segmentation creation/confirmation/editor controls, component regeneration buttons, and the quick-to-precise PSD conversion flow. Restoring legacy precise history must not reactivate these flows.
- Keep existing historical images and metadata, and allow direct download of already-generated historical PSD files. Do not generate new segmented PSDs from this page.
- Preserve backend/API compatibility and stored records. This is a page workflow removal, not deletion of historical data or unrelated backend modules.
- Validate with TypeScript/lint and browser tests using mocked image generation only, including history restoration and request payloads. No paid provider calls.
