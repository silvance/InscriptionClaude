# Suite setup — Windows (PowerShell)

This repo contains three tools that work together:

| Tool | What it does |
|---|---|
| **Inscription** | Capture a Windows workflow; generate an annotated step guide |
| **CaseForge** | Case intake, chain-of-custody, and report generation |
| **CaseGuide** | LLM-assisted exam coach that suggests next actions |

---

## Quick start (one shared venv)

Open **InscriptionClaude.code-workspace** in VS Code, then run these commands
from the **repo root** in a PowerShell terminal:

```powershell
# 1. Create and activate the shared virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Upgrade pip, then install all three tools in editable mode
python -m pip install --upgrade pip
python -m pip install -e inscription -e caseforge -e caseguide

# 3. Verify all three entry points are reachable
python -m inscription --help
caseforge --help
caseguide --help
```

> **Why `.venv\Scripts\Activate.ps1` and not `source`?**
> `source` is a bash built-in; it does not exist in PowerShell.
> Always use the `.ps1` form on Windows.

---

## Running each tool

```powershell
# Must activate the venv first in every new terminal session
.venv\Scripts\Activate.ps1

python -m inscription          # Inscription capture studio
caseforge                      # CaseForge case manager
caseguide                      # CaseGuide exam coach
```

VS Code picks up the venv automatically once you open the workspace —
the Python extension reads `.venv\` from the workspace root.

---

## Running the test suite

```powershell
.venv\Scripts\Activate.ps1

# All three tools
pytest inscription/tests caseguide/tests caseforge/tests -v

# Individual tool
pytest inscription/tests -v
```

---

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `source: command not found` | Running bash syntax in PowerShell | Use `.venv\Scripts\Activate.ps1` |
| `caseforge` not recognized | venv not activated, or installed to system Python | Activate first, then `pip install -e caseforge` |
| Packages install to `AppData\Local\…` | venv not active when running pip | Check prompt shows `(.venv)`, then reinstall |
| `ModuleNotFoundError: inscription` | Installed to wrong env | `pip show inscription` — confirm `Location` is inside `.venv` |

---

## LLM setup (Inscription AI rewrite)

The step generator always runs without AI. The AI rewrite (File → Rewrite with AI)
is optional and needs a running OpenAI-compatible endpoint. Fastest path:

```powershell
# Install Ollama, then:
ollama pull granite3.3:8b
```

Ollama exposes `http://localhost:11434/v1` — that is Inscription's default.
Change model/endpoint in `%LOCALAPPDATA%\Inscription\config.ini`.
