# Changelog

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
