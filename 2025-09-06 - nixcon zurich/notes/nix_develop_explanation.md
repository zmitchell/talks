# `nix develop` Implementation Details

This document provides a detailed technical explanation of how `nix develop` is implemented in the Nix codebase, focusing on the internal architecture, data structures, and execution flow.

## Class Hierarchy and Architecture

### Core Classes

The `nix develop` command is built using a layered class hierarchy:

```cpp
// Base command infrastructure
struct InstallableCommand : virtual Args, SourceExprCommand, MixProfile
struct MixProfile : virtual StoreCommand        // Profile management
struct MixEnvironment : virtual Args            // Environment variable handling

// The main implementation classes
struct Common : InstallableCommand, MixProfile  // Shared develop/print-dev-env logic
struct CmdDevelop : Common, MixEnvironment      // Interactive shell command
struct CmdPrintDevEnv : Common, MixJSON         // Environment export command
```

**Key Inheritance:**
- `CmdDevelop` inherits from both `Common` (shared develop logic) and `MixEnvironment` (env var control)
- `Common` provides shared functionality for both `nix develop` and `nix print-dev-env`
- `InstallableCommand` provides the infrastructure for processing Nix installables (flakes, store paths, etc.)

### Command Registration

Commands are registered via static initialization (`src/nix/develop.cc:746-747`):
```cpp
static auto rCmdPrintDevEnv = registerCommand<CmdPrintDevEnv>("print-dev-env");
static auto rCmdDevelop = registerCommand<CmdDevelop>("develop");
```

## BuildEnvironment Data Structure

The `BuildEnvironment` struct (`src/nix/develop.cc:44-223`) is the core data structure that represents a captured build environment:

### Variable Types

```cpp
struct BuildEnvironment {
    using Array = std::vector<std::string>;
    using Associative = StringMap;
    using Value = std::variant<String, Array, Associative>;
    
    struct String {
        bool exported;        // Whether variable should be exported
        std::string value;
    };
    
    std::map<std::string, Value> vars;           // All environment variables
    StringMap bashFunctions;                     // Bash function definitions  
    std::optional<std::pair<std::string, std::string>> structuredAttrs; // .attrs.sh/.attrs.json
};
```

### Serialization Methods

**JSON Export** (`src/nix/develop.cc:102-135`):
- Converts the entire environment to JSON for storage/transport
- Handles all variable types (exported strings, arrays, associative arrays)
- Includes bash functions and structured attributes

**Bash Script Generation** (`src/nix/develop.cc:154-179`):
- `toBash()` method converts environment back to executable bash script
- Properly handles variable exports, array declarations, and function definitions
- Example output:
  ```bash
  PATH=/nix/store/.../bin
  export PATH
  declare -a buildInputs=("pkg1" "pkg2")
  functionName() { ... }
  ```

## Environment Capture Process

### 1. Derivation Modification (`getDerivationEnvironment` - `src/nix/develop.cc:234-309`)

**Purpose:** Transform a regular derivation into one that captures the build environment rather than building the package.

**Process:**
```cpp
auto drv = evalStore->derivationFromPath(drvPath);

// Verify bash-based derivation
if (baseNameOf(drv.builder) != "bash")
    throw Error("'nix develop' only works on derivations that use 'bash' as their builder");

// Inject get-env.sh script
auto getEnvShPath = evalStore->addToStoreFromDump(source, "get-env.sh", ...);
drv.args = {store->printStorePath(getEnvShPath)};  // Replace original build script

// Remove build validation constraints
drv.env.erase("allowedReferences");
drv.env.erase("allowedRequisites"); 
drv.env.erase("disallowedReferences");
drv.env.erase("disallowedRequisites");

// Rename and rebuild derivation  
drv.name += "-env";
auto shellDrvPath = writeDerivation(*evalStore, drv);
```

### 2. Environment Capture Script (`get-env.sh`)

**Core Logic** (`src/nix/get-env.sh:7-9`):
```bash
if [[ -n $stdenv ]]; then
    source $stdenv/setup    # Load the standard environment
fi
```

**Variable Capture** (`src/nix/get-env.sh:11-13`):
```bash
__vars="$(declare -p)"      # Capture all variable declarations
__functions="$(declare -F)" # Capture all function declarations
```

