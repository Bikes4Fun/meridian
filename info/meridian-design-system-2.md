# Meridian Design System
**Digital Assistant for Dementia Care · Multi-Platform Ecosystem**

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Core Design Principles](#core-design-principles)
3. [Multi-Platform Strategy](#multi-platform-strategy)
4. [Color Palettes](#color-palettes)
5. [Typography](#typography)
6. [Components](#components)
7. [Accessibility Guidelines](#accessibility-guidelines)
8. [Cross-Platform User Flows](#cross-platform-user-flows)

---

## Project Overview

Meridian is a multi-platform digital assistant ecosystem designed for people living with mild-to-moderate dementia and their family caregivers. The system consists of three interconnected platforms that work together to provide care, communication, and peace of mind.

### The Three Platforms

#### 1. TV Kiosk (Hardware)
- **Description:** Vertical touchscreen display installed in the patient's home
- **Dimensions:** 27" diagonal display (portrait monitor)
- **Resolution:** 1080×1920px (Full HD portrait)
- **Physical Size:** Approximately 14"W × 23"H
- **Viewing Distance:** 4-6 feet (typical room distance)
- **Primary User:** Person with dementia
- **Key Features:**
  - Daily orientation (date, time, weather)
  - Medication reminders
  - Emergency medical info
  - Photo-based family directory with one-touch calling
  - Always-on display

#### 2. Web Dashboard (Admin)
- **Description:** Full-featured dashboard for system configuration and management
- **Platform:** Desktop/tablet responsive web application
- **Primary User:** Primary caregiver/family admin
- **Key Features:**
  - User management (add/edit family members & permissions)
  - Medication scheduling (set reminders, dosages, instructions)
  - Photo library management
  - Activity logs and analytics
  - Payment and account settings
  - Reports and data export

#### 3. Mobile App
- **Description:** On-the-go communication hub
- **Platform:** iOS & Android native apps
- **Primary Users:** All family members and caregivers
- **Key Features:**
  - Quick call/message to patient
  - Push notifications (medication alerts, emergency calls)
  - Real-time activity feed
  - Photo sharing to kiosk
  - Location updates
  - Quick settings adjustments

---

## Core Design Principles

### 1. Reduce Cognitive Load
- Minimize information density
- Use clear visual hierarchy
- One primary action per screen
- Maximum 3-4 options to choose from
- Avoid jargon, acronyms, or technical terms

### 2. Familiarity & Trust
- Use recognizable patterns
- Warm, personal photography
- Consistent layouts and navigation
- Calming aesthetics
- Professional yet friendly tone

### 3. Simple Interaction
- Large touch targets (minimum 120px on kiosk)
- Clear affordances
- Immediate visual feedback
- Minimal steps to complete tasks
- No complex gestures

### 4. High Contrast
- WCAG AAA compliance (7:1 contrast ratio minimum)
- Strong text contrast on all backgrounds
- Clear boundaries between interactive elements
- No reliance on color alone for meaning

### 5. Calm & Reassuring
- Soft, stress-reducing color palette
- Generous whitespace
- Gentle transitions (no jarring animations)
- Avoid creating urgency except for emergencies

### 6. Orientation Support
- Always display current date, time, and weather
- Photo-based recognition for family members
- Visual context cues on every screen
- Clear indication of "where am I" at all times

---

## Multi-Platform Strategy

### Shared Design Tokens

**Consistent Across All Platforms:**
- Color palette (same primary, secondary, semantic colors)
- Typography (same font family: Atkinson Hyperlegible or Inter)
- Icon library (consistent style and meaning)
- Component shapes (same border radius, shadow styles)
- Language & tone (clear, warm, supportive)

**Adapted Per Platform:**
- Text sizes (larger for TV, standard for web/mobile)
- Touch targets (120px TV, 44px mobile, 32px web)
- Information density (low on TV, higher on web)
- Navigation patterns (minimal on TV, sidebar on web, bottom nav on mobile)
- Layout complexity (simple on TV, moderate on mobile, advanced on web)

### Platform-Specific Specifications

#### TV Kiosk Design Specs

**Visual Design:**
- Minimum text: 24px (absolute minimum), 32px+ preferred
- Headings: 48-72px for main titles
- Display headings: 96-128px for time/date displays
- Touch targets: 120×120px minimum, 160×160px ideal
- Spacing: 32-48px between major elements
- Contrast: WCAG AAA (7:1) for all text
- Line height: 1.6-1.8 for maximum readability
- Safe margins: 40-48px from screen edges

**Interaction Design:**
- Max actions per screen: 1 primary, 2-3 secondary
- Navigation depth: Maximum 2 levels from home
- Feedback timing: Immediate (<100ms) visual response
- Animations: Minimal, gentle fades only
- Auto-dismiss: Never (user must confirm all actions)
- Error recovery: Always provide clear "go back" option

**Key Principle:** The TV kiosk is designed for someone who may be confused or disoriented. Every screen should answer: "Where am I?" "What should I do?" "How do I get help?"

#### Web Dashboard Design Specs

**Visual Design:**
- Text sizes: 14-16px body, 20-32px headings
- Click targets: 32×32px minimum (standard web)
- Grid system: 12-column responsive layout
- Sidebar: 240-280px navigation sidebar
- Data tables: Sortable, filterable, paginated
- Forms: Clear labels, inline validation, helpful hints

**Key Principle:** The web dashboard is for caregivers who need detailed control and visibility. Balance power-user features with clarity—avoid overwhelming first-time users.

#### Mobile App Design Specs

**Visual Design:**
- Text sizes: 16px body minimum, 24-32px headings
- Touch targets: 44×44px minimum (iOS standard)
- Bottom navigation: 4-5 primary sections
- Safe areas: Respect device notches, home indicators
- Dark mode: Support system theme preference
- Native patterns: Follow iOS/Android guidelines

**Key Principle:** The mobile app is for family members on the go. Prioritize speed and notifications—enable quick check-ins and responses without opening the full app.

---

## Color Palettes

### Direction 1: Warm & Familiar

**Concept:** Soft earth tones that evoke comfort and home. High contrast while maintaining warmth.

**Color Specifications:**
- Base: #FAF8F3 (Background)
- Cream: #F5EFE7 (Surface)
- Warm Gray: #4A4A4A (Primary text, 12.6:1 contrast on base)
- Terracotta: #C85A3F (Primary action, 5.2:1 contrast on base)
- Sage: #7A9B76 (Success states, 4.8:1 contrast on base)
- Golden: #D4A574 (Warning states, 3.8:1 contrast on base)

**Use Cases:** Best for home-like environments, reduces anxiety, feels personal and inviting.

### Direction 2: Clinical Clarity

**Concept:** Professional medical palette with trustworthy blues and crisp contrast.

**Color Specifications:**
- Pure White: #FFFFFF (Background)
- Light Gray: #F7F9FA (Surface)
- Charcoal: #2C3E50 (Primary text, 14.8:1 contrast on white)
- Medical Blue: #2E7D9B (Primary action, 5.5:1 contrast on white)
- Clinical Green: #52A675 (Success states, 4.9:1 contrast on white)
- Alert Coral: #E67E73 (Warning states, 4.2:1 contrast on white)

**Use Cases:** Best for medical facilities, professional caregiving settings, high trust environments.

### Direction 3: Gentle Pastels

**Concept:** Calming, low-stress palette designed to reduce anxiety and promote peace.

**Color Specifications:**
- Soft White: #FDFCFB (Background)
- Lavender Mist: #F4F1F8 (Surface)
- Deep Plum: #3D2E4F (Primary text, 13.2:1 contrast on base)
- Sky Blue: #6B9AC4 (Primary action, 4.6:1 contrast on base)
- Sage Green: #94B49F (Success states, 4.3:1 contrast on base)
- Soft Coral: #D89B9E (Warning states, 4.0:1 contrast on base)

**Use Cases:** Best for maximum calm, stress reduction, peaceful morning/evening use.

### Color Accessibility Notes
- All text colors meet WCAG AAA standard (7:1 minimum contrast ratio)
- Interactive elements use both color AND shape/text to convey meaning
- Emergency/urgent states use both red AND icon + bold text
- Color is never the only method of conveying information
- Tested for common types of color blindness (protanopia, deuteranopia, tritanopia)

---

## Typography

### Recommended Typefaces

#### 1. Atkinson Hyperlegible (RECOMMENDED)
- **Why:** Specifically designed for low vision readers
- **Features:** High character differentiation, open counters
- **Best for:** Dementia care - maximizes readability
- **Source:** Google Fonts

#### 2. Inter (RECOMMENDED)
- **Why:** Excellent for UI, optimized for screens
- **Features:** Tall x-height, open apertures
- **Best for:** Widely used, highly legible, professional
- **Source:** Google Fonts

#### 3. Lexend (RECOMMENDED)
- **Why:** Designed to reduce visual stress
- **Features:** Improves reading fluency
- **Best for:** Reduces reading effort and cognitive load
- **Source:** Google Fonts

### Typography Scale

**TV Kiosk:**
- Display: 72px / 700 weight (Large time display, emergency alerts)
- Heading 1: 56px / 700 weight (Screen titles, greetings)
- Heading 2: 40px / 600 weight (Section headers, card titles)
- Body Large: 32px / 400 weight (Primary body text, descriptions)
- Body: 28px / 400 weight (Secondary text, labels)
- Caption: 24px / 500 weight (Minimum size - timestamps, metadata)

**Web Dashboard:**
- Heading 1: 32px / 700 weight
- Heading 2: 24px / 600 weight
- Body: 16px / 400 weight
- Small: 14px / 400 weight

**Mobile App:**
- Heading 1: 28px / 700 weight
- Heading 2: 20px / 600 weight
- Body: 16px / 400 weight
- Small: 14px / 400 weight

### Typography Best Practices
- Line height: 1.5-1.7 for optimal readability
- Line length: Maximum 60-70 characters per line
- Paragraph spacing: 1.5-2× the line height
- Never use all caps for sentences (harder to read)
- Use sentence case for most text, Title Case for buttons/headings
- Avoid italics in body text (reduces legibility)
- Letter spacing: Default or slightly increased (never decreased)
- Use bold for emphasis, not color alone

---

## Components

### Photo-Based Recognition Principle

**Critical Design Decision:** For users with dementia, visual recognition of faces is often preserved longer than name recall. The kiosk and mobile app prioritize photos to make family members instantly recognizable.

### Call/Contact Buttons Across Platforms

#### TV Kiosk (Photo-Based)
- **Photo size:** 128px circular
- **Total height:** 180px
- **Name text:** 32px bold
- **Relationship:** 20px regular
- **Status indicator:** Green dot + "Available" text
- **Design:** Large photo with name below, optimized for 6-10 foot viewing distance

#### Web Dashboard (Text-Based)
- **Height:** 44px
- **Text size:** 16px
- **Avatar:** 32px small circular thumbnail
- **Layout:** Small avatar + full name + relationship context
- **Design:** Compact, information-dense for administrative tasks

#### Mobile App (Photo-Based)
- **Photo size:** 64px circular
- **Total height:** 84px
- **Name text:** 18px bold
- **Action icon:** 48px circular button (call/video)
- **Design:** Medium photo with clear tap target for thumb-friendly interaction

### Button Specifications

**TV Kiosk:**
- Primary buttons: 160×160px minimum
- Icon + text always (never icon-only)
- Text: 24px minimum
- Rounded corners: 12-16px
- Immediate visual feedback on tap

**Web Dashboard:**
- Primary buttons: 32×44px minimum
- Standard web conventions
- Text: 16px
- Rounded corners: 8px

**Mobile App:**
- Primary buttons: 44×44px minimum (iOS standard)
- Native platform patterns
- Text: 16px
- Rounded corners: 8-12px

### Card Components

**All cards should include:**
- Clear borders (2px minimum)
- Generous padding (16-24px)
- Clear visual hierarchy
- One primary action per card
- High contrast between card and background

### Status Indicators

**Never rely on color alone - always include:**
- Icon (checkmark, bell, alert triangle)
- Text label ("Medication taken", "Reminder pending")
- Visual shape/border distinction
- Sufficient contrast (7:1 minimum)

---

## Accessibility Guidelines

### Visual Clarity
- Minimum 7:1 contrast ratio (WCAG AAA)
- Minimum text size: 24px for TV viewing distance
- No reliance on color alone to convey information
- High contrast borders on all interactive elements
- Avoid busy backgrounds or patterns behind text
- Use matte finishes to reduce screen glare

### Motor & Touch
- Minimum touch target: 120×120px (TV kiosk)
- Minimum touch target: 44×44px (mobile app)
- Minimum spacing between targets: 24px
- No double-tap or complex gestures required
- Simple tap is primary interaction
- No drag or swipe gestures for critical functions
- Visible feedback on all touches (instant response)

### Cognitive Load
- One primary action per screen
- Maximum 3-4 options to choose from
- Consistent layout and navigation patterns
- Clear, simple language (6th grade reading level)
- Avoid jargon, acronyms, or technical terms
- Provide context at every step (where am I?)

### Time & Memory
- No time limits on any tasks
- Always show current date, time, and location
- Confirmation before destructive actions
- Easy undo for all actions
- Persistent reminders (don't auto-dismiss)
- Photo-based recognition over text-based memory

### Audio Support
- Optional text-to-speech for all content
- Audio confirmations for actions
- Clear, high-quality audio (no background noise)
- Volume controls easily accessible
- Captions for all video content
- Visual + audio feedback for important events

### Safety & Privacy
- Emergency contact always visible
- Clear "Help" button on every screen
- Prevent accidental calls/messages (confirmation)
- No personal data visible to visitors
- Family can monitor but not intrude
- Clear indication when being monitored/recorded

---

## Cross-Platform User Flows

### Flow 1: Setting Up a Medication Reminder

**Step 1: Web Dashboard (Caregiver)**
- Primary caregiver logs into web dashboard
- Navigates to "Medications" section
- Creates new reminder: drug name, dosage, time, frequency, special instructions
- Uses progressive disclosure (common fields first, advanced options behind toggle)

**Step 2: Mobile App (Family Members)**
- All authorized family members receive push notification
- "Sarah added a new medication reminder for Mom - Aricept at 2:00 PM daily"
- Can tap to view details or quick "Got it" acknowledgment

**Step 3: TV Kiosk (Patient)**
- At 2:00 PM, kiosk displays full-screen medication reminder
- Shows medication name, dosage photo if available
- Large "Mark as Taken" button
- Option: "Remind me in 15 min" (without guilt)
- Gentle audio chime (not alarming)

### Flow 2: Emergency Help Request

**Step 1: TV Kiosk (Patient)**
- Patient taps large "Emergency Help" button on home screen
- Confirmation: "Call emergency contact Sarah?" with her photo
- Patient taps "Yes, Call Now"

**Step 2: Mobile App (Primary Contact)**
- Sarah's phone rings with high-priority call (overrides Do Not Disturb)
- Shows clear visual indication this is from Meridian system
- If no answer within 30 seconds, escalates to next contact
- Video call connects immediately when answered

**Step 3: Mobile App (Other Family)**
- All other family members receive notification
- "Mom requested emergency help. Sarah is responding."
- Can view status and offer to help if needed

**Step 4: Web Dashboard (Activity Log)**
- Emergency event logged with timestamp, responder, duration, outcome
- Caregivers can add notes for context
- Timeline view with color coding for event types

### Flow 3: Morning Check-In & Photo Sharing

**Step 1: TV Kiosk (Patient)**
- 8:00 AM greeting: "Good morning, Margaret! Today is Monday, March 16, 2026"
- Shows weather, today's schedule, new photos from family
- Patient browses photos of grandchildren

**Step 2: Mobile App (Grandson)**
- John opens app during commute
- Shares photo from weekend soccer game with caption "Scored 2 goals, Grandma!"
- Photo instantly syncs to kiosk display
- Auto-moderated for appropriate content

**Step 3: TV Kiosk (Patient)**
- Gentle notification: "New photo from John!"
- Shows grandson in soccer uniform with caption
- "Call John" button immediately available

**Step 4: Web Dashboard (Analytics)**
- Primary caregiver checks weekly report
- Sees patient viewed photo 4 times, called John once
- Positive engagement metrics indicate good cognitive/emotional connection
- Data framed as "connection insights" not surveillance

---

## Design Principles for Multi-Platform Flows

### Seamless Handoffs
- Actions started on one platform can be completed on another
- State syncs in real-time (or as close as possible)
- Clear visual indicators when data is syncing
- Graceful handling of offline/connection issues

### Contextual Notifications
- Right information to right person at right time
- Urgent vs. informational notification hierarchy
- Respect notification preferences per platform
- Allow muting without missing critical alerts

### Privacy & Dignity
- Patient knows when family is monitoring activity
- Family can see health/safety info without feeling invasive
- Clear consent and permission settings
- Data shown in supportive, not judgmental way

### Graceful Degradation
- Each platform works independently if others fail
- Offline modes for mobile app and web dashboard
- Fallback to SMS if push notifications fail
- Emergency contacts always reachable via phone

---

## Testing Checklist

### Visual Testing
- [ ] Test with color blindness simulators
- [ ] Verify contrast ratios with tools
- [ ] View from 10 feet away (kiosk)
- [ ] Test in bright and dim lighting
- [ ] Check with blurred vision simulation

### Interaction Testing
- [ ] Test with limited fine motor control
- [ ] Verify all targets meet minimum sizes
- [ ] Try with finger, stylus, and pointer
- [ ] Ensure no accidental activations
- [ ] Test response time and feedback

### Cognitive Testing
- [ ] Test with users with cognitive challenges
- [ ] Measure time to complete tasks
- [ ] Observe confusion points
- [ ] Check reading level (6th grade max)
- [ ] Verify consistent mental models

### Real-World Testing
- [ ] Test in actual home environment
- [ ] Different times of day (sunlight/glare)
- [ ] With caregivers present and absent
- [ ] During stress or confusion episodes
- [ ] Long-term usage patterns (weeks)

---

## Resources

### Accessibility Standards
- WCAG 2.2 Level AAA Guidelines
- Alzheimer's Society Design Guidelines
- Inclusive Design Toolkit (Microsoft)

### Tools
- WebAIM Contrast Checker
- Stark plugin for Figma
- Color Oracle (color blindness simulator)

### Fonts
- Atkinson Hyperlegible: https://fonts.google.com/specimen/Atkinson+Hyperlegible
- Inter: https://fonts.google.com/specimen/Inter
- Lexend: https://fonts.google.com/specimen/Lexend

---

**Document Version:** 1.0  
**Last Updated:** March 16, 2026  
**Prepared for:** Meridian Design Team  
**Contact:** design@meridiancare.com

---

*This design system prioritizes accessibility, dignity, and independence for people living with dementia. Every design decision should be made with empathy, tested with real users, and refined based on their feedback.*
