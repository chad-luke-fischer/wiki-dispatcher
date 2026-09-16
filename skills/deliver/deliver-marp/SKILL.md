---
name: deliver-marp
description: "Produce a Marp slide deck (markdown) from vault context — use when the ask mentions slides, a deck, a presentation, or a talk."
metadata:
  wd:
    family: deliver
    state: active
    pinned: false
    version: 0.1.0
---
# deliver-marp

## Shape
```
---
marp: true
theme: default
paginate: true
---
# Title
<!-- speaker notes -->
---
## One idea per slide
- ≤5 bullets, ≤12 words each
---
## Sources
- [[note]] · [[note]]
```

## Rules
- 6-12 slides. Title → context → 3-6 idea slides → contradictions/open questions → sources.
- Each idea slide's notes name the vault note it came from.
- Diagrams: a ```mermaid fence on its own slide (`vault_mermaid` for link structure).
- No external images; the vault is the only source.
