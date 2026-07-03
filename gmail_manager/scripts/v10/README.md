# ORDO V10 - Framework de migration

Ce dossier contient les scripts de migration ORDO V10.

## Règles

- Ne jamais modifier les fichiers métier sans backup.
- Utiliser les fonctions du dossier `lib/`.
- Chaque migration doit être traçable dans `migrations.log`.
- Chaque modification doit être réversible.
- Le moteur V9 ne doit pas être modifié sans validation explicite.

## Structure

- `lib/backup.py` : sauvegardes automatiques
- `lib/patch.py` : modifications sécurisées
- `lib/logger.py` : journal des migrations
- `lib/scanner.py` : scan du projet
- `lib/report.py` : rapports Markdown
- `reports/` : rapports générés
- `logs/` : journaux détaillés
- `backups/` : backups spécifiques aux scripts
