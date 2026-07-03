# ORDO V10 - Découverte des modèles Django

## core_adminconsole.AdminAuditEvent
Table : `core_adminconsole_adminauditevent`

- `id` (BigAutoField)
- `actor` → `auth.User` (ForeignKey)
- `action` (CharField)
- `target_type` (CharField)
- `target_id` (CharField)
- `summary` (CharField)
- `ip_address` (GenericIPAddressField)
- `user_agent` (TextField)
- `metadata` (JSONField)
- `created_at` (DateTimeField)

## admin.LogEntry
Table : `django_admin_log`

- `id` (AutoField)
- `action_time` (DateTimeField)
- `user` → `auth.User` (ForeignKey)
- `content_type` → `contenttypes.ContentType` (ForeignKey)
- `object_id` (TextField)
- `object_repr` (CharField)
- `action_flag` (PositiveSmallIntegerField)
- `change_message` (TextField)

## auth.Permission
Table : `auth_permission`

- `group` → `auth.Group` (ManyToManyRel)
- `user` → `auth.User` (ManyToManyRel)
- `id` (AutoField)
- `name` (CharField)
- `content_type` → `contenttypes.ContentType` (ForeignKey)
- `codename` (CharField)

## auth.Group
Table : `auth_group`

- `user` → `auth.User` (ManyToManyRel)
- `id` (AutoField)
- `name` (CharField)
- `permissions` → `auth.Permission` (ManyToManyField)

## auth.User
Table : `auth_user`

- `admin_audit_events` → `core_adminconsole.AdminAuditEvent` (ManyToOneRel)
- `logentry` → `admin.LogEntry` (ManyToOneRel)
- `profile` → `core_accounts.UserProfile` (OneToOneRel)
- `prescription` → `core_emails.Prescription` (ManyToOneRel)
- `deleted_prescriptions` → `core_emails.Prescription` (ManyToOneRel)
- `prescriptionstatushistory` → `core_emails.PrescriptionStatusHistory` (ManyToOneRel)
- `created_renewal_events` → `core_emails.PrescriptionRenewalEvent` (ManyToOneRel)
- `created_notification_events` → `core_emails.PrescriptionNotificationEvent` (ManyToOneRel)
- `prescriptionattachment` → `core_attachments.PrescriptionAttachment` (ManyToOneRel)
- `prescriptionattachmentaccess` → `core_attachments.PrescriptionAttachmentAccess` (ManyToOneRel)
- `notifications` → `core_notifications.Notification` (ManyToOneRel)
- `id` (AutoField)
- `password` (CharField)
- `last_login` (DateTimeField)
- `is_superuser` (BooleanField)
- `username` (CharField)
- `first_name` (CharField)
- `last_name` (CharField)
- `email` (EmailField)
- `is_staff` (BooleanField)
- `is_active` (BooleanField)
- `date_joined` (DateTimeField)
- `groups` → `auth.Group` (ManyToManyField)
- `user_permissions` → `auth.Permission` (ManyToManyField)

## contenttypes.ContentType
Table : `django_content_type`

- `logentry` → `admin.LogEntry` (ManyToOneRel)
- `permission` → `auth.Permission` (ManyToOneRel)
- `id` (AutoField)
- `app_label` (CharField)
- `model` (CharField)

## sessions.Session
Table : `django_session`

- `session_key` (CharField)
- `session_data` (TextField)
- `expire_date` (DateTimeField)

## core_accounts.UserProfile
Table : `core_accounts_userprofile`

- `id` (BigAutoField)
- `user` → `auth.User` (OneToOneField)
- `role` (CharField)
- `per_page` (PositiveSmallIntegerField)
- `created_at` (DateTimeField)

## core_gmail.GmailMessage
Table : `core_gmail_gmailmessage`

- `id` (BigAutoField)
- `message_id` (CharField)
- `subject` (CharField)
- `from_email` (EmailField)
- `received_at` (DateTimeField)
- `processed_at` (DateTimeField)

## core_emails.Prescription
Table : `core_emails_prescription`

