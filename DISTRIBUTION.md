# FLIQ: PyPI vs GitHub Repository

This document explains what's included in the PyPI package vs what remains in the GitHub repository.

## PyPI Package (Published)

The `fliq` package published on PyPI contains **only the production code**:

### Included in PyPI
```
fliq/
├── __init__.py
├── config.py
├── engine.py
├── py.typed
├── api/
├── cache/
├── detection/
├── embeddings/
├── tracking/
├── vector/
├── video/
├── benchmarks/          (benchmark functions only)
├── stress/              (stress testing framework)
├── stability/           (stability monitoring)
├── protection.py        (load protection systems)
└── cli.py               (CLI tools)
```

### Not Included in PyPI
- ❌ Test files (`fliq/tests/`)
- ❌ Benchmark reports (`benchmarks/reports/`)
- ❌ Development documentation
- ❌ Scripts directory
- ❌ Build configuration files

## GitHub Repository (Development)

The GitHub repository contains **everything**: production code, tests, documentation, and development tools.

### GitHub-Only Content

#### Tests (Not in PyPI)
- `fliq/tests/test_*.py` - All unit and integration tests
- ~600 lines of comprehensive test coverage
- Tests for all production hardening features
- Command: `pytest` to run locally

#### Documentation (Not in PyPI)
- `PRODUCTION.md` - Complete production deployment guide
- `UPGRADE_SUMMARY.md` - Summary of changes
- `CLI_REFERENCE.md` - CLI command reference
- `IMPLEMENTATION_COMPLETE.md` - Technical implementation details
- `README_PRODUCTION.md` - File manifest and reference
- `DISTRIBUTION.md` - This file

#### Development Tools (Not in PyPI)
- `scripts/benchmark_runner.py` - Standalone benchmark script
- `scripts/` directory - Development utilities
- `.github/` - GitHub workflows and configuration
- Build and development configuration files

#### Configuration (Not in PyPI)
- `.gitignore` - Git ignore patterns
- `tox.ini` - Testing configuration
- `pytest.ini` - Test configuration
- `.flake8` - Linting configuration
- `setup.py` - Build configuration (if present)
- `MANIFEST.in` - Package distribution configuration

## Why This Split?

### Reasons to Exclude Tests from PyPI
1. **Smaller package size** - Reduces installation time
2. **Faster installation** - Less data to download
3. **Clean production distribution** - Only what's needed to run
4. **Standard practice** - Most Python packages follow this pattern

### Reasons to Keep Everything in GitHub
1. **Transparency** - Users can review tests and docs
2. **Community contribution** - Tests are essential for PRs
3. **Documentation** - Guides help with deployment
4. **Development** - Full context for contributors

## Using FLIQ

### From PyPI (Normal Users)
```bash
# Install production-ready package
pip install fliq

# Use in your code
from fliq import Fliq
engine = Fliq()
results = engine.recognize(image)
```

**Size**: ~500 KB (just the code)

### From GitHub (Contributors/Developers)
```bash
# Clone repository
git clone https://github.com/your-org/fliq.git
cd fliq

# Install with development tools
pip install -e .[dev]

# Run tests
pytest

# Read documentation
cat PRODUCTION.md
cat CLI_REFERENCE.md
```

**Size**: ~10 MB (includes tests and documentation)

## PyPI vs GitHub File Structure

### PyPI (`pip install fliq`)
```
fliq/
├── __init__.py
├── engine.py
├── config.py
├── cli.py
├── protection.py
├── api/
├── cache/
├── detection/
├── embeddings/
├── stress/
├── stability/
├── tracking/
├── vector/
└── video/
```

### GitHub (git clone)
```
fliq/                       (everything above PLUS:)
├── fliq/tests/            ← NOT in PyPI
├── PRODUCTION.md          ← NOT in PyPI
├── UPGRADE_SUMMARY.md     ← NOT in PyPI
├── CLI_REFERENCE.md       ← NOT in PyPI
├── README_PRODUCTION.md   ← NOT in PyPI
├── IMPLEMENTATION_COMPLETE.md ← NOT in PyPI
├── DISTRIBUTION.md        ← NOT in PyPI (this file)
├── scripts/               ← NOT in PyPI
├── .github/               ← NOT in PyPI
├── MANIFEST.in            (controls PyPI exclusions)
└── .gitignore
```

