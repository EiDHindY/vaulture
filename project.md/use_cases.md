Account Management
 ├─ create_account
 ├─ log in 
 ├─ delete_account
 ├─ change_master_password
 ├─ link_drive_account        (OAuth2)
 ├─ add_recovery_contact_and_verify
 ├─ remove_recovery_contact
 └─ recover_account_with_token

Session & Vault
 ├─ unlock_vault_with_master_password
 ├─ lock_vault                (manual)
 ├─ autolock_vault            (system)
 └─ logout_user

CRUD & Query
 ├─ save_password              (includes tag drop-down)
 ├─ show_password
 ├─ update_password              (tag can be changed here)
 ├─ delete_password
 ├─ list_passwords
 └─ search_passwords             (supports tag filter)

 Clipboard
 ├─ copy_to_clipboard
 └─ clear_clipboard_after_timeout (system)

Generator
 ├─ generate_password
 ├─ generate_passphrase
 └─ evaluate_password_strength (inner helper)

Backup & Restore
 ├─ backup_vault_to_google_drive
 ├─ auto_backup_vault_to_google_drive
 ├─ restore_vault_from_google_drive
 ├─ import_credentials
 └─ export_credentials_csv

Analysis & Monitoring
 ├─ generate_vault_health_report   (system or on-demand)
 └─ poll_breach_monitor            (system)

Preferences
 └─ update_user_preferences



