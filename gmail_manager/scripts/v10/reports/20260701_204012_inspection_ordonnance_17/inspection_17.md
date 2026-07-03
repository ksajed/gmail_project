# ORDO Inspector - Ordonnance 17

Date : 20260701_204012

## Prescription
- **id** : 17
- **status** : ARCHIVED
- **type** : RENOUVELLEMENT
- **sender_type** : doctor
- **patient** : Khalid Sajed
- **established_at** : 2026-01-27
- **received_at** : 2026-01-27 17:25:11.237094+00:00
- **updated_at** : 2026-01-30 00:23:58.444620+00:00
- **processing_started_at** : None
- **created_by** : None
- **is_deleted** : False
- **deleted_at** : None
- **deleted_by** : None
- **delete_reason** : 

## Objets liés
### PrescriptionStatusHistory via `status_history`
Nombre : 21

```
id: 7
prescription: Ordonnance #17 – Archivée
old_status: RECEIVED
new_status: RECEIVED
changed_by: ksajed
changed_at: 2026-01-27 17:37:17.550350+00:00
comment: Type d’ordonnance modifié : INCOMPLETE → RENOUVELLEMENT
```

```
id: 8
prescription: Ordonnance #17 – Archivée
old_status: RECEIVED
new_status: RECEIVED
changed_by: ksajed
changed_at: 2026-01-27 17:37:26.131371+00:00
comment: Infos renouvellement mises à jour : date médecin=2026-01-27, renewal_times=0, period_days=30, doctor_email=—.
```

```
id: 9
prescription: Ordonnance #17 – Archivée
old_status: RECEIVED
new_status: RECEIVED
changed_by: ksajed
changed_at: 2026-01-27 17:48:16.974233+00:00
comment: Infos renouvellement mises à jour : date médecin=2026-01-27, renewal_times=1, period_days=30, doctor_email=—.
```

```
id: 10
prescription: Ordonnance #17 – Archivée
old_status: RECEIVED
new_status: RECEIVED
changed_by: ksajed
changed_at: 2026-01-27 17:48:35.217192+00:00
comment: Origine de l’ordonnance modifiée : unknown → patient
```

```
id: 11
prescription: Ordonnance #17 – Archivée
old_status: RECEIVED
new_status: IN_PROGRESS
changed_by: ksajed
changed_at: 2026-01-27 17:48:42.915370+00:00
comment: Changement de statut : Received → In Progress
```

```
id: 12
prescription: Ordonnance #17 – Archivée
old_status: IN_PROGRESS
new_status: READY
changed_by: ksajed
changed_at: 2026-01-27 17:48:50.545488+00:00
comment: Changement de statut : In Progress → Ready
```

```
id: 13
prescription: Ordonnance #17 – Archivée
old_status: READY
new_status: DELIVERED
changed_by: ksajed
changed_at: 2026-01-27 17:49:02.923745+00:00
comment: Changement de statut : Ready → Delivered
```

```
id: 14
prescription: Ordonnance #17 – Archivée
old_status: DELIVERED
new_status: RECEIVED
changed_by: ksajed
changed_at: 2026-01-27 17:49:03.865753+00:00
comment: Renouvellement: délivrance enregistrée (n°1/2). Statut réinitialisé pour le prochain cycle.
```

```
id: 15
prescription: Ordonnance #17 – Archivée
old_status: RECEIVED
new_status: RECEIVED
changed_by: ksajed
changed_at: 2026-01-27 19:00:42.548094+00:00
comment: Infos renouvellement mises à jour : date médecin=2026-01-27, renewal_times=1, period_days=30, doctor_email=khalidsajed1975@gmail.com.
```

```
id: 16
prescription: Ordonnance #17 – Archivée
old_status: RECEIVED
new_status: RECEIVED
changed_by: ksajed
changed_at: 2026-01-27 19:00:49.278446+00:00
comment: Demande renouvellement envoyée au médecin (EMAIL).
```

### PrescriptionRenewalEvent via `renewal_events`
Nombre : 0

### PrescriptionRenewalCycle via `renewal_cycles`
Nombre : 1

```
id: 99
prescription: Ordonnance #17 – Archivée
cycle_number: 1
status: RECEIVED
started_at: 2026-03-31 14:24:24.854010+00:00
closed_at: None
reminder_5_patient_email_sent_at: None
reminder_5_patient_sms_sent_at: None
reminder_3_patient_email_sent_at: None
reminder_3_patient_sms_sent_at: None
doctor_email_sent_at: None
```

### PrescriptionNotificationEvent via `notification_events`
Nombre : 0

### PrescriptionAttachment via `attachments`
Nombre : 0

### SmsMessage via `sms_messages`
Nombre : 0


## Anomalies détectées
- ⚠️ Ordonnance archivée : vérifier pourquoi elle apparaît encore dans les urgences.
- ⚠️ Cycle encore en statut RECEIVED pour une ordonnance potentiellement archivée.