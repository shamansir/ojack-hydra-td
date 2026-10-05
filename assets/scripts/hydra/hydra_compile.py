"""Compile a chain of hydra components into one shader, the way hydra does.

Hydra never rasterizes intermediate stages. `osc().rotate().posterize()` becomes
a single nested expression, `posterize(osc(rotate(st, ...), ...), ...)`, so the
source is evaluated analytically at the final coordinate -- no wrap, no seam, no
resampling. This module walks the TD wiring upstream from a component and emits
that same expression (hydra src/generate-glsl.js, v1.3.29), then installs it in
the component's GLSL TOP.

Embedded verbatim into every component as the `compile` Text DAT, so an
exported .tox carries it -- this file is the editable master. Re-run the
builder (or `upgrade`) after changing it.

Per component, in Mode = Compiled:

  - every upstream hydra component becomes one instance of its function, body
    verbatim, renamed <fn>_<k>, with its arguments as uniforms u<k>_<arg> that
    read that component's own CHOP input / parameter
  - `time` is #defined per instance to that component's own Time parameter, so
    per-component clocks survive; with equal clocks this is exactly hydra
  - anything that is not a compilable hydra component -- a plain TD TOP, a
    component in Image or Coordinates mode, the texture fed to `src`/`prev` --
    is a boundary, read as texture(<sampler>, fract(uv)), which is what hydra's
    own src() does
  - the GLSL TOP is unwired from its In TOPs, so upstream components do not
    cook for it

Only components that something actually looks at are compiled: Viewer on, or
an output -- their texture is read by something outside the compiled chain.
Everything else keeps its last shader and, with nothing pulling it, never cooks.
"""

HYDRA_TAG = 'hydra'
SPEC_KEY = 'hydra_spec'          # set by the builder: see build_hydra.store_spec
PENDING_KEY = 'hydra_compile_frame'
MAX_DEPTH = 64

# `src` and `prev` read a texture -- in hydra a buffer, never an inlined chain
TEXTURE_INPUT = {'src': 'source', 'prev': 'source'}

SIGNATURE = {
    'src':          ('vec4', ['vec2 _st']),
    'coord':        ('vec2', ['vec2 _st']),
    'color':        ('vec4', ['vec4 _c0']),
    'combine':      ('vec4', ['vec4 _c0', 'vec4 _c1']),
    'combineCoord': ('vec2', ['vec2 _st', 'vec4 _c0']),
}


# --- reading the graph ---------------------------------------------------------

def spec_of(o):
    if o is None or not o.isCOMP or HYDRA_TAG not in o.tags:
        return None
    return o.fetch(SPEC_KEY, None, search=False)


def mode_of(o):
    names = [p.name for p in o.customPars]
    return o.par.Mode.eval() if 'Mode' in names else 'image'


def compilable(o):
    """A hydra component this chain can inline instead of reading its texture."""
    spec = spec_of(o)
    return (spec is not None and spec['name'] != 'coords'
            and mode_of(o) != 'coords')


def upstream(comp, label):
    """(op, TOP) wired into the component input whose In TOP is `label`."""
    for c in comp.inputConnectors:
        if c.inOP is not None and c.inOP.name == label and c.connections:
            src = c.connections[0]
            owner = src.owner
            top = src.outOP if owner.isCOMP and src.outOP is not None else owner
            return owner, top
    return None, None


def is_boundary_input(comp, label):
    spec = spec_of(comp)
    return spec is None or TEXTURE_INPUT.get(spec['name']) == label \
        or not compilable(comp) or mode_of(comp) != 'compiled'


def is_output(comp):
    """True when something outside a compiled chain reads this texture."""
    targets = [conn for oc in comp.outputConnectors for conn in oc.connections]
    if not targets:
        return True
    for conn in targets:
        label = conn.inOP.name if conn.inOP is not None else None
        if is_boundary_input(conn.owner, label):
            return True
    return False


def hydra_neighbours(comp, outputs=True):
    side = comp.outputConnectors if outputs else comp.inputConnectors
    return [conn.owner for c in side for conn in c.connections
            if spec_of(conn.owner) is not None]


