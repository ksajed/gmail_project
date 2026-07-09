from django.apps import apps

def count_models():
    results = []

    for model in apps.get_models():
        try:
            count = model.objects.count()
        except Exception:
            count = None

        results.append({
            "app": model._meta.app_label,
            "model": model.__name__,
            "table": model._meta.db_table,
            "count": count,
        })

    return results
