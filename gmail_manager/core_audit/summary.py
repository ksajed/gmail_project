from collections import Counter


def summarize_integrity(integrity_report):
    items = integrity_report.get("items", [])

    rule_counter = Counter()
    severity_counter = Counter()
    scores = []

    for item in items:
        scores.append(item.get("score", 100))

        for result in item.get("results", []):
            rule_counter[result.get("code", "UNKNOWN")] += 1
            severity_counter[result.get("severity", "UNKNOWN")] += 1

    avg_score = 100
    if scores:
        avg_score = round(sum(scores) / len(scores), 2)

    return {
        "average_score": avg_score,
        "rules": dict(rule_counter),
        "severities": dict(severity_counter),
        "top_prescriptions": sorted(
            items,
            key=lambda x: x.get("score", 100)
        )[:20],
    }
