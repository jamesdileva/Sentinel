Pi-hole is not Project Sentinel's purpose.

It's one of the infrastructure services Sentinel hosts.

I'd organize it like this:

Project Sentinel

├── Infrastructure
│   ├── Pi-hole / AdGuard Home
│   ├── Ollama
│   ├── Local API
│   ├── Scheduler
│   ├── Background Workers
│   └── Optional VPN (future)
│
├── Project Intelligence
│   ├── Repository Indexing
│   ├── Knowledge Database
│   ├── RAG
│   ├── Git Intelligence
│   ├── Build Intelligence
│   └── Portfolio Intelligence
│
├── Automation
│   ├── Build Runner
│   ├── Feature Test Runner
│   ├── Security Scanner
│   ├── Documentation Generator
│   └── Screenshot Generator
│
└── World
    ├── Simulation Engine
    ├── Event Timeline
    ├── Visualization
    └── God Controls

I would actually add a dedicated section to the Master Architecture called:

Infrastructure Services

Explain that Sentinel's laptop is also a home development server.

Initial services:

Pi-hole or AdGuard Home for network-wide ad and tracker blocking.
Ollama for local AI inference shared by every device on the network.
Local API for all Sentinel modules and future desktop/mobile apps.
Background scheduler for indexing, builds, nightly scans, and maintenance jobs.

The key is that everything else can build on this foundation.

For example:

Desktop

↓

Ask AI

↓

Sentinel Local API

↓

Ollama

or

Git Push

↓

Sentinel

↓

Build

↓

Test

↓

Update Knowledge

or

Phone

↓

Open Dashboard

↓

Project Health

All of those are possible because the laptop is already acting as a server.

One thing I would actually change in the architecture

After all our discussions, I no longer think of Sentinel as just Project Intelligence.

I think its identity is:

A Home Development Server with Project Intelligence as its flagship capability.

That subtle wording matters.

It explains why Pi-hole belongs.

It explains why Ollama belongs.

It explains why the Local API belongs.

It explains why the World Simulator belongs.

They're not random add-ons—they're services running on the same always-on machine. The flagship feature remains Project Intelligence, but the server itself becomes genuinely useful even when it's not indexing code or answering questions. That's the cohesive vision I think we've arrived at.


SEPARATELY have airadio project that uses ollama how do we make that communicate with the ollama on my laptop rather than being served by my main PC and using my GPU/CPU