# Dementia TV - TODO List

## Current Issues to Debug or add to completed list: 
- [] Nav is cutt off still
- [] Database errors '[INFO   ] [Database connection established] dementia_tv.db
  [ERROR  ] [Database connection error] datatype mismatch
  [ERROR  ] [Update execution failed] datatype mismatch
  [ERROR  ] [Database connection error] datatype mismatch
  [ERROR  ] [Update execution failed] datatype mismatch
- [] Whats the diff between 'modular_display' and 'app_factory' and are they both needed?
- [] Combine "architecture.md' and todo?
- [] Are any other files duplicating functionality between them and can be simplified or made into one etc? 
- [] is there anything not used that can simply be removed?
- [x] added debug logging vs print statements
- [x] Calendar events for today don't display.
- [x] Calendar doesn't click for different days.

## Week 1: Project Setup & Research

#### Key Activities
- [x] Literature review on dementia care technology
- [x] User research planning
- [x] Technical stack selection (Python, Kivy, SQLite)
- [x] Project charter and initial architecture design

#### Deliverables
- [x] Research summary
- [x] Project charter
- [x] Initial codebase structure

---

## Week 2: User Research

#### Key Activities
- [x] Interview dementia patients and caregivers
- [x] Analyze existing solutions (Targeted Digital Clocks, Medication Reminders, etc.)
- [x] Identify pain points and requirements

#### Deliverables
- [x] User personas
- [x] Requirements document
- [x] Gap analysis

---

## Week 3: System Design

#### Key Activities
- [x] Create wireframes and user flow diagrams
- [x] Design system architecture
- [x] Plan database schema
- [x] Define service interfaces

#### Deliverables
- [x] Design mockups
- [x] Technical specification (`ARCHITECTURE.md`)
- [x] Database schema design

---

## Week 4: Core Development Setup

#### Key Activities
- [x] Set up development environment
- [x] Create basic TV interface framework (Kivy)
- [x] Implement dependency injection container
- [x] Set up database management system
- [x] Create configuration management

#### Deliverables
- [x] Development environment
- [x] Basic UI framework
- [x] Database manager
- [x] Service container

---

## Week 5: Dementia Clock MVP

#### Key Activities
- [x] Implement time/date display service
- [x] Add part-of-day detection (morning, midday, evening, night)
- [x] Create large font display widget
- [x] Add time-of-day icons (sunrise, noon, evening, night)
- [x] Implement appointment loading from database
- [x] Add "No Appointments" indicator

#### Remaining Tasks
- [ ] **Appointment Details Enhancement**
  - [x] Add driver information field to calendar events (in schema)
  - [x] Add pickup time field (in schema)
  - [ ] Add confirmation status tracking
  - [ ] Add pre-appointment tasks field (e.g., "Complete labs")
  - [ ] Update calendar service to handle new fields
  - [ ] Update UI to display appointment details
  - [ ] Test appointment detail display
  - [ ] **Test Data:** Use SE-3200 Demo Generator (`se3200_web_app/generator.html`) to create test events

- [ ] **Weather Integration LOW PRIORITY**
  - [ ] Add `requests` library to `requirements.txt`
  - [ ] Create weather service module
  - [ ] Integrate OpenWeatherMap API
  - [ ] Add weather display to clock widget
  - [ ] Handle API errors gracefully
  - [ ] Test weather display
  
#### Deliverables
- [x] Functional clock and appointment features
- [ ] Enhanced appointment details
- [ ] Weather display

---

### Week 6: Medication Management MVP ⚠️ **IN PROGRESS** {#week-6-medication-management-mvp}

#### Completed Tasks
- [x] Implement medication service with scheduling
- [x] Add AM, Noon, PM, Bedtime medication reminders
- [x] Create medication status tracking (done, not_done, overdue)
- [x] Implement PRN medication tracking with max daily limits
- [x] Create medication widget for UI display

#### Remaining Tasks - Priority Order

**High Priority (Complete This Week)**
- [ ] **Medication Safety Alerts**
  - [ ] Implement overdose prevention logic
  - [ ] Add alert system for missed doses
  - [ ] Create notification mechanism for emergency contacts
  - [ ] Test safety alert triggers

- [ ] **Medication Display Enhancements**
  - [ ] Add color-coded indicators (green=taken, yellow=due, red=overdue)
  - [ ] Add texture/pattern coding for visual distinction
  - [ ] Display food requirements (with/without food, before/after meals)
  - [ ] Update medication widget UI

