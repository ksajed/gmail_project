# ORDO Global Audit

Date : 20260703_163930

## Modèles
- core_adminconsole.AdminAuditEvent : 100
- admin.LogEntry : 12
- auth.Permission : 125
- auth.Group : 7
- auth.User : 8
- contenttypes.ContentType : 30
- sessions.Session : 17
- core_accounts.UserProfile : 8
- core_gmail.GmailMessage : 501
- core_emails.Prescription : 569
- core_emails.PrescriptionStatusHistory : 794
- core_emails.PrescriptionAssignment : 55
- core_emails.PrescriptionRenewalInfo : 113
- core_emails.PrescriptionRenewalEvent : 36
- core_emails.PrescriptionRenewalCycle : 109
- core_emails.PrescriptionNotificationSettings : 123
- core_emails.PrescriptionNotificationEvent : 180
- core_emails.RenewalSettings : 1
- core_emails.RenewalNotificationRule : 5
- core_emails.RenewalNotificationTemplate : 2
- core_emails.Holiday : 1
- core_attachments.PrescriptionAttachment : 53
- core_attachments.PrescriptionAttachmentAccess : 16
- core_notifications.Notification : 3721
- core_notifications.SmsTemplate : 0
- core_notifications.SmsMessage : 134
- core_notifications.SmsAttempt : 134
- core_patients.Patient : 72
- core_people.Person : 16

## Integrity
- Prescriptions totales : 569
- Prescriptions avec anomalies : 46

## Anomalies
### Ordonnance 17 - Score 50 %
Ordonnance #17 – Archivée
- **P001** ERROR : Ordonnance archivée avec un cycle encore actif.
  - Suggestion : Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 19 - Score 75 %
Ordonnance #19 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 31 - Score 75 %
Ordonnance #31 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 42 - Score 75 %
Ordonnance #42 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 43 - Score 75 %
Ordonnance #43 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 44 - Score 75 %
Ordonnance #44 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 46 - Score 75 %
Ordonnance #46 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 47 - Score 75 %
Ordonnance #47 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 49 - Score 75 %
Ordonnance #49 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 50 - Score 75 %
Ordonnance #50 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 51 - Score 75 %
Ordonnance #51 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 52 - Score 75 %
Ordonnance #52 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 53 - Score 75 %
Ordonnance #53 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 188 - Score 75 %
Ordonnance #188 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 214 - Score 75 %
Ordonnance #214 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 233 - Score 75 %
Ordonnance #233 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 269 - Score 75 %
Ordonnance #269 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 276 - Score 75 %
Ordonnance #276 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 287 - Score 75 %
Ordonnance #287 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 297 - Score 75 %
Ordonnance #297 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 304 - Score 75 %
Ordonnance #304 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 314 - Score 75 %
Ordonnance #314 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 316 - Score 75 %
Ordonnance #316 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 318 - Score 75 %
Ordonnance #318 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 331 - Score 75 %
Ordonnance #331 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 353 - Score 75 %
Ordonnance #353 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 364 - Score 50 %
Ordonnance #364 – Archivée
- **P001** ERROR : Ordonnance archivée avec un cycle encore actif.
  - Suggestion : Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 376 - Score 50 %
Ordonnance #376 – Archivée
- **P001** ERROR : Ordonnance archivée avec un cycle encore actif.
  - Suggestion : Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 380 - Score 50 %
Ordonnance #380 – Archivée
- **P001** ERROR : Ordonnance archivée avec un cycle encore actif.
  - Suggestion : Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 384 - Score 50 %
Ordonnance #384 – Archivée
- **P001** ERROR : Ordonnance archivée avec un cycle encore actif.
  - Suggestion : Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 394 - Score 50 %
Ordonnance #394 – Archivée
- **P001** ERROR : Ordonnance archivée avec un cycle encore actif.
  - Suggestion : Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 409 - Score 50 %
Ordonnance #409 – Archivée
- **P001** ERROR : Ordonnance archivée avec un cycle encore actif.
  - Suggestion : Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 411 - Score 75 %
Ordonnance #411 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 421 - Score 75 %
Ordonnance #421 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 427 - Score 75 %
Ordonnance #427 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 432 - Score 75 %
Ordonnance #432 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 440 - Score 75 %
Ordonnance #440 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 452 - Score 75 %
Ordonnance #452 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 457 - Score 75 %
Ordonnance #457 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 458 - Score 75 %
Ordonnance #458 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 459 - Score 75 %
Ordonnance #459 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 460 - Score 75 %
Ordonnance #460 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 469 - Score 75 %
Ordonnance #469 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 470 - Score 75 %
Ordonnance #470 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 474 - Score 75 %
Ordonnance #474 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.

### Ordonnance 477 - Score 75 %
Ordonnance #477 – Archivée
- **P002** ERROR : Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.
  - Suggestion : Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.
