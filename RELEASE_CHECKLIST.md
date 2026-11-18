# Bible Brain 0.2.0 release checklist

- [x] Freeze current implementation and use an isolated test profile.
- [x] Add incremental FTS synchronization and manual rebuild support.
- [x] Add conversation proposal source display and review controls.
- [x] Add Ollama conversation analysis action with offline fallback.
- [x] Link approved conversation proposals to validated Scripture anchors.
- [x] Run regression and migration smoke tests.
- [x] Establish application version 0.2.0 and update installer documentation.
- [x] Rebuild Windows executable and per-user MSI.
- [x] Complete genuine Ollama generation acceptance test on this machine (`phi3.5:3.8b`).
- [x] Complete upgrade test over the existing per-user installation (MSI exit 0, executable and Start-menu shortcut verified).
- [ ] Complete clean-install test on a separate Windows profile.
- [x] Add and run repeatable isolated acceptance coverage for Tree of Life, conversation reimport, rejected discoveries, FTS repair and backup/restore.
- [ ] Complete the full interactive UI walkthrough for all five scenarios.

The unchecked items require interactive Windows/model state and must not be claimed from compilation alone.
