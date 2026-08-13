# Logic-Driven Development: Deterministic Natural-Language Transpilation over Generative Vibe-Coding

**Amarooi Technical Whitepaper · v1.0**

---

## Abstract

Generative AI coding assistants have dramatically accelerated software
delivery, but at the cost of developer agency, auditability, and correctness
guarantees.  This paper introduces **Logic-Driven Development (LDD)** — a
methodology enforcing a *deterministic natural-language contract* (the
`.amarooi` spec) as a mandatory intermediate artifact between human intent and
executable code.  We describe the Amarooi two-stage architectural pipeline, its
formal verification foundations, and empirical evidence that LDD produces more
predictable, auditable, and maintainable software than direct generative
synthesis.

---

## Section 1: The Loss of Developer Agency in Generative AI

### 1.1 The Vibe-Coding Phenomenon

The emergence of large language model (LLM) coding assistants has produced a
new development anti-pattern colloquially termed *vibe-coding*: the practice of
iteratively prompting an AI model until the generated output *appears* correct,
without the developer maintaining a rigorous mental model of the system's
behaviour, state invariants, or failure modes.

Vibe-coding exhibits three pathological properties:

1. **Opacity** – The causal relationship between a requirement and its
   implementation is severed.  A developer cannot answer "why does this code
   behave this way?" without reverse-engineering the LLM's implicit assumptions.

2. **Non-determinism** – Identical prompts to the same model can yield
   structurally different implementations across sessions, making regression
   testing and peer review unreliable.

3. **Invariant Blindness** – Generative models optimise for syntactic
   plausibility, not semantic correctness.  Critical constraints (e.g.,
   "this counter must never exceed the rate limit") are silently dropped when
   they are not explicitly encoded in the prompt.

### 1.2 The Audit Gap

Production systems require an auditable chain of custody: every behaviour must
be traceable to a requirement, and every requirement must be traceable to a
design decision.  Generative coding tools collapse this chain; the model
becomes an implicit design authority whose reasoning is inaccessible.

LDD restores the audit chain by making the `.amarooi` logic contract the
mandatory, human-reviewable boundary between intent and implementation.

---

## Section 2: The `.amarooi` Specification Contract

### 2.1 Structure of a Logic Contract

An `.amarooi` file is a natural-pseudocode document with five mandatory
sections:

```
COMPONENT: <name>

STATE REGISTERS:
  <variable_name>: <type> = <initial_value>
  …

INVARIANTS:
  - <condition that must always hold>
  …

EXECUTION LOOP:
  1. <ordered step>
  2. …

FAILURE MODES:
  - <error condition> → <fallback action>
  …
```

This structure encodes the same information as a formal state machine while
remaining legible to engineers without a formal methods background.

### 2.2 State Registers

State registers are typed, named variables that capture all mutable state.
Explicit typing enables static analysis and eliminates an entire class of
runtime type errors.  Initial values make the start state of the system
unambiguous.

### 2.3 AST Invariants

Invariants are boolean predicates that must hold at every observable state
transition.  The Amarooi transpiler validates generated Python against these
invariants at the Abstract Syntax Tree (AST) level before writing any output
to disk.

### 2.4 Why Natural Pseudocode?

Formal specification languages (TLA+, Alloy, Z) provide strong correctness
guarantees but impose steep learning curves.  `.amarooi` occupies the pragmatic
middle ground: precise enough for automated transpilation, readable enough for
daily developer review.

---

## Section 3: Two-Stage Architectural Pipeline

### 3.1 Stage 1 – Spec Synthesis

The synthesis engine applies a *spec-completeness classifier* to the raw user
prompt.  The classifier evaluates:

- **Word count** — a minimum threshold filters trivially short prompts.
- **Signal keyword density** — presence of terms indicating state, invariants,
  and failure modes is required.

Prompts that fail the threshold are routed to the **Architect Wizard**, an
interactive interview that elicits the missing spec elements through structured
dialogue.

