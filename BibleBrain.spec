from importlib.metadata import distribution
from pathlib import Path
import sys

root = Path(SPECPATH)
pyinstaller = distribution("pyinstaller")
pyinstaller_license = next(path for path in pyinstaller.files if path.name == "COPYING.txt")

analysis = Analysis(
    [str(root / "bible_brain" / "__main__.py")],
    pathex=[str(root)],
    datas=[
        (str(root / "bible_brain" / "data" / "web.json.gz"), "bible_brain/data"),
        (str(root / "bible_brain" / "data" / "STEP-TAGNT-AR3.bb-lang"), "bible_brain/data"),
        (str(root / "bible_brain" / "data" / "STEP-TAHOT-GEN3.bb-lang"), "bible_brain/data"),
        (str(root / "bible_brain" / "data" / "STEP-TAHOT-ARAMAIC2.bb-lang"), "bible_brain/data"),
        (str(root / "bible_brain" / "migrations" / "*.sql"), "bible_brain/migrations"),
        (str(root / "bible_brain" / "fonts" / "*.otf"), "bible_brain/fonts"),
        (str(root / "bible_brain" / "fonts" / "*.ttf"), "bible_brain/fonts"),
        (str(root / "bible_brain" / "fonts" / "*.txt"), "licenses/Fonts"),
        (str(root / "docs" / "SCRIPTURE.md"), "licenses"),
        (str(root / "docs" / "THIRD_PARTY.md"), "licenses"),
        (str(root / "docs" / "qt-licenses" / "*.txt"), "licenses/Qt"),
        (str(Path(sys.base_prefix) / "LICENSE.txt"), "licenses/CPython"),
        (str(pyinstaller.locate_file(pyinstaller_license)), "licenses/PyInstaller"),
    ],
    excludes=["PySide6.QtNetwork", "tkinter"],
)


def ship_binary(entry):
    name = Path(entry[0]).name.casefold()
    # Windows 11 supplies Qt's unversioned ICU C ABI and the UCRT. Avoid resolving them to unrelated tools on PATH.
    if name in {"icu.dll", "icuuc.dll", "icuin.dll", "ucrtbase.dll"} or name.startswith(("api-ms-win-", "icudt")):
        return False
    # This Widgets app uses raster rendering and has no Qt TLS or OpenGL surfaces.
    return name not in {"opengl32sw.dll", "libssl-3-x64.dll", "libcrypto-3-x64.dll"}


analysis.binaries = [entry for entry in analysis.binaries if ship_binary(entry)]
archive = PYZ(analysis.pure)
application = EXE(archive, analysis.scripts, exclude_binaries=True, name="Bible Brain", console=False, upx=False)
bundle = COLLECT(application, analysis.binaries, analysis.datas, name="Bible Brain", upx=False)
