# fusion2urdf-ros2 (patched)

A patched fork of [syuntoku14/fusion2urdf](https://github.com/syuntoku14/fusion2urdf) (ROS2 variant) — a Fusion 360 add-in that exports a Fusion design to a URDF package for ROS / ROS2.

## What's different

The upstream script crashes with `AttributeError: 'NoneType' object has no attribute 'component'` when an assembly contains joints that aren't cleanly connected to two sub-components. This is very common in practice:

- **Ghost / dangling joints** — joints whose components were deleted, leaving both sides `None`. Often invisible in the timeline because they live inside a **derived (read-only)** component.
- **Joints attached to the root component or to ground** — exactly one side is `None`.

### Patches in `core/Joint.py`

1. **Pre-pass deletes fully-dangling ghost joints** (both `occurrenceOne` and `occurrenceTwo` are `None`) automatically when possible. Reports the deleted joint names and asks the user to re-run.
2. **Silently skips ghost joints that can't be deleted** (e.g. trapped inside read-only derived components) — they contribute nothing to the URDF anyway.
3. **Helpful error for partially-dangling joints** (exactly one side `None`): names the joint, names which side is bad, names the component the *good* side is attached to, and **selects the joint** in the Fusion browser so you can find it.

End result: the export no longer crashes on common real-world assemblies, and when it does need user intervention it tells you exactly which joint to fix and where.

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