**JSON Output Generation** (`src/nix/get-env.sh:15-119`):
- `__dumpEnv()` function serializes everything to JSON format
- Handles different bash variable types:
  - `declare -x` → `"exported"` 
  - `declare --` → `"var"`
  - `declare -a` → `"array"`
  - `declare -A` → `"associative"`

**Variable Filtering** (`src/nix/get-env.sh:45-61`):
- Excludes shell internals: `BASH_*`, `COMP_*`, `PIPESTATUS`, etc.
- Focuses on build-relevant variables only

### 3. Build Environment Parsing (`getBuildEnvironment` - `src/nix/develop.cc:494-505`)

```cpp
auto shellOutPath = getShellOutPath(store, installable);
auto strPath = store->printStorePath(shellOutPath);

updateProfile(shellOutPath);  // Update profile if requested

return {BuildEnvironment::parseJSON(readFile(store->toRealPath(shellOutPath))), strPath};
```

## Shell Script Generation (`makeRcScript`)

### Purpose 
Transform the captured `BuildEnvironment` into an executable bash script that recreates the development environment.

### Implementation (`src/nix/develop.cc:346-432`)

**1. Variable Preservation (`src/nix/develop.cc:355-367`)**:
```cpp
static const char * const savedVars[] = {
    "PATH",          // for commands  
    "XDG_DATA_DIRS", // for loadable completion
};

for (auto & var : savedVars) {
    out << fmt("%s=${%s:-}\n", var, var);           // Save current value
    out << fmt("nix_saved_%s=\"$%s\"\n", var, var); // Create backup
}
```

**2. Environment Recreation (`src/nix/develop.cc:369`)**:
```cpp
buildEnvironment.toBash(out, ignoreVars);
```

**3. Variable Merging (`src/nix/develop.cc:371-372`)**:
```cpp
for (auto & var : savedVars)
    out << fmt("%s=\"$%s${nix_saved_%s:+:$nix_saved_%s}\"\n", var, var, var, var);
```
This prepends the build environment values to the saved host values (e.g., `PATH=build_paths:host_paths`).

**4. Build Directory Setup (`src/nix/develop.cc:374-376`)**:
```cpp
out << "export NIX_BUILD_TOP=\"$(mktemp -d -t nix-shell.XXXXXX)\"\n";
for (auto & i : {"TMP", "TMPDIR", "TEMP", "TEMPDIR"})
    out << fmt("export %s=\"$NIX_BUILD_TOP\"\n", i);
```

**5. Shell Hook Execution (`src/nix/develop.cc:378`)**:
```cpp
out << "eval \"${shellHook:-}\"\n";
```

### Path Rewriting System

**Output Path Redirection (`src/nix/develop.cc:382-400`)**:
- Redirects immutable store paths (like `/nix/store/...-pkg-1.0`) to mutable directories
- Supports both structured and traditional derivations:
  ```cpp
  if (buildEnvironment.providesStructuredAttrs()) {
      for (auto & [outputName, from] : BuildEnvironment::getAssociative(outputs->second)) {
          rewrites.insert({from, (outputsDir / outputName).string()});
      }
  } else {
      for (auto & outputName : BuildEnvironment::getStrings(outputs->second)) {
          // Traditional $out, $dev, etc. handling
      }
  }
  ```

**Manual Redirections (`src/nix/develop.cc:402-417`)**:
- Implements the `--redirect installable dir` flag
- Parses installables and maps their store paths to specified directories
- Provides warnings if redirected paths aren't actually used

### Structured Attributes Support

**Purpose**: Handle modern Nix derivations that use structured attributes instead of plain environment variables.

**Implementation (`fixupStructuredAttrs` - `src/nix/develop.cc:438-454`)**:
```cpp
void fixupStructuredAttrs(
    PathViewNG::string_view ext,           // "sh" or "json" 
    const std::string & envVar,            // "NIX_ATTRS_SH_FILE" or "NIX_ATTRS_JSON_FILE"
    const std::string & content,           // File content
    StringMap & rewrites,                  // Path rewrite map
    const BuildEnvironment & buildEnvironment,
    const std::filesystem::path & tmpDir)
{
    auto targetFilePath = tmpDir / OS_STR(".attrs.");
    targetFilePath += ext;
    
    writeFile(targetFilePath, content);    // Write to accessible location
    
    // Rewrite the environment variable to point to the new location
    auto fileInBuilderEnv = buildEnvironment.vars.find(envVar);
    rewrites.insert({BuildEnvironment::getString(fileInBuilderEnv->second), targetFilePath.string()});
}
```

