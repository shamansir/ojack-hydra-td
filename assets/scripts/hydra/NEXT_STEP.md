# Next step: reduce to Compiled + Image

Written 2026-10-06, after Compiled mode was confirmed working in TouchDesigner on
`osc().rotate().scale()` — seamless, no frame drops. Not started yet.

**Goal:** keep only two modes, **Compiled** (the default) and **Image** (to save
work where it helps), remove Coordinates mode and Seamless tiling, and make
Compiled cheaper for complex chains.

**Precondition:** the more complex sketches are moved to Compiled and confirmed
working before Coordinates and Seamless are removed (step 6).

## Suggested order

1. **#3 statements** and **#5 recompile cost**: low risk, and they help the
   complex sketches being moved over now.
2. **#2 Image as a boundary**, then **#1 Image mode from the compiler**: they
   change what Image means and remove the most code.
3. **#6 remove Coordinates and Seamless**, once the complex sketches are proven.
4. **#4 uniform expressions**: needs testing in TD first.

Rough net effect: about 600 lines of Python, the 52 shader files and about 150
lines of `BUILD.md` removed; about 50 lines added to the compiler.

---

## 1. Image mode from the compiler (biggest cut)

Image mode is compiling with nothing inlined: the component's own function, with
its direct inputs read as textures. For every class, the compiler's texture read
`texture(s, fract(uv))` gives the same result as today's per-class `main()` in
`emit_frags.py`:

| class | today's Image `main()` | compiler, nothing inlined |
|---|---|---|
| src | `fn(vUV.st)` | `fn(st)` |
| coord | `texture(in0, fract(fn(st)))` | same |
| color | `fn(texture(in0, st))` | `fn(texture(in0, fract(st)))` — same inside the frame |
| combine | `fn(texture(in0, st), texture(in1, st))` | same, with `fract` |
| combineCoord | `texture(in0, fract(fn(st, texture(in1, st))))` | same, with `fract` |

So one code path (`Chain` with an "inline nothing" switch) produces both modes.
In Image mode the In TOPs are the boundaries, wired straight in, with no Select
TOPs needed.

That removes:

- `emit_frags.py` (321 lines), the 52 generated `shader/*.frag` files and the
  file-synced `pixel` DAT. `_utils.glsl` stays — `store_spec` reads it.
- `shader_text`, `_uniforms`, `apply_uniforms` in `build_hydra.py`. The compiler
  already generates uniforms from the spec stored on each component
  (`hydra_spec`).
- Most of `upgrade()`. Shaders are generated from each component's stored spec,
  so a shader change can no longer leave placed copies out of sync (the
  "checkerboard" problem in `BUILD.md`). Re-storing the spec becomes the whole
  repair.
- `uses_time` / `uses_coordmode` reading shader text — the spec's `uses` already
  says it.

Cost: no readable `.frag` per function any more. The generated shader is still
visible in each component's `pixel_compiled` (rename it to `pixel`).

## 2. Image means "render this as a texture here"

Today Compiled inlines upstream components even when they're in Image mode
(`compilable()` only excludes Coordinates mode). Treating Image as a boundary
instead gives Image a real job: a **cache point**.

- Compiled re-evaluates a shared upstream once per use. One `noise` feeding five
  branches runs five times per pixel.
- A slow source that doesn't change over time (`voronoi` with speed 0) gets
  re-evaluated every frame inside the chain. Rendered as a texture, it only cooks
  when its parameters change.

Setting such a node to Image means it renders once, and everything downstream
reads its texture. That's the case where Image actually saves work.

Changes in `hydra_compile.py`: `compilable()` requires Mode = Compiled;
`is_boundary_input()` already treats a non-compiled consumer as reading the
texture, so `is_output()` follows without changes.

## 3. Emit statements instead of one nested expression

`Chain.gen` for `combineCoord` puts the incoming `uv` expression into the shader
twice — once in the modulate call, once for the modulator:

```python
return inp('source', f"{fn}({uv}, {inp('modulator', uv)}{a})")
```

