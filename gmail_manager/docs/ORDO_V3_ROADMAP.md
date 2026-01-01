# Ordo V3 — Roadmap officielle

## Base de référence
- Version stable : Ordo V2 (tag `ordo-v2.0`)
- Branche de travail : `v3`
- Interdiction absolue : régression V2

---

## Objectif principal V3

Permettre au pharmacien de créer manuellement une ordonnance depuis le dashboard
lorsqu’elle ne provient pas d’un email (papier, comptoir, téléphone, urgence).

---

## Fonctionnalités incluses en V3

### 1. Création manuelle d’une ordonnance
- Bouton « Nouvelle ordonnance » dans le dashboard
- Création d’un dossier ordonnance sans email
- Statut initial automatique : Reçue
- Création par un utilisateur authentifié (pharmacien)

### 2. Données saisissables
- Origine de l’ordonnance :
  - Patient
  - Infirmier
  - Médecin
- Email patient (minimum requis)
- Ajout de pièces jointes (scan / photo)
- Commentaire organisationnel optionnel

---

## Traçabilité & preuve (obligatoire)
- Historique opposable :
  - « Ordonnance créée manuellement par le pharmacien »
- Horodatage
- Auteur identifié
- Aucune suppression possible

---

## Hors périmètre V3
- Décision médicale
- Posologie
- Validation clinique
- Facturation / télétransmission
- Notifications automatiques (V3+)

---

## Critères de validation V3
- Création visible dans le dashboard
- Redirection vers le détail ordonnance
- Historique présent et lisible
- Aucune régression V2