- `status_history` → `core_emails.PrescriptionStatusHistory` (ManyToOneRel)
- `assignment` → `core_emails.PrescriptionAssignment` (OneToOneRel)
- `renewal_info` → `core_emails.PrescriptionRenewalInfo` (OneToOneRel)
- `renewal_events` → `core_emails.PrescriptionRenewalEvent` (ManyToOneRel)
- `renewal_cycles` → `core_emails.PrescriptionRenewalCycle` (ManyToOneRel)
- `notification_settings` → `core_emails.PrescriptionNotificationSettings` (OneToOneRel)
- `notification_events` → `core_emails.PrescriptionNotificationEvent` (ManyToOneRel)
- `attachments` → `core_attachments.PrescriptionAttachment` (ManyToOneRel)
- `sms_messages` → `core_notifications.SmsMessage` (ManyToOneRel)
- `id` (BigAutoField)
- `status` (CharField)
- `type` (CharField)
- `sender_type` (CharField)
- `patient` → `core_patients.Patient` (ForeignKey)
- `established_at` (DateField)
- `received_at` (DateTimeField)
- `updated_at` (DateTimeField)
- `processing_started_at` (DateTimeField)
- `created_by` → `auth.User` (ForeignKey)
- `is_deleted` (BooleanField)
- `deleted_at` (DateTimeField)
- `deleted_by` → `auth.User` (ForeignKey)
- `delete_reason` (CharField)

## core_emails.PrescriptionStatusHistory
Table : `core_emails_prescriptionstatushistory`

- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (ForeignKey)
- `old_status` (CharField)
- `new_status` (CharField)
- `changed_by` → `auth.User` (ForeignKey)
- `changed_at` (DateTimeField)
- `comment` (TextField)

## core_emails.PrescriptionAssignment
Table : `core_emails_prescriptionassignment`

- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (OneToOneField)
- `nurse` → `core_people.Person` (ForeignKey)
- `patient` → `core_patients.Patient` (ForeignKey)
- `assigned_at` (DateTimeField)

## core_emails.PrescriptionRenewalInfo
Table : `core_emails_prescriptionrenewalinfo`

- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (OneToOneField)
- `renewal_times` (PositiveSmallIntegerField)
- `period_days` (PositiveSmallIntegerField)
- `renewal_done_count` (PositiveSmallIntegerField)
- `last_renewal_ordered_at` (DateTimeField)
- `doctor_email` (EmailField)
- `doctor_name` (CharField)
- `reminder_5_patient_email_sent_at` (DateTimeField)
- `reminder_5_patient_sms_sent_at` (DateTimeField)
- `reminder_3_patient_email_sent_at` (DateTimeField)
- `reminder_3_patient_sms_sent_at` (DateTimeField)
- `doctor_email_sent_at` (DateTimeField)

## core_emails.PrescriptionRenewalEvent
Table : `core_emails_prescriptionrenewalevent`

- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (ForeignKey)
- `number` (PositiveSmallIntegerField)
- `ordered_at` (DateTimeField)
- `created_by` → `auth.User` (ForeignKey)
- `note` (CharField)

## core_emails.PrescriptionRenewalCycle
Table : `core_emails_prescriptionrenewalcycle`

- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (ForeignKey)
- `cycle_number` (PositiveSmallIntegerField)
- `status` (CharField)
- `started_at` (DateTimeField)
- `closed_at` (DateTimeField)
- `reminder_5_patient_email_sent_at` (DateTimeField)
- `reminder_5_patient_sms_sent_at` (DateTimeField)
- `reminder_3_patient_email_sent_at` (DateTimeField)
- `reminder_3_patient_sms_sent_at` (DateTimeField)
- `doctor_email_sent_at` (DateTimeField)

## core_emails.PrescriptionNotificationSettings
Table : `core_emails_prescriptionnotificationsettings`

- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (OneToOneField)
- `patient_channel` (CharField)
- `nurse_channel` (CharField)
- `free_text_message` (TextField)
- `updated_at` (DateTimeField)

## core_emails.PrescriptionNotificationEvent
Table : `core_emails_prescriptionnotificationevent`

- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (ForeignKey)
- `recipient_type` (CharField)
- `channel` (CharField)
- `destination` (CharField)
- `result` (CharField)
- `error_message` (TextField)
- `created_at` (DateTimeField)
- `created_by` → `auth.User` (ForeignKey)

## core_emails.RenewalSettings
Table : `core_emails_renewalsettings`

- `id` (BigAutoField)
- `pharmacy_name` (CharField)
- `phone` (CharField)
- `email` (EmailField)
- `opening_time` (TimeField)
- `closing_time` (TimeField)
- `created_at` (DateTimeField)
- `updated_at` (DateTimeField)

