## Why

The local index should not hard-code storage semantics that make an optional pgvector backend a later rewrite.

## What Changes

- Define a provider-neutral `KnowledgeStore` contract.
- Move local persistence/query behind the contract.
- Require explicit collection/scope and embedding compatibility.
- Define atomic document replacement and health/stats semantics.

## Capabilities

### Modified Capabilities
- `knowledge-store-provider`
- `local-knowledge-index`
