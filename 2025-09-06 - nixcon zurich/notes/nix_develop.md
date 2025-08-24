# How `nix develop` Works: Under the Hood

This document explains the internal mechanics of how `nix develop` creates and populates development shells, based on analysis of the Nix codebase.

## How Package Contents Are Made Available

The contents of packages are made available in the `nix develop` shell through a sophisticated environment replication process:

### Environment Capture Process

1. **Derivation Analysis** (`src/nix/develop.cc:234-309`): When you run `nix develop`, Nix first takes the target derivation and creates a modified version that captures the build environment rather than actually building the package.

2. **get-env.sh Script** (`src/nix/get-env.sh`): Nix injects a special script called `get-env.sh` that sources the stdenv setup script (`$stdenv/setup`) and then captures:
   - All environment variables (exported and non-exported)
   - All bash functions
   - Associative arrays
   - Structured attributes (if enabled)

3. **JSON Environment Export** (`src/nix/get-env.sh:15-119`): The captured environment is serialized to JSON format containing:
   ```json
   {
     "variables": {
       "VAR_NAME": {"type": "exported", "value": "..."},
       "ARRAY_VAR": {"type": "array", "value": ["item1", "item2"]}
     },
     "bashFunctions": {
       "functionName": "function body..."
     }
   }
   ```

4. **Environment Reconstruction** (`src/nix/develop.cc:154-179`): The JSON environment is parsed and converted back to bash script format that recreates all the variables, exports, arrays, and functions in the interactive shell.

### Key Environment Variables

The most important environment variables that make package contents available include:
- `PATH`: Contains `$out/bin` directories from all build dependencies
- `PKG_CONFIG_PATH`, `CMAKE_PREFIX_PATH`: For build tool discovery
- Output paths like `$out`, `$dev`, etc. are redirected to mutable directories

## Hook Scripts and Their Sources

Hook scripts in `nix develop` come from multiple sources:

### stdenv Setup Script
- **Primary Source**: `$stdenv/setup` is sourced in `get-env.sh:8`
- **Content**: This script defines the core build phases and hook infrastructure
- **Functions**: Defines `runHook` function and phase functions like `configurePhase`, `buildPhase`, etc.

### Package-Specific Hooks
- **shellHook**: Custom shell setup code defined in derivations
- **Phase Hooks**: `preConfigureHooks`, `postInstallHooks`, etc.
- **Setup Hooks**: Scripts from build dependencies that extend the build environment

### Hook Execution in develop.cc
- `shellHook` is explicitly handled (`src/nix/develop.cc:362,378`):
  ```cpp
  out << "unset shellHook\n";  // Clear initially
  // ... environment setup ...
  out << "eval \"${shellHook:-}\"\n";  // Execute at the end
  ```

- Phase execution (`src/nix/develop.cc:604`):
  ```cpp
  script += fmt("runHook %1%Phase\n", *phase);
  ```

## Step-by-Step Execution of `nix develop`

Here's the detailed execution flow when someone runs `nix develop`:

### 1. Command Parsing and Setup (`src/nix/develop.cc:583`)
- Parse installable (flake reference or derivation path)
- Initialize store connections
- Set up development settings (bash prompt, etc.)

### 2. Environment Capture (`src/nix/develop.cc:585`)
- Call `getBuildEnvironment()` which:
  - Calls `getShellOutPath()` to get or create the environment derivation
  - If needed, calls `getDerivationEnvironment()` to build the modified derivation

### 3. Modified Derivation Building (`src/nix/develop.cc:234-309`)
```cpp
// Create modified derivation that just captures environment
drv.args = {store->printStorePath(getEnvShPath)};  // Replace with get-env.sh
drv.name += "-env";  // Rename to indicate it's environment-only
// Remove validation checks that would prevent execution
drv.env.erase("allowedReferences");
// Build the modified derivation
store->buildPaths({DerivedPath::Built{...}});
```

### 4. Environment JSON Parsing (`src/nix/develop.cc:504`)
```cpp
return {BuildEnvironment::parseJSON(readFile(store->toRealPath(shellOutPath))), strPath};
```

### 5. Shell Script Generation (`src/nix/develop.cc:591`)
- Create temporary RC file with environment setup
- Generate bash script that:
  - Preserves important shell variables (PATH, XDG_DATA_DIRS)
  - Sets up build environment variables
  - Defines bash functions
  - Executes shellHook

### 6. Bash Shell Selection (`src/nix/develop.cc:635-675`)
```cpp
Path shell = "bash";  // Default fallback
// Try to get nixpkgs#bashInteractive
auto bashInstallable = make_ref<InstallableFlake>(..., "bashInteractive", ...);
// Look for bin/bash in the result
shell = store->printStorePath(path) + "/bin/bash";
```

### 7. Shell Execution (`src/nix/develop.cc:707`)
```cpp
execProgramInStore(store, UseLookupPath::Use, shell, args, buildEnvironment.getSystem());
```

## Which Bash Shell `nix develop` Uses

`nix develop` uses a specific bash selection strategy (`src/nix/develop.cc:635-675`):

1. **Primary Choice**: `nixpkgs#bashInteractive` - A full-featured interactive bash
2. **Fallback**: System `bash` from PATH if nixpkgs bash is unavailable
3. **Error Handling**: Throws error if neither is available with bin/bash

The shell path is explicitly set via `setEnv("SHELL", shell.c_str())` to ensure the build environment uses the chosen bash, not the system default.

## Differences Between `nix-shell` and `nix develop`

### Architecture Differences

**nix-shell** (`src/nix/nix-build/nix-build.cc:629-644`):
- Generates inline bash script that sources `$stdenv/setup` directly
- Simpler string-based environment setup
- Uses `execvp` to start bash with generated script

**nix develop** (`src/nix/develop.cc`):
- Builds a separate derivation to capture environment as JSON
- More sophisticated environment representation (BuildEnvironment class)
- Uses `execProgramInStore` for better store path handling
- Supports structured attributes and more complex variable types

### Environment Handling

**nix-shell**:
```cpp
"[ -e $stdenv/setup ] && source $stdenv/setup; "
"if [ \"$(type -t runHook)\" = function ]; then runHook shellHook; fi; "
```

**nix develop**:
```cpp
// Separate JSON-based environment capture and reconstruction
buildEnvironment.toBash(out, ignoreVars);
out << "eval \"${shellHook:-}\"\n";
```

### Key Advantages of `nix develop`
1. **Better Flake Integration**: Native support for development shells in flakes
2. **Environment Portability**: Can save/load environments via profiles
3. **Structured Attributes**: Full support for complex build configurations  
4. **Path Redirection**: `--redirect` flag for mutable development directories
5. **Phase Execution**: Direct phase execution (`--build`, `--configure`, etc.)

### Legacy Compatibility
Both commands achieve similar results but `nix develop` provides a more robust and extensible architecture for modern Nix development workflows.