def downstream(comp):
    seen, queue, found = {comp.id}, [comp], []
    while queue:
        for nxt in hydra_neighbours(queue.pop(0)):
            if nxt.id not in seen:
                seen.add(nxt.id)
                queue.append(nxt)
                found.append(nxt)
    return found


def par_name(hydra_name):
    return hydra_name[0].upper() + hydra_name[1:].lower()


# --- code generation -------------------------------------------------------------

class Chain:
    """One compiled shader: instances, uniforms, samplers, and the expression."""

    def __init__(self):
        self.uniforms = []       # (glsl type, name, (expr per component,))
        self.samplers = []       # (name, TOP path)
        self.functions = []      # instance definitions, in dependency order
        self.utils = {}          # utility name -> text, first use wins
        self.instances = {}      # comp.id -> (fn name, [uniform names])
        self.boundaries = {}     # TOP path -> sampler name
        self.resolution = False  # an instance uses hydra's `resolution`

    # entry point: the expression for `comp` evaluated at coordinate `uv`
    def gen(self, comp, uv, depth=0):
        if depth > MAX_DEPTH:
            raise RuntimeError(f'chain deeper than {MAX_DEPTH} at {comp.path}')
        spec = spec_of(comp)
        fn, args = self.define(comp, spec)
        a = ''.join(', ' + x for x in args)
        kind = spec['type']
        inp = lambda label, at: self.input(comp, label, at, depth)

        if kind == 'src':
            return f'{fn}({uv}{a})'
        if kind == 'coord':
            return inp('source', f'{fn}({uv}{a})')
        if kind == 'color':
            return f"{fn}({inp('source', uv)}{a})"
        if kind == 'combine':
            return f"{fn}({inp('source', uv)}, {inp('with', uv)}{a})"
        if kind == 'combineCoord':
            # hydra: f0(modulate(uv, f1(uv), ...)) -- the modulator is evaluated
            # at the incoming uv, the source at the modulated one
            return inp('source', f"{fn}({uv}, {inp('modulator', uv)}{a})")
        raise RuntimeError(f'{comp.path}: unknown class {kind!r}')

    def input(self, comp, label, uv, depth):
        owner, top = upstream(comp, label)
        if owner is None:
            return 'vec4(0.0)'                       # nothing wired: transparent black
        if compilable(owner) and spec_of(comp)['name'] not in TEXTURE_INPUT:
            return self.gen(owner, uv, depth + 1)
        return f'texture({self.sampler(top)}, fract({uv}))'

    def sampler(self, top):
        path = top.path if top is not None else ''
        if path not in self.boundaries:
            name = f's{len(self.boundaries)}'
            self.boundaries[path] = name
            self.samplers.append((name, path))
        return self.boundaries[path]

    def uniform(self, gtype, name, exprs):
        self.uniforms.append((gtype, name, tuple(exprs)))
        return name

    def define(self, comp, spec):
        """Emit one instance of this component's function; return (name, args)."""
        if comp.id in self.instances:
            return self.instances[comp.id]

        k = len(self.instances)
        name, kind = spec['name'], spec['type']
        fn = f'{name}_{k}'
        ret, lead = SIGNATURE[kind]
        p = comp.path
        alias = spec.get('alias')
        body = spec['glsl']
        if name == 'sum':
            # hydra's `sum` closes itself early to add a vec2 overload, which
            # would be redefined per instance -- keep only the vec4 function
            body = body.split('float sum(vec2')[0].rstrip().rstrip('}').rstrip()

        passed = [i for i in spec['inputs']
                  if i['type'] != 'sampler2D' and not i.get('extension')]
        extension = [i for i in spec['inputs'] if i.get('extension')]

        args = []
        for i in passed + extension:
            n = i['name']
            un = f'u{k}_{n}'
            if i['type'] == 'float':
                chop = f"op('{p}/{n}')"
                self.uniform('float', un, (f'{chop}[0].eval() if {chop} and '
                                           f'{chop}.numChans else '
                                           f"op('{p}').par.{par_name(n)}",))
            else:                                       # vecN: straight from pars
                pars = sorted(comp.pars(par_name(n) + '*'), key=lambda q: q.name)
                self.uniform(i['type'], un,
                             [f"op('{p}').par.{q.name}" for q in pars])
            args.append(un)

        out = [f'// {name}  <-  {p}']
        undef = []
        if 'time' in spec.get('uses', ()):
            self.uniform('float', f'u{k}_time', (f"op('{p}').par.Time",))
            out.append(f'#define time u{k}_time')
            undef.append('time')
        if alias:
            owner, top = upstream(comp, TEXTURE_INPUT[name])
            out.append(f'#define {alias} {self.sampler(top)}')
            undef.append(alias)
        if 'resolution' in spec.get('uses', ()):
            self.resolution = True

        sig = lead + [f"{i['type']} {i['name']}" for i in passed]
        out += [f"{ret} {fn}({', '.join(sig)}) {{", body.rstrip(), '}']
        out += [f'#undef {u}' for u in undef]

        if extension:
            # blend_amount: fade the result back toward the source, applied
            # around the call so the body stays verbatim (see emit_frags)
            wsig = lead + [f"{i['type']} {i['name']}" for i in passed + extension]
            inner = ', '.join([s.split()[1] for s in lead] + [i['name'] for i in passed])
            out += [f"{ret} {fn}_x({', '.join(wsig)}) {{",
                    f'   return mix(_c0, {fn}({inner}), amount);', '}']
            fn = f'{fn}_x'

        for uname, text in spec.get('utils', {}).items():
            self.utils.setdefault(uname, text)
        self.functions.append('\n'.join(out))
        self.instances[comp.id] = (fn, args)
        return fn, args

    def shader(self, expr, path):
        lines = [f'// hydra chain compiled for {path}',
                 '// GENERATED by hydra_compile on every rewire -- do not edit.', '']
        lines += [f'uniform {t} {n};' for t, n, _ in self.uniforms]
        if self.resolution:
            lines.append('uniform vec2 resolution;')
        # boundaries arrive on the GLSL TOP's inputs, in this order
        lines += [f'#define {n} sTD2DInputs[{i}]'
                  for i, (n, _) in enumerate(self.samplers)]
        lines += ['', '#define texture2D texture', '', 'out vec4 fragColor;', '']
        for uname, text in self.utils.items():
            lines += [f'// --- {uname}, from hydra utility-functions.js ---', text, '']
        for f in self.functions:
            lines += [f, '']
        lines += ['void main() {',
                  '   vec2 st = vUV.st;',
                  f'   fragColor = TDOutputSwizzle({expr});',
                  '}']
        return '\n'.join(lines) + '\n'


