# Amarooi

**Deterministic AI-Driven Infrastructure & Logic Transpiler Engine**

Amarooi enforces *Logic-Driven Development* (LDD) — a methodology where every
component begins as a human-readable `.amarooi` logic contract before a single
line of Python is generated.  Raw text **never** compiles directly to code.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Installation](#installation)
3. [First-Run Onboarding](#first-run-onboarding)
4. [Usage](#usage)
   - [synthesize](#synthesize--two-stage-spec-pipeline)
   - [plan](#plan)
   - [transpile](#transpile)
   - [run](#run)
   - [architect](#architect)
5. [Two-Stage Spec Workflow](#two-stage-spec-workflow)
6. [Freemium Usage Limits](#freemium-usage-limits)
7. [VS Code Extension](#vs-code-extension)
8. [Contributing](#contributing)
9. [License](#license)

---

## Architecture Overview

```
┌──────────────────────────┐
│   Unstructured Input     │  (Detailed paragraph OR vague prompt)
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  Stage 1: Spec Synthesis │  (Evaluates prompt completeness)
└────────────┬─────────────┘
             │
     ┌───────┴──────────────────────────┐
     ▼                                  ▼
[Vague Prompt]                 [Detailed Prompt]
Fails spec threshold →         Bypasses Q&A →
Launches Architect Interview   Synthesises logic, state, &
                               invariants directly into spec
     │                                  │
     └──────────────┬────────────────────┘
                    ▼
     ┌──────────────────────────────────────────┐
     │        .amarooi Logic Contract           │  ← MANDATORY REVIEW POINT
     └────────────────────┬─────────────────────┘
                          ▼
     ┌──────────────────────────────────────────┐
     │ Stage 2: Deterministic Transpilation     │  → Generates Typed Python
     └──────────────────────────────────────────┘
```

Key principle: **`.amarooi` is the mandatory intermediate contract**.  All
generated Python is traceable back to a reviewed spec.

---

## Installation

```bash
pip install amarooi
```

Requires Python 3.10+ and a free [Groq API key](https://console.groq.com/keys).

---

## First-Run Onboarding

On the first invocation Amarooi checks for `GROQ_API_KEY` in your environment
and in `~/.amarooi/.env`.  If the key is absent you will be prompted:

```
[Amarooi] First-run setup: a Groq API key is required.
  Get a free key at https://console.groq.com/keys

  Enter your GROQ_API_KEY: ▌
  ✓ Key saved to /home/you/.amarooi/.env
```

The key is persisted to `~/.amarooi/.env` and loaded automatically on all
subsequent runs.  You can also set it manually:

```bash
export GROQ_API_KEY=gsk_...
# or
echo "GROQ_API_KEY=gsk_..." >> ~/.amarooi/.env
```

---

## Usage

### `synthesize` – Two-Stage Spec Pipeline

Convert a detailed free-text description directly into a `.amarooi` spec:

```bash
amarooi synthesize \
  --prompt "Design a rate-limiter that tracks request counts in a state
            register keyed by client ID.  The invariant is that no client
            must exceed 100 requests per minute.  Include failure modes for
            timeout, missing client ID, and invalid token." \
  --out-dir logic/
```

If your prompt is **too vague** (missing state registers, invariants, or
failure modes) you will be directed to the Architect Wizard instead:

```
Prompt is too vague: …
Run `amarooi architect` to launch the interactive Architect Wizard.
```

### `plan`

Generate a `.amarooi.json` logic manifest from a prompt:

```bash
amarooi plan --prompt "Build an even/odd checker" --out logic.amarooi.json
```

### `transpile`

Convert a logic manifest or hand-written `.amarooi` file to Python:

```bash
# From a JSON manifest
amarooi transpile --manifest logic.amarooi.json --out output.py

# From a hand-written .amarooi spec
amarooi transpile --file logic/rate_limiter.amarooi --out src/rate_limiter.py
```

### `run`

Plan and transpile in one step:

```bash
amarooi run --prompt "Build a retry handler" --out src/retry_handler.py
```

### `architect`

Launch the interactive SDLC Architect Wizard for complex projects:

```bash
amarooi architect --prompt "I need a distributed task queue"
```

---

## Two-Stage Spec Workflow

1. **Stage 1 – Spec Synthesis** (`amarooi synthesize`)
   - Evaluates your prompt for spec completeness.
   - Vague prompts → Architect Wizard interview.
   - Detailed prompts → LLM synthesises structured state registers,
     execution loops, and invariant boundaries into `logic/<slug>.amarooi`.

2. **Mandatory Review** – Open the `.amarooi` file, verify the logic contract,
   and edit it if necessary.  This is the *only* checkpoint before code
   generation.

3. **Stage 2 – Transpilation** (`amarooi transpile --file ...`)
   - Generates fully typed Python 3.10+ source code from the reviewed spec.
   - AST-validates the output before writing it to disk.

---

## Freemium Usage Limits

Monthly free-tier allowances (tracked locally in `~/.amarooi/usage.json`):

| Feature         | Monthly Limit |
|-----------------|---------------|
| Transpile runs  | 30            |
| Code extractions| 10            |
| Active specs    | 5 per project |

When a limit is reached:

> *"Monthly free allowance reached.  Unlock unlimited local runs forever
> with an Amarooi Pro Lifetime Key ($29 Dev / $149 Team)."*

---

## VS Code Extension

Install the Amarooi extension from the VS Code Marketplace or build the VSIX
locally:

```bash
cd vscode-extension
npm install
npm run package   # outputs amarooi-vscode.vsix
code --install-extension amarooi-vscode.vsix
```

If the `amarooi` CLI is not found on your PATH the extension will offer to
install it automatically via `pip install amarooi`.

---

## Contributing

```bash
git clone https://github.com/kaboa-dev/amarooi.git
cd amarooi
pip install -e ".[dev]"
pytest
```

---

## License

MIT © kaboa-dev
