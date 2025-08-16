slidenumbers: true
slidecount: true

# Learn You Some Rust: Generics

Zach Mitchell

---

# [fit] Sponsored by
# [fit] [Flox!](https://flox.dev)

---

# What is a "generic"?

- A "generic" is shorthand for a data structure or function that uses a "generic type".
- A generic type is a placeholder for a type that's made concrete at compile time.

---

# Examples
- A data structure parameterized by another type.
- A function that could take different types for one of its arguments.


```rust
struct Foo<T> {
	bar: T
}

fn foo<T>(bar: T) -> T {
  T
}
```

---

# Basic motivation

- I have a container data structure
- Its operations are mostly agnostic to the kind of items it contains
- I don't want to rewrite the data structure for every kind of item

Solution: make the container "generic" over the type of item it contains

---

# Basic motivation

- I have a function that works with a range of data types
- I'm lazy and don't want a separate function for each type

Solution: make some of the arguments generic

---

# Real world Flox example

```rust
pub fn read_environment_registry(
    path: impl AsRef<Path>,
) -> ...
```

- You'll see `impl AsRef<Path>` all over `flox/flox`
- Allows you to provide any type that can provide a file path.
- `&Path`, `PathBuf`, `&PathBuf`, `CanonicalPath`, `&CanonicalPath`, ...

---

# How does it work?

Say you have this struct:

```rust
struct Foo<T> {
	bar: T
}
```

- For every `T` that you use with `Foo<T>`, you'll get a different struct with its own set of methods, etc.
- In other words `Foo<i32> != Foo<u8>` even though they're both `Foo<T>`.

---

# How does it work?

Say you have this function:

```rust
fn foo<T>(arg: T) -> T { arg }
```

For every `T` you use with `foo<T>` you'll get a different function that takes that type as an argument, but they're generated at compile time and never shown to you.

---

# How do dynamic languages do it?

- An object may implement multiple interfaces or inherit from multiple classes.
- Objects store a pointer to a "vtable", a list of pointers to the functions that implement class methods.
- When a method is called it's looked up in one of these vtables.

---

# Any type?

If `T` can be any type, that means you don't actually know much about what it can or can't do.

This means you need to somehow constrain what types `T` can be.

---

# Any type?

In Rust you do this by providing _trait bounds_.

```rust
// Constrains T to be types that can be printed
fn foo<T: Display>(arg: T) {
	println!("arg is {arg}");
}
```

---

# Trait bound syntax

If you only want to allow types that implement at least the traits `Foo` and `Bar`:

```rust
T: Foo + Bar
```

---

# Where can I put generic types?

```rust
// Note that T is part of the struct name!
struct Foo<T> {
	foo: T
}

// Note that T is part of the function name!
fn foo<T>(arg: T) {}

// Note that T is part of the trait name!
trait Foo<T> {
	fn bar<T>(arg: T) {}
}
impl Foo<i32> for Bar {...}
```

---

# Where *should* I put trait bounds?

Never put them on struct/enum definitions, only on traits/functions.

---

# [fit] Never
# [fit] on structs/enums
# [fit] only on functions/traits

---

# Why?

```rust
struct Foo<T: MyTrait>(T);

struct Bar<T> {
	x: T,
	y: Foo<T> // straight to jail, needs T: MyTrait
}
```

---

# Why?

```rust
struct Foo<T: MyTrait>(T);

// ಠ_ಠ, now `x` is unnecessarily constrained
struct Bar<T: MyTrait> { 
	x: T,
	y: Foo<T>
}
```

---

# Why?

You would have to repeat the trait bound in the function definition anyway

```rust
// Doesn't compile, Foo<T> needs T: MyTrait
fn myfunc<T>(arg: Foo<T>) {}

// Does compile
fn myfunc<T: MyTrait>(arg: Foo<T>) {}
```
---

# What if I have a bunch of generics and trait bounds?

```rust
// Don't do this
fn foo<T: Send + Sync + Display + MyTrait, U: OtherTrait>(x: T, y: U) {}

// Do this
fn foo<T, U>(x: T, y: U)
where
	T: Send + Sync + Display + MyTrait
	U: OtherTrait
{}
```
---

# How do I call a generic function?

Most of the time it's exactly the same as if it wasn't generic.

You can use "turbofish" syntax to help the compiler if it can't figure it out.

```rust
fn foo<T>(arg: T) {}

// 5 is a literal, what's its type?
foo(5)

// Help the compiler out if it's struggling
foo::<i32>(5)
```

---

> That looks pretty verbose...

- You, probably

---

# [fit] Introducing...
# [fit] impl Trait

---

# impl Trait

There are two positions:
- Argument position
- Return position

```rust
fn foo(arg: impl MyTrait) {}
fn foo() -> impl MyTrait {}
```

---

# impl Trait: argument position

Generics:

```rust
fn foo<T: MyTrait>(arg: T) {}
```

impl Trait

```rust
// Easier to write, but you lose the ability
// to disambiguate literals
// e.g. foo::<i32>(5).
fn foo(arg: impl MyTrait) {}
```

