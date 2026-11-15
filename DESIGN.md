# ElderCare Connect — Design System

A calm, trustworthy and highly legible design system for older adults managing medications and appointments, and for the caregivers who support them. It should feel professional, modern and reassuring, never clinical or cluttered.

## 1. Principles

1. **Readable first.** Large text, generous line height, high contrast. Nothing important below 18px.
2. **One thing at a time.** Each screen has one clear primary task and one primary button.
3. **Never rely on colour alone.** Every status uses an icon, a text label and a colour.
4. **Big, forgiving targets.** Minimum 48×48px touch targets with at least 8px between them.
5. **Predictable navigation.** The same few destinations, always in the same place, always labelled with text.
6. **Reassuring tone.** Plain, friendly language. Confirm actions clearly and explain errors kindly.

## 2. Colour

All text pairs meet WCAG 2.2 AA (4.5:1). Body text meets AAA (7:1).

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `primary` | `#0F766E` | Primary buttons, active nav, links | 5.5:1 on white |
| `primary-hover` | `#115E59` | Hover/pressed primary | 7.6:1 on white |
| `on-primary` | `#FFFFFF` | Text on primary | — |
| `primary-container` | `#CCFBF1` | Selected states, highlight panels | — |
| `on-primary-container` | `#134E4A` | Text on primary-container | 9.6:1 |
| `background` | `#F8FAFC` | Page background | — |
| `surface` | `#FFFFFF` | Cards, forms, nav bar | — |
| `surface-muted` | `#F1F5F9` | Secondary panels, table stripes | — |
| `text-primary` | `#0F172A` | Headings, body text | 17.8:1 on white |
| `text-secondary` | `#334155` | Supporting text | 10.4:1 on white |
| `border` | `#CBD5E1` | Card and divider lines (decorative) | — |
| `border-strong` | `#64748B` | Input borders, outlined buttons | 4.8:1 on white |
| `focus` | `#1D4ED8` | Focus ring | 6.7:1 on white |

### Status colours

| Status | Foreground | Background | Icon | Label |
|---|---|---|---|---|
| Success / Taken | `#15803D` (text `#14532D`) | `#F0FDF4` | Check circle | "Taken" |
| Warning / Pending / Due | `#B45309` (text `#78350F`) | `#FFFBEB` | Clock | "Due at 2:00 PM" |
| Danger / Missed | `#B91C1C` (text `#7F1D1D`) | `#FEF2F2` | Alert triangle | "Missed" |
| Info / Upcoming | `#1D4ED8` (text `#1E3A8A`) | `#EFF6FF` | Info circle / calendar | "Upcoming" |

Use the background tint with a 1px border in the foreground colour, a bold text label and an icon. Never use colour alone.

## 3. Typography

- **Font family:** Atkinson Hyperlegible Next for everything (headings, body, labels). Fallback: Lexend, then system-ui, sans-serif.
- **Minimum body size:** 18px. Nothing interactive or essential smaller than 18px. Metadata may use 16px sparingly.
- Left-aligned text. No justified text, no all-caps paragraphs, no italics for meaning.
- Maximum line length about 70 characters.

| Level | Size / Line height | Weight | Use |
|---|---|---|---|
| `display` | 40px / 48px | 700 | Welcome greeting |
| `h1` | 32px / 40px | 700 | Page title |
| `h2` | 26px / 34px | 700 | Section title |
| `h3` | 22px / 30px | 600 | Card title, medication name |
| `body-lg` | 20px / 32px | 400 | Key values, intro text |
| `body` | 18px / 28px | 400 | Default body text |
| `label` | 18px / 24px | 600 | Buttons, form labels, nav labels |
| `caption` | 16px / 24px | 400 | Timestamps, helper text only |

Mobile: `display` 32px, `h1` 28px, `h2` 24px. Body stays 18px.

## 4. Spacing & Layout

- **Base unit:** 8px. Scale: 4, 8, 12, 16, 24, 32, 48, 64.
- **Card padding:** 24px (mobile 20px).
- **Gap between cards/sections:** 24px; between page sections 32–48px.
- **Max content width:** 1200px, centred.
- **Page gutters:** 16px mobile, 24px tablet, 32px desktop.

| Breakpoint | Width | Grid |
|---|---|---|
| Mobile | < 640px | 1 column |
| Tablet | 640–1023px | 2 columns |
| Desktop | ≥ 1024px | 12 columns (cards span 4, 6 or 8) |

