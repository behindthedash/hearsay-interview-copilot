# Hearsay Interview Copilot

A local-first interview assistance application built on Hearsay's supported transcript/session host API.

This repository owns interviewer question detection, knowledge retrieval, cue composition, interview overlays, and the speech-following teleprompter. Hearsay remains a separate transcription host dependency.

## Local knowledge index

The first implemented capability is a manifest-driven local index over user-owned Markdown, text, or JSON documents. Real career/interview material stays outside this repository.

Example `corpus.json`:

```json
{
  "documents": [
    {
      "path": "projects/project-alpha.md",
      "title": "Project Alpha",
      "project": "project-alpha",
      "experience_status": "implemented",
      "topics": ["data-platform"],
      "skills": ["Snowflake", "dbt"]
    }
  ]
}
```

Supported `experience_status` values are `implemented`, `prototype`, `design`, and `hypothetical`. The field is required so downstream cue logic cannot silently present planned material as completed work.

For development/tests:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

For the production local embedding adapter:

```bash
python -m pip install -e ".[embeddings]"
```

`FastEmbedEmbedding(local_files_only=True)` can be used after the selected model has already been cached.
