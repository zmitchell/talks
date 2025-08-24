## `nix develop` command implementation

`MixEnvironment` constructor and `setEnviron` are in `src/libcmd/command.cc`.
Operates on `StringMap` types via `getEnv`, `setEnv`, and `replaceEnv`.
Those are defined in `src/libutil/environment-variables.cc`.

`Common` is in `src/nix/develop.cc`.

Command description:
```
run a bash shell that provides the build environment of a derivation
```

Actual implementation logic is in `CmdDevelop::run`.
- `getBuildEnvironment`
  - `getShellOutpath`
    - Get the store path for the `devShell` attribute
    - `Installable::toDerivations` -> installable is `"."` (the flake in the current directory).
    - `getDerivationEnvironment`
      - Get the derivation for the `devShell` storepath
      - Add `get-env.sh` to the Nix store.
      - Modify the derivation for the `devShell` attribute to run the `get-env.sh` script instead of whatever it was going to run.
      - Write the new derivation to the store.
      - Build the derivation, which runs `get-env.sh`.
      - `get-env.sh`
        - This is an unholy script that builds a JSON object line by line.
          - Not object attribute by object attribute. Line by line.
        - You can peek at the output by running `nix print-dev-env --json`.
        - It produces an object with two attributes: `bashFunctions`, `variables`.
      - Do some rewriting of the derivation attributes.
        - Make the derivation outputs "deferred"?
      - Compute the store paths for each output.
      - Write and build the derivation to get its store path.
      - The output is the JSON file containing the details of the shell environment
  - Create a `BuildEnvironment` by parsing the JSON file.
- `makeRcScript`
  - Creates an RC script that recreates the build environment
  - There's a small list of variables that it prepends to rather than replacing them
    - `PATH`, `XDG_DATA_DIRS`
  - Ensure that they exist and if they don't, initialize them to an empty string
  - Save a copy of each of them named `nix_saved_<var>`
  - Translate the contents of `BuildEnvironment` to Bash syntax
  - Prepend the build environments values of `PATH`, etc to the saved values and export that

  - Create a temporary directory named `nix-shell.<random>` and point all `TMP`-like variables at it
  - Rewrites the destination path for each of the outputs so that they don't write directly to the Nix store.
    - Since you still have access to the `*Phase` scripts, you could run them manually, and that would now write them to a temporary location rather than the store.
  - Returns this string stream as a string.
- If you're running with debug output, append `set -x`.
- Handle different invocations:
  - Running a particular phase
    - Append `runHook <phase>`
  - Running a specified command via `nix develop --command <args>`
    - Append `exec <args>`
  - Otherwise (i.e. interactive case)
    - Prepend a line that sources `~/.bashrc` if it exists.
    - This means that all of the Nix logic runs _after_ sourcing `.bashrc`
- Write the script somewhere
- Set the shell environment
  - There are flags for telling `nix develop` which variables to keep/discard/add from the existing environment when entering the shell.
- Set `NIX_GCROOT` to the JSON file containing the shell's environment
  - `LocalStore::findRuntimeRoots` scans `/proc` to see if any running processes are holding references to store paths either in their environment, via file descriptors, etc.
- Locate a Bash shell to use
  - First try to find `nixpkgs#bashInteractive`
  - Fall back to system Bash (e.g. just `bash`)
    - Possible syntax incompatibilities?
- Override `SHELL` with the shell we chose.
- Provide arguments to this shell
  - If running a command or phase, provide the script path as an argument
  - If running interactively, pass the rc file via `--rcfile`
  - This ensures that if you Ctrl-C while running a phase or command, you won't be dropped back into an interactive Bash shell.

