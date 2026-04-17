# Ceramic Solutions Studio OpenAlex Bridge

OpenAlex-powered search bridge for an Arabic ceramic manufacturing assistant.

This public repository shares the OpenAlex integration layer, search expansion,
result reranking, live suggestions, and short article summaries used to enrich
ceramic defect diagnosis.

## What is included

- `openalex_ceramic_bridge.py`
  OpenAlex search logic and Tkinter bridge layer.
- `CeramicSolutionsStudio_OpenAlex.py`
  Small launcher entry point.
- `openalex_config.example.json`
  Optional config template for OpenAlex email or API key.

## What is intentionally not included

This public repository does not include:

- packaged `.exe` builds
- extracted runtime files from the original desktop application
- local build output

That keeps the public repo lightweight and avoids publishing bundled binaries or
runtime artifacts that are better kept in a private archive.

## Main features

- hybrid OpenAlex search:
  - exact search
  - boolean expansion
  - semantic search
  - related works expansion
- Arabic and English query expansion for ceramic defects
- live search suggestions while typing
- ceramic-specific reranking to reduce noisy papers
- short article summaries to save operator time
- practical solution bullets with confidence indicators

## Typical use

This bridge is designed to sit beside an existing Ceramic Solutions Studio
runtime, or to be adapted into another Python desktop assistant.

If you already have the original runtime locally:

1. Place these files next to the original extracted runtime folder.
2. Optionally copy `openalex_config.example.json` to `openalex_config.json`.
3. Run:

```powershell
python .\CeramicSolutionsStudio_OpenAlex.py
```

## Notes

- The code uses only Python standard library modules for the OpenAlex requests.
- The bridge expects the original app runtime structure if used as-is.
- If you are building your own interface, you can reuse the OpenAlex search and
  summarization logic directly from `openalex_ceramic_bridge.py`.

## License

Released under the MIT License so others can study, reuse, and improve it.