## Configuration Files

### MANIFEST.in
Controls what gets included/excluded from PyPI distribution:
```
recursive-exclude fliq/tests *
exclude PRODUCTION.md
exclude CLI_REFERENCE.md
exclude scripts
... (excludes tests and docs)

recursive-include fliq *.py
... (includes production code)
```

### pyproject.toml
Specifies:
```toml
[project.scripts]
fliq = "fliq.cli:main"  # CLI entry point

[tool.setuptools]
packages = { find = { exclude = ["fliq.tests*"] } }
```

### .gitignore
Manages local development artifacts (not related to PyPI).

## Installation Paths

### For End Users (PyPI)
```bash
pip install fliq
# ↓ Downloads ~500 KB from PyPI
# ↓ Installs production code only
```

### For Developers (GitHub)
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
pip install -e .[dev]
# ↓ Installs from local source
# ↓ Includes all tests and development tools
```

### For CI/CD (GitHub)
```bash
pip install -e .[dev]
pytest
# ↓ Full testing suite available
# ↓ All documentation present
```

## CLI Tool Availability

The `fliq` CLI is available in **both** PyPI and GitHub:

```bash
# From PyPI
pip install fliq
fliq stress --streams 5 --duration 10

# From GitHub (development)
pip install -e .
fliq benchmark classroom.mp4
```

## What's the Same in Both

✅ Production code (engine, detection, tracking, etc.)  
✅ Optional extras (faiss, onnx, api, video)  
✅ CLI tools  
✅ Stress testing framework  
✅ Stability monitoring  
✅ Protection systems  
✅ Type hints  
✅ Documentation strings in code  

## What's Different

| Aspect | PyPI | GitHub |
|--------|------|--------|
| Test files | ❌ | ✅ |
| Documentation files | ❌ | ✅ |
| Development scripts | ❌ | ✅ |
| GitHub workflows | ❌ | ✅ |
| Size | ~500 KB | ~10 MB |
| Build files | Minimal | Complete |

## Verifying What's in PyPI

To see exactly what gets packaged:

```bash
# Build the distribution
pip install build
python -m build --sdist

# Extract and inspect
cd dist
tar -tzf fliq-0.1.0.tar.gz | head -20

# Should show:
# fliq-0.1.0/fliq/__init__.py
# fliq-0.1.0/fliq/engine.py
# ... (no tests/ directory)
```

## For Package Maintainers

### Building and Publishing

```bash
# Install build tools
pip install build twine

# Build distributions
python -m build

# Upload to PyPI (test first)
twine upload --repository testpypi dist/*
twine upload dist/*
```

**MANIFEST.in** automatically excludes tests and docs from the distribution.

### For Contributors

Tests are only in GitHub because:
1. They're essential for code review and quality assurance
2. They're not needed by end users
3. They keep the PyPI package lean

When you submit a PR:
- Include tests in `fliq/tests/`
- Update documentation in GitHub markdown
- All tests must pass (`pytest`)

## Common Questions

### Q: Can I access tests from the PyPI package?
**A**: No. Install from GitHub instead: `pip install -e git+https://github.com/your-org/fliq.git#egg=fliq[dev]`

### Q: Why are tests not in PyPI?
**A**: Standard practice. Tests are for developers; end users don't need them. This keeps the package small and fast to install.

### Q: Can I run tests with `pip install fliq`?
**A**: No. Use the GitHub repository version: `pip install -e .[dev]` then `pytest`.

### Q: Is the code the same?
**A**: Yes! The production code is identical. PyPI just has a subset of the files.

### Q: Where should I report bugs?
**A**: Always use GitHub. This is where the full source lives.

## Summary

- **PyPI (`pip install fliq`)**: Production code only, ~500 KB
- **GitHub (git clone)**: Everything including tests/docs, ~10 MB
- **Both include**: The actual production engine and all features
- **CLI works**: In both PyPI and GitHub versions
- **Tests available**: GitHub only, use `pytest` after cloning

This is a standard Python packaging practice that provides fast installation for users while maintaining full transparency and development tools for contributors.

---

**Last Updated**: May 2026  
**FLIQ Version**: v2.0 (Production Hardening)
