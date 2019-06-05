slidenumbers: true
slidecount: true
footer: Zach Mitchell

# Polsim
### A case study for scientific computing in Rust

Zach Mitchell

[.hide-footer]

---

## **polsim** provides a simple, declarative way to simulate the polarization of a laser.

---

# Huh?

- Light in a laser is *polarized*
- Interactions change the polarization of the beam
    - Reflection from a surface
    - Transmission through a surface
    - Various optical elements

^ I'll keep the physics to a minimum, but some background is necessary.

---

![](polarization.svg)

[.background-color: #ffffff]

^ The polarization is defined as how the light oscillates perpendicular to the direction that it's traveling.

^ You can see that the polarization changes as the beam passes through these elements.

^ That's what I'm modeling.

---

# Project structure

- `polarization`
    - Crate I wrote for the polarization simulations
- `polsim`
    - Provides a CLI for `polarization`

---

# Modeling polarization

There are standard techniques for this.
- Jones calculus (simpler, what I'm using)
- Mueller calculus

### Don't reinvent the wheel!

---

# Jones calculus primer

Polarization is a vector with two components:

$$
\vec{E} = \begin{bmatrix} A \\ B e^{i\delta} \end{bmatrix} = \begin{bmatrix} \text{complex number} \\ \text{complex number} \end{bmatrix}
$$

Optical elements that interact with the beam are 2x2 matrices:

$$
M = \begin{bmatrix}
m_{00} & m_{01} \\
m_{10} & m_{11}
\end{bmatrix} = \begin{bmatrix}
\text{complex} & \text{complex} \\
\text{complex} & \text{complex}
\end{bmatrix}
$$

---

# Jones calculus primer

Multiply initial polarization by the optical elements to get the final polarization

$$
E_{f} = M_{N} \times \ldots \times M_2 \times M_1 \times E_i
$$

When you get down to it, you're just multiplying 2x2 matrices.

---

# Those matrices can be pretty ugly...

$$
\begin{bmatrix}
\cos^{2}\left(\theta\right) + e^{i\varphi} \sin^{2}\left(\theta\right) & \sin\left(\theta\right)\cos\left(\theta\right) - e^{i\varphi} \sin\left(\theta\right)\cos\left(\theta\right) \\\\
\sin\left(\theta\right)\cos\left(\theta\right) - e^{i\varphi} \sin\left(\theta\right)\cos\left(\theta\right) & \sin^{2}\left(\theta\right) + e^{i\varphi} \cos^{2}\left(\theta\right) \\\\
\end{bmatrix}
$$

No one has ever used this matrix without looking it up

---

# Translation to Rust

- Complex numbers
    - `num::complex::Complex<T>`
- Vectors
    - `nalgebra::Vector2<T>`
- Matrices
    - `nalgebra::Matrix2<T>`

---

# num::complex::Complex

Easily the most mature crate for complex numbers

---

# Linear algebra libraries

- Lots of options
    - `nalgebra`, `ndarray`, `vecmath`, `cgmath`, ...
- Many are designed specifically for games/graphics
- `nalgebra` and `ndarray` seem more applicable for general use.
- `nalgebra` seemed more tailored to my requirements.

---

# JonesVector trait

^ This is the trait for something that can represent a beam.

```rust
pub trait JonesVector {
    // Intensity of the beam
    fn intensity(&self) -> Result<f64>;

    // Returns the x-component of the beam
    fn x(&self) -> f64;

    // Returns the y-component of the beam
    fn y(&self) -> f64;

    ...
}
```

---

# Beam

^ I make a container for the vector so I can implement my own methods on it.

```rust
// Basically a container for the Vector2<T>
pub struct Beam {
    vec: Vector2<Complex<f64>>,
}

impl Beam {
    // mostly convenience methods
}

impl JonesVector for Beam {
    ...
}
```

---

# JonesMatrix trait

Represents an optical element

```rust
pub trait JonesMatrix {
    // Rotate the element by the given angle
    fn rotated(&self, angle: Angle) -> Self;

    // Return the inner matrix of the element
    fn matrix(&self) -> Matrix2<Complex<f64>>;

    ...
}
```

---

# Optical elements

Optical elements implement `JonesMatrix`

```rust
// An ideal linear polarizer
pub struct Polarizer {
    mat: Matrix2<Complex<f64>>,
}

impl Polarizer {
    // convenience methods
}

impl JonesMatrix for Polarizer {
    ...
}
```

---

# Putting it all together

```rust
let beam = ...
let e1 = ...
let e2 = ...
let system = OpticalSystem::new()
    .add_beam(beam)
    .add_element(e1)
    .add_element(e2);
let final_beam = system.propagate().unwrap();
```

^ You add a beam and some elements to the optical system, then tell it to propagate the beam through.

---

# Testing

- This is science
- Results should be
    - reproducible
    - correct
    - etc

---

# Science 
# ❤ 
# Property Based Testing

---

# Property based testing (PBT)

- Unit tests
    - "The sum of 2 and 2 should be 4."
- Property based tests
    - "The sum of positive integers **x** and **y** should be positive."
    - "The sum of positive integers **x** and **y** should be greater than both **x** and **y**."

---

# PBT and polarization

Tons of opportunities for soundness checks
- "No beam can pass through two crossed polarizers."
- "A beam that's rotated 360 degrees should look the same."
- "An optical element that's rotated 360 degrees should look the same."
- etc.

--- 

# PBT in Rust - proptest

Generate arbitrary instances of your types

[.code-highlight: all]
[.code-highlight: 7-10]

```rust
// Arbitrary trait from proptest
impl Arbitrary for Angle {
    type Parameters = ();
    type Strategy = BoxedStrategy<Self>;

    fn arbitrary_with(_: Self::Parameters) -> Self::Strategy {
        prop_oneof![
            (any::<f64>()).prop_map(|x| Angle::Degrees(x)),
            (any::<f64>()).prop_map(|x| Angle::Radians(x)),
        ]
        .boxed()
    }
}
```

^ Randomly selects an f64, then randomly selects whether it should be radians or degrees.

---

# PBT in Rust - proptest

Compose arbitrary instances from other arbitrary instances

[.code-highlight: 6-7]

```rust
impl Arbitrary for Polarizer {
    type Parameters = ();
    type Strategy = BoxedStrategy<Self>;

    fn arbitrary_with(_: Self::Parameters) -> Self::Strategy {
        any::<Angle>()  // select an arbitrary angle
            .prop_map(|angle| Polarizer::new(angle))  // use it to make a polarizer
            .boxed()
    }
}
```

^ Beware, the more things you compose, the less of the space you explore.

---

# polsim

High level overview
- The user writes a simulation definition file.
- The file is read into a struct using `serde`.
- The simulation definition is validated.
- The simulation is performed.
- The results are printed.


---

# Simulation definition

```toml
[beam]
polarization = "linear"
angle = 90
angle_units = "degrees"

[[elements]]
element_type = "polarizer"
angle = 45
angle_units = "degrees"

[[elements]]
element_type = "qwp"
angle = 0
angle_units = "degrees"
```

^ There's a section for the beam.

^ Each element is defined separately and in the order the beam should pass through them.

---

# Simulation definition

```rust
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct SystemDef {
    pub beam: BeamDef,
    pub elements: Vec<ElemDef>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct ElemDef {
    pub element_type: ElemType,
    pub phase: Option<f64>,
    pub phase_units: Option<AngleType>,
    pub angle: Option<f64>,
    pub angle_units: Option<AngleType>,
}
```

--- 

# Beam definition

```rust
#[derive(Debug, Deserialize, Serialize)]
pub struct BeamDef {
    pub polarization: PolType,
    pub angle: Option<f64>,
    pub angle_units: Option<AngleType>,
    pub x_mag: Option<f64>,
    pub x_phase: Option<f64>,
    pub y_mag: Option<f64>,
    pub y_phase: Option<f64>,
    pub phase_units: Option<AngleType>,
    pub handedness: Option<HandednessType>,
}
```

---

# Validation

[.code-highlight: all]
[.code-highlight: 3-5]

```rust
fn validate_element(elem: &ElemDef) -> Result<OpticalElement> {
    match elem.element_type {
        ElemType::Polarizer => {
            validate_polarizer(elem).chain_err(|| "invalid polarizer definition")
        }
        ElemType::HWP => validate_hwp(elem).chain_err(|| "invalid half-wave plate definition"),
        ElemType::QWP => validate_qwp(elem).chain_err(|| "invalid quarter-wave plate definition"),
        ElemType::Retarder => validate_retarder(elem).chain_err(|| "invalid retarder definition"),
        ElemType::Rotator => {
            validate_rotator(elem).chain_err(|| "invalid polarization rotator definition")
        }
    }
}
```

---

# Validation

[.code-highlight: all]
[.code-highlight: 9]
[.code-highlight: 10-11]

```rust
fn validate_polarizer(elem: &ElemDef) -> Result<OpticalElement> {
    if elem.element_type != ElemType::Polarizer {
        return Err(ErrorKind::WrongElementType(format!(
            "Expected to validate element type Polarizer, found {:#?} instead",
            elem.element_type
        ))
        .into());
    }
    error_on_extra_params!(elem, phase, phase_units);
    let angle_res =
        validate_angle(&elem.angle, &elem.angle_units).chain_err(|| "invalid angle definition");
    match angle_res {
        Err(err) => Err(err),
        Ok(angle) => Ok(OpticalElement::Polarizer(Polarizer::new(angle))),
    }
}
```

---

# Errors

Using `error-chain` to provide breadcrumbs for the user.

```
$ polsim has_error.toml
error: invalid system definition
caused by: invalid element definition
caused by: invalid polarizer definition
caused by: invalid angle definition
caused by: missing parameter in definition: 'units'
```

^ Doesn't tell you *which* polarizer is the problem, though.

