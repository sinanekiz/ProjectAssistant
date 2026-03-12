# Mobitolya Context

## Identity And Ownership

`Mobitolya` is Sinan's personal startup project.

It must be treated as a separate business context from company projects such as:

- `GridBox.HeadEnd`
- `GridBox.MDM`
- any other `HayenTechnology` / `GridBox` repository

This separation matters operationally and legally:

- support answers must not mix company product assumptions into Mobitolya
- company internal context must not be treated as Mobitolya product knowledge
- ownership, priorities, and expectations are different

## What Mobitolya Is

Mobitolya appears to be a business operations platform with backend and frontend
projects covering areas such as:

- product and catalog management
- order and incoming order handling
- offers and invoicing
- finance and payment flows
- warehouse and stock operations
- production planning and execution
- company and address data
- messaging, mail, and SMS
- e-commerce integrations
- AI-assisted parsing of incoming requests/orders

Operationally, it looks much closer to an ERP / commerce / operations platform
than to a field communication system.

## Main Business Boundary

Mobitolya scope appears to include:

- receiving business requests from customers, often through WhatsApp
- helping users operate the product correctly
- troubleshooting application behavior
- handling operational and workflow questions
- interpreting incoming customer intents and occasionally converting them into
  structured orders or tasks

The user's description is especially important:

- around 90 percent of incoming work/questions arrive via WhatsApp
- most questions are support/how-to/troubleshooting style
- occasional messages are genuine new feature requests

## Explicitly Out Of Scope

The following must stay outside the Mobitolya context unless the user explicitly
connects them:

- GridBox / HeadEnd meter communication issues
- MDM analytics, billing visualization, or utility-side downstream topics
- company-only infrastructure or internal enterprise codebases unrelated to
  Mobitolya

If a message is clearly about meters, device protocols, field data ingestion, or
utility platform operations, it likely belongs to GridBox context instead.

## Repository Root

Main repository root:

- `C:\Users\Sinan\source\repos\sinanekiz\Mobitolya`

Main solution:

- `C:\Users\Sinan\source\repos\sinanekiz\Mobitolya\Mobitolya.sln`

## Main Projects

Observed primary projects:

- `Mobitolya.Api`
- `Mobitolya.Entities`
- `mobitolya.web`
- `mobitolya.web.poseidon`

Additional repository content also exists:

- `Poseidon-main`
- `.github`
- `artifacts`

## Runtime Shape

From the current scan, the runtime is centered around:

- an ASP.NET Core backend
- a PostgreSQL-backed data model
- Vue-based frontend applications
- background hosted services
- AI-assisted parsing and messaging services
- commerce integrations such as WooCommerce and Shopify

This means many real-world support questions will likely be about:

- business flows not behaving as expected
- document, order, or invoice state transitions
- finance/accounting workflow issues
- warehouse and stock inconsistencies
- incoming order parsing problems
- WhatsApp/message-originated request handling
- integration sync behavior

## Key Backend Signals

Useful backend entry point:

- `C:\Users\Sinan\source\repos\sinanekiz\Mobitolya\Mobitolya.Api\Program.cs`

Important architecture signals observed there:

- JWT authentication
- Npgsql / PostgreSQL
- Serilog
- OData exposure
- hosted background workers
- static file/image serving
- AI services and incoming order parsers
- messaging worker infrastructure

Key business managers/services registered there include domains like:

- auth and user management
- products and categories
- customer orders and incoming orders
- invoices and incoming invoices
- financial accounts, items, transactions, and documents
- offers
- warehouses and warehouse stock
- production
- payment requests
- mail/SMS/messaging
- WooCommerce / Shopify integrations

This suggests Mobitolya support traffic is often tied to concrete business
entities and workflows rather than generic app issues.

## Key Frontend Signals

Useful frontend indicator:

- `C:\Users\Sinan\source\repos\sinanekiz\Mobitolya\mobitolya.web\package.json`

Observed frontend stack signals:

- Vue 3
- Vite
- PrimeVue / PrimeFlex
- Vue Router
- Vue i18n
- FullCalendar
- Chart.js
- Quill editor
- QR / PDF utilities
- MQTT client

This suggests the product has substantial user-facing workflows and rich
operational screens, not just a thin admin panel.

## Message Routing Rules

Messages likely belonging to Mobitolya:

- "Why is this not working?" type product support questions
- "How do I do X?" usage questions
- issues around orders, offers, invoices, products, stock, or payment flows
- WhatsApp-originated customer/support messages
- integration sync issues with sales channels or commerce platforms
- AI parsing / incoming order interpretation issues
- feature requests for business workflows

Messages that should usually be routed elsewhere:

- GridBox / utility / meter / field communication issues
- HeadEnd listener / protocol / queue / parser device problems
- MDM reporting, billing visualization, or downstream utility analytics

## Recommended Internal Triage For Mobitolya Messages

When a Mobitolya message arrives, classify it first as one of:

1. usage question
2. troubleshooting / bug-like issue
3. configuration / setup issue
4. data/workflow inconsistency
5. feature request

This distinction matters because the response style should differ:

- usage questions need short instructional answers
- troubleshooting needs diagnosis and next-step guidance
- workflow/data issues need entity-aware investigation
- feature requests need expectation management and scoping

## Important Language / Tone Notes

Because many questions come from customer messaging channels:

- responses should usually be short, calm, and practical
- they should avoid internal engineering jargon unless necessary
- they should prefer direct guidance over architectural explanation
- they should distinguish known behavior, likely cause, and next step

## Good Future Context Expansions

Useful future Mobitolya sub-context files would likely be:

- `Mobitolya.Orders.md`
- `Mobitolya.Finance.md`
- `Mobitolya.Warehouse.md`
- `Mobitolya.Integrations.md`
- `Mobitolya.WhatsAppFlows.md`

These should be added only if question volume shows that one broad Mobitolya
context is no longer enough.

## Recommended Long-Term Separation Model

For ProjectAssistant, keep contexts separated by ownership and product family:

- `GridBox.HeadEnd.md` for company field communication work
- `Mobitolya.md` for personal startup work

Do not merge them into one generic "Sinan projects" context.

The cleaner model is:

- one context file per product family
- explicit ownership/boundary notes in each file
- later, a database-backed context registry with tags such as:
  - `personal`
  - `company`
  - `out_of_scope`
  - `support`
  - `feature_request`

## Practical Usage In ProjectAssistant

When a new message is evaluated:

- if it mentions Mobitolya workflows, WhatsApp support, orders, invoices,
  stock, production, offers, finance, or related business operations, prefer
  this context
- if it mentions field devices, meters, protocols, listeners, queues, or MDM,
  do not default to Mobitolya

This file should be the base context note for future Mobitolya-specific
question-answering and message triage.
