# Port of Olivia Jack's Hydra to TouchDesigner

This is a full function-to-component port of Olivia Jack's [`hydra`](https://github.com/hydra-synth) visual synth engine to TouchDesigner.

`hydra` project is built using GLSL functions, in this case its WebGL.

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

## Function-to-Component Logic

Each Hydra function is converted to a corresponding TD Component holding its shader source inside, together with wiring of parameters to shader inputs. Output is mapped to be the output of the component (TOP).

For every numeric argument, both CHOP-based input and parameter key/value pair are created (on `Hydra` tab). If there is no input for this argument connected, then the parameter value/expession is used. So you can either put values or expressions on the parameters tabs or connect CHOPs instead, both ways are supported.

For source arguments any TOP component may be passed in the input.

Also includes `hydra_fft` CHOP which replicates `a.fft[n]` functionality of Hydra, but creates a channel output for every bin.

## Building

For details on building, see `assets/scripts/hydra/Build.md`.

`Hydra.toe` project includes all the function-components and the generator component `build_hydra` inside the `hydra` Base Component. Which is itself stored in `components/hydra`.

Components are rewritten all the time when `build_hydra.py` is changed and those lines performed in Textport:

```python
b = mod('/project1/hydra/build_hydra')
b.rebuild(op('/project1/hydra'))
```

BE AWARE: In this case it automatically generates and puts components to your Palette as well, under `/My Components/Hydra`. I do it not to forget to update them and not to do it by hand, but you might have concerns on this behaviour.

![Hydra Scale component parameters](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/hydra-scale-params-00.png?raw=true)

## Structure

* `Hydra.toe` — the project containing `hydra` base component (`hydra.tox`) already set up to make cloning them or building new versions easier;
* `components/hydra/hydra.tox` — the `hydra` base component containing all the functions-components as well as the generator (`build_hydra`);
* `components/hydra/<group>/hydra_<fn>.tox` — the components files themselves.
* `assets/scripts/hydra/*` — the code for generating components, the main script is `build_hydra.py`;
* `assets/ceripts/hydra-functions.json` — the source of `hydra` functions and their arguments used when building; Converted from `hydra` sources and can easily be updated;
* `assets/scripts/hydra/shader/<fn>.frag` — fragment shader source for every `hydra` function, used inside the components;
* `assets/scripts/hydra/hydra_seq.py` — a helper to work with `hydra`-like sequences in TD: e.g. `[1, 2, 3, 4].fast()`. But since all of them can easily be recreated using basic TD functionality, it is left for academic purposes mostly;

![Structure](https://github.com/shamansir/ojack-hydra-td/blob/main/screens/structure-02.png?raw=true)
