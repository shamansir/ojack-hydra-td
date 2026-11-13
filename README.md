# Port of Olivia Jack's Hydra to TouchDesigner

This is a full function-to-component port of Olivia Jack's [`hydra`](https://github.com/hydra-synth) visual synth engine to TouchDesigner.

[`hydra` project API](https://hydra.ojack.xyz/api/) is built using [GLSL functions](https://github.com/hydra-synth/hydra-functions/blob/main/libs/hydra/glsl-functions.js), in this case its WebGL.

TouchDesigner has GLSL TOP which uses native OpenGL.

This project is built 96% with the help of Claude Code in two relaxed days. [Headless Hydra](https://codeberg.org/gugray/HeadlessHydra) source also helped in the work.

## Screenshots

![All components grouped including the generator](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/all-grouped-02.png?raw=true)

![Source Group with previews](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/group-source-01.png?raw=true)

![Geometry Group with previews](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/group-geometry-00.png?raw=true)

![Color Group with previews](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/group-color-00.png?raw=true)

![Blend Group with previews](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/group-blend-01.png?raw=true)

![Modulate Group with previews](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/group-modulate-01.png?raw=true)

![Audio Group with previews](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/group-audio-00.png?raw=true)

![In Action](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/in-action-02.png?raw=true)

### Examples

![All Examples](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/all-examples-00.png?raw=true)

![`khoparzi_1`](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/example-khoparzi_1-01.png?raw=true) [`khoparzi_1` at Hydra](https://hydra.ojack.xyz/?sketch_id=khoparzi_1)

![`ritchse_4`](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/example-ritchse_4-00.png?raw=true) [`ritchse_4` at Hydra](https://hydra.ojack.xyz/?sketch_id=ritchse_4)

![`rangga_3`](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/example-rangga_3-00.png?raw=true) [`rangga_3` at Hydra](https://hydra.ojack.xyz/?sketch_id=rangga_3)

![`example_11`](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/example-example11-00.png?raw=true) [`example_11` at Hydra](https://hydra.ojack.xyz/?sketch_id=example_11)

![`example_18`](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/example-example_18-00.png?raw=true) [`example_18` at Hydra](https://hydra.ojack.xyz/?sketch_id=example_18)

![`flor_2`](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/example-flor_2-01.png?raw=true) [`flor_2` at Hydra](https://hydra.ojack.xyz/?sketch_id=flor_2)

![`example_10`](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/example-example_10-01.png?raw=true) [`example_10` at Hydra](https://hydra.ojack.xyz/?sketch_id=example_10)

## Function-to-Component Logic

Each Hydra function is converted to a corresponding TD Component holding its shader source inside, together with wiring of parameters to shader inputs. Output is mapped to be the output of the component (TOP).

For every numeric argument, both CHOP-based input and parameter key/value pair are created (on `Hydra` tab). If there is no input for this argument connected, then the parameter value/expession is used. So you can either put values or expressions on the parameters tabs or connect CHOPs instead, both ways are supported.

For source arguments any TOP component may be passed in the input.

Also includes `hydra_fft` CHOP which replicates `a.fft[n]` functionality of Hydra, but creates a channel output for every bin.

![In Action](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/audio-in-action-00.png?raw=true)

## Building

For details on building, see [`assets/scripts/hydra/BUILD.md`](assets/scripts/hydra/BUILD.md).

`Hydra.toe` project includes all the function-components and the generator component `build_hydra` inside the `hydra` Base Component. Which is itself stored in `components/hydra`.

`build_hydra` is a Text DAT synced to `assets/scripts/hydra/build_hydra.py`. It is *imported*, not run, so all the commands go to the Textport:

```python
b = mod('/project1/hydra/build_hydra')

b.build_all(op('/project1/hydra'))    # build everything (replaces same-named components)
b.rebuild(op('/project1/hydra'))      # wipe all generated components, then build
b.clear(op('/project1/hydra'))        # wipe only
b.build_audio(op('/project1/hydra'))  # just hydra_fft
b.build(spec, op('/project1/hydra'))  # a single component, from one spec dict (see b.load_specs())
```

`build_all` takes `layout=False`, `audio=False`, `tox=False`, `palette=False` to skip those stages, e.g. `b.build_all(op('/project1/hydra'), palette=False)`. `rebuild` always runs all of them.

BE AWARE: By default a build automatically generates and puts components to your Palette as well, under `/My Components/Hydra`. I do it not to forget to update them and not to do it by hand, but you might have concerns on this behaviour. Pass `palette=False` to `build_all` to skip it.

ALSO BE AWARE: `clear` and `rebuild` destroy **every** `hydra_*` component and **every** Annotate COMP directly in the target container, including annotations you added by hand. Keep the library container for generated content only, and patch with spawned copies elsewhere (see below).

### Exporting

```python
b.export_tox(op('/project1/hydra'))      # write components/hydra/<group>/hydra_<fn>.tox
b.export_palette(op('/project1/hydra'))  # write into the TD user palette
b.export_palette(op('/project1/hydra'), root='/some/other/Palette')
b.layout_groups(op('/project1/hydra'), b.load_specs())   # only re-arrange and re-annotate the groups
```

Every `.tox` is self-contained: the function spec, the compiler and every callback live inside it, nothing is file-synced. Export only writes and never deletes, so a renamed function leaves its old `.tox` behind. Refresh the Palette pane after an export, it does not watch the folder.

### Upgrading placed copies and versions

A placed copy carries its own internals, so a change in the builder or the compiler does not reach it by itself. Every component has a read-only **Version** page: `version` (the builder's `VERSION`), `compiler` (hash of the embedded `hydra_compile.py`) and `built` (time of the build or last upgrade).

```python
b.upgrade(op('/project1'))          # bring every placed copy under it, recursively, up to the current code
b.version_report(op('/project1'))   # list components not built from the current code; empty = all current
```

`upgrade` keeps the wiring, parameter values and node positions, creates whatever the copy lacks and rewrites only what is generated (spec, compiler, callbacks, shader). It identifies components by the spec stored on them (or their `hydra:fn:` tag), never by name, so renamed copies are recognised too.

After a `hydra` update upstream: run `./assets/scripts/hydra/generate-hydra-functions.sh` to refresh the JSON, then `b.rebuild(...)` and `b.upgrade(...)` in TD.

When reporting a problem, the version and compiler hash of the component involved say exactly which code it runs.

![Hydra Scale component parameters](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/hydra-scale-params-00.png?raw=true)

## Structure

* `Hydra.toe` — the project containing `hydra` base component (`hydra.tox`) already set up to make cloning them or building new versions easier;
* `components/hydra/hydra.tox` — the `hydra` base component containing all the functions-components as well as the generator (`build_hydra`);
* `components/hydra/<group>/hydra_<fn>.tox` — the components files themselves.
* `assets/scripts/hydra/*` — the code for generating components, the main script is `build_hydra.py`;
* `assets/scripts/hydra-functions.json` — the source of `hydra` functions and their arguments used when building; Converted from `hydra` sources and can easily be updated;
* `assets/scripts/hydra/shader/<fn>.frag` — fragment shader source for every `hydra` function, used inside the components;
* `assets/scripts/hydra/hydra_seq.py` — a helper to work with `hydra`-like sequences in TD: e.g. `[1, 2, 3, 4].fast()`. But since all of them can easily be recreated using basic TD functionality, it is left for academic purposes mostly;

![Structure](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/structure-02.png?raw=true)

## Features

`build_hydra` script has many helpers. All the ones taking a container search it recursively, nested containers included.

### Spawning

The generated components are a library — patch with copies of them, not with the originals:

* `b.spawn(['osc', 'osc', 'rotate', 'scale'])` would spawn copies of those components from the library into the library's parent (your project root, by default);
  * `b.spawn(['osc*3', 'rotate'])` or `b.spawn('osc*3 rotate scale')` — counts and a single string work too;
  * pass `, dest=op('/project1/sketch')` to spawn them to some other destination;
  * pass `, postfix='_a'` to spawn them with postfix after the name (`hydra_osc_a`); repeats get a numeric suffix (`hydra_osc`, `hydra_osc1`);
  * pass `, lib=op('/some/other/hydra')` to spawn from a different library;
* `spawn` returns the created components, so you can wire them right away:

```python
a, n, m = b.spawn(['osc', 'noise', 'modulate'])
m.inputConnectors[0].connect(a)   # source
m.inputConnectors[1].connect(n)   # modulator
```

Copies land outside the library on purpose: they inherit the `hydra` tag, so `clear()` / `rebuild()` of the library would destroy them too.

### Modes: Compiled and Image

Every component has a **Mode** on its **Pipeline** page:

* **Compiled** (default) — hydra's own model: the component walks the wiring upstream and fuses every Compiled hydra component into one shader, the way hydra does, so `osc → rotate → scale` evaluates `osc(rotate(scale(st)))` in a single pass: nothing is resampled, nothing seams;
* **Image** — renders this component on its own and makes it a texture for everything downstream. Use it for a slow source shared by several branches or one that doesn't change over time; keep it out of the way of `rotate` / `scale` / `kaleid`, since downstream of it they sample a finite texture again.

```python
b.set_mode(op('/project1/sketch'), 'image')     # or 'compiled', on every component under it
```

A chain recompiles by itself on rewiring, renaming, Viewer flag or Mode change; the **Compile** pulse forces it. Parameter and CHOP changes need no recompile. Compiled components that nothing looks at (no Viewer, no output) are not compiled at all.

### Time

The functions that use `time` (`osc`, `noise`, `voronoi`, `gradient`, `rotate`, `scroll*`, `modulateScroll*`) have a **Time Sync** page with a **Time** parameter holding `absTime.seconds`. Replace it with any expression (Timer CHOP, a slowed clock, ...) and pulse **Propagate Time Expr** to copy it to every hydra component downstream.

### Resolution and Output

* `b.set_resolution(op('/project1/hydra'), 1280, 1280)` sets given resolution to all Hydra source components at given path (source components such as `osc` or `shape`, all have `Output` tab individually to allow setting it on your own). Everything else follows the resolution of its chain's source. Default is 1280×720; a non-commercial licence caps output at 1280×1280, and `set_resolution` warns when you ask for more;
* `b.set_output(op('/project1/hydra'), smoothness='nearest')` / `b.set_output(op('/project1/hydra'), pixel_format='8-bit')` — set input smoothness and pixel format on every component (matched by substring against TD's menu). `nearest` + 8-bit is what hydra itself uses and keeps feedback loops crisp; 16-bit float keeps negative values when `noise()` feeds `modulate()`.

### Debugging

* `b.version_report(op('/project1'))` — components not built from the current code;
* `b.cook_report(op('/project1/sketch'))` — last-frame GPU and CPU cook time per component;
* `b.dump_shaders(op('/project1'))` — write every generated shader to `build/hydra-shaders/<path>.frag` (git-ignored, export only), pass `root='/some/folder'` to change the place.

### Tags

Every generated component is tagged `hydra`, `hydra:fn:<func>` and `hydra:class:<class>`, so you can find them yourself:

```python
op('/project1/hydra').findChildren(tags=['hydra:class:coord'])
```

`hydra_seq` script can be used to emulate Hydra array arguments which allow to step over a set of values with constant speed or with easing. Same and even much more powerful can be achieved using CHOPs of course, so you have a freedom to choose any way you prefer.

Associate Text DAT with `hydra_seq.py` and then put in any expression:

* `mod('/project1/hydra/hydra_seq').val([0.1, -0.0625, 0.005, 0.00001])` — same as `[0.1, -0.0625, 0.005, 0.00001]` argument in hydra;
* `mod('/project1/hydra/hydra_seq').val([0.1, -0.0625, 0.005, 0.00001], speed=2)` — same as `[0.1, -0.0625, 0.005, 0.00001].fast(2)` argument in hydra;
* `mod('/project1/hydra/hydra_seq').val([0.1, -0.0625, 0.005, 0.00001], smooth=1)` — same as `[0.1, -0.0625, 0.005, 0.00001].smooth()` argument in hydra;
* `mod('/project1/hydra/hydra_seq').val([0.1, -0.0625, 0.005, 0.00001], ease='easeInOutCubic')` — same as `[0.1, -0.0625, 0.005, 0.00001].ease('easeInOutCubic')` argument in hydra;
