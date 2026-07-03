# Audit Services

## core_adminconsole/services.py
- function `get_client_ip`
- function `audit`
- function `_get_ip`
- function `audit`
- function `_is_last_superuser`
- function `soft_delete_user`
- function `reactivate_user`
- function `_count_active_superusers_excluding`
- function `guard_not_last_superuser_change`
- function `guard_not_last_superuser_deactivate`
- function `guard_self_lockout`

## core_adminconsole/views_renewals.py
- function `_admin_required`
- function `_get_models`
- function `_model_field_names`
- function `_safe_bool`
- function `renewals_settings`
- function `renewals_rules`
- function `renewals_rule_delete`
- function `renewals_templates`
- function `renewals_holidays`
- function `renewals_holiday_delete`
- function `renewals_logs`
- function `renewals_stats`
- function `renewals_alerts`
- function `renewals_export_excel`

## core_emails/management/commands/run_renewal_notifications.py
- class `Command`

## core_emails/migrations/0006_prescription_established_at_prescriptionrenewalinfo.py
- class `Migration`

## core_emails/migrations/0007_prescriptionrenewalinfo_last_renewal_ordered_at_and_more.py
- class `Migration`

## core_emails/migrations/0008_prescriptionrenewalevent.py
- class `Migration`

## core_emails/migrations/0012_renewal_cycle_v1.py
- class `Migration`

## core_emails/migrations/0015_renewalsettings_alter_prescription_status_and_more.py
- class `Migration`

## core_emails/migrations/0016_renewals_v9_default_data.py
- function `create_default_renewal_v9_data`
- function `reverse_default_renewal_v9_data`
- class `Migration`

## core_emails/services.py
- function `_mask_destination`
- function `log_notification_event_safe`
- function `log_status_history_notification_summary_safe`
- function `_mask_phone`
- function `_mask_email`
- function `_log_notification_business`
- function `status_label`
- function `change_prescription_status`
- function `compute_renewals_watch`
- function `compute_renewals_watch_from_delivered`
- function `_mask_email`
- function `_status_label_fr`
- function `_sms_text_status_only`
- function `send_prescription_notifications`
- function `compute_renewals_watch_v9`

## core_emails/services_notifications.py
- function `_send_email_if_possible`
- function `_status_label_fr`
- function `build_sms_text_status_only`
- function `_sanitize_free_text`
- function `_append_free_text`
- function `_send_email_strict`
- function `notify_patient`
- function `notify_nurse`
- function `_legacy_send_prescription_notifications_void`
- function `mask_phone`
- function `mask_email`
- function `build_notification_audit_summary`
- function `build_notification_result_summary`
- function `_send_email_strict`
- function `build_notification_result_summary`
- function `_email_status_from_helper`
- function `send_prescription_notifications`
- class `NotificationPlan`

## core_emails/services_renewal_rules.py
- function `_today`
- function `get_active_renewal_rules`
- function `calculate_notification_date`
- function `is_closed_day`
- function `move_to_next_open_day`
- function `_get_cycle_due_date`
- function `_get_active_cycles`
- function `_rule_already_sent`
- function `get_due_notifications`
- function `get_overdue_renewals`
- function `_get_remaining_cycles`
- function `_get_final_alert_threshold_cycles`
- function `_get_cycle_total_cycles`
- function `_get_cycle_remaining_until_final`
- function `get_final_renewals`
- function `get_urgent_renewals`
- function `get_activity_metrics`

## core_emails/services_renewal_templates.py
- function `get_active_template`
- function `_safe_get_patient_name`
- function `_safe_format_date`
- function `_get_renewal_settings`
- function `_get_due_date`
- function `_get_cycle_number`
- function `_get_cycles_restants`
- function `build_renewal_context`
- function `_safe_render`
- function `render_renewal_template`
- function `render_renewal_message`

## core_emails/services_workflow.py
- function `_get_or_create_notification_settings`
- function `status_label`
- function `_status_label_fr`
- function `_send_external_notifications`
- function `change_prescription_status`

## core_emails/tests/test_renewals_cycles_archiving_functional.py
- class `RenewalCyclesArchivingFunctionalTests`

## core_emails/tests/test_renewals_cycles_functional.py
- class `RenewalCyclesFunctionalTests`

## core_emails/tests/test_renewals_functional.py
- function `_rand_email`
- function `make_minimal_instance`
- function `set_first_delivered_at`
- class `RenewalsFunctionalTests`

## core_emails/tests/test_renewals_lot18_catchup.py
- class `RenewalsLot18CatchupTests`

## core_emails/tests/test_renewals_regression.py
- function `_change_status`
- class `RenewalsV9RegressionTests`

## core_emails/tests/test_renewals_rules_regression.py
- class `RenewalsRulesRegressionTests`

## core_emails/tests/test_renewals_v9_engine.py
- class `RenewalsV9EngineTests`

## core_gmail/services.py
- function `_default_search_criteria`
- function `_build_search_args`
- function `fetch_new_gmail_messages`

## core_notifications/services.py
- function `notify_users`
- function `_assert_sms_rgpd_safe`
- function `send_sms_logged`

## core_notifications/tests/test_sms_services.py
- class `SendSmsLoggedHardeningTests`

## core_patients/services.py
- function `get_or_create_patient_from_email`

## scripts/ovh_list_sms_services.py
- function `ovh_time`
- function `sign`
- function `request`

## scripts/patches/patch_services_workflow_v1.py
- function `ts`
- function `backup`
- function `ensure_text_file`
- function `patch_views_import`
- function `main`

## scripts/patches/patch_services_workflow_v2_on_commit.py
- function `ts`
- function `backup`
- function `main`

## scripts/patches/patch_services_workflow_v2_on_commit_safe.py
- function `ts`
- function `backup`
- function `main`
