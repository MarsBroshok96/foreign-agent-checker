# Context Profile Enrichment Skill

Codex-compatible skill file: [context-profile-enrichment/SKILL.md](context-profile-enrichment/SKILL.md).

## Purpose

Build local auxiliary context profiles for weak-candidate disambiguation.

Context profiles are not a source of truth for foreign-agent status. The
official Ministry of Justice registry remains the only source of truth.

## Inputs

- official registry snapshot: `data/registry/minjust_registry_latest.xlsx`
- existing profiles: `data/context/context_profiles.example.json` or
  `data/context/context_profiles.json`

## Output

- enriched profiles: `data/context/context_profiles.json`

## Recommended Workflow

1. Run profile coverage:

   ```bash
   poetry run python scripts/profile_coverage.py data/registry/minjust_registry_latest.xlsx data/context/context_profiles.json --limit 50
   ```

2. Pick a small batch of missing entries.

3. Research each entity manually or with explicitly requested developer/Codex
   web research. This is an offline enrichment workflow, not runtime agent
   behavior.

4. Fill profiles using neutral, source-backed descriptions.

5. Save the batch to a temporary JSON file:

   ```text
   data/context/context_profiles.batch.json
   ```

6. Merge:

   ```bash
   poetry run python scripts/merge_context_profiles.py data/context/context_profiles.json data/context/context_profiles.batch.json data/context/context_profiles.json
   ```

7. Validate:

   ```bash
   poetry run python scripts/validate_context_profiles.py data/context/context_profiles.json --registry-xlsx data/registry/minjust_registry_latest.xlsx
   ```

8. Review the git diff before using enriched profiles.

## Research Guidelines

- Prefer official/source-like pages and stable references.
- Keep descriptions short.
- Do not include unsupported claims.
- Do not include sensitive speculation.
- Do not state or infer legal status from context profile.
- Use `registry_id` and exact `entity_name` from the registry.
- Include sources as URLs when available.
- If uncertain, set `confidence="low"` and keep notes cautious.

## Profile Quality Guidelines

For a person:

- `descriptors`: profession/activity markers such as journalist, blogger,
  politician, artist, activist, lawyer, or economist.
- `common_mentions`: common public name forms.
- `disambiguation_hints`: context clues that support a match.
- `negative_context_hints`: common false-positive contexts.

For media, project, or organization:

- `descriptors`: media, project, foundation, movement, NGO, company, publication.
- `known_projects`: public names and related projects.
- `known_domains`: own domains, not generic social platform hosts only.
- `common_mentions`: short and full names.
- `negative_context_hints`: common word usage where the name is ambiguous.

Do not attempt to enrich all registry profiles in one manual Codex run. Work in
batches. A batch size of 20-50 profiles is more realistic. Runtime agent
behavior must remain offline.