# --- applying it in TouchDesigner -----------------------------------------------

def _set_uniforms(glsl, uniforms):
    """[(name, (expr, ...))] onto the Vectors page."""
    glsl.seq.vec.numBlocks = max(len(uniforms), 1)
    for i, (uname, exprs) in enumerate(uniforms):
        glsl.par[f'vec{i}name'] = uname
        for c in 'xyzw':
            p = glsl.par[f'vec{i}value{c}']
            p.mode = ParMode.CONSTANT
            p.val = 0
        for c, expr in zip('xyzw', exprs):
            glsl.par[f'vec{i}value{c}'].expr = expr


def _set_boundaries(comp, glsl, samplers):
    """Boundary textures, wired in as GLSL TOP inputs through Select TOPs.

    The GLSL TOP has no Samplers page (the GLSL MAT does), so a texture from
    elsewhere in the network can only arrive on an input. The shader maps each
    boundary name onto sTD2DInputs[i]. Expects the inputs to be disconnected.
    """
    for i, (name, path) in enumerate(samplers):
        sel = comp.op(f'boundary{i}') or comp.create(selectTOP, f'boundary{i}')
        sel.nodeX, sel.nodeY = -300, -600 - 120 * i
        sel.par.top = path
        glsl.inputConnectors[i].connect(sel)
    i = len(samplers)
    while comp.op(f'boundary{i}'):              # left over from a longer chain
        comp.op(f'boundary{i}').destroy()
        i += 1