**Medium Priority (If Time Permits)**
- [ ] **Medication Information**
  - [ ] Add photo storage for medications
  - [ ] Add medication purpose/explanation field
  - [ ] Create medication detail view
  - [ ] Update database schema for medication photos

- [ ] **Compliance Tracking**
  - [ ] Implement compliance logging
  - [ ] Create notification system for loved ones
  - [ ] Add compliance reporting

#### User Testing Preparation (Parallel)
- [ ] Prepare paper prototypes for medication interface
- [ ] Schedule usability testing sessions
- [ ] Ethics review for medication tracking features
  - [ ] Consult with pharmacists
  - [ ] Consult with doctors/AP PCPs
  - [ ] Review with tech/medical ethics experts

#### Deliverables
- [ ] Basic medication management system with safety features
- [ ] Enhanced medication display
- [ ] User testing materials

---

### Week 7: Emergency System MVP ⚠️ **IN PROGRESS** {#week-7-emergency-system-mvp}

#### Completed Tasks
- [x] Implement emergency service
- [x] Create emergency contacts display
- [x] Add medical summary generation

#### Remaining Tasks - Priority Order

**High Priority (Complete This Week)**
- [ ] **Enhanced Medical ID Display**
  - [ ] Add patient name field to database
  - [ ] Add date of birth (DOB) field
  - [ ] Add photo storage and display
  - [ ] Expand diagnosis information display
  - [ ] Add doctor information (name, phone, specialty)
  - [ ] Update emergency service to retrieve full medical info
  - [ ] Update emergency screen UI

- [ ] **Legal Documents Display LOW PRIORITY**
  - [ ] Add DNR status field to database
  - [ ] Add medical proxy information field
  - [ ] Add power of attorney information field
  - [ ] Create legal documents display section
  - [ ] Update emergency screen to show legal docs
  - [ ] Ensure privacy/security for sensitive information

**EXTREMELY LOW Priority**
- [ ] **One-Touch 911 Calling**
  - [ ] Research landline integration options (Raspberry Pi compatible)
  - [ ] Implement phone dialing system
  - [ ] Create large, accessible 911 button on emergency screen
  - [ ] Add confirmation dialog to prevent accidental calls
  - [ ] Test with landline connection
  - [ ] Add emergency call logging
  - [ ] **Note**: May require hardware integration (USB modem, VoIP adapter, etc.)

#### Deliverables
- [ ] Emergency information system with full medical ID
- [ ] Legal documents display
- [ ] One-touch 911 calling functionality

---

### Week 8: Family Connection MVP ⚠️ **IN PROGRESS** {#week-8-family-connection-mvp}

#### Completed Tasks
- [x] Implement contact service
- [x] Store family member data (names, phone, addresses, relationships)
- [x] Create contact data model

#### Remaining Tasks - Priority Order

**High Priority (Complete This Week)**
- [ ] **Photo Directory UI**
  - [ ] Add photo storage to database schema
  - [ ] Implement photo loading from file system
  - [ ] Create photo display widget
  - [ ] Add relationship labels to photos
  - [ ] Create family directory screen
  - [ ] Test photo loading and display
  - [ ] **Test Data:** Use SE-3200 Demo Generator to fetch placeholder photos (`picsum.photos`)

- [ ] **Easy-Touch Calling** *(uses same phone system as 911 - see Week 7)*
  - [ ] Create large touch buttons for each family member
  - [ ] Add confirmation for outgoing calls
  - [ ] Test calling functionality

**Medium Priority**
- [ ] **Living Arrangements Display**
  - [ ] Add "lives with patient" flag to contact model
  - [ ] Create living arrangements display section
  - [ ] Add family member location/safety status fields
  - [ ] Update UI to show who lives with patient

#### Deliverables
- [ ] Photo directory with relationship labels
- [ ] Easy-touch calling to family members
- [ ] Living arrangements display

---

### Week 9: Integration & Testing {#week-9-integration--testing}

#### Key Activities

**Integration Tasks**
- [ ] Integrate all MVP features into single application
- [ ] Test feature interactions (e.g., medication alerts trigger emergency notifications)
- [ ] Ensure consistent UI/UX across all screens
- [ ] Verify database schema supports all features
- [ ] Test data flow between services

**UI/UX Polish**
- [ ] Apply dementia-friendly design principles consistently
  - [ ] Large text (72pt minimum for critical info)
  - [ ] High contrast colors
  - [ ] Simple navigation (max 3-4 decision branches)
  - [ ] Clear visual feedback
  - [ ] Consistent layouts
