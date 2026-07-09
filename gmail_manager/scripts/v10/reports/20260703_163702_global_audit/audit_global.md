# ORDO Global Audit

Date : 20260703_163702

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
- Prescriptions avec anomalies : 10

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
