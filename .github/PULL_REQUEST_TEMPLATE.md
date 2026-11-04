## What changed

<!-- One or two sentences. Link the issue if there is one. -->

## Verification

<!-- Paste actual command output, not just "tested". -->

- [ ] `python3 scripts/verify_claims.py` passes (if any catalog number changed)
- [ ] `python3 scripts/test_claims_tools.py` passes (if verify/sync changed)
- [ ] `python3 scripts/test_error_handlers.py` passes (if error handling changed)
- [ ] `python3 scripts/test_aiwave_setup.py` passes (if the setup script changed)
- [ ] Syntax checks: `python3 -m compileall -q examples scripts`, `node --check examples/*.mjs`, `bash -n examples/*.sh`
- [ ] No API keys, tokens or customer data in the diff

## Notes

<!-- Caveats, follow-ups, anything a reviewer should know. -->
