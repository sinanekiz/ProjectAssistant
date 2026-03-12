# GridBox.HeadEnd Context

## What It Is

`GridBox.HeadEnd` is the field communication side of the GridBox product.
Its job is to communicate safely and reliably with very large fleets of field
devices and meters, collect data from the field, process protocol-level traffic,
and move that data into the rest of the platform.

## Business Boundary

HeadEnd scope:

- Communicating with meters and field devices
- Managing protocol-level connectivity and listeners
- Receiving field data securely and reliably
- Dispatching commands toward field devices
- Queueing, routing, and background processing around field communication
- Moving collected data into downstream systems

HeadEnd is the system that brings the data in from the field side.

## Explicitly Out Of Scope

`MDM` is not part of Sinan's scope.

MDM scope is downstream of HeadEnd and is responsible for things such as:

- Visualizing and processing collected data
- User-facing data views
- Analysis and reporting
- Billing integrations and downstream business flows

If a message is mainly about post-ingestion analytics, reporting, billing, or
end-user data presentation, it likely belongs to the MDM team rather than the
HeadEnd team.

## Main Repository Root

Repository family root:

- `C:\Users\Sinan\source\repos\HayenTechnology`

Main solution:

- `C:\Users\Sinan\source\repos\HayenTechnology\GridBox.HeadEnd\GridBox.HeadEnd.sln`

## Main Projects

Core HeadEnd projects in the main solution include:

- `GridBox.HeadEnd.Api`
- `GridBox.HeadEnd.Application`
- `GridBox.HeadEnd.Application.MongoDb`
- `GridBox.HeadEnd.Cache`
- `GridBox.HeadEnd.Consumers`
- `GridBox.HeadEnd.Core`
- `GridBox.HeadEnd.Domain`
- `GridBox.HeadEnd.ExternalDataAccess`
- `GridBox.HeadEnd.InMemory`
- `GridBox.HeadEnd.InMemory.Redis`
- `GridBox.HeadEnd.MongoDb`
- `GridBox.HeadEnd.Parser`
- `GridBox.HeadEnd.RabbitMq.Server`
- `GridBox.HeadEnd.Service`
- `GridBox.HeadEnd.ServiceBase`
- `GridBox.HeadEnd.Workers`
- `GridBox.HeadEnd.Workflow`

Related helper or dependency projects visible in the wider repository family:

- `GridBox.Protocols`
- `Anatolio.Core`
- `Anatolio.DynamicDataManagement`
- `Anatolio.Extentions`
- `Anatolio.GBot`
- `Anatolio.Parser`
- `Anatolio.RabbitMq`
- `Anatolio.Sockets`
- `Anatolio.Workflow`

## Runtime Shape

The solution is not a single simple web app. It looks like a multi-process
HeadEnd platform with:

- API host
- Windows/generic service host
- Background workers
- RabbitMQ-based communication
- MongoDB-backed persistence
- MQTT server setup
- Protocol listeners and parsers

This strongly suggests that many production issues will involve:

- listeners not receiving traffic
- queue backlogs
- parser/protocol mismatches
- command routing issues
- background worker behavior
- device communication stability

## Key Entry Points

Useful starting files for understanding the system:

- `C:\Users\Sinan\source\repos\HayenTechnology\GridBox.HeadEnd\GridBox.HeadEnd.Api\Program.cs`
- `C:\Users\Sinan\source\repos\HayenTechnology\GridBox.HeadEnd\GridBox.HeadEnd.Service\Program.cs`
- `C:\Users\Sinan\source\repos\HayenTechnology\GridBox.HeadEnd\GridBox.HeadEnd.Workers\CommunicationInformationWorker.cs`

Why these matter:

- `GridBox.HeadEnd.Api\Program.cs` shows the API composition root and service
  registrations.
- `GridBox.HeadEnd.Service\Program.cs` shows the service/hosted runtime model.
- `CommunicationInformationWorker.cs` shows the field communication orchestration
  path and is a strong signal for how device communication is coordinated.

## Architecture Signals Observed

From the current scan, the HeadEnd solution appears to use:

- ASP.NET Core API hosting
- Hosted background services
- RabbitMQ for messaging/queue workflows
- MongoDB repositories
- MQTT server initialization
- Protocol-specific listeners, including TCP and UDP cases

This means HeadEnd issue messages will often use keywords like:

- meter
- device
- communication
- listener
- sender
- queue
- rabbit
- parser
- protocol
- dlms
- tcp
- udp
- packet
- command
- timeout
- field data

## Practical Message Routing Rules

Messages likely owned by HeadEnd:

- device or meter communication problems
- field data not arriving
- parser/protocol errors
- queue/listener/worker issues
- command send/receive failures
- MQTT, RabbitMQ, TCP, UDP, DLMS, protocol concerns

Messages likely owned by MDM or another downstream team:

- dashboards, reporting, or analytics issues
- billing pipeline issues after data already arrived
- end-user presentation or visualization issues
- customer-facing data interpretation problems

Borderline case:

- If the complaint is data is missing, first determine whether the data failed
  before ingestion or after ingestion.
  Before ingestion points to HeadEnd.
  After ingestion points to MDM/downstream systems.

## Operational Interpretation

When triaging messages for Sinan:

- Prioritize issues that block or degrade field communication
- Treat device connectivity and protocol failures as high-signal HeadEnd topics
- Treat MDM-only work as out of scope unless the root cause appears to start in
  HeadEnd

## Notes For Future Expansion

The next useful context files to create would likely be:

- `GridBox.MDM.md`
- `GridBox.Protocols.md`
- a focused note for `Anatolio.*` helper libraries if they become a frequent
  source of operational questions
