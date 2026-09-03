# Changelog

All notable changes to this project will be documented in this file.

## v0.1.4 - 2026-03-11

### Changed

- Reworked `xhs login --qrcode` to use a browser-assisted network-response flow.
- Removed the legacy DOM/screenshot-based QR extraction path.
- Synced README and README_EN to the current QR login behavior.

### Validation

- `python -m compileall xhs_cli` passes.
- `uv run pytest tests/test_auth.py tests/test_cli.py` passes (`61 passed`).

## v0.1.2 - 2026-03-06

### Added

- Added terminal QR rendering with half-block characters (`▀`, `▄`, `█`) for QR login.
- Added post-login session usability probing (feed/search) to detect limited/guest sessions.
- Added stricter and broader test coverage for auth, CLI login flows, and publish heuristics.
- Added `qrcode` dependency for terminal QR rendering.

### Changed

- Strengthened cookie requirements for saved/manual auth:
  - Required cookies are now `a1` + `web_session`.
- Improved QR login robustness:
  - Switched `xhs login --qrcode` to a browser-assisted network-response flow.
  - Export QR URL from `login/qrcode/create` instead of scraping page DOM.
  - Export session cookies after `login/qrcode/status` instead of guessing from page state.
- Improved login success detection:
  - Treat guest sessions as invalid.
  - Wait for post-login browser session stabilization before persisting cookies.
- Improved operation reliability:
  - Tightened success criteria for publish/comment/delete flows.
  - Added strict data-wait timeout path to reduce silent empty results.
- Updated `whoami --json` to include normalized top-level fields when resolvable.
- Updated docs (`README.md` and `README_EN.md`) to match current login/auth behavior.

### Fixed

- Fixed transient cookie verification flow to avoid unintended QR login fallback.
- Fixed favorites note ID extraction regex to support alphanumeric note IDs.
- Fixed cross-platform cookie save behavior by handling `chmod` failures safely.
- Fixed multiple false-positive success cases in interaction and publish flows.

### Validation

- `ruff check .` passes.
- `pytest -q` passes (`66 passed, 21 deselected`).