## 5. Shape & Elevation

- **Radius:** 12px buttons and inputs; 16px cards; full (pill) for status badges.
- **Elevation:** flat, quiet surfaces. Cards: 1px `border` plus a subtle shadow `0 1px 3px rgba(15,23,42,0.08)`. No heavy shadows, gradients or glassmorphism.

## 6. Components

### Buttons
- Height **56px** for primary actions, **48px** minimum for all others. Padding 24px horizontal. `label` typography.
- **Primary:** `primary` fill, white text. One per view.
- **Secondary:** white fill, 2px `border-strong` outline, `text-primary` text.
- **Danger:** `#B91C1C` fill, white text, always with a confirmation.
- Always a text label; an icon on its own is never enough. Icon (24px) leads the label.
- Full width on mobile for primary actions.

### Form fields
- Label always visible above the field (never placeholder-only), `label` style.
- Input height 56px, 18px text, 2px `border-strong` border, 12px radius, white fill.
- Helper text below in `caption` `text-secondary`.
- Error: 2px `#B91C1C` border, alert icon, and a plain-language message below ("Please enter your email address").
- Password fields include a labelled "Show password" toggle.

### Focus
- Every interactive element shows a 3px `focus` ring with a 2px offset. Never remove outlines.

### Cards
- White surface, 16px radius, 24px padding, `h3` title, optional status badge top-right.

### Status badges
- Pill shape, 32px tall minimum, 16px horizontal padding, icon plus bold label, tinted background with a 1px border.

### Progress
- Daily progress shown as a thick (12px) rounded bar **plus** text: "3 of 5 doses taken".

### Alerts
- Full-width banner, tinted status background, 4px left border in the status colour, icon, bold title and short message.

## 7. Navigation

- **Desktop/tablet:** top bar with logo on the left, at most 5 text-labelled destinations, and the account menu on the right. Active item: `primary-container` background plus `primary` text and a 3px underline.
- **Mobile:** bottom tab bar with 4–5 items, each 64px tall with a 24px icon **and** a text label.
- Primary destinations for older users: **Home, Medications, Appointments, Family, Profile**.
- Page title (`h1`) at the top of every page; a "Back" button with text where depth > 1.

## 8. Iconography & Imagery

- Outlined icons (Material Symbols Rounded), 24px default, 2px stroke, always paired with text.
- Imagery: warm, real, diverse older adults; optional and never essential to meaning.

## 9. Voice & Content

- Plain English, short sentences, second person ("Your next dose is at 2:00 PM").
- Times in 12-hour format with AM/PM; dates written out ("Monday, 16 November").
- Confirm success clearly ("Done — Metformin marked as taken").
- Avoid jargon, abbreviations and medical shorthand.

## 10. Accessibility Checklist

- WCAG 2.2 AA minimum; AAA contrast for body text.
- 48×48px minimum targets, 8px spacing between targets.
- Supports 200% zoom without horizontal scrolling.
- Respects `prefers-reduced-motion`; animations ≤ 200ms and non-essential.
- Logical heading order; landmarks (`header`, `nav`, `main`, `footer`).
- Status changes announced to screen readers (live regions).

## Data access and performance

- **Layering:** routes, then services (business rules such as `Scope.may_record`), then repositories (the only code that touches MongoDB collections). The notification engine also reads through repositories.
- **Projections:** dose and appointment `history` arrays (audit trail) are excluded from list and read queries (`WITHOUT_HISTORY`). Today's-doses replies shrank from 12.9 KB to 9.2 KB of database payload.
- **Combined overview:** `GET /api/medications/overview` (and the linked-profile variant) replaces three requests on the medication page: 12 database commands and 18 KB become 5 commands and 7.6 KB. The original endpoints remain.
- **Reminder cycle:** each pass loads only due doses and appointments, the medications that need schedule top-up (`medications_top_up` index), and batched profiles, users, preferences and links. It then inserts new notifications in one `insert_many` after one dedupe-key lookup. In a 500-user benchmark the steady-state cycle went from 2,316 database commands and 2.95 s to 18 commands and about 0.45 s, with identical notifications queued.
- **Frontend:** 18 secondary routes are lazy-loaded (`React.lazy` with an accessible `Suspense` loader). The entry bundle went from 445.9 KB (134.0 KB gzip) to 355.4 KB (114.7 KB gzip).
