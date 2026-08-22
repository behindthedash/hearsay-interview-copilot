## Purpose

Defines the Interview Copilot application session that attaches to Hearsay, manages consumer resources, and composes interviewer-turn detection, knowledge retrieval, and cue presentation.

## Requirements

### Requirement: The application establishes a supported Hearsay host session
The application SHALL use only Hearsay's documented public host/session API to request or attach to a live low-latency session and register transcript handlers.

#### Scenario: Copilot starts successfully
- **WHEN** required Hearsay host capabilities and consumer resources are available
- **THEN** the application registers its handlers and enters an explicit listening/ready state

### Requirement: Consumer preflight validates consumer-owned resources
Before declaring itself ready, the application SHALL validate configured knowledge sources/provider, required local models, and presentation resources. Consumer preflight SHALL NOT inspect Hearsay private implementation state.

### Requirement: Remote speech drives cue retrieval
Finalized `Remote` events SHALL flow through coherent-turn assembly and retrieval. `Local` speech SHALL NOT automatically launch interviewer-query retrieval.

### Requirement: New interviewer intent supersedes stale work
A newer query generation SHALL prevent older retrieval/cue completions from becoming current.

### Requirement: Privacy-sensitive host configuration is requested explicitly
The application SHALL request Hearsay live-only/no-save behavior by default for interview use when the host supports it; persisting a transcript requires an explicit user choice in the host/session contract.

### Requirement: Consumer failure does not terminate the host
Knowledge, retrieval, or overlay failure SHALL surface degraded consumer state and SHALL NOT directly stop an otherwise healthy Hearsay session.

### Requirement: Manual retrieval is available
The user SHALL have an explicit action to retrieve against the currently buffered Remote interviewer turn.

### Requirement: Teardown is complete
Stopping the consumer SHALL unregister transcript handlers, clear transient query/cue state, close provider resources, and leave Hearsay host lifecycle decisions to the documented session ownership contract.
