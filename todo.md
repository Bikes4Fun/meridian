# Dementia TV - Project Plan & Progress

**Overview:** 14-week plan Jan 11–Apr 20 (final presentation). Everything must be done before Apr 20. Weeks 1–6 done: setup, map, GPS, checkin, meds. Week 7 in progress: ICE UI done, org/arch. Weeks 8–14: tests, family, QR, safety, final polish & docs.

| Date | Checkpoint |
|------|------------|
| **Mar 17** | ICE + Tests + Family |
| **Mar 31** | Map + QR |
| **Apr 7** | Safety + Polish |
| **Apr 20** | Final presentation |

## Current Issues
- [ ] Nav cut off
- [ ] Database datatype mismatch
- [ ] modular_display vs app_factory – both needed?
- [ ] Combine architecture.md and todo?
- [ ] Duplicate functionality to simplify?
- [ ] Unused code to remove?
- [x] Debug logging, calendar fixes

---
# Week by Week Plans:

## Week 1 (Jan 11–17) and Week 2 (Jan 18–24): Setup & Research ✓
- [x] Literature review, user needs, tech stack
- [x] Proof of concept level functionality
  - [x] Service, AM/Noon/PM/Bedtime, PRN, widget
- [x] requirements, gap analysis

## Week 3 (Jan 25–31): System Design ✓

- [x] Progress check 1
- [x] Kivy framework, DI container, DB manager, config
- [x] development environment
- [x] basic TV interface framework (Kivy)
  - [x] home screen
  - [x] demo data
  - [x] calendar
  - [x] Time/date, part-of-day, appointments, "No Appointments"

## Week 4 (Feb 1–7): Core Dev Setup ✓
- [x] Map / family checkin started

## Week 5 (Feb 8–14): Dementia Clock MVP ✓
- [x] Raw text GPS coordinates working
- [x] Family can check-in on webapp

## Week 6 (Feb 15–21): Medication MVP ✓ (core)
- [x] Map displays family photos and locations

## Week 7 (Feb 22–28): Emergency/ICE + Org/Arch ⚠️ IN PROGRESS
- [x] Emergency service, contacts, medical summary, ICE Profile Service
- [x] ICE Screen UI (full-screen EMS display, DNR/proxy/POA, ICE button)
- [ ] stop flashing
- [ ] Safety alerts, color indicators, pill-pack QR scan, ethics review
- [ ] Enhanced Medical ID (name, DOB, photo, doctor)
- [ ] ICE #3–7: Editor, PDF, Smart911, 911 trigger

- [] Org/Arch ⚠️ IN PROGRESS

## Week 8 (Mar 1–7): Tests ⚠️ NEXT
- [ ] Unit tests (contact, calendar, medication, emergency, ICE)
- [ ] Integration tests, framework cleanup

## Week 9 (Mar 8–14): Family Connection MVP
- [x] Contact service, family data model
- [ ] Photo directory UI, Easy-touch calling, Living arrangements

## Week 10 (Mar 15–21)
*Checkpoint Mar 17*

## Week 11 (Mar 22–28)
*Map done in week 6/7 (Named Places, circles, labels – #11–13 closed)*

## Week 12 (Mar 29–Apr 4): QR Code
- [ ] Setup (opencv, qrcode, pyzbar), generation, camera scanning, med verification, integration

## Week 13 (Apr 5–11): Advanced Safety
- [ ] Multi-dose, PRN logic, overdose prevention, interaction warnings
- [ ] Emergency alerts, fall detection, family notifications, ICE override

## Week 14 (Apr 12–18): Final polish & docs before Apr 20
- [ ] Integration testing, accessibility, UI polish
- [ ] User manual, deployment guide, RPi setup
- [ ] Presentation prep

---

## Code Quality & Refactoring (GitHub Issues)

See GitHub for details. Some issues may duplicate across repos (dementia_tv_python → meridian).

### Closed
- [x] #1: Remove responsive_system.py
- [x] #8: Switch Kivy to HTML/CSS
- [x] #9: Geofencing/Location checkin
- [x] #11–13: Map (Data Model, Backend, Frontend) + Named Places
- [x] #19: ICE #1 – ICE Data Model & Storage
- [x] #2–4: Skipped (interfaces, display, schema)

### Open – ICE Screen & Smart911
- [ ] #20: ICE #2 – ICE Screen UI
- [ ] #21: ICE #3 – Caregiver ICE Profile Editor (Web)
- [ ] #22: ICE #4 – Printable POLST-Formatted PDF
- [ ] #23: Apply for Smart911 partnership/API access
- [ ] #24: ICE #5 – Smart911 Account Connection (Blocked)
- [ ] #25: ICE #6 – Smart911 Auto-Sync
- [ ] #26: ICE #7 – 911 Call Trigger + ICE Auto-Display

### Open – Other
- [ ] #5: LAST final polish
- [ ] #7: Consider Using a Calendar API
- [ ] #18: Map details and UI
- [ ] #28: Architecture review part 1
- [ ] #29: Define tests | #30: Create tests | #31: Load tests into GitHub
- [ ] #32: Fix vercel

---
---
---
---
---

# Deprecated / Removed

Things we decided not to do or completely overhauled.

## Tech – Dropped

- **Flask** – Originally planned for main app API; dropped (lib/server may have remnants)
- **OpenAI API** – Voice commands and text-to-speech; not in scope
- **Google/iOS Calendar APIs** – Using database + SE-3200 demo generator instead of external calendar sync
- **JSON config files** – Using config.py instead

## Features – Dropped / Overhauled

- **Family Management mobile app** – Full mobile app (location sharing, visit scheduling, permission levels, remote override). Scope reduced to TV-side only (photo directory, easy-touch calling)

## Features – Deferred (pushed out indefinitely)

- **HIPAA-aligned privacy** – In proposal; not in active scope

- **FaceTime integration** – Phase 2; not in current roadmap
- **One-touch 911** – LOW priority but keeping in mind; hardware-dependent
- **Fall detection** – Far future; “if hardware available”
- **Print functionality** – Phase 3; not in todo
- **Weather** – EXTREMELY LOW PRIORITY in clock widget
- **Cloud backup** – Optional in proposal; not active in todo
- **Location services** – Family member location/safety sharing; medium priority, may slip

## Files / Code Removed

- **proposal.md** – Submitted as PDF; content folded into todo.md
- **ARCHITECTURE.md** – Merged into todo.md
- **responsive_system.py** – Removed (Issue #1)
