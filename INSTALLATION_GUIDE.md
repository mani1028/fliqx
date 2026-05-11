# Installation & What's Included

Quick reference for different installation methods.

## Three Ways to Use FLIQ

### 1️⃣ PyPI Installation (End Users)
```bash
pip install fliq
```

**What you get:**
- ✅ Core FLIQ engine
- ✅ CLI tools (`fliq` command)
- ✅ All optional extras (ONNX, FAISS, FastAPI, OpenCV)
- ✅ Production-ready code
- ✅ Type hints and stubs

**What you don't get:**
- ❌ Test files
- ❌ Development documentation
- ❌ Example scripts
- ❌ Benchmark reports

**Size:** ~500 KB  
**Installation time:** ~30 seconds  
**Suitable for:** Production deployments, application development

### 2️⃣ GitHub Development Installation (Contributors)
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
pip install -e .[dev]
```

**What you get:**
- ✅ Everything from PyPI (above)
- ✅ All test files
- ✅ Complete documentation
- ✅ Development tools
- ✅ Example scripts
- ✅ GitHub workflows
- ✅ Build configuration

**Size:** ~10 MB  
**Installation time:** ~60 seconds  
**Suitable for:** Development, testing, contributions

### 3️⃣ GitHub Production Installation (Own Servers)
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
pip install -e .
```

**What you get:**
- ✅ Same as PyPI (production code)
- ✅ Latest development version
- ✅ Editable for debugging
- ❌ No tests or dev tools (unless you add `[dev]`)

**Suitable for:** Testing pre-release versions, custom deployments

## Comparison Table

| Feature | PyPI | GitHub Dev | GitHub Prod |
|---------|------|-----------|------------|
| **Core engine** | ✅ | ✅ | ✅ |
| **CLI tools** | ✅ | ✅ | ✅ |
| **Tests** | ❌ | ✅ | ❌ |
| **Documentation** | README | Full | README |
| **Type hints** | ✅ | ✅ | ✅ |
| **Optional extras** | ✅ | ✅ | ✅ |
| **Development tools** | ❌ | ✅ | ❌ |
| **Size** | 500 KB | 10 MB | 500 KB |
| **Latest version** | Release only | Latest | Latest |

## Why Three Options?

### PyPI
- **Simplest** for end users
- **Smallest** for production servers
- **Official** release version
- **Tested** and stable

### GitHub Development
- **Complete** with tests and docs
- **Contributing** ready
- **Latest** features and fixes
- **Full transparency** of codebase

### GitHub Production
- **Editable** for debugging
- **Latest** development version
- **Same size** as PyPI
- **Full access** to source

## Common Scenarios

### Scenario 1: Adding FLIQ to Your App
```bash
pip install fliq
from fliq import Fliq
engine = Fliq()
```
✅ Use **PyPI** - clean, fast, production-ready

### Scenario 2: Contributing to FLIQ
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
pip install -e .[dev]
pytest
```
✅ Use **GitHub Development** - run tests, access docs

### Scenario 3: Testing Pre-Release
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
pip install -e .
```
✅ Use **GitHub Production** - latest code without dev overhead

### Scenario 4: Deploying with CI/CD
```yaml
- run: pip install fliq[video,faiss]  # or from GitHub
- run: fliq stress --streams 5 --duration 10
- run: python my_app.py
```
✅ Use **PyPI** or **GitHub Prod** - whichever is in your workflow

### Scenario 5: Local Development and Testing
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
pip install -e .[dev]
pytest
python scripts/benchmark_runner.py
```
✅ Use **GitHub Development** - full toolkit

## File Availability by Installation Method

### PyPI Package
```
fliq/
├── __init__.py              ✅
├── engine.py                ✅
├── config.py                ✅
├── cli.py                   ✅
├── protection.py            ✅
├── api/                     ✅
├── cache/                   ✅
├── detection/               ✅
├── embeddings/              ✅
├── stress/                  ✅
├── stability/               ✅
├── tracking/                ✅
├── vector/                  ✅
├── benchmarks/              ✅ (functions only)
├── video/                   ✅
├── tests/                   ❌
└── py.typed                 ✅

README.md                     ✅
LICENSE                       ✅
PRODUCTION.md                 ❌
CLI_REFERENCE.md              ❌
All other .md files           ❌
```

### GitHub Development
```
(All of PyPI PLUS:)

fliq/
└── tests/                   ✅

PRODUCTION.md                ✅
CLI_REFERENCE.md             ✅
IMPLEMENTATION_COMPLETE.md   ✅
UPGRADE_SUMMARY.md           ✅
DISTRIBUTION.md              ✅
PACKAGE_CONFIGURATION.md     ✅
README_PRODUCTION.md         ✅

scripts/                     ✅
.github/                     ✅
MANIFEST.in                  ✅
pyproject.toml              ✅
.gitignore                   ✅
```

## Using Production Documentation

### If you installed from PyPI
Documentation is available online:
- GitHub repository (full docs)
- Official docs site (when available)
- Inline help: `fliq --help`

Install from GitHub if you want local copies:
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
cat PRODUCTION.md
cat CLI_REFERENCE.md
```

### If you installed from GitHub
Documentation is available locally:
```bash
cat PRODUCTION.md
cat CLI_REFERENCE.md
cat DISTRIBUTION.md
cat PACKAGE_CONFIGURATION.md
```

## Using Tests

### If you installed from PyPI
Tests are not available. To run tests:
```bash
pip install pytest
git clone https://github.com/your-org/fliq.git
cd fliq
pytest
```

### If you installed from GitHub Dev
Tests are available:
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest -k test_memory     # Run specific tests
```

### If you installed from GitHub Prod
Tests are not available. To get them:
```bash
pip install -e .[dev]
pytest
```

## Optional Dependencies

All installation methods support the same optional dependencies:

```bash
# Video support (OpenCV)
pip install fliq[video]

# Vector search (FAISS)
pip install fliq[faiss]

# HTTP API (FastAPI + Uvicorn)
pip install fliq[api]

# ONNX acceleration
pip install fliq[onnx]

# Everything
pip install fliq[full]

# Development tools (GitHub only)
pip install fliq[dev]
```

## Updating FLIQ

### From PyPI
```bash
pip install --upgrade fliq
```

### From GitHub
```bash
cd fliq
git pull origin main
pip install -e .
```

## Checking Your Installation

```bash
# Check version
python -c "import fliq; print(fliq.Fliq.__module__)"

# Check what's installed
pip show fliq

# List installed modules
python -c "import fliq; print(dir(fliq))"

# Check if tests are available
python -c "from fliq.tests import *"  # Will fail if from PyPI
```

## Summary

| Need | Use | Command |
|------|-----|---------|
| Production use | PyPI | `pip install fliq` |
| Development | GitHub Dev | `git clone ... && pip install -e .[dev]` |
| Testing pre-release | GitHub Prod | `git clone ... && pip install -e .` |
| Latest features | GitHub | `git clone && pip install -e .` |
| Run tests locally | GitHub Dev | `pip install -e .[dev] && pytest` |
| Read documentation | GitHub | `cat PRODUCTION.md` |

---

Choose the installation method that best fits your use case!
