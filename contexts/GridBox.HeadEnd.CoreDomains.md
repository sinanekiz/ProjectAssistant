# GridBox.HeadEnd Core Domains

## Main Domains

From repository structure and entry points, HeadEnd appears to include:

- device and meter communication
- protocol handling and parsing
- listener and socket behavior
- queue-based processing
- command dispatch to field devices
- communication workers and service hosts
- data ingestion before downstream consumption

## Common Technical Concepts

High-signal HeadEnd concepts include:

- meter
- device
- protocol
- parser
- listener
- communication
- command
- queue
- RabbitMQ
- MongoDB
- MQTT
- TCP
- UDP
- timeout
- packet
- OBIS

## Typical HeadEnd Problems

- field data not arriving
- parser/protocol mismatches
- queue backlog or stuck workers
- listener not receiving traffic
- command send/receive failures
- connection instability to devices
