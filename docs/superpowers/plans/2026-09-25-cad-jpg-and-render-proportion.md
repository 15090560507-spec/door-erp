# CAD JPG and Render Proportion Implementation Plan

1. Add a DXF sheet renderer that crops from the `ORDER_FORM` outer boundary and returns a JPEG download response.
2. Tighten front/back line-art extraction to structural door geometry and expose its source aspect ratio.
3. Route drawing-page effect generation through the exact DXF geometry pipeline.
4. Place `Download line-art JPG` and `Save changes` in the drawing action row.
5. Add focused backend tests, then run backend tests and the frontend production build.
