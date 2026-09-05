# fusion2urdf-ros2 (patched)

A patched fork of [syuntoku14/fusion2urdf](https://github.com/syuntoku14/fusion2urdf) (ROS2 variant) — a Fusion 360 add-in that exports a Fusion design to a URDF package for ROS / ROS2.

## What's different

The upstream script crashes with `AttributeError: 'NoneType' object has no attribute 'component'` when an assembly contains joints that aren't cleanly connected to two sub-components. This is very common in practice:

- **Ghost / dangling joints** — joints whose components were deleted, leaving both sides `None`. Often invisible in the timeline because they live inside a **derived (read-only)** component.
- **Joints attached to the root component or to ground** — exactly one side is `None`.

### Patches in `core/Joint.py`

1. **Pre-pass ignores fully-dangling ghost joints** (both `occurrenceOne` and `occurrenceTwo` are `None`) and reports them. The exporter never deletes CAD objects.
2. **Silently skips ghost joints that can't be deleted** (e.g. trapped inside read-only derived components) — they contribute nothing to the URDF anyway.
3. **Helpful error for partially-dangling joints** (exactly one side `None`): names the joint, names which side is bad, names the component the *good* side is attached to, and **selects the joint** in the Fusion browser so you can find it.

End result: the export no longer crashes on common real-world assemblies, and when it does need user intervention it tells you exactly which joint to fix and where.

### Read-only, repeatable mesh export

The exporter asks Fusion to materialise each original occurrence-context body
as an in-memory temporary BRep, preserving the assembly placement. It does not
rewrite vertices, origins, or
transforms; clone bodies; rename components to `old_component`; or delete
dangling joints. Running it twice must leave the CAD occurrence/joint signature unchanged
and produce the same link-to-mesh manifest.

Every STL is staged first, checked as a structurally complete binary STL, and
only then promoted into `meshes/`. Export failures are fatal. The standalone
URDF is published only after its mesh manifest exactly matches the files
exported by that run, so stale files cannot hide a missing mesh.

### Plain URDF bundle

Each successful export also writes `urdf/<robot>.urdf`. The file bundles the
generated materials, links, joints, transmissions, and Gazebo elements without
requiring ROS or `xacro` inside Fusion. Mesh references use portable
`package://<package>/meshes/...` URIs. The exporter validates that the output
contains no unresolved xacro expressions and that every joint references an
emitted link before publishing the file.

## Companion script: `Fix_Dangling_Joints`

The exporter never deletes anything, so ghost joints stay in the design and get
reported on every run. `Fix_Dangling_Joints/` is a separate Fusion script that
removes them on demand — a deliberate, undoable edit you trigger yourself rather
than a side effect of exporting.

It deletes, after showing you the list and asking for confirmation:

- **ghost joints** — both endpoints are `None`, so the joint connects nothing.
- **unreadable joints** — accessing an endpoint raises; this is what makes the
  exporter crash.

It never deletes **half-dangling joints** (exactly one side `None`, i.e.
attached to the root component or to ground). Those encode real modelling
intent, so the script only reports them and selects the first one in the
browser. Joints it cannot delete — typically inside a derived, read-only
component — are listed as failures; fix those in the source design.

The script scans every component in the design (both regular and as-built
joints), and it does not save the document: review the result and save yourself.

Install it like any other script: in Fusion **Utilities → Add-Ins → Scripts**,
press the green **+**, and point it at the `Fix_Dangling_Joints` folder.

## Install

1. Clone or download this repo.
2. Rename the folder to `URDF_Exporter_Ros2` (Fusion expects the folder name to match the script name).
3. Move it to:
   - **macOS**: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Scripts/`
   - **Windows**: `%appdata%\Autodesk\Autodesk Fusion 360\API\Scripts\`
4. In Fusion 360: **Utilities → Add-Ins → Scripts** → select `URDF_Exporter_Ros2` → Run.

## Usage tips

- Every link must be its own **component** (not a loose body in the root). Name the root link's component `base_link`.
- Joints must connect **component-to-component**, never component-to-root-body and never to ground / origin.
- **Derived** components are read-only — if there are problems inside them, fix them in the source design and let the Derive update.
- **Linked** components: use **Break Link** (right-click) to make them local before exporting. "Break Link" doesn't apply to Derive.

## Credits

- Original add-in: [syuntoku14/fusion2urdf](https://github.com/syuntoku14/fusion2urdf) — MIT.
- ROS2 variant: based on the same project's ROS2 branch / community forks.
- Patches in this fork: Elia Huber, 2026.

## License

MIT — see [LICENSE](LICENSE). Original copyright © 2019 syuntoku14 is preserved.
