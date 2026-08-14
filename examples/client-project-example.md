# Example: Client Project Workflow

## Scenario

A client wants a **restaurant website** with online ordering and reservations.

---

## Step 1: CEO Agent (Thread 1)

**Input (Client Message):**
> I need a website for my restaurant. It should have online ordering and a reservation system. We're a mid-sized Italian restaurant in Jakarta.

**CEO Agent Output:**

```markdown
# Project Brief: Bella Italia Restaurant Website

## Business Goals
- Increase online orders by 40% within 6 months
- Reduce phone reservation calls by 60%
- Build a modern digital presence

## Functional Requirements
1. **Online Ordering Menu**
   - Browse menu with categories (Appetizers, Mains, Desserts, Drinks)
   - Add items to cart with quantity selection
   - Customization options (spice level, dietary preferences)
   - Order summary and checkout

2. **Reservation System**
   - Calendar-based date/time selection
   - Party size selection (1-10 guests)
   - Table availability display
   - Confirmation email

3. **Payment Integration**
   - Credit/debit cards
   - Digital wallets (GoPay, OVO)
   - Cash on delivery option

## Non-functional Requirements
- Mobile-first responsive design
- Page load time < 3 seconds
- Support 500 concurrent users
- Indonesian and English language support

## Constraints
- Budget: IDR 75,000,000
- Timeline: 6 weeks
- Must integrate with existing POS system

## Success Criteria
- Online orders increase 40%
- Reservation calls decrease 60%
- User satisfaction score > 4.5/5
```

---

## Step 2: Researcher Agent (Thread 7)

**Input:** CEO's Project Brief

**Researcher Agent Output:**

```markdown
# Technology Research Report

## Recommended Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Frontend | Next.js 14 | SSR for SEO, React ecosystem |
| Backend | Node.js + Express | JavaScript consistency, rapid dev |
| Database | PostgreSQL | Relational data (orders, reservations) |
| ORM | Prisma | Type-safe database queries |
| Payments | Midtrans | Local Indonesian payment methods |
| Hosting | Vercel + Supabase | Easy deployment, managed database |
| Email | Resend | Transactional emails, good DX |

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| POS integration complexity | High | Medium | Use REST API, fallback to CSV import |
| Payment gateway approval delay | Medium | High | Start integration early, use sandbox |
| Mobile performance | Low | Medium | Image optimization, lazy loading |

## Alternatives Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| WordPress + WooCommerce | Fast setup, many plugins | Limited customization, slower | Rejected |
| Laravel + Blade | Good for PHP teams | Smaller ecosystem than Next.js | Rejected |
| Flutter Web | Single codebase | SEO challenges, smaller community | Rejected |
```

---

## Step 3: Project Manager Agent (Thread 3)

**Input:** CEO Brief + Research Report

**Project Manager Agent Output:**

```markdown
# Technical Design Document (TDD)

## Milestones

| # | Milestone | Tasks | Agent | Duration |
|---|-----------|-------|-------|----------|
| M1 | Design | Wireframes, design system, mockups | Designer | Week 1 |
| M2 | Backend | API design, DB schema, auth | Developer | Week 2-3 |
| M3 | Frontend | Pages, components, responsive | Developer | Week 2-3 |
| M4 | Integration | Payment, email, POS sync | Developer | Week 4 |
| M5 | Testing | Unit, integration, UAT | QA | Week 5 |
| M6 | Launch | Deploy, DNS, monitoring | Developer | Week 6 |

## Task Breakdown

### M1: Design (Week 1)
- [ ] Create wireframes for all pages
- [ ] Define design system (colors, typography)
- [ ] Design menu page with item cards
- [ ] Design reservation flow
- [ ] Design checkout process
- [ ] Get client approval on designs

### M2: Backend (Week 2-3)
- [ ] Design PostgreSQL schema
- [ ] Create API endpoints (menu, orders, reservations)
- [ ] Implement authentication
- [ ] Set up Midtrans payment integration
- [ ] Create email templates

### M3: Frontend (Week 2-3)
- [ ] Set up Next.js project
- [ ] Build responsive layout
- [ ] Create menu browsing page
- [ ] Build cart and checkout flow
- [ ] Create reservation calendar

### M4: Integration (Week 4)
- [ ] Connect frontend to backend APIs
- [ ] Test payment flow end-to-end
- [ ] Set up POS data sync
- [ ] Configure email delivery

### M5: Testing (Week 5)
- [ ] Write unit tests for API endpoints
- [ ] Test responsive design on devices
- [ ] Perform security review
- [ ] Load testing for concurrent users
- [ ] Client UAT session

### M6: Launch (Week 6)
- [ ] Deploy to Vercel
- [ ] Configure custom domain
- [ ] Set up monitoring and alerts
- [ ] Handoff documentation
- [ ] Client training session
```

