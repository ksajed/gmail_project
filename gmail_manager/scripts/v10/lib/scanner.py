from pathlib import Path

def find_files(base_dir, patterns):
    base_dir = Path(base_dir)
    results = []

    for pattern in patterns:
        results.extend(base_dir.rglob(pattern))

    ignored = [
        "/venv/",
        "/.git/",
        "/__pycache__/",
        "/backups/",
        "/node_modules/",
    ]

    clean = []
    for path in results:
        text = str(path)
        if any(i in text for i in ignored):
            continue
        clean.append(path)

    return sorted(clean)
