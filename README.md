# mindgraph

[![PyPI](https://img.shields.io/pypi/v/mindgraph-sdk)](https://pypi.org/project/mindgraph-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Python client for the [MindGraph Cloud](https://mindgraph.cloud) API — a structured semantic memory graph for AI agents.

## Install

```bash
pip install mindgraph-sdk
```

## Quick Start

```python
from mindgraph import MindGraph

with MindGraph("https://api.mindgraph.cloud", api_key="mg_...") as graph:
    # Add a node
    node = graph.add_node(
        label="User prefers dark mode",
        node_type="Preference",
    )

    # Search
    results = graph.search("what does the user prefer?")

    # Connect knowledge
    graph.add_link(
        from_uid=node["uid"],
        to_uid="user_abc",
        edge_type="BelongsTo",
    )
```

## API Reference

### Constructor

```python
MindGraph(base_url, *, api_key=None, jwt=None, timeout=30.0)
```

Supports context manager protocol (`with` statement) for automatic cleanup.

### Reality Layer

| Method | Description |
|--------|-------------|
| `capture(**kwargs)` | Capture a source, snippet, or observation |
| `entity(**kwargs)` | Create, alias, resolve, or merge entities |
| `find_or_create_entity(label, entity_type?, agent_id?)` | Convenience: create or find an entity by label (generic fallback) |
| `find_or_create_person(label, props?, agent_id?)` | Find or create a Person entity |
| `find_or_create_organization(label, props?, agent_id?)` | Find or create an Organization entity |
| `find_or_create_nation(label, props?, agent_id?)` | Find or create a Nation entity |
| `find_or_create_event(label, props?, agent_id?)` | Find or create an Event entity |
| `find_or_create_place(label, props?, agent_id?)` | Find or create a Place entity |
| `find_or_create_concept(label, props?, agent_id?)` | Find or create a Concept entity |
| `add_claim(label, props?, agent_id?)` | Add a Claim node |
| `add_evidence(label, props?, agent_id?)` | Add an Evidence node |
| `add_observation(label, props?, agent_id?)` | Add an Observation node |

**Typed entity example:**

```python
person = graph.find_or_create_person("Marie Curie", props={"nationality": "Polish"})
org = graph.find_or_create_organization("CERN", props={"org_type": "intergovernmental"})
concept = graph.find_or_create_concept("Nuclear Physics")

# find_or_create_entity() still works as a generic fallback for any entity type
entity = graph.find_or_create_entity("Some Entity")
```

### Epistemic Layer

| Method | Description |
|--------|-------------|
| `argue(**kwargs)` | Construct a full argument: claim + evidence + warrant + edges |
| `inquire(**kwargs)` | Add hypothesis, theory, paradigm, anomaly, assumption, or question |
| `structure(**kwargs)` | Add concept, pattern, mechanism, model, analogy, theorem, etc. |

### Intent Layer

| Method | Description |
|--------|-------------|
| `commit(**kwargs)` | Create a goal, project, or milestone |
| `deliberate(**kwargs)` | Open decisions, add options/constraints, resolve decisions |

### Action Layer

| Method | Description |
|--------|-------------|
| `procedure(**kwargs)` | Build flows, add steps, affordances, and controls |
| `risk(**kwargs)` | Assess risk or retrieve existing assessments |

### Memory Layer

| Method | Description |
|--------|-------------|
| `session(**kwargs)` | Open a session, record traces, or close a session |
| `journal(label, props?, *, summary?, session_uid?, ...)` | Record a journal entry linked to an optional session |
| `distill(**kwargs)` | Create a summary that distills multiple source nodes |
| `memory_config(**kwargs)` | Set/get preferences and memory policies |

### Agent Layer

| Method | Description |
|--------|-------------|
| `plan(**kwargs)` | Create tasks, plans, plan steps, update status |
| `governance(**kwargs)` | Create policies, set safety budgets, request/resolve approvals |
| `execution(**kwargs)` | Track execution lifecycle and register agents |

### Synthesis (Projects)

Scope a corpus to a `Project` (via `commit(action="project", ...)` then link documents with `PartOfProject`), then mine cross-document signals and generate synthesis articles.

| Method | Description |
|--------|-------------|
| `signals(project_uid, *, signals?, target_types?)` | Mine cross-document structural signals for a project |
| `run_synthesis(project_uid)` | Spawn async synthesis job that turns top clusters into Article nodes; returns `{"job_id": ...}` |

```python
project = graph.commit(action="project", label="Q2 China strategy")
# ...link documents to the project via PartOfProject edges...
signals = graph.signals(project["uid"], signals="clustered_claim_hubs,dialectical_pairs")
job = graph.run_synthesis(project["uid"])
status = graph.get_job(job["job_id"])
```

### CRUD

| Method | Description |
|--------|-------------|
| `get_node(uid)` | Get a node by UID |
| `add_node(label, node_type?, props?, agent_id?)` | Add a generic node |
| `update_node(uid, **kwargs)` | Update node fields |
| `delete_node(uid)` | Tombstone a node and all connected edges |
| `add_link(from_uid, to_uid, edge_type, agent_id?)` | Add a typed edge |
| `get_edges(from_uid?, to_uid?)` | Get edges by source or target |

### Search

| Method | Description |
|--------|-------------|
| `search(query, node_type?, layer?, limit?)` | Full-text search |
| `hybrid_search(query, k?, node_types?, layer?)` | BM25 + vector search with rank fusion |

### Traversal

| Method | Description |
|--------|-------------|
| `reasoning_chain(uid, max_depth=5)` | Follow epistemic edges from a node |
| `neighborhood(uid, max_depth=1)` | Get all nodes within N hops |

### Ingestion & Retrieval

| Method | Description |
|--------|-------------|
| `ingest_chunk(content, *, chunk_type?, ...)` | Ingest a single text chunk (sync): stores, embeds, and runs LLM extraction |
| `ingest_document(content, *, title?, ...)` | Ingest a full document (async): chunks text, returns job ID |
| `ingest_session(content, *, session_uid?, ...)` | Ingest a session transcript (async): links to session, returns job ID |
| `retrieve_context(query, *, k?, depth?, ...)` | Retrieve semantically matched chunks + connected graph nodes/edges |
| `get_job(job_id)` | Get async job status and progress |
| `clear_graph()` | Clear all graph data |

### Lifecycle Shortcuts

| Method | Description |
|--------|-------------|
| `tombstone(uid, reason?, agent_id?)` | Soft-delete a node |
| `restore(uid, agent_id?)` | Restore a tombstoned node |

### Cross-cutting

| Method | Description |
|--------|-------------|
| `retrieve(**kwargs)` | Unified retrieval: text search, active goals, open questions, weak claims |
| `traverse(**kwargs)` | Graph traversal: chain, neighborhood, path, or subgraph |
| `evolve(**kwargs)` | Lifecycle mutations: update, tombstone, restore, decay, history |

### Health & Stats

| Method | Description |
|--------|-------------|
| `health()` | Health check |
| `stats()` | Graph-wide statistics |

### Management (Cloud only)

| Method | Description |
|--------|-------------|
| `signup(email, password)` | Create a new account |
| `login(email, password)` | Login and receive JWT |
| `create_api_key(name?)` | Create an API key |
| `list_api_keys()` | List all API keys |
| `revoke_api_key(key_id)` | Revoke an API key |
| `get_usage()` | Get usage statistics |

## Examples

See [`examples/`](examples/) for runnable demos, including a [research continuity](examples/research_continuity.py) scenario showing cross-session memory retrieval.

## Error Handling

All methods raise `MindGraphError` on HTTP errors:

```python
from mindgraph import MindGraphError

try:
    graph.get_node("nonexistent")
except MindGraphError as e:
    print(e.status, e.body)
```

## License

MIT
