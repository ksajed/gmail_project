from datetime import datetime
import json
from pathlib import Path

from core_audit.summary import summarize_integrity


def write_audit_report(base_dir, model_counts, integrity_report):
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path(base_dir) / "scripts" / "v10" / "reports" / f"{now}_global_audit"
    report_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize_integrity(integrity_report)

    data = {
        "generated_at": now,
        "model_counts": model_counts,
        "integrity": integrity_report,
        "summary": summary,
    }

    json_path = report_dir / "audit_global.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    md = []
    md.append("# ORDO Global Audit")
    md.append("")
    md.append(f"Date : {now}")
    md.append("")
    md.append("## Résumé")
    md.append(f"- Score moyen : {summary['average_score']} %")
    md.append(f"- Prescriptions totales : {integrity_report.get('total')}")
    md.append(f"- Prescriptions avec anomalies : {integrity_report.get('anomalies_count')}")
    md.append("")

    md.append("## Anomalies par gravité")
    for severity, count in summary["severities"].items():
        md.append(f"- {severity} : {count}")
    md.append("")

    md.append("## Anomalies par règle")
    for code, count in summary["rules"].items():
        md.append(f"- {code} : {count}")
    md.append("")

    md.append("## Top ordonnances critiques")
    for item in summary["top_prescriptions"]:
        md.append(f"- Ordonnance {item['prescription_id']} — Score {item['score']} % — {item['prescription']}")
    md.append("")

    md.append("## Modèles")
    for item in model_counts:
        md.append(f"- {item['app']}.{item['model']} : {item['count']}")

    md.append("")
    md.append("## Détail des anomalies")
    for item in integrity_report.get("items", [])[:200]:
        md.append(f"### Ordonnance {item['prescription_id']} - Score {item['score']} %")
        md.append(f"{item['prescription']}")
        for r in item["results"]:
            md.append(f"- **{r.get('code')}** {r.get('severity')} : {r.get('message')}")
            md.append(f"  - Suggestion : {r.get('suggestion')}")
        md.append("")

    md_path = report_dir / "audit_global.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    return report_dir, md_path, json_path