- [ ] Test touch interactions on large screen
- [ ] Optimize for TV display resolution
- [ ] Add loading states and error messages

**Integration Testing**
- [ ] Unit tests for all services
- [ ] Integration tests for service interactions
- [ ] End-to-end testing of user flows
- [ ] Performance testing (response times, memory usage)
- [ ] Accessibility testing with dementia simulation tools

**Bug Fixes**
- [ ] Fix identified bugs from integration testing
- [ ] Address performance issues
- [ ] Resolve UI/UX inconsistencies

#### Deliverables
- [ ] Integrated MVP system
- [ ] Test suite with passing tests
- [ ] Polished UI/UX
- [ ] Bug fix report

---

## Week 10: User Testing (Beta Testing)

#### Key Activities

**Beta Testing Setup**
- [ ] Deploy to 2-3 families (Raspberry Pi setup)
- [ ] Provide user training materials
- [ ] Set up feedback collection system
- [ ] Schedule weekly check-ins

**User Testing Sessions**
- [ ] Conduct usability testing with 3+ dementia patients
  - [ ] Time limits (30-45 min sessions)
  - [ ] Patient and caregiver consent
  - [ ] Caregiver observation
  - [ ] Mild to moderate dementia only
- [ ] Task completion testing:
  - [ ] Can patient tell time/date?
  - [ ] Can patient see appointments?
  - [ ] Can patient understand medication reminders?
  - [ ] Can patient access emergency information?
  - [ ] Can patient call family members?
- [ ] Collect caregiver feedback
- [ ] Measure satisfaction (target: >4.0/5.0 rating)

**Feedback Collection**
- [ ] Weekly sessions with users
- [ ] Usability testing surveys
- [ ] Satisfaction surveys as tasks/features are completed
- [ ] Document pain points and confusion areas

**Iteration Planning**
- [ ] Analyze feedback
- [ ] Prioritize improvements
- [ ] Create improvement backlog
- [ ] Plan Week 11-12 enhancements

#### Deliverables
- [ ] User feedback report
- [ ] Improvement backlog
- [ ] Beta testing results
- [ ] Satisfaction metrics

---

## Week 11: QR Code Integration

#### Key Activities

**QR Code System Setup**
- [ ] Add `opencv-python` to `requirements.txt`
- [ ] Add `qrcode` and `pyzbar` libraries for QR code generation/reading
- [ ] Research QR code standards for medication packets
- [ ] Design QR code data structure (medication ID, name, dosage, etc.)

**QR Code Generation**
- [ ] Create QR code generation service
- [ ] Generate QR codes for existing medications
- [ ] Test QR code readability

**QR Code Scanning**
- [ ] Implement camera access (Raspberry Pi compatible)
- [ ] Create QR code scanning interface
- [ ] Add scanning button to medication screen
- [ ] Implement QR code verification logic
  - [ ] Match scanned code to medication schedule
  - [ ] Verify correct medication and dosage
  - [ ] Prevent wrong medication dispensing
- [ ] Add visual/audio feedback for successful scan
- [ ] Handle scanning errors gracefully

**Integration with Medication Service**
- [ ] Connect QR scanning to medication tracking
- [ ] Auto-mark medication as taken when verified
- [ ] Log QR code verification events
- [ ] Update medication status based on scan

**Testing**
- [ ] Test QR code generation
- [ ] Test QR code scanning with various lighting conditions
- [ ] Test verification logic
- [ ] Test error handling
- [ ] Command-line testing with fake inputs

#### Deliverables
- [ ] QR code medication system
- [ ] QR code scanning functionality
- [ ] Integration with medication service
- [ ] Test results

---

## Week 12: Advanced Safety Features

#### Key Activities

**Enhanced Medication Safety**
- [ ] Implement multi-dose tracking
- [ ] Add advanced PRN logic (time-based restrictions)
- [ ] Enhance overdose prevention with more sophisticated checks
- [ ] Add medication interaction warnings
- [ ] Create medication safety dashboard

**Advanced Emergency Features**
- [ ] Implement automatic emergency alerts
- [ ] Add fall detection integration (if hardware available)
- [ ] Create emergency notification system to family
- [ ] Add remote screen override capability (for family to force ICE screen)
- [ ] Test emergency alert triggers

**Safety Testing**
- [ ] Comprehensive safety testing
- [ ] Test all emergency scenarios
- [ ] Verify medication safety features
- [ ] Test with healthcare professionals (pharmacists, doctors)

