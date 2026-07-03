from pathlib import Path
from datetime import datetime
import shutil

def create_backup(base_dir, files, label="backup"):
    base_dir = Path(base_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = base_dir / "backups" / "ordo_v10" / f"{timestamp}_{label}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    copied = []

    for file in files:
        source = base_dir / file
        if not source.exists():
            continue

        destination = backup_dir / file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(file)

    return backup_dir, copied
