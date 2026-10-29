# Contributing

Use Python 3.12 and Node 22+. Keep the policy kernel deterministic and pure. New requirement definitions need a source pointer, explicit applicability conditions and representative-scope notes. Never introduce a claim of comprehensive regulation coverage without evidence.

For every material decision-rule change, add a targeted kernel regression test and a workflow test when it changes persistence, authorization, reviews or audit semantics. Run `pytest backend/tests -q`, `python scripts/evaluate.py`, and `npm run build --prefix frontend`.

Never commit `.env`, `.local-keys.txt`, local database files, paid-provider credentials or real customer evidence. Avoid including private source text in test fixtures. New mapping proposals require independent approval rather than silently editing the active library through agent output.

## Frontend changes

Use the existing console palette and semantic status colors. Check both light and dark appearances, narrow-screen navigation, visible keyboard focus and Left/Right/Home/End behavior in tab groups. Keep user theme preferences separate from credentials; access tokens must remain in memory. Rebuild with `npm run build --prefix frontend` before testing through FastAPI.

## Review and commits

Keep each commit focused on a real behavior, configuration or documentation improvement. Describe the resulting change in the commit subject. Include the checks actually run and their limitations in the pull request. A repeated last-change message in GitHub's file listing simply means those files were changed together.

Run `python scripts/source_manifest.py --write` after the final source edits, stage the refreshed manifest, and use `python scripts/source_manifest.py --check` to verify the tracked snapshot.
