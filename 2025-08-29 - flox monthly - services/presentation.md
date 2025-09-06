footer: Zach Mitchell - Flox
slidenumbers: true

# [fit] Services

---

# Why

![right](./images/but_why.jpg)

- You want something running in the background
- OR
- You need long-running programs during development

---

# Examples

- Dev server with live reload for a website
- A test runner that watches source files
- Local copy of a database for a web backend

---

# Existing solutions: Procfiles

![right fit](./images/back_in_my_day.jpg)

- Tools
  - Foreman (ca. 2010)
  - Overmind/Hivemind
- Pro: Simple syntax
- Cons:
  - No dependency management
  - No startup order
  - Defined separate from dev env
  - Complex setup is painful

---

# docker-compose

![right fit](./images/docker_compose.jpg)

- Pros:
  - Modularity (depend on preconfigured images)
- Cons:
  - YAML
  - Hooking up shared volumes/networks
  - Defined separate from dev env

---

# [fit] Salvation

---

# Services in your environment

![right](./images/utopia.jpg)

- Pros:
  - Dependencies managed reproducibly
  - One file for the entire dev env
  - "Just" a process, inspect freely
  - Literally anything other than YAML
- Cons:
  - No startup order (yet)

---

# How

Literally just write out the command

```toml
[services.<name>]
command = '''
  # put a script here
'''
```

---

# How

```toml
[services.my_awesome_service]
command = '''
  while true; do date; sleep 5; done
'''
```

---

# How

Variables defined in `[vars]` are available

```toml
[vars]
NAME = "gif-not-jif"

[services.whats_it_called]
command = '''
  while true; echo $NAME; sleep 5; done
'''
```

---

# How

So are variables exported in `hook.on-activate`

```toml
[hook]
on-activate = '''
  export NAME="gif-not-jif"
'''

[services.whats_it_called]
command = '''
  while true; echo $NAME; sleep 5; done
'''
```

---

# How

Or define service-specific variables

```toml
[services.whats_it_called]
command = '''
  while true; echo $NAME; sleep 5; done
'''
vars.NAME = "gif-not-jif"
```

These even work now!

---

# How

Daemon support

```toml
[services.whats_it_called]
command = '''
  run-my-daemon.sh
'''
is-daemon = true
shutdown.command = '''
  begone-daemon
'''
```

---

# Usage

```
$ flox services start [name]
$ flox services stop [name]
$ flox services restart [name]
```

---

# Usage

```
$ flox services status
NAME            STATUS       PID
whats_it_called Running    80818
```

---

# Usage

```
$ flox services status --json
[
  {
    "name": "whats_it_called",
    "status": "Running",
    "pid": 80818,
    "exit_code": null
  }
]
```

---

# Usage

```
$ flox services logs -f
whats_it_called: gif-not-jif
whats_it_called: gif-not-jif
whats_it_called: gif-not-jif
whats_it_called: gif-not-jif
whats_it_called: gif-not-jif
whats_it_called: gif-not-jif
...
```

---

# [fit] Demo:
# [fit] flox/floxdocs

---

# Composition: what is it?

- Define environments as reusable building blocks
- "Include" them into new projects
- Merges the manifests together
- Builds a _single_ environment from multiple manifests

---

# Composition: usage

```toml
version = 1

[include]
environments = [
  { remote = "zmitchell/rust-build" },
  { remote = "zmitchell/rust-dev" },
  { path = "path/to/env" }
]
```

---

# Composition: reusable service definitions

```toml
version = 1

[include]
environments = [
  { remote = "zmitchell/redis" }
]
```

Congrats, you just bootstrapped a project with reproducible service definitions.

---

# [fit] Demo:
# [fit] Composition

---

# [fit] Under the hood

---

# process-compose

- We use `process-compose` to run services
  - Tracks process status, PID, etc
- `[services]` gets translated to `process-compose` config file
  - `$FLOX_ENV/service-config.yml`

---

# [fit] Automatic
# [fit] cleanup

---

# [fit] End
