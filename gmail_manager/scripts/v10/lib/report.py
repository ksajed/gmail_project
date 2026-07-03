from pathlib import Path
from datetime import datetime

def write_report(base_dir, name, content):
    base_dir = Path(base_dir)
    reports_dir = base_dir / "scripts" / "v10" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = reports_dir / f"{timestamp}_{name}.md"
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path
