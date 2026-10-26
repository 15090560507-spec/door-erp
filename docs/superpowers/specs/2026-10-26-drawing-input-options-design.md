# Additional Drawing Input Fields

The user explicitly deferred all layout changes and requested only three input fields in the current form. This supersedes both layout mockups.

## Approved Behavior

- `lock_core_height`: lock core height above floor, default 1050mm. Use the existing editable Combobox with 950, 1050, and 1150 presets; accept custom finite positive values.
- `frame_assembly`: frame/trim assembly, default `框套一体`; dropdown also offers `框套分体`.
- `installation_method`: dropdown with `拉片安装` and `膨胀螺丝安装`. Default empty because no default was requested.

Add frame assembly and installation under the existing Structure and Opening card. Add lock core height under the existing Hardware card. Keep the outer three-column form, section order, styles, preview placement, and existing controls unchanged except for the minimum local field-row space needed for the additions.

Persist these values in task params, restore them when editing, preserve them when copying tasks, and keep change history through the existing generic params mechanism. Old tasks load defaults without any bulk migration. State-only updates must not replace params.

The fields are metadata only in this change. Do not move CAD locks or handles, change geometry, affect disc centers, add CAD annotations, alter BOMs, change pricing, or undo the DXF download fix.

## Validation And Verification

Share validation/defaults for the three fields between direct CAD request models and task params request models. Keep unrelated task params intact. Test defaults, presets/custom values, invalid heights/options, disk-backed create/read/update/copy, status-only updates, and unchanged CAD builder inputs. Confirm original layout and field interaction in desktop and mobile screenshots, then run type checking, lint, and scoped regressions. Push only the feature files and records to the previously authorized branch; deployment remains a separate user action.
