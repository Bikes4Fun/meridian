# Meridian - Project Plan & Progress

**Overview:** 14-week plan Jan 11–Apr 20 (final presentation). Weeks 1–9 largely done: setup, map, GPS, checkin, meds, ICE, iOS, tests, org/arch. Remaining: QR, safety, polish & docs.

| Date | Checkpoint |
|------|------------|
| **Mar 17** | ICE + Tests + Family |
| **Mar 31** | Map + QR |
| **Apr 7** | Safety + Polish |
| **Apr 20** | Final presentation |

## Current Issues
- [ ] Map populates but incorrectly (see screenshots)
- [ ] Nav cut off
- [ ] Database datatype mismatch
- [ ] modular_display vs app_factory – both needed?
- [x] Combine architecture.md and todo?
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

## Week 7 (Feb 22–28): Emergency/ICE + Org/Arch ✓
- [x] Emergency service, contacts, medical summary, ICE Profile Service
- [x] ICE Screen UI (full-screen EMS display, DNR/proxy/POA, ICE button)
- [x] ICE #4 – Printable POLST-Formatted PDF (#22)
- [ ] stop flashing
- [ ] Safety alerts, color indicators, pill-pack QR scan, ethics review
- [ ] Enhanced Medical ID (name, DOB, photo, doctor)
- [ ] ICE #3, #5–7: Editor, Smart911, 911 trigger

- [x] Org/Arch (#28 architecture review, #57 kiosk screen progression)

## Week 8 (Mar 1–7): Tests ✓
- [x] Define tests (#29), Create tests (#30), Load tests into GitHub (#31)
- [x] e2e critical path, emergency (#107)

## Week 9 (Mar 8–14): Family Connection MVP ✓
- [x] Contact service, family data model
- [x] Kivy → HTML/CSS (#8), Sendbird (#55), chat to kiosk/webapp (#67)
- [x] iOS mobile app (#52), TestFlight (#78), iOS login/alert/checkin (#80)
- [x] Manage meds and events (#86, #88, #82)
- [x] Security fixes (#36, #41), separate family id (#34)
- [ ] Photo directory UI, Easy-touch calling, Living arrangements

## Week 10 (Mar 15–21) ✓
*Checkpoint Mar 17 – passed*
- [x] Readme, demo data (#110)

## Week 11 (Mar 22–28)
- [x] Map (#18), e2e tests (#107)

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
- [x] #2–4: Skipped (interfaces, display, schema)
- [x] #8: Switch Kivy to HTML/CSS
- [x] #9: Geofencing/Location checkin
- [x] #11–13: Map (Data Model, Backend, Frontend) + Named Places
- [x] #18: Map details and UI
- [x] #19: ICE #1 – ICE Data Model & Storage
- [x] #20: ICE #2 – ICE Screen UI
- [x] #22: ICE #4 – Printable POLST-Formatted PDF
- [x] #28: Architecture review part 1
- [x] #29: Define tests | #30: Create tests | #31: Load tests into GitHub
- [x] #32: Fix Vercel
- [x] #34: Separate family id from user id
- [x] #36: Fix minor bugs in sessions and security
- [x] #41: Security issues
- [x] #52: Mobile iOS app
- [x] #55: Sendbird
- [x] #57: Fix kiosk screen creation progression
- [x] #61: Tests
- [x] #67: Update basic chat to kiosk webapp chat
- [x] #78: Test TestFlight
- [x] #80: iOS login alert checkin
- [x] #82, #86, #88: Fix/add/edit meds and events
- [x] #110: Readme and demo data

### Open – ICE Screen & Smart911
- [ ] #21: ICE #3 – Caregiver ICE Profile Editor (Web)
- [ ] #23: Apply for Smart911 partnership (Not planned / skipped)
- [ ] #24: ICE #5 – Smart911 Account Connection (Blocked)
- [ ] #25: ICE #6 – Smart911 Auto-Sync
- [ ] #26: ICE #7 – 911 Call Trigger (Not planned / skipped)

### Open – Other
- [ ] #5: LAST final polish
- [ ] #7: Consider Using a Calendar API

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
- **Print functionality** – Emergency auto-print on alert done; full print Phase 3 deferred
- **Weather** – EXTREMELY LOW PRIORITY in clock widget
- **Cloud backup** – Optional in proposal; not active in todo
- **Location services** – Family member location/safety sharing; medium priority, may slip

## Files / Code Removed

- **proposal.md** – Submitted as PDF; content folded into todo.md
- **ARCHITECTURE.md** – Merged into todo.md
- **responsive_system.py** – Removed (Issue #1)
