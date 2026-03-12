# Mobitolya WhatsApp Flows

## Role

This file describes how WhatsApp-driven support traffic should be interpreted
for the Mobitolya product family.

## Why It Matters

Most incoming Mobitolya questions arrive over WhatsApp. They are usually not
formal bug reports. They are short operational questions, confusion about a
screen, or requests to explain why an expected action did not happen.

The assistant should treat WhatsApp traffic as the default operational support
channel for Mobitolya.

## Main WhatsApp Message Types

### How-to Questions

Examples:

- how do I create this
- how do I send this
- how do I cancel this
- where is this screen

These should usually be answered from context, expected workflow, and product
rules.

### Troubleshooting Questions

Examples:

- why did this not send
- why is this not visible
- why did the queue not process
- why is this customer not appearing

These should first be classified as:

- expected workflow misunderstanding
- missing prerequisite data
- operational state issue
- probable real defect

### Feature Requests

Examples:

- can we add this field
- can WhatsApp share look different
- can this screen show more info

These should be routed as product improvement requests, not operational bugs.

### Operational Requests

Examples:

- send this document
- fix this offer
- check this order
- rename this customer

These should be answered as operational handling requests and mapped to the
correct domain.

## Normalization Rule

When a WhatsApp message is short, ambiguous, or incomplete, normalize it into:

- user goal
- current blocker
- likely domain
- whether the user is asking how-to, why-not, or feature-request

## Likely Domains

### order or offer

If the message is about teklif, siparis, customer confirmation, or sending a
price/offer, the likely domain is order and offer flow.

### accounting or statement or receivable

If the message is about hesap ekstresi, borc, alacak, tahsilat, or balance
visibility, the likely domain is accounting.

### invoice or finance document

If the message is about fatura, e-fatura, e-arsiv, document numbering, or
financial document generation, the likely domain is finance document flow.

### inventory or warehouse or production

If the message is about stock, depo, production, availability, or item
movement, the likely domain is inventory and warehouse.

### marketplace or store integration

If the message is about Shopify, Trendyol, OpenCart, WooCommerce, or external
store sync, the likely domain is integration flow.

### AI parsing or automation behavior

If the message is about an incoming document, parsed order, automation result,
or unexpected system-generated action, the likely domain is workers and AI
automation behavior.

### WhatsApp sharing itself

If the message is about a share button, generated WhatsApp text, missing phone
target, or sending a link through WhatsApp, the likely domain is messaging and
share flow.

## Fast Triage Hints

- If the user says "why didn't it send", check first whether required contact
  data or document prerequisites are likely missing.
- If the user says "I can't find it", check whether the issue sounds like
  navigation, visibility, permissions, or workflow expectation.
- If the user says "this should happen automatically", check whether there is a
  worker, queue, or integration expectation.
- If the user sends a screenshot plus a short complaint, assume the user wants
  diagnosis first and a feature proposal only if the behavior is confirmed as
  expected but undesirable.

## Known WhatsApp-Related Flows

- Offers can be shared over WhatsApp.
- Accounting statements can be shared over WhatsApp.
- WhatsApp-related problems often come from missing customer identity or contact
  data, malformed share target, or misunderstanding of which record is being
  shared.

## Default Answering Style

- Be direct.
- Explain likely cause before proposing deep technical investigation.
- Prefer step-by-step guidance when the issue sounds operational.
- Distinguish clearly between:
  - expected behavior
  - likely setup/data issue
  - likely real bug

## When Code Lookup Is Actually Needed

Use repository inspection only if:

- the context does not explain the observed behavior
- the user claims a regression
- automation, parsing, or worker behavior seems inconsistent
- a real bug is more likely than user confusion

## Out of Scope

- GridBox HeadEnd
- GridBox MDM
- company utility/field communication systems

Mobitolya WhatsApp traffic must stay isolated from company project reasoning.