Aside from losing turbofish syntax, they're identical.

---

# impl Trait: return position

These are _not_ the same:

```rust
// Case A
fn foo<T: MyTrait>(arg: T) -> T { arg }
// Case B
fn foo<T: MyTrait>(arg: T) -> impl MyTrait { arg }
// Case C
fn foo(arg: impl MyTrait) -> impl MyTrait { arg }
```

Sorry

---

# Explanation

```rust
fn foo<T: MyTrait>(arg: T) -> T { arg }
```
This returns the same type that was passed in, so the returned value is like any other `T`.

```rust
fn foo<T: MyTrait>(arg: T) -> impl MyTrait { arg }
fn foo(arg: impl MyTrait) -> impl MyTrait { arg }
```
`-> impl MyTrait` effectively erases the underlying type, so you only know that it implements `MyTrait` and therefore can only call `MyTrait` methods.

---

# impl trait positions

[Rust Playground Example](https://play.rust-lang.org/?version=stable&mode=debug&edition=2021&gist=e47de598ca11424757fb85fab4c7d2c2)

---

# Generic vs. ...?

ex.) You provide an API, and one input parameter is a type that implements `MyTrait`.

- Do you control the types that implement `MyTrait`?
- Do you need to enumerate the types that implement `MyTrait`?

---

# Do you control the implementors of MyTrait?

- If not, the parameter probably needs to be generic.

---

# Do you need to enumerate the types that implement MyTrait?

- You may want to switch on the different implementors to handle them differently.
- Stuff them into an enum, implement `MyTrait` on the enum.

[Rust Playground Example](https://play.rust-lang.org/?version=stable&mode=debug&edition=2021&gist=11950963849695e0d825c23660dc6f92)

---

# Compilation speed and size trade-off

```rust
// Compiled once per T *per crate that uses foo*,
// separate function for each T
fn foo<T: AsRef<Path>>(path: T) {}

// Compiled once, one function.
fn foo(path: &Path) {}
```

---

# Compromise

```rust
// Still have a generic interface,
// wrapper is still compiled once per T per crate,
// but the wrappers are small and fast to compile.
fn foo<T: AsRef<Path>>(path: T) {
	foo_impl(path.as_ref());
}

// Actual implementation takes a concrete type,
// only compiled once, single function
fn foo_impl(path: &Path) {}
```

---

# If that's _still_ not good enough...

Use a trait object (topic for a different day)

```rust
fn foo(path: &dyn AsRef<Path>) {}
```

Slight runtime performance penalty in exchange for better compilation speed and code size.

---

# [fit] Advanced
# [fit] Topics

---

# So far we've been reactive

- Rust has a strong type system
- Different types for different contexts
- ex.) `&Path`, `PathBuf`, `Cow<Path>`, etc
- Still want to make interfaces that accept `Path`-like things
- Need to use generics

These are _consequences_ of the type system.

---

# What if we *leveraged* the type system instead?

- Type states
- Const generics

---

# Type states

- Encode a state machine into the type system
- Make certain transitions impossible at compile time
- Very useful when correctness is mission critical
- Verbose and unwieldy in most other situations

[Rust Playground Example](https://play.rust-lang.org/?version=stable&mode=debug&edition=2021&gist=c878c7e2f5aa262f052a185ae08fd839)

---

# Const generics

- Encode certain constants into the type system.
- Not all types can be constants at the moment.
- Very useful for operations on arrays (e.g. scientific computing).
- Useful for other things as well.

---

# Example: version constraint

```rust
pub struct Version<const N: usize>;

pub struct Install;
pub struct Variables;
pub struct Hook;
pub struct Profile;
pub struct Options;
pub struct Services;
pub struct Build;

pub struct Manifest {
    // The manifest schema version is verified at compile time
    pub version: Version<1>,
    pub install: Install,
    pub vars: Variables,
    pub hook: Hook,
    pub profile: Profile,
    pub options: Options,
    pub services: Services,
    pub build: Build
}
```

---

# Const generics: array pair

```rust
struct ArrayPair<const N: usize> {
    x: [u32; N],
    y: [u32; N]
}
```

- Two equal length arrays of arbitrary size, verified to be the same length at compile time.
- Without const generics you would have to write out `ArrayStruct` for every value of `N`.

---

# Lifetimes

Lifetimes are also generic parameters, but they aren't types.

```rust
struct Foo<T, 'a> {
	bar: &'a T
}

fn foo<T: MyTrait + 'a>(arg: &'a T) {}
```

---

# Resources

- [Official Rust API Guidelines: Generics](https://rust-lang.github.io/api-guidelines/flexibility.html#functions-minimize-assumptions-about-parameters-by-using-generics-c-generic)
- [Unofficial Rust - Design Patterns](https://rust-unofficial.github.io/patterns/functional/generics-type-classes.html)
- [Rust by Example - Generics](https://doc.rust-lang.org/rust-by-example/generics.html)

---

# Me

- [tinkering.xyz](https://tinkering.xyz)
- [GitHub](https://github.com/zmitchell)
- [Flox](https://github.com/flox/flox)
