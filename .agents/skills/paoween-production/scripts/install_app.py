#!/usr/bin/env python3
"""Copy the bundled clean Paoween application into a new empty project."""
import argparse
import shutil
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = SKILL_ROOT / "assets" / "production-app"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, help="New or empty application directory")
    args = parser.parse_args()
    destination = Path(args.destination).expanduser().resolve()
    if not APP_SOURCE.is_dir():
        raise SystemExit(f"Bundled application is missing: {APP_SOURCE}")
    if destination.exists():
        if not destination.is_dir():
            raise SystemExit(f"Destination is not a directory: {destination}")
        if any(destination.iterdir()):
            raise SystemExit(f"Refusing to overwrite a non-empty directory: {destination}")
    else:
        destination.mkdir(parents=True)
    shutil.copytree(APP_SOURCE, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    # The app's "ช้อปอย่างคิด" box reads .agents/skills/shopping-agent from the app folder.
    # In my-finance that skill sits next to this one, so bring it along.
    shopping = SKILL_ROOT.parent / "shopping-agent"
    if shopping.is_dir():
        shutil.copytree(shopping, destination / ".agents" / "skills" / "shopping-agent", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    print(f"Installed clean Paoween app to {destination}")
    print("Ledger templates contain headers only. Install dependencies with: python3 -m pip install -r requirements.txt")


if __name__ == "__main__":
    main()