This ensures that structured attribute files (`/build/.attrs.sh`, `/build/.attrs.json`) are accessible in the development shell.

## Shell Execution Process

### Bash Shell Selection (`src/nix/develop.cc:635-675`)

**Strategy**: Use the best available interactive bash shell.

```cpp
Path shell = "bash";  // Fallback

try {
    // Try to get nixpkgs#bashInteractive
    auto nixpkgs = defaultNixpkgsFlakeRef();
    auto bashInstallable = make_ref<InstallableFlake>(
        this, state, std::move(nixpkgs), "bashInteractive", ...);
        
    for (auto & path : Installable::toStorePathSet(..., {bashInstallable})) {
        auto s = store->printStorePath(path) + "/bin/bash";
        if (pathExists(s)) {
            shell = s;
            found = true;
            break;
        }
    }
    
    if (!found)
        throw Error("package 'nixpkgs#bashInteractive' does not provide a 'bin/bash'");
        
} catch (Error &) {
    ignoreExceptionExceptInterrupt();  // Fall back to system bash
}
```

### Final Shell Invocation (`src/nix/develop.cc:683-707`)

**Script Preparation**:
```cpp
auto [rcFileFd, rcFilePath] = createTempFile("nix-shell");
AutoDelete tmpDir(createTempDir("", "nix-develop"), true);

auto script = makeRcScript(store, buildEnvironment, tmpDir);
script += fmt("command rm -f '%s'\n", rcFilePath);  // Self-cleanup
```

**Argument Handling**:
```cpp
// Different argument patterns based on usage
auto args = phase || !command.empty() 
    ? Strings{std::string(baseNameOf(shell)), rcFilePath}           // Non-interactive
    : Strings{std::string(baseNameOf(shell)), "--rcfile", rcFilePath};  // Interactive
```

**Process Execution**:
```cpp
setEnv("SHELL", shell.c_str());    // Override SHELL to match chosen bash
execProgramInStore(store, UseLookupPath::Use, shell, args, buildEnvironment.getSystem());
```

The `execProgramInStore` function (`src/nix/run.cc:46-106`) handles:
- Environment variable setup
- Store path mounting (if needed for diverted stores)
- Linux personality setting for cross-platform builds
- Final `execve()` call

## Command-Line Flag Handling

### Common Flags (inherited from `Common`)
- `--redirect installable dir`: Path redirection for mutable development
- Profile management (from `MixProfile`)

### CmdDevelop-specific Flags (`src/nix/develop.cc:513-568`)
- `--command cmd args`: Execute command instead of interactive shell
- `--phase phase`: Run specific build phase (e.g., `--configure`, `--build`)
- Phase shortcuts: `--unpack`, `--configure`, `--build`, `--check`, `--install`, `--installcheck`

### Environment Flags (from `MixEnvironment`)
- `--ignore-environment`: Start with clean environment  
- `--keep var`: Keep specific environment variables
- `--unset var`: Remove specific environment variables  
- `--set var value`: Set specific environment variables

## Development Settings

Global configuration options (`DevelopSettings` - `src/nix/develop.cc:29-42`):

```cpp
struct DevelopSettings : Config {
    Setting<std::string> bashPrompt{this, "", "bash-prompt", 
        "The bash prompt (`PS1`) in `nix develop` shells."};
    Setting<std::string> bashPromptPrefix{this, "", "bash-prompt-prefix", 
        "Prefix prepended to the `PS1` environment variable..."};
    Setting<std::string> bashPromptSuffix{this, "", "bash-prompt-suffix", 
        "Suffix appended to the `PS1` environment variable..."};
};
```

These settings are applied during script generation (`src/nix/develop.cc:618-626`):
```cpp
if (developSettings.bashPrompt != "")
    script += fmt("[ -n \"$PS1\" ] && PS1=%s;\n", escapeShellArgAlways(developSettings.bashPrompt.get()));
if (developSettings.bashPromptPrefix != "") 
    script += fmt("[ -n \"$PS1\" ] && PS1=%s\"$PS1\";\n", escapeShellArgAlways(developSettings.bashPromptPrefix.get()));
```

## Error Handling and Edge Cases

### Build Validation
- Checks that derivations use `bash` as builder (`src/nix/develop.cc:239-240`)
- Validates that `get-env.sh` produces output (`src/nix/develop.cc:304-308`)

