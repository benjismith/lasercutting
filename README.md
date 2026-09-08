# lasercutting

Projects for a Glowforge Pro (with passthrough), built either as directly generated
SVG cut files or as parametric geometry that is previewed in Blender first and
exported to SVG later.

## Layout

- `lasercut/` – shared Python package.
  - `panel.py` – flat panels as notched rectangles with a 3D placement. Pure Python; this
    is the geometry the cut files will come from.
  - `glowforge.py` – bed size and passthrough rules.
  - `blender.py` – builds panels as meshes and renders previews. Only works inside Blender.
- `projects/<name>/` – one folder per project: its design module, a config with the
  real-world numbers, a Blender build script, and preview renders.
- `tests/` – tests for the shared package. Each project keeps its own tests beside its code.

## Running things

Tests (uses [uv](https://docs.astral.sh/uv/) to manage a throwaway venv):

    uv run pytest

Blender is not on the PATH, so call it by its full path. Build a project scene headless
and render previews, from the repo root:

    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python projects/drawer-organizer/build.py -- \
        --blend out/organizer.blend --render out/renders

Or open the project's `build.py` in Blender's Text Editor and run it there to get the
scene in an interactive session. Scenes are built in inches.

`out/` is scratch output and is ignored by git.
