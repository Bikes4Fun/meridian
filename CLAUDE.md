# PatientHealthData Page — ICE/POLST Wiring Audit

## DB tables used by this page

| Table | Key columns used |
|-------|-----------------|
| `care_recipients` | `family_circle_id`, `care_recipient_user_id`, `name`, `dob`, `photo_path`, `medical_dnr`, `dnr_document_path`, `notes` |
| `conditions` | `care_recipient_user_id`, `condition_name`, `diagnosis_date`, `notes` |
| `allergies` | `care_recipient_user_id`, `allergen` |
| `medications` | `id`, `care_recipient_user_id`, `name`, `dosage`, `frequency`, `fda_rxcui`, `max_daily`, `last_taken`, `taken_today` |
| `medication_times` | `id`, `family_circle_id`, `name`, `time` |
| `medication_to_time` | `medication_id`, `group_id` |
| `contacts` | `id`, `family_circle_id`, `display_name`, `phone`, `email`, `relationship`, `emergency_priority` |
| `ice_contact_roles` | `family_circle_id`, `role`, `contact_id` (roles: medical_proxy, poa) |
| `care_recipient_documents` | NEW — see schema.sql; `id`, `family_circle_id`, `care_recipient_user_id`, `doc_type`, `doc_label`, `doc_date`, `file_path`, `sort_order` |

## Kiosk reads (DO NOT break these)

The kiosk calls `GET /api/family_circles/<id>/emergency-profile` and reads:
- `care_recipients.care_recipient_user_id`, `.name`, `.dob`, `.photo_path`, `.medical_dnr`, `.dnr_document_path`, `.notes`
- `conditions.condition_name`
- `allergies.allergen`
- `medications.id/.name/.dosage/.frequency/.fda_rxcui` + `medication_to_time` + `medication_times.name`
- `ice_contact_roles` + `contacts.display_name/.phone`
- `contacts.emergency_priority` for sorted emergency contacts

The kiosk does `bool(medical_data.get("dnr", False))` → `bool(0)=False, bool(1)=True, bool(2)=True`
so extending medical_dnr to 0/1/2 integers is safe.

## API endpoints serving this page

| Endpoint | Method | Status |
|----------|--------|--------|
| `GET /api/family_circles/<id>/emergency-profile` | GET | Real |
| `PUT /api/family_circles/<id>/emergency-profile` | PUT | Real |
| `POST /api/family_circles/<id>/care-recipient-photo` | POST | Real |
| `POST /api/family_circles/<id>/care-recipient-dnr-document` | POST | Real |
| `GET /api/family_circles/<id>/care-recipients/<cr_id>/dnr-document` | GET | Real |
| `GET/POST /api/family_circles/<id>/contacts` | GET/POST | Real |
| `GET/POST/PUT/DELETE /api/family_circles/<id>/medications/<id>` | CRUD | Real |
| `POST /api/family_circles/<id>/allergies` | POST | Real — no DELETE yet |
| `POST /api/family_circles/<id>/conditions` | POST | Real — no DELETE/replace-all yet |
| `GET/POST /api/family_circles/<id>/documents` | CRUD | **STUB → wired** |
| `POST /api/family_circles/<id>/documents/<id>/upload` | POST | **STUB → wired** |
| `PUT/DELETE /api/family_circles/<id>/documents/<id>` | PUT/DELETE | **STUB → wired** |

## UI element → DB mapping

| UI id | DB column | Status |
|-------|-----------|--------|
| `iceName` | `care_recipients.name` | Wired |
| `iceDob` | `care_recipients.dob` | Wired |
| `iceDnr` (3-way) | `care_recipients.medical_dnr` INTEGER 0/1/2 | Needs integer fix |
| `iceDniStatus` | `care_recipients.medical_dni_status` TEXT | **Missing column → added** |
| `iceNutritionStatus` | `care_recipients.medical_nutrition_status` TEXT | **Missing column → added** |
| `icePhotoPreview` | `care_recipients.photo_path` | Wired |
| `iceDnrDoc` upload | `care_recipients.dnr_document_path` | Wired |
| Documents rows | `care_recipient_documents` table | **Missing table → added** |
| `iceConditions` textarea | `conditions` table | Read-only → **made editable** |
| `iceAllergies` | `allergies` table | Read-only → **made editable** |
| `iceDevicesNotes` | `care_recipients.devices_notes` TEXT | **Missing column → added** |
| `iceBriefHistory` | `care_recipients.brief_history` TEXT | **Missing column → added** |
| `iceOtherNotes` | `care_recipients.other_notes` TEXT | **Missing column → added** |
| Medications inline editor | `medications` table | Wired |
| `iceProxyName` | `contacts.display_name` via `ice_contact_roles` | Wired |
| `iceProxyPhone` | `contacts.phone` via `ice_contact_roles` | Wired |
| `icePoaName` | `contacts.display_name` via `ice_contact_roles` | Wired |
| `icePoaPhone` | `contacts.phone` via `ice_contact_roles` | Wired |
| `iceEmergencyContacts` rows | `contacts` table | Wired |
| `iceNotes` | `care_recipients.notes` | Wired |

## Notes

- `ice_profile` table exists in schema but is NOT used by any service; `care_recipients` is authoritative.
- New columns on `care_recipients` are added via migration in `safe_query_manager.py` (ALTER TABLE ADD COLUMN).
- The kiosk does NOT read the new columns, so they're purely webapp-side.