## core_emails.RenewalNotificationRule
Table : `core_emails_renewalnotificationrule`

- `id` (BigAutoField)
- `name` (CharField)
- `days_before` (PositiveIntegerField)
- `send_sms` (BooleanField)
- `send_email` (BooleanField)
- `active` (BooleanField)
- `sort_order` (PositiveIntegerField)
- `created_at` (DateTimeField)
- `updated_at` (DateTimeField)

## core_emails.RenewalNotificationTemplate
Table : `core_emails_renewalnotificationtemplate`

- `id` (BigAutoField)
- `name` (CharField)
- `channel` (CharField)
- `subject` (CharField)
- `body` (TextField)
- `active` (BooleanField)
- `created_at` (DateTimeField)
- `updated_at` (DateTimeField)

## core_emails.Holiday
Table : `core_emails_holiday`

- `id` (BigAutoField)
- `name` (CharField)
- `date` (DateField)
- `active` (BooleanField)
- `created_at` (DateTimeField)

## core_attachments.PrescriptionAttachment
Table : `core_attachments_prescriptionattachment`

- `access_logs` → `core_attachments.PrescriptionAttachmentAccess` (ManyToOneRel)
- `id` (BigAutoField)
- `prescription` → `core_emails.Prescription` (ForeignKey)
- `file` (FileField)
- `original_filename` (CharField)
- `mime_type` (CharField)
- `uploaded_at` (DateTimeField)
- `uploaded_by` → `auth.User` (ForeignKey)

## core_attachments.PrescriptionAttachmentAccess
Table : `core_attachments_prescriptionattachmentaccess`

- `id` (BigAutoField)
- `attachment` → `core_attachments.PrescriptionAttachment` (ForeignKey)
- `accessed_by` → `auth.User` (ForeignKey)
- `accessed_at` (DateTimeField)
- `action` (CharField)

## core_notifications.Notification
Table : `core_notifications_notification`

- `id` (BigAutoField)
- `recipient` → `auth.User` (ForeignKey)
- `title` (CharField)
- `message` (TextField)
- `is_read` (BooleanField)
- `created_at` (DateTimeField)
- `object_type` (CharField)
- `object_id` (PositiveIntegerField)

## core_notifications.SmsTemplate
Table : `core_notifications_smstemplate`

- `id` (BigAutoField)
- `key` (CharField)
- `language` (CharField)
- `content` (TextField)
- `is_active` (BooleanField)

## core_notifications.SmsMessage
Table : `core_notifications_smsmessage`

- `attempts` → `core_notifications.SmsAttempt` (ManyToOneRel)
- `id` (BigAutoField)
- `recipient_phone` (CharField)
- `purpose` (CharField)
- `template_key` (CharField)
- `rendered_text` (TextField)
- `provider` (CharField)
- `provider_message_id` (CharField)
- `status` (CharField)
- `last_error_message` (TextField)
- `related_prescription` → `core_emails.Prescription` (ForeignKey)
- `created_at` (DateTimeField)
- `sent_at` (DateTimeField)

## core_notifications.SmsAttempt
Table : `core_notifications_smsattempt`

- `id` (BigAutoField)
- `sms_message` → `core_notifications.SmsMessage` (ForeignKey)
- `attempt_no` (PositiveIntegerField)
- `requested_at` (DateTimeField)
- `success` (BooleanField)
- `error_message` (TextField)
- `response_payload` (JSONField)

## core_patients.Patient
Table : `core_patients_patient`

- `prescriptions` → `core_emails.Prescription` (ManyToOneRel)
- `assigned_prescriptions` → `core_emails.PrescriptionAssignment` (ManyToOneRel)
- `id` (BigAutoField)
- `full_name` (CharField)
- `email` (EmailField)
- `phone_number` (CharField)
- `created_at` (DateTimeField)

## core_people.Person
Table : `core_people_person`

- `assigned_prescriptions` → `core_emails.PrescriptionAssignment` (ManyToOneRel)
- `id` (BigAutoField)
- `first_name` (CharField)
- `last_name` (CharField)
- `role` (CharField)
- `email` (EmailField)
- `phone` (CharField)
- `is_active` (BooleanField)
- `created_at` (DateTimeField)
- `updated_at` (DateTimeField)
