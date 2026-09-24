# PSD Download And Material Feedback Fix

## Goal

Make PSD export visibly complete in one action and prevent door-frame or trim material failures from appearing as unexplained flat vector fills.

## PSD Action

- Use one action for precise results: generate the PSD when needed, then immediately download it.
- Keep the action disabled while generating or downloading and show its current state in the button.
- Increase the PSD request timeout for 4K layer packages.
- Show a dialog when generation succeeds without a downloadable file or when the authenticated file download fails.
- Keep already-generated PSD files reusable without regenerating them.

## Material Generation

- A role's own references always have highest priority.
- When frame or trim has no independent reference, reuse the panel reference files but run a separate role-specific material operation. Do not copy unchanged pixels from the panel operation.
- Glass and hardware keep their existing independent-reference behavior.
- Preserve the exact shared masks and face-local canvas; material generation may not move geometry.
- Persist whether the result used AI material or flat fallback and include inheritance/failure notes.

## Result Feedback

- Show `AI 材质` or `平整材质` beside the precise result.
- Display provider fallback errors prominently.
- Explain when frame or trim reused the panel reference so the user knows which reference controls the finish.

## Verification

- Test that frame and trim each receive a role-specific material call when only panel references are present.
- Test that a provider failure remains a valid flat fallback and records a visible reason.
- Run the rendering regression subset, CAD baseline, and frontend production build.