def _set_menu(par, *needles):
    for i, n in enumerate(par.menuNames):
        if all(x in n.lower() for x in needles):
            par.menuIndex = i
            return


def _resolution(comp):
    """(w expr, h expr) of the chain's canvas: the root along `source` inputs."""
    cur = comp
    for _ in range(MAX_DEPTH):
        spec = spec_of(cur)
        if spec['type'] == 'src' and spec['name'] not in TEXTURE_INPUT:
            pars = sorted((q for q in cur.customPars
                           if q.name.startswith('Resolution')), key=lambda q: q.name)
            if len(pars) >= 2:
                return tuple(f"op('{cur.path}').par.{q.name}" for q in pars[:2])
            return None
        label = TEXTURE_INPUT.get(spec['name'], 'source')
        owner, top = upstream(cur, label)
        if owner is None:
            return None
        if compilable(owner) and spec['name'] not in TEXTURE_INPUT:
            cur = owner
            continue
        return (f"op('{top.path}').width", f"op('{top.path}').height")
    return None


def detach(comp):
    glsl = comp.op('glsl')
    for c in glsl.inputConnectors:
        c.disconnect()


def restore_image(comp):
    """Back to the per-node shader: file-synced DAT, In TOPs, local uniforms."""
    spec = spec_of(comp)
    glsl = comp.op('glsl')
    if glsl.par.pixeldat.eval() != comp.op('pixel'):
        glsl.par.pixeldat = comp.op('pixel')
    detach(comp)
    _set_boundaries(comp, glsl, [])
    for i, name in enumerate(spec.get('tops', [])):
        t = comp.op(name)
        if t:
            glsl.inputConnectors[i].connect(t)
    _set_uniforms(glsl, spec.get('uniforms', []))
    if spec['type'] != 'src' or spec['name'] in TEXTURE_INPUT:
        _set_menu(glsl.par.outputresolution, 'input')


def compile_chain(comp):
    """Generate and install the fused shader for `comp`. Returns stage count."""
    chain = Chain()
    expr = chain.gen(comp, 'st')
    text = chain.shader(expr, comp.path)

    glsl = comp.op('glsl')
    dat = comp.op('pixel_compiled')
    if not dat:
        dat = comp.create(textDAT, 'pixel_compiled')
        dat.nodeX, dat.nodeY = 0, -300
    dat.text = text
    if glsl.par.pixeldat.eval() != dat:
        glsl.par.pixeldat = dat

    uniforms = [(n, exprs) for _, n, exprs in chain.uniforms]
    if chain.resolution:
        uniforms.append(('resolution', ('me.width', 'me.height')))
    _set_uniforms(glsl, uniforms)
    _set_boundaries(comp, glsl, chain.samplers)

    res = _resolution(comp)
    if res is not None and spec_of(comp)['type'] != 'src':
        _set_menu(glsl.par.outputresolution, 'custom')
        glsl.par.resolutionw.expr, glsl.par.resolutionh.expr = res
    return len(chain.instances)


def compile_now(comp):
    comp.unstore(PENDING_KEY)
    if spec_of(comp) is None or not comp.op('glsl'):
        return
    try:
        if mode_of(comp) != 'compiled':
            # only a component that was compiled before has anything to undo
            if comp.op('glsl').par.pixeldat.eval() != comp.op('pixel'):
                restore_image(comp)
            return
        detach(comp)
        if not (comp.viewer or is_output(comp)):
            return                   # nothing looks at it; compiled when that changes
        n = compile_chain(comp)
        print(f'{comp.path}: compiled {n} stage(s)')
    except Exception as e:
        print(f'  !! {comp.path}: compile failed ({e})')


def schedule(comp, down=True, up=False):
    """Compile next frame, once per component however many triggers arrive."""
    targets = [comp] + (downstream(comp) if down else []) \
        + (hydra_neighbours(comp, outputs=False) if up else [])
    frame = absTime.frame
    for t in targets:
        if t.fetch(PENDING_KEY, None, search=False) == frame:
            continue
        t.store(PENDING_KEY, frame)
        run('args[0].op("compile").module.compile_now(args[0])', t,
            delayFrames=1, delayRef=op.TDResources)
