# Context System

This folder is the durable knowledge base for ProjectAssistant.

The operating rule is:

1. Answer from context first.
2. Only inspect repository code when a message may describe a real defect,
   uncertain runtime behavior, a regression, or a claim that must be verified.
3. Keep personal and company product families strictly separated.

## Current Product Families

- `GridBox.HeadEnd` - company product context
- `Mobitolya` - personal startup context

## Working Model

Each product family should have:

- one root index file
- multiple sub-context files by domain
- explicit ownership and out-of-scope notes
- routing rules for incoming support and feature messages
- answer patterns for repeated support traffic
- source notes that explain when documentation outranks code lookup

## Code Lookup Policy

Default behavior:

- use context files to answer support, how-to, routing, and ownership questions
- use repository code only for:
  - suspected bugs
  - uncertain behavior
  - implementation confirmation
  - missing or stale context

## Source Priority Rule

When enough context exists, prefer this order:

1. product-family index and sub-context files in this folder
2. known product documentation and exported documents
3. repository-side operational notes and docs
4. repository code, only if uncertainty remains

The goal is for the assistant to solve most message traffic without reading code on
most turns.
