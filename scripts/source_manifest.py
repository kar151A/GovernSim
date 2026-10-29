"""Hash tracked source files reproducibly without including local runtime data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

MANIFEST = 'SOURCE_MANIFEST.json'

def file_digest(path: Path) -> str:
    data = path.read_bytes()
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        pass  # Binary artifacts retain their original bytes.
    else:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()

def snapshot(root: Path) -> dict[str, str]:
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    return {name: file_digest(root / name)
            for name in sorted(set(paths)) if name and name != MANIFEST}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true', help='Refresh the manifest.')
    mode.add_argument('--check', action='store_true', help='Verify without changing files.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / MANIFEST
    current = snapshot(root)
    if args.write:
        target.write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
        print(f'Recorded {len(current)} tracked files.')
        return 0
    recorded = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    differences = [name for name in sorted(current.keys() | recorded.keys()) if current.get(name) != recorded.get(name)]
    if differences:
        print('Source manifest needs refresh: ' + ', '.join(differences))
        return 1
    print(f'Verified {len(current)} tracked files.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
