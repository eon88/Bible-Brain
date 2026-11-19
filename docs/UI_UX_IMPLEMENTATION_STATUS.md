# Bible Brain UI/UX redesign implementation status

Updated 19 November 2026. The authoritative design remains `UI_UX_REDESIGN_PLAN.md`.

## Verified in the current repository

- Reader-first launch: Bible opens in Reading mode with the Companion closed.
- Direct reference navigation, continuous same-book chapters, visible chapter tracking, translation selection, typography settings and saved reader location.
- Study Companion with exactly three tabs: Connections, Traces and Studies.
- Desktop right-side Companion and narrow-window vertical bottom-sheet layout.
- Stable pinned investigations and up to 50 recent investigation entries.
- Independent, persistent collapsible Companion sections keyed by investigation, tab and section ID.
- Manual Reading, Exploration and Mapping modes with independent Exploration filters.
- Exact selection toolbar: Explore, Trace, Save and Copy.
- Copy preserves selected text, reference and displayed translation.
- Explicit Trace picker, saved ordering, non-looping navigation, passage list and origin restoration.
- Mapping preview, explicit Follow, Back history and return to the originating reader location.
- Structured Studies with observations, questions, interpretations, conclusions, Scripture links and Trace attachments.
- Evidence/review separation and existing Keep, Investigate, Park and Reject workflows.
- Backup/restore and existing SQLite data model remain intact.

## Automated evidence

Run from the repository root:

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

The current suite contains 37 passing tests, including reader launch, selection actions, Companion persistence, phone-portrait layout, the Tree of Life Trace journey and Mapping preview/follow/back.

Windows packaging has been rebuilt successfully with:

```powershell
& .\scripts\build-windows.ps1
& .\scripts\build-installer.ps1 -PerUser
```

Artifacts:

- `dist\Bible Brain\Bible Brain.exe`
- `dist\Bible-Brain-Setup-0.2.0-x64-user.msi`
- The current user's desktop shortcut is verified to target `%LOCALAPPDATA%\Programs\Bible Brain\Bible Brain.exe` directly.

## Still required before formal release acceptance

- Execute the complete ten-step acceptance journey on the installed build, including real persisted data, backup/restore and restart boundaries.
- Test touch selection, sheet dragging and Trace navigator collision behavior on a physical Android/iOS device or equivalent device lab.
- Record final clean-install and upgrade results from a separate Windows profile.

These are verification gates, not claims that the application has already passed them.
