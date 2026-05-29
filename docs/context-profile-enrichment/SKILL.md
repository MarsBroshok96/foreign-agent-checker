---
name: context-profile-enrichment
description: Use this skill to enrich local FA checker context profiles for weak-candidate disambiguation, validate them against a Ministry of Justice registry XLSX snapshot, merge reviewed batches, and keep runtime agent behavior offline and bounded.
---

# Context Profile Enrichment

Use this workflow when asked to add or review local auxiliary context profiles for
the FA checker agent.

## Boundaries

- The official Ministry of Justice registry XLSX is the only source of
  foreign-agent status.
- Context profiles are auxiliary disambiguation data only.
- Do not add legal conclusions, status claims, speculation, or unsupported facts.
- The runtime agent must remain offline. Web research is allowed only during this
  offline enrichment workflow when the user asks for it.
- Prefer small batches. A batch of 20-50 profiles is the practical upper bound.

## Files

- Registry snapshot: `data/registry/minjust_registry_latest.xlsx`
- Existing profiles: `data/context/context_profiles.json` or
  `data/context/context_profiles.example.json`
- Batch template: `data/context/context_profiles.batch.template.json`
- Temporary batch: `data/context/context_profiles.batch.json`
- Main guide: `docs/context_profile_enrichment_skill.md`

## Workflow

1. Check coverage:

   ```bash
   poetry run python scripts/profile_coverage.py data/registry/minjust_registry_latest.xlsx data/context/context_profiles.json --limit 50
   ```

2. Select a small batch from the missing entries. Use the exact `registry_id` and
   `entity_name` from the XLSX output.

3. Research only enough to disambiguate the entity. Prefer official, primary, or
   stable source-like pages. Keep descriptions neutral and short.

4. Write the batch using this shape:

   ```json
   {
     "profiles": [
       {
         "registry_id": "560",
         "entity_name": "Exact registry name",
         "entity_type": "person",
         "role_or_category": "journalist",
         "short_description": "Neutral one-sentence description.",
         "descriptors": ["journalist"],
         "known_projects": [],
         "known_domains": [],
         "common_mentions": [],
         "disambiguation_hints": [],
         "negative_context_hints": [],
         "primary_language": "ru",
         "confidence": "medium",
         "notes": "Auxiliary context for disambiguation only.",
         "sources": []
       }
     ]
   }
   ```

5. Merge into the target profile file:

   ```bash
   poetry run python scripts/merge_context_profiles.py data/context/context_profiles.json data/context/context_profiles.batch.json data/context/context_profiles.json
   ```

6. Validate structure and registry consistency:

   ```bash
   poetry run python scripts/validate_context_profiles.py data/context/context_profiles.json --registry-xlsx data/registry/minjust_registry_latest.xlsx
   ```

7. Review the diff. Check that `registry_id` exists, `entity_name` exactly
   matches the registry, and all sources support only the auxiliary context.

## Quality Bar

- `short_description`: factual, neutral, one sentence.
- `descriptors`: profession/type markers useful for disambiguation.
- `common_mentions`: public mention forms, not invented aliases.
- `disambiguation_hints`: context that supports a same-entity decision.
- `negative_context_hints`: common false-positive contexts.
- `confidence`: one of `low`, `medium`, `high`; use `low` when unsure.