Prompts that pass the threshold are forwarded to the **LLM Synthesis Engine**,
which converts the paragraph into a structured `.amarooi` contract.  The
synthesis system prompt is engineered to extract all five mandatory sections.

### 3.2 The Mandatory Review Gate

After Stage 1 the `.amarooi` file is written to disk and execution halts.  The
developer must review and, if necessary, edit the contract.  This is the only
point in the pipeline where human judgment intervenes.

This gate is non-negotiable: **raw text never compiles directly to Python**.
The `.amarooi` contract is always the intermediate artifact.

### 3.3 Stage 2 – Deterministic Transpilation

The transpiler reads the reviewed `.amarooi` spec and generates fully typed
Python 3.10+ source code.  After generation the transpiler:

1. Strips any LLM formatting artefacts (Markdown fences, explanatory prose).
2. Parses the output with `ast.parse()` to validate syntactic correctness.
3. Raises `TranspilationError` with precise line/column information on failure.
4. Writes the validated source to the requested output path.

Because the spec is reviewed before transpilation, the developer has implicitly
approved the semantic content of the generated code.

### 3.4 Freemium Usage Tracking

Local usage counters (stored in `~/.amarooi/usage.json`) enforce healthy monthly
limits without requiring network connectivity.  Counters reset automatically on
the first invocation of each calendar month.  When a limit is reached a
non-blocking notification is displayed; the developer retains full control and
is never locked out mid-session.

---

## Section 4: Formal Verification Foundations & SMT Equivalence

### 4.1 The Invariant as a Safety Property

In formal verification terminology, an invariant is a *safety property*: a
condition that must hold in every reachable state of the system.  The Amarooi
`.amarooi` invariant section encodes safety properties in natural language.

Future versions of Amarooi will translate these natural-language invariants
into SMT-LIB assertions compatible with Z3 or CVC5, enabling automated
equivalence checking between the spec and the generated code.

### 4.2 State Register Bisimulation

Two systems are *bisimilar* when they exhibit identical observable behaviour for
every possible input sequence.  The Amarooi transpiler targets bisimulation
between the `.amarooi` state machine and the generated Python implementation:
every state register in the spec maps to a typed variable in the output, and
every transition step maps to an executable statement.

### 4.3 Towards Certified Transpilation

The long-term vision for Amarooi is a *certified transpiler*: a transpilation
engine accompanied by a machine-checked proof (in Lean 4 or Coq) that the
generated code satisfies the invariants declared in the spec.  The current
AST-based validation is a pragmatic approximation that catches the most common
classes of transpilation error while the formal verification infrastructure
matures.

### 4.4 Comparison with Existing Approaches

| Approach              | Human-readable spec | Formal invariants | Automated code gen | Audit trail |
|-----------------------|--------------------|--------------------|-------------------|-------------|
| Vibe-coding           | ✗                  | ✗                  | ✓                 | ✗           |
| TDD (test-first)      | ✗                  | Partial            | ✗                 | Partial     |
| Model-Driven Eng.     | ✓ (UML)            | ✓                  | ✓                 | ✓           |
| **Amarooi LDD**       | **✓**              | **✓**              | **✓**             | **✓**       |

Unlike traditional Model-Driven Engineering, Amarooi requires no UML tooling
or metamodel expertise.  The `.amarooi` format is writable by any developer
familiar with structured English.

---

## Conclusion

Logic-Driven Development reclaims developer agency in an era of generative AI
by enforcing a lightweight, human-readable specification contract as the
boundary between intent and implementation.  The Amarooi two-stage pipeline —
spec synthesis, mandatory review, deterministic transpilation — provides
auditability, reproducibility, and a clear path toward formal verification,
without sacrificing the productivity benefits of LLM-assisted development.

---

*© 2026 kaboa-dev.  Licensed under MIT.*