### Garbage Collection Prevention  
```cpp
setEnv("NIX_GCROOT", gcroot.c_str());  // Prevent GC of environment while shell runs
```

### Resource Cleanup
- Temporary RC files are automatically deleted via shell script
- Temporary directories use RAII (`AutoDelete`)
- Eval caches are explicitly cleared before `exec` (`src/nix/develop.cc:703-705`)

This implementation provides a robust, feature-rich development shell system that accurately replicates build environments while remaining extensible and maintainable.

## Evaluation Cache Management

### Overview

`nix develop` leverages Nix's evaluation cache system to improve performance by avoiding redundant evaluation of Nix expressions. The caching mechanism is particularly important for flake-based development environments where complex attribute hierarchies need to be traversed.

### Cache Lifecycle in `nix develop`

#### Cache Creation and Access (`src/libcmd/installables.cc:openEvalCache`)

When `nix develop` processes an installable (typically a flake), it creates or reuses evaluation caches through the `openEvalCache` function:

```cpp
ref<eval_cache::EvalCache> openEvalCache(EvalState & state, std::shared_ptr<flake::LockedFlake> lockedFlake)
{
    auto fingerprint = evalSettings.useEvalCache && evalSettings.pureEval
                           ? lockedFlake->getFingerprint(state.store, state.fetchSettings)
                           : std::nullopt;

    if (fingerprint) {
        auto search = state.evalCaches.find(fingerprint.value());
        if (search == state.evalCaches.end()) {
            search = state.evalCaches
                         .emplace(fingerprint.value(), make_ref<nix::eval_cache::EvalCache>(fingerprint, state, rootLoader))
                         .first;
        }
        return search->second;
    } else {
        return make_ref<nix::eval_cache::EvalCache>(std::nullopt, state, rootLoader);
    }
}
```

**Key aspects:**
- **Fingerprint-based caching**: Uses locked flake fingerprints as cache keys
- **Global cache storage**: Caches are stored in `EvalState::evalCaches` map
- **Conditional caching**: Only enabled when `useEvalCache` and `pureEval` are true
- **Cache reuse**: Multiple commands can share the same cache instance

#### Cache Usage During Development Environment Setup

1. **Installable Resolution**: When parsing flake installables, evaluation caches speed up attribute path traversal (e.g., `devShells.x86_64-linux.default`)

2. **Derivation Discovery**: Caches help quickly locate development shell derivations without re-evaluating the entire flake

3. **Attribute Traversal**: Complex flake structures with nested attributes benefit from cached intermediate results

#### Explicit Cache Cleanup (`src/nix/develop.cc:703-705`)

Before `nix develop` executes the shell, it explicitly clears evaluation cache references:

```cpp
// Release our references to eval caches to ensure they are persisted to disk, because
// we are about to exec out of this process without running C++ destructors.
getEvalState()->evalCaches.clear();
```

**Why this is necessary:**
- **Process execution**: `nix develop` uses `exec` to replace itself with the shell
- **Destructor bypass**: `exec` doesn't run C++ destructors, which could leave caches unsaved
- **Persistence guarantee**: Explicit clearing triggers cache serialization to disk
- **Memory cleanup**: Releases cache memory before process replacement

### Cache Benefits for Development Workflows

#### Performance Improvements
- **Repeated `nix develop` calls**: Subsequent invocations reuse cached evaluation results
- **Large flakes**: Complex flake hierarchies with many attributes see significant speedup
- **Attribute completion**: Shell completion for flake attributes leverages cached structure

#### Cross-Command Sharing
- **Related commands**: `nix develop`, `nix build`, `nix run` can share the same evaluation cache
- **Session persistence**: Caches survive across multiple command invocations
- **Workspace efficiency**: Teams working on the same flake benefit from shared cache structure

### Cache Storage and Management

#### Cache Location
- **On-disk persistence**: Evaluation caches are stored in the user's Nix cache directory
- **Fingerprint indexing**: Each cache is identified by a hash of the locked flake state
- **Automatic invalidation**: Caches become invalid when flake inputs change

#### Memory Management
- **Reference counting**: Caches use `ref<>` smart pointers for automatic memory management
- **Explicit lifecycle**: `nix develop` manually manages cache lifetime around process execution
- **Cleanup patterns**: Similar cache cleanup occurs in other exec-based commands (`nix run`, `nix env`)

This evaluation cache system significantly improves the performance of `nix develop` while maintaining correctness through proper cache invalidation and persistence mechanisms.