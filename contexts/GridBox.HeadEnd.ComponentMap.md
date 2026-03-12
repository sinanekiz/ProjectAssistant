# GridBox HeadEnd Component Map

## Purpose

This file gives a practical map of the major HeadEnd solution areas so incoming
questions can be routed to the right subsystem before code lookup.

## Main Solution Areas

### API and Web Entry Points

Likely user-facing or integration-facing entry points:

- `GridBox.HeadEnd.Api`
- `GridBox.HeadEnd.Web`
- `GridBox.HeadEnd.Web.Poseidon`
- `gridbox.headend.newweb`
- `GridBox.HeadEnd.WebApp`
- `GridBox.Headend.WebNew`

Use these contexts when the question is about exposed endpoints, user actions,
or administrative interface behavior.

### Application and Core Logic

Main business and orchestration layers:

- `GridBox.HeadEnd.Application`
- `GridBox.HeadEnd.Core`
- `GridBox.HeadEnd.Domain`
- `GridBox.HeadEnd.Workflow`
- `GridBox.HeadEnd.Service`
- `GridBox.HeadEnd.ServiceBase`

Use these contexts when the issue is about process flow, orchestration, state
transition, or domain behavior.

### Consumers, Workers, and Background Processing

Asynchronous and queue-driven runtime parts:

- `GridBox.HeadEnd.Consumers`
- `GridBox.HeadEnd.Workers`
- `GridBox.HeadEnd.Workflow`
- `GridBox.Headend.Workflows.Test`

Use these contexts when the complaint is about delayed processing, stale data,
queue backlog, or background actions not happening.

### Parsing and Protocol Handling

Communication interpretation layer:

- `GridBox.HeadEnd.Parser`
- `GridBox.Protocols`
- `GridBox.Protocols.Dlms`

Use these contexts when raw device communication exists but values or meanings
look wrong.

### Messaging and Queue Infrastructure

Transport and messaging support:

- `GridBox.HeadEnd.RabbitMq.Client`
- `GridBox.HeadEnd.RabbitMq.Server`
- `GridBox.HeadEnd.Consumers`

Use these contexts when the issue sounds like message movement, queue backlog,
or asynchronous dispatch failure.

### Data Access and Persistence

Persistence and external storage layers:

- `GridBox.HeadEnd.MongoDb`
- `GridBox.HeadEnd.Application.MongoDb`
- `GridBox.HeadEnd.Infrastucture`
- `GridBox.HeadEnd.ExternalDataAccess`
- `GridBox.HeadEnd.Cache`
- `GridBox.HeadEnd.GCache`
- `GridBox.HeadEnd.InMemory`
- `GridBox.HeadEnd.InMemory.Redis`

Use these contexts when a problem sounds like state visibility, persistence,
cache inconsistency, or data-access path confusion.

## Routing Rule

If a question clearly maps to one of these component families, answer from that
component context first. Only open code when the component family is known but
behavior still cannot be explained.