With k chained `modulate*` the shader text grows as 2^k. Hydra's generator
(`generate-glsl.js`, `shaderString`) has the same blow-up. GLSL compilers often
merge repeated identical subexpressions, but not reliably, and noise-heavy code is
expensive to repeat.

Fix: store each coordinate in a local variable.

```glsl
vec2 uv1 = modulate_3(st, noise_4(st, u4_scale, u4_offset), u3_amount);
vec2 uv2 = modulate_5(uv1, noise_6(uv1, u6_scale, u6_offset), u5_amount);
fragColor = TDOutputSwizzle(osc_7(uv2, u7_frequency, u7_sync, u7_offset));
```

The result is identical to hydra, because every function is pure, and the code
grows linearly. `gen()` appends lines to a `main` body list and returns a
variable name. Caching results by `(comp.id, uv variable)` also gives
shared-input reuse for free: the same component at the same coordinate becomes
one variable. About 30 lines of `Chain.gen`.

## 4. Uniform expressions (CPU, every frame)

Each argument's uniform is currently:

```python
op('/p/x/frequency')[0].eval() if op('/p/x/frequency') and op('/p/x/frequency').numChans else op('/p/x').par.Frequency
```

That's three `op()` lookups in Python per argument, per compiled component, per
frame. Viewing intermediates multiplies the count.

- **Cheap fix:** the fallback Constant CHOP guarantees the In CHOP has a channel,
  so the guard can go: `op('/p/x/frequency')[0]`. Simple expressions like that
  may be handled by TD's optimized-expression path, which skips Python. Not yet
  verified that `[0]` qualifies — compare `cook_report` CPU times before and
  after.
- **Bigger fix:** merge all of a chain's arguments into one CHOP and bind it as a
  uniform array on the GLSL TOP's Arrays page. No Python per frame at all. Needs
  checking in TD first: the Arrays page parameter names, and whether one Select
  CHOP can take several CHOP paths.

## 5. Recompile cost

- Compare the generated text and uniforms with what's already installed, and skip
  writing if nothing changed. Every unrelated flag change (display, bypass, lock)
  currently rewrites `pixel_compiled` and forces a GLSL recompile.
- `onFlagChange` in `CHAIN_EXEC` (`build_hydra.py`) could react only to the
  viewer flag — first print what `flag` actually contains in this TD build.

## 6. Remove Coordinates and Seamless

| where | what goes |
|---|---|
| `emit_frags.py` | `uvmode` branches, `COORD_IN`, `SEAMLESS`, `MAIN_SEAMLESS` (the whole file, if #1 is done) |
| shaders | `coords.frag`, the `hydra_coords` component, `coords` in `EXTRA_SPECS` / `EXTRA_MEMBERS` |
| `build_hydra.py` | the `coords` In TOP on sources, `uses_coordmode`, `uses_seamless`, `make_seamless_pars`, `coords` in `mode_menu`, the `Coordmode` migration |
| `hydra_compile.py` | the `coords` checks in `compilable`, `is_boundary_input`, `_resolution` |
| `BUILD.md` | the "Coordinate mode" and "Seamless tiling" sections (~120 lines), replaced by a short Image vs Compiled note |
| `claude/HYDRA_RESEARCH.md`, the Hydra vs TouchDesigner doc | the three-modes comparison becomes two |

`upgrade()` needs one cleanup step for placed copies: remove the `Seamless` and
`Seamwidth` parameters and the `coords` In TOP, and map Mode `coords` to
`compiled`.

Make **Compiled the default** Mode in `make_mode_par` at the same time.

## 7. Smaller items

- Old migrations in `upgrade()` — the `Coordmode` toggle, the bare `hydra:<x>`
  tag scheme, Connect Order fixes, missing In CHOP plumbing — can be deleted once
  every placed copy has been upgraded once.
- The compiler is copied into every component (`compile` DAT, ~400 lines each).
  One shared module would mean fewer DATs and one place to edit, but a `.tox`
  dropped into another project would then need that module too. Keep the copies:
  `.tox` portability was a stated goal.