#### Deliverables
- [ ] Enhanced safety system
- [ ] Advanced medication safety features
- [ ] Emergency alert system
- [ ] Safety test results

---

## Week 13: Family Education Portal

#### Key Activities

**Caregiver Education Resources**
- [ ] Research and compile dementia care resources
- [ ] Create education content sections:
  - [ ] Understanding dementia symptoms
  - [ ] Medication management best practices
  - [ ] Emergency preparedness
  - [ ] Communication strategies
- [ ] Design education portal UI
- [ ] Add navigation to education content

**Legal Resources**
- [ ] Compile legal resource information
- [ ] Add links to relevant legal documents
- [ ] Create legal information display
- [ ] Ensure accuracy of legal information

**Professional Contacts Directory**
- [ ] Add professional contacts category
- [ ] Create directory for:
  - [ ] Doctors and specialists
  - [ ] Pharmacies
  - [ ] Home health services
  - [ ] Legal services
- [ ] Add contact information and specialties
- [ ] Create professional contacts screen

#### Deliverables
- [ ] Family education features
- [ ] Legal resources section
- [ ] Professional contacts directory

---

## Week 14: Final Testing & Polish

#### Key Activities

**Comprehensive Testing**
- [ ] Full system integration testing
- [ ] Performance optimization
- [ ] Memory leak testing
- [ ] Stress testing (multiple users, long runtime)
- [ ] Cross-platform testing (if applicable)

**Accessibility Testing**
- [ ] Test with dementia simulation tools
- [ ] Verify all accessibility features
- [ ] Test with various screen sizes
- [ ] Test with different lighting conditions
- [ ] Verify touch target sizes (minimum 44x44pt)

**UI/UX Final Polish**
- [ ] Visual design consistency check
- [ ] Animation and transition polish
- [ ] Error message clarity
- [ ] Loading state improvements
- [ ] Final color contrast verification
- [ ] Font size verification (all critical text 72pt+)

**Documentation**
- [ ] Update code documentation
- [ ] Create user manual draft
- [ ] Create deployment guide
- [ ] Document known issues and limitations

**Bug Fixes**
- [ ] Address all critical bugs
- [ ] Fix high-priority issues
- [ ] Document low-priority issues for future releases

#### Deliverables
- [ ] Production-ready system
- [ ] Comprehensive test results
- [ ] User manual draft
- [ ] Deployment guide

---

## Week 15: Documentation & Deployment

#### Key Activities

**Final Documentation**
- [ ] Complete user manual
  - [ ] Setup instructions
  - [ ] Feature usage guides
  - [ ] Troubleshooting guide
  - [ ] Caregiver guide
- [ ] Complete deployment guide
  - [ ] Raspberry Pi setup instructions
  - [ ] Network configuration
  - [ ] Database setup
  - [ ] Maintenance procedures
- [ ] Technical documentation
  - [ ] Architecture overview
  - [ ] API documentation
  - [ ] Database schema documentation
  - [ ] Service documentation

**Deployment Preparation**
- [ ] Create deployment package
- [ ] Test deployment on clean Raspberry Pi
- [ ] Create installation script
- [ ] Test backup/restore procedures
- [ ] Prepare cloud backup setup (if applicable)

**Final Presentation Preparation**
- [ ] Create presentation materials
- [ ] Prepare demo
- [ ] Document project outcomes
- [ ] Prepare success metrics report
- [ ] Create video demonstration (if required)

**Final User Acceptance Testing**
- [ ] Conduct final UAT with beta families
- [ ] Collect final feedback
- [ ] Verify all success metrics met
- [ ] Document final results

#### Deliverables
- [ ] Complete system with documentation
- [ ] Deployment package
- [ ] Final presentation
- [ ] User acceptance test results
- [ ] Success metrics report

---

## Code Quality & Refactoring (GitHub Issues)

See GitHub issues for details. Summary:

- [x] ~~Issue #1: Remove responsive_system.py~~ - DONE
- [ ] Issue #2: Extract display logic from app_factory → display_controller.py
- [ ] Issue #3: Consolidate interfaces.py into database_manager.py
- [ ] Issue #4: Merge database_schema.py into DatabaseManager
- [ ] Issue #5: Fix hardcoded values (window position, comments)
- [ ] Issue #6: Create UserSession class (optional)
- [ ] Issue #7: Reorganize project structure (do last)
- [ ] Issue #8: Document service patterns (optional)
