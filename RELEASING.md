# Releasing

This repo holds examples and scripts, not a published package. The SDKs
(`aiwave-sdk-python`, `aiwave-sdk-node`) are published separately.

## Before any release

```bash
python3 scripts/verify_claims.py          # every repo's numbers vs the live endpoint
python3 scripts/test_claims_tools.py      # verify/sync tools still agree
python3 scripts/test_error_handlers.py    # offline behavior of error handlers
bash -n examples/*.sh                     # shell syntax
node --check examples/*.mjs               # JS syntax
```

`verify_claims.py` reads the live public endpoint and scans the text of all
repos for catalog-listed IDs, family counts, and video IDs. These counts do
not measure live route health. If it fails, the catalog changed — run `sync_claims.py` (it rewrites
only the numbers and stamps `catalog-claims.json`), review `git diff`, then
re-run the verify. Never patch numbers by hand.

CI (`.github/workflows/ci.yml`) runs these on every push and also daily
at 06:17 UTC, so catalog drift is caught even when nobody commits.

## SDK release (separate repos)

1. Bump version in all places: `pyproject.toml`, `setup.py`,
   `aiwave/__init__.py` (Python) / `package.json` (Node)
2. Regenerate `MODEL_REFERENCE.md`:
   `python3 scripts/gen_model_reference.py`
3. Update `CHANGELOG.md` with the date and what changed
4. Commit and tag: `git tag -a v0.2.0 -m "..."`
5. Build and verify locally:
   - Python: `python -m build && twine check dist/*`
   - Node: `npm pack --dry-run && node --check src/index.js`
6. Publish:
   - Python: `twine upload dist/*` (token scoped to the `aiwave` project)
   - Node: `npm publish --access public` (requires a granular token with
     **Bypass 2FA** enabled)
7. Verify from a clean environment — this step is not optional:
   - `pip install aiwave==<version>` then import and call a method
   - `npm install aiwave@<version>` then `require` and call a method
   npm CDN propagation can take a few minutes; a `notarget` error right
   after publishing usually means "wait and retry", not "publish failed".
8. Report the verified version in the release notes.

## Rollback

A broken example or script: revert the commit. A broken SDK release cannot
be unpublished from PyPI/npm — publish a new patch version instead and mark
the bad one as yanked/deprecated in the release notes.
