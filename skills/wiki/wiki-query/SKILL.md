---
name: wiki-query
description: "Answer a question from the vault with citations, then offer to file the answer back as a synthesis page — the llm-wiki 'query' operation. Use for direct questions where the user wants an answer, not a document."
metadata:
  wd:
    family: wiki
    state: active
    pinned: false
    version: 0.1.0
---
# wiki-query

## Steps
1. `deliver-brief` contract → kind is usually `note` or `brief`.
2. `hub-find` if broad, else `branch-extract` from the best seed. Two seeds + `path-bridge` for two-topic questions.
3. Answer in ≤300 words with inline [[citations]]. Separate *what the vault says* from *what I infer*.
4. If the answer required synthesis across ≥3 notes, end with: "Worth filing as a synthesis page? (`file-back`)". Do not file it yourself.

## Rules
- If the vault does not contain the answer, say so in the first line. Do not fill from general knowledge without labelling it "outside the vault".
