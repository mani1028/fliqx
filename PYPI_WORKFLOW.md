# PyPI Publishing Workflow

Automated GitHub Actions workflows for testing and publishing FLIQ to PyPI.

## Workflows Created

### 1. **Tests Workflow** (`.github/workflows/tests.yml`)
**Triggers**: Every push to `main`/`develop`, all pull requests

**What it does**:
- Runs pytest on Python 3.10, 3.11, 3.12
- Installs development dependencies
- Reports test results
- Uploads coverage to codecov

**When to look**: Before merging any PR

---

### 2. **PyPI Publish Workflow** (`.github/workflows/publish-to-pypi.yml`)
**Triggers**: 
- On GitHub release publish (automatic)
- Manual workflow dispatch

**What it does**:
1. Builds source distribution (sdist) and wheel
2. **Verifies** test files are excluded from distribution
3. **Uploads** to PyPI using token authentication
4. Stores artifacts in GitHub

---

## Setup Instructions

### Step 1: Get PyPI API Token

**On PyPI.org**:
1. Go to https://pypi.org/account/
2. Create new API token with "Entire account" scope
3. Copy token (starts with `pypi-`)

**On PyPI Test (optional, for testing first)**:
1. Go to https://test.pypi.org/account/
2. Create test API token

### Step 2: Add Secret to GitHub

**In GitHub Repository**:
1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `PYPI_API_TOKEN`
4. Value: Paste your PyPI token
5. Save

**Optional**: Add `TEST_PYPI_API_TOKEN` for test deployments

### Step 3: Configure Version

**In `pyproject.toml`**:
```toml
[project]
name = "fliq"
version = "0.1.0"  # Update this for each release
```

---

## Publishing Process

### Option 1: Automatic Release (Recommended)
```bash
# Create a git tag
git tag -a v0.1.0 -m "Release version 0.1.0"

# Push tag to GitHub
git push origin v0.1.0

# Go to GitHub → Releases → Create release from tag
# → Click "Publish release"
# → Workflow automatically starts
```

### Option 2: Manual Trigger
```bash
# Go to GitHub Actions
# Select "Publish to PyPI" workflow
# Click "Run workflow"
# Choose branch and click "Run"
```

---

## What Happens in Publishing Workflow

### 1. Build Phase
```
✓ Python 3.10 environment created
✓ Dependencies installed (build, twine)
✓ Distribution files generated:
  - fliq-0.1.0.tar.gz (source)
  - fliq-0.1.0-py3-*.whl (wheel)
```

### 2. Verification Phase
```
✓ Checks source distribution contents
✓ Verifies test files NOT in distribution
✓ Confirms py.typed marker included
✓ Fails if tests/ found (protection)
```

### 3. Upload Phase
```
✓ Authenticates to PyPI with token
✓ Uploads both sdist and wheel
✓ Stores artifacts for download
```

### 4. After Upload
- PyPI indexes the new version
- Available via `pip install fliq==0.1.0` after ~5 minutes
- GitHub Actions artifacts available for 90 days

---

## Workflow Files

### `publish-to-pypi.yml`

**Triggers**:
- `release: published` - When you publish a GitHub release
- `workflow_dispatch` - Manual trigger from Actions tab

**Key steps**:
- Build distributions with `python -m build`
- Verify test files excluded
- Upload with `twine upload`

**Secrets needed**:
- `PYPI_API_TOKEN` - PyPI authentication

### `tests.yml`

**Triggers**:
- Push to main/develop
- All pull requests

**Key steps**:
- Matrix test on Python 3.10, 3.11, 3.12
- Install dev dependencies
- Run pytest
- Report coverage

**No secrets needed** (tests are public)

---

## Complete Release Checklist

### Before Release
- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md` (if you have one)
- [ ] Run tests locally: `pytest`
- [ ] Verify no uncommitted changes: `git status`

### Create Release
```bash
# 1. Update version
nano pyproject.toml  # Update version = "X.Y.Z"

# 2. Commit version bump
git add pyproject.toml
git commit -m "Bump version to X.Y.Z"

# 3. Create tag
git tag -a vX.Y.Z -m "Release version X.Y.Z"

# 4. Push
git push origin main
git push origin vX.Y.Z

# 5. Create release on GitHub
# Go to https://github.com/your-org/fliq/releases
# Click "Create release from tag"
# Select your tag
# Add release notes
# Click "Publish release"
```

### After Release
- Workflow automatically starts
- Check Actions tab for progress
- Wait for green checkmark (usually 2-3 minutes)
- Verify on PyPI: https://pypi.org/project/fliq/
- Test installation: `pip install fliq==X.Y.Z`

---

## Testing Before Production

### Option 1: Test on TestPyPI First
```bash
# Modify workflow to use TestPyPI
# Or manually upload to test:

