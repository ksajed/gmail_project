from pathlib import Path
from datetime import datetime

def log_migration(base_dir, script_name, status, message=""):
    base_dir = Path(base_dir)
    log_file = base_dir / "scripts" / "v10" / "migrations.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    line = (
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"{script_name} | {status} | {message}\n"
    )

    with log_file.open("a", encoding="utf-8") as f:
        f.write(line)