---

## Step 4: Designer Agent (Thread 4)

**Input:** CEO Brief + PM's TDD

**Designer Agent Output:**

```markdown
# Design System: Bella Italia

## Colors
| Role | Name | Hex | Usage |
|------|------|-----|-------|
| Primary | Italian Red | #C41E3A | CTAs, headers |
| Secondary | Olive Green | #556B2F | Accents, badges |
| Background | Cream | #FFF8E7 | Page background |
| Text | Espresso | #3C2415 | Body text |
| Surface | White | #FFFFFF | Cards, modals |

## Typography
| Element | Font | Size | Weight |
|---------|------|------|--------|
| H1 | Playfair Display | 40px | Bold |
| H2 | Playfair Display | 32px | SemiBold |
| Body | Inter | 16px | Regular |
| Button | Inter | 14px | SemiBold |

## Key Pages
1. **Home** — Hero, featured dishes, CTA
2. **Menu** — Category filters, item cards, cart
3. **Reservation** — Calendar, time slots, confirmation
4. **Checkout** — Order summary, payment, confirmation
```

---

## Step 5: Developer Agent (Thread 6)

**Input:** TDD + Designs

**Developer Agent Output:**

```markdown
# Implementation Report

## Completed Features
- [x] Menu API (CRUD operations)
- [x] Order API (create, status tracking)
- [x] Reservation API (availability, booking)
- [x] Payment integration (Midtrans sandbox)
- [x] Responsive menu page
- [x] Cart functionality
- [x] Checkout flow

## Code Structure
```
src/
├── app/
│   ├── page.tsx          # Home
│   ├── menu/page.tsx     # Menu
│   ├── reservation/      # Reservation
│   └── checkout/         # Checkout
├── components/
│   ├── MenuCard.tsx
│   ├── CartDrawer.tsx
│   └── ReservationForm.tsx
├── api/
│   ├── menu/route.ts
│   ├── orders/route.ts
│   └── reservations/route.ts
└── lib/
    ├── db.ts             # Prisma client
    └── payments.ts       # Midtrans
```

## Git Commits
- `feat: initialize Next.js project` (a1b2c3d)
- `feat: implement menu API` (e4f5g6h)
- `feat: build responsive menu page` (i7j8k9l)
- `feat: add cart functionality` (m0n1o2p)
- `feat: integrate Midtrans payment` (q3r4s5t)
```

---

## Step 6: QA Agent (Thread 8)

**Input:** TDD + Code + Designs

**QA Agent Output:**

```markdown
# Test Report: Bella Italia Website

## Summary
| Metric | Value |
|--------|-------|
| Test Cases | 52 |
| Passed | 48 |
| Failed | 3 |
| Blocked | 1 |
| Pass Rate | 92.3% |

## Failed Tests
| ID | Feature | Severity | Description |
|----|---------|----------|-------------|
| F01 | Cart | High | Total not updating on quantity change |
| F02 | Reservation | Medium | Past dates selectable in calendar |
| F03 | Mobile | Medium | Menu images overflow on small screens |

## Blocked
| ID | Feature | Reason |
|----|---------|--------|
| B01 | Payment | Need production Midtrans credentials |

## Quality Gate: CONDITIONAL PASS
Fix 1 High-severity bug before deployment. Medium bugs can be patched post-launch.

## Performance
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Page Load | < 3s | 2.1s | Pass |
| API Response | < 500ms | 320ms | Pass |
| Lighthouse | > 90 | 94 | Pass |
```

---

## Final Handoff

```markdown
# Project Complete: Bella Italia Website

## Deliverables
- [x] Responsive restaurant website
- [x] Online ordering system
- [x] Reservation system
- [x] Payment integration
- [x] Admin documentation

## Status: DEPLOYED
- URL: https://bellaitalia.id
- Hosting: Vercel
- Database: Supabase

## Next Steps
1. Client to add real menu photos
2. Switch to production Midtrans keys
3. Monitor analytics for 2 weeks
4. Schedule Phase 2 planning (loyalty program)
```
