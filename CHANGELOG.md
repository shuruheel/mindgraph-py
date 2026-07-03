# Changelog

## 0.9.1 (2026-07-03)

### Docs

- `traverse()` docstring documents the `path_cost` / `path_confidence` fields on
  traversal steps (server ≥ mindgraph 1.6.0); responses are untyped dicts, so the
  fields flow through without a code change.

## 0.9.0 (2026-06-29)

### Added

- `ingest_document()` gains optional `page_offsets`, `page_count`, `mime_type`, and
  `force_reingest`. `page_offsets` entries are `{"page", "char_start"}` where
  `char_start` is a UTF-8 **byte** offset into `content`. Identical content reuses the
  existing Document (response `deduplicated`). Server ≥ 1.5.0.
- `retrieve_context()` responses: Claim/graph nodes may carry `source_chunks`
  (citation provenance: chunk offsets, page range, matched quote, anchor selector)
  and `believed_by` (per-agent assertion stance: `agent_uid`, `agent_label`,
  `confidence`). Documented in the method docstring.
- `backfill_anchors()` — start the `/backfill/anchors` job (populate
  `ExtractedFrom.location` selectors for pre-existing edges).

## 0.8.0 (2026-06-17)

### Added

- `list_ontology_tools()` — the generated read-tool manifest
  (`GET /v1/ontology/tools`): per active object type, descriptors for
  `search_<objs>` / `get_<obj>` / `summarize_<obj>` that an MCP server (or your
  own agent loop) renders into tools. `summarize_<obj>` returns the object —
  whether mapped from a connected SQL database or extracted from documents —
  plus its cognitive context. Parity with the TypeScript SDK.
- `backing` kwarg on ontology object-type creation — bind a type to an external
  SQL source (Layer 7 semantic contract). Connection management itself stays in
  the dashboard.

## 0.7.0 (2026-06-14)

### Added

- `preferences(query=None, k=10, limit=None, offset=None)` — retrieve the
  user's stated/learned preferences (server ≥ 1.4.0). With a *query*,
  topic-relevant preferences via the semantic leg; without one, all
  preferences by salience. Returns a list of search results
  (`{"node": ..., "score": ...}`). For advice/recommendation requests.

(Changelog note: 0.5.0–0.6.0 were published without changelog entries; this
file resumes at 0.7.0.)

## 0.4.1 (2026-04-16)

### Docs

- README: correct `add_claim` / `add_evidence` / `add_observation` signatures and `find_or_create_entity` parameter name to match `mindgraph/client.py`.
- README: remove Management (Cloud only) section — those methods were never part of the SDK. Account sign-up, login, and API key management live in the [MindGraph dashboard](https://mindgraph.cloud/dashboard).

No code changes in this release.

## 0.4.0 (2026-04-16)

### Synthesis (Projects)

Scoped-corpus synthesis: mine cross-document signals for a `Project` and turn top idea clusters into Article nodes via a background job.

- `signals(project_uid, *, signals=None, target_types=None)` — `GET /synthesis/signals/{project_uid}`. Returns entity bridges, claim hubs, ranked/clustered claim hubs, theory support gaps, concept clusters, analogy candidates, and dialectical pairs.
- `run_synthesis(project_uid)` — `POST /synthesis/run/{project_uid}`. Spawns a background synthesis job and returns `{"job_id": ...}`; poll with `get_job()`.

## 0.2.0 (2026-03-30)

### New Entity Types

The Reality layer now has first-class node types instead of a single generic `Entity`:

- **Person** — Named individuals (`find_or_create_person`)
- **Organization** — Companies, nonprofits, government bodies (`find_or_create_organization`)
- **Nation** — Countries and sovereign states (`find_or_create_nation`)
- **Event** — Named occurrences (`find_or_create_event`)
- **Place** — Geographic locations (`find_or_create_place`)
- **Concept** — Topics, subjects, defined terms (`find_or_create_concept`)
- **Entity** — Retained as fallback for technology, product, and other types

### New Convenience Methods

- `find_or_create_person(label, props?, agent_id?)`
- `find_or_create_organization(label, props?, agent_id?)`
- `find_or_create_nation(label, props?, agent_id?)`
- `find_or_create_event(label, props?, agent_id?)`
- `find_or_create_place(label, props?, agent_id?)`
- `find_or_create_concept(label, props?, agent_id?)`
- `add_claim(label, content, confidence?, agent_id?)`
- `add_evidence(label, description, agent_id?)`
- `add_observation(label, description, agent_id?)`

### New Edge Types (18)

**Structural:** MEMBER_OF, LEADER_OF, FOUNDED_BY, BASED_IN, CITIZEN_OF, LOCATED_IN, OCCURRED_AT, PARTICIPATED_IN

**Stance:** ALLIED_WITH, RIVAL_OF, REPORTS_TO, ENDORSES, CRITICIZES

**Concept/Influence:** RELATED_TO, EXPERT_IN, OPERATES_IN, STRENGTHENS, CHALLENGES

### Breaking Changes

- `find_or_create_entity` with `entity_type="person"` now returns `node_type: "Person"` instead of `"Entity"`. Code that filters on `node_type == "Entity"` for people/organizations should update.
- `find_or_create_entity` still works and is backward-compatible — it routes to the correct type internally.

## 0.1.5 and earlier

Initial release with core CRUD, cognitive endpoints, entity resolution, decision management, and journal support.
