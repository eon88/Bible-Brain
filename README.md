# Bible Brain

Bible Brain is a standalone, offline Scripture reader and personal research workspace for Windows. Bundle 01 ships the complete public-domain World English Bible Protestant Edition, a local SQLite library and a versioned note editor.

## Run on Windows 11 x64

- **Portable build** — open `dist\Bible Brain\Bible Brain.exe`. Keep `_internal` alongside the executable.
- **Installer** — open `dist\Bible-Brain-Setup-0.1.0-x64.msi` on 64-bit Windows. Windows Installer installs the app in Program Files and adds shortcuts. This local development package is unsigned and Windows may ask for administrator approval.

The packaged app includes Python, Qt and Scripture. It opens without an internet connection or a separate runtime installation. The default data directory is `%LOCALAPPDATA%\Bible Brain`, which contains `library.sqlite3`, preferences and rotating diagnostic logs. The installer manages the program files. Each library and any backup files you create are stored separately.

## Read and research

1. Pick the translation, book and chapter in the reader. The previous and next buttons also navigate across book boundaries.
2. Click a verse to select its reference. Drag across a word, phrase or several verses to select edition-specific text. Use **New note** in the selection bar, or open **Research** and attach the selection to an existing note.
3. In **Research**, use **Manage** to create, rename, move or delete folders. Use the note’s **Folder** control to move a note. Deleting a folder moves its contents to the parent and keeps the notes. In a folder name collision, the moved subfolder receives a numeric suffix. Choose **Labels** to organize a note and **History** to inspect or restore saved revisions. Restoring a revision from a deleted folder places the note at the top level.
4. Use **Settings** to choose a theme or reading size, import a local translation, and find, open or create a database. Opening a different path switches libraries. Back up and restore when you want to copy a library to a different path.
5. Choose **Back up** in Settings for a consistent SQLite snapshot. **Restore** checks the chosen snapshot and replaces the active library after making a recovery copy of its previous state. Keep backups in a location you control. Backups contain Scripture, research, and revisions. Appearance preferences are stored in `settings.json`.

See [Scripture datasets](docs/SCRIPTURE.md) for the publisher’s licence, provenance and the UTF-8 `.json` / `.json.gz` import format. See [Third-party notices](docs/THIRD_PARTY.md) for the packaged runtime licences.

## Develop and build

From the repository root in PowerShell, using 64-bit Python 3.12 and Git:

```powershell
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-build.txt
& '.\.venv\Scripts\python.exe' -m bible_brain
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '.\scripts\build-windows.ps1'
& '.\scripts\build-installer.ps1'
```

Use `-m bible_brain --data-dir 'C:\path\to\test-profile'` to launch with a separate local profile. The packaged executable accepts the same option. The dependency installation and initial WiX Toolset download require internet access on an uncached development machine. See [Architecture](docs/ARCHITECTURE.md) for the database model, local service boundaries and extension contracts. [WiX Toolset 3.14.1](https://github.com/wixtoolset/wix3/releases/tag/wix3141rtm)

## Scope

Bundle 01 includes the Scripture reader, shared graph storage and research workspace basics. The bundled edition uses verse text and omits publisher notes, headings and paragraph layout. The next bundle is Original Languages, starting with one licensed Greek text and verified Strong’s and morphology mappings, then expanding to Hebrew and Aramaic. AI, advanced graph tools and Android synchronization are later bundles.
