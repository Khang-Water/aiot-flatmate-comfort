# One-bedroom apartment digital-twin handoff

Use `one_bedroom_digital_twin_spec.json` as the semantic and dimensional brief, and `source_floorplan.png` as the visual authority for topology and wall traces.

The plan is suitable for a reconstruction draft, visualization, or furniture study. It is **not** a construction drawing. Dimensions printed on the image use a mixture of clear spans and overall spans, so the specification records conflicts and confidence levels explicitly.

Recommended reconstruction order:

1. Calibrate the image using the 6.05 m top dimension.
2. Trace and extrude the exterior walls.
3. Add interior walls while honoring clear room dimensions.
4. Cut doors and windows.
5. Add architectural fixtures, then furniture proxies.
6. Validate the top view against the source and produce a dimension report.

Do not invent hidden elevations, exact product models, materials, plumbing connections, or structural details. Keep inferred elements parametric and editable.