pip install build twine

python -m build

# Create TestPyPI token at https://test.pypi.org
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="your-test-pypi-token"

twine upload --repository testpypi dist/*

# Test installation
pip install -i https://test.pypi.org/simple/ fliq==X.Y.Z
```

### Option 2: Dry Run
```bash
# Build without uploading
python -m build

# Check contents
tar -tzf dist/fliq-*.tar.gz | head -20

# Verify no tests
tar -tzf dist/fliq-*.tar.gz | grep tests
# Should return nothing
```

---

## Monitoring Workflow Status

### In GitHub
1. Go to **Actions** tab
2. Select **"Publish to PyPI"** workflow
3. Click latest run to see details
4. Check for green checkmark ✓

### Workflow Logs
- Build output
- Verification results
- Upload confirmation
- Error details if failed

---

## Troubleshooting

### "PYPI_API_TOKEN not set"
**Fix**: Add secret to GitHub (Settings → Secrets)

### "Test files found in distribution"
**Fix**: Check MANIFEST.in syntax, rebuild with `python -m build`

### "Authentication failed"
**Fix**: 
- Verify token is correct
- Token may have expired (recreate on PyPI)
- Check token has "Entire account" or package scope

### "Connection timeout"
**Fix**: Usually temporary, retry the workflow

### "Wheel build failed"
**Fix**: 
- Check Python version compatibility
- Verify `pyproject.toml` syntax
- Run locally: `python -m build`

---

## Local Testing (Don't Publish)

To test your package without publishing:

```bash
# Build distributions
python -m build

# Verify contents
echo "=== Distribution contents ==="
tar -tzf dist/fliq-*.tar.gz | grep '\.py$' | head -10

# Check for test files (should be empty)
echo "=== Looking for tests (should find nothing) ==="
tar -tzf dist/fliq-*.tar.gz | grep tests

# Extract and test locally
mkdir test-install
cd test-install
pip install ../dist/fliq-*.whl
python -c "from fliq import Fliq; print(Fliq.__module__)"
```

---

## Best Practices

✅ **Always test first** - Run tests before creating release  
✅ **Use semantic versioning** - v1.0.0, v1.1.0, v2.0.0  
✅ **Update documentation** - Keep version number consistent  
✅ **Add release notes** - Explain changes in GitHub release  
✅ **Tag commits** - Use git tags for versions  
✅ **Test on testpypi first** - Before production release  
✅ **Keep tokens secret** - Never commit PYPI_API_TOKEN  
✅ **Verify distribution** - Check contents before publishing  

---

## GitHub Actions vs Local Publishing

### Using Workflow (Recommended)
```bash
# Just create a release
git tag v1.0.0
git push --tags
# Workflow does the rest
```
✅ Automated  
✅ Consistent environment  
✅ Auditable in Actions tab  
✅ No local setup needed  

### Local Publishing
```bash
python -m build
twine upload dist/*
```
✅ Full control  
✅ Test before uploading  
✅ No GitHub access needed  
❌ Manual process  
❌ Need local setup  

---

## Useful Commands

```bash
# Check if token is working
python -m twine check dist/*

# Verify package metadata
python -c "from importlib.metadata import metadata; print(metadata('fliq'))"

# Simulate upload (dry run)
twine upload --skip-existing dist/* --dry-run

# Check PyPI package
curl https://pypi.org/pypi/fliq/json | jq '.info.version'
```

---

## For Future: Additional Workflows

Consider adding:
- **CodeQL analysis** - Security scanning
- **Linting** - Code style checks
- **Type checking** - mypy validation
- **Build matrix** - Test on multiple OS (macOS, Windows, Linux)
- **Documentation** - Auto-deploy docs on release

---

## Summary

| Step | Action | Trigger |
|------|--------|---------|
| 1 | Code → GitHub | `git push` |
| 2 | Tests run | Auto on push |
| 3 | Create release | Manual on GitHub |
| 4 | Publish workflow | Auto on release |
| 5 | PyPI gets update | Workflow completes |
| 6 | Users install | `pip install fliq` |

**Time to PyPI**: ~2-3 minutes from release creation

---

**Status**: Workflows configured and ready  
**Next**: Add PYPI_API_TOKEN secret to GitHub  
**Then**: Create your first release!
