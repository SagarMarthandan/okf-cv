"""
organize_applications.py — Sort application folders into a Year/Month/Date tree.

Layout produced under Applications/:

    Applications/
        2026/
            06/
                24/
                    [Company Name] — [Job Role]/
                    ...

Usage
-----
Standalone (sort everything in Applications/):
    python organize_applications.py

Targeted (sort a single freshly-created application folder, used by the pipeline):
    python organize_applications.py "Applications/[Company Name] — [Job Role]"

Dry run (report what would move, change nothing):
    python organize_applications.py --dry-run

Override the Applications root (for testing):
    python organize_applications.py --root "C:/path/to/fake/Applications"

The date bucket is derived from the folder's creation time (os.path.getctime),
which on Windows reflects when the folder was actually created by the pipeline.

The script is idempotent: folders already nested under a YYYY/MM/DD structure
are left in place. Re-running it is safe.
"""
import os
import shutil
import sys
from datetime import datetime

# Application folder names use an em dash (U+2014) which the default Windows
# console encoding cannot always render, crashing print() with OSError 22.
# Force UTF-8 on stdout/stderr so unicode paths always print safely.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# Resolve Applications/ relative to the project root, mirroring config.py.
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SKILL_DIR))
APPLICATIONS_DIR = os.path.join(PROJECT_ROOT, "Applications")


def _is_year_folder(name: str) -> bool:
    """True if name is a 4-digit year (top-level date bucket)."""
    return len(name) == 4 and name.isdigit()


def _creation_date(path: str) -> datetime:
    """Return the folder creation timestamp as a datetime."""
    return datetime.fromtimestamp(os.path.getctime(path))


def _target_subpath(dt: datetime) -> str:
    """Build the YYYY/MM/DD relative subpath for a given datetime."""
    return os.path.join(f"{dt.year:04d}", f"{dt.month:02d}", f"{dt.day:02d}")


def _move_into_tree(
    folder_path: str,
    applications_dir: str | None = None,
    dry_run: bool = False,
) -> str | None:
    """
    Move a single application folder into Applications/YYYY/MM/DD/.

    Returns the new path on success, or None if the folder was already nested
    under a date tree (or could not be moved).
    """
    apps_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(folder_path):
        print(f"  skip (not a directory): {folder_path}")
        return None

    # Skip folders already inside a YYYY/MM/DD tree.
    rel = os.path.relpath(folder_path, apps_dir)
    parts = rel.split(os.sep)
    if len(parts) >= 4 and _is_year_folder(parts[0]):
        print(f"  skip (already sorted): {rel}")
        return None

    dt = _creation_date(folder_path)
    dest_dir = os.path.join(apps_dir, _target_subpath(dt))
    dest_path = os.path.join(dest_dir, os.path.basename(folder_path))

    if os.path.exists(dest_path):
        # Same-named folder already exists at the destination. If the source is
        # already there (path equals dest), nothing to do. Otherwise warn.
        if os.path.normcase(folder_path) == os.path.normcase(dest_path):
            print(f"  skip (already in place): {rel}")
            return None
        print(f"  WARN destination exists, leaving in place: {dest_path}")
        return None

    if dry_run:
        print(f"  [dry-run] {rel} -> {os.path.relpath(dest_path, apps_dir)}")
        return dest_path

    os.makedirs(dest_dir, exist_ok=True)
    shutil.move(folder_path, dest_path)
    print(f"  moved: {rel} -> {os.path.relpath(dest_path, apps_dir)}")
    return dest_path


def sort_all(
    applications_dir: str | None = None,
    dry_run: bool = False,
) -> int:
    """Scan Applications/ top-level and move every non-year folder into the tree."""
    apps_dir = applications_dir if applications_dir is not None else APPLICATIONS_DIR
    if not os.path.isdir(apps_dir):
        print(f"Applications directory not found: {apps_dir}")
        return 0

    moved = 0
    for name in sorted(os.listdir(apps_dir)):
        full = os.path.join(apps_dir, name)
        if not os.path.isdir(full):
            continue
        if _is_year_folder(name):
            continue  # existing date-tree year bucket
        if _move_into_tree(full, applications_dir=apps_dir, dry_run=dry_run):
            moved += 1
    return moved


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    apps_dir = APPLICATIONS_DIR
    args: list[str] = []
    it = iter(argv[1:])
    for arg in it:
        if arg == "--dry-run":
            continue
        if arg == "--root":
            apps_dir = next(it, APPLICATIONS_DIR)
            continue
        args.append(arg)

    print(f"Applications root: {apps_dir}")

    if args:
        # Targeted mode: sort the supplied folder(s).
        for arg in args:
            # Accept a path relative to cwd or to Applications/.
            candidate = arg if os.path.isabs(arg) else os.path.abspath(arg)
            if not os.path.isdir(candidate):
                candidate = os.path.join(apps_dir, arg)
            print(f"Sorting: {candidate}")
            _move_into_tree(candidate, applications_dir=apps_dir, dry_run=dry_run)
    else:
        # Scan mode: sort everything in Applications/.
        print("Scanning Applications/ for unsorted application folders...")
        count = sort_all(applications_dir=apps_dir, dry_run=dry_run)
        print(f"Done. Moved {count} folder(s).")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
