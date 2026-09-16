---
name: deliver-canvas
description: "Produce an Obsidian JSON Canvas (.canvas) that lays out real vault notes as file nodes with synthesis text nodes and labelled edges — use when the ask wants a board, canvas, map, or spatial view."
metadata:
  wd:
    family: deliver
    state: active
    pinned: false
    version: 0.1.0
---
# deliver-canvas

## Shape (JSON Canvas 1.0)
```json
{"nodes":[
  {"id":"n1","type":"file","file":"wiki/concepts/Skill Evolution.md","x":0,"y":0,"width":400,"height":300},
  {"id":"t1","type":"text","text":"# Synthesis\n…","x":500,"y":0,"width":400,"height":200}],
 "edges":[{"id":"e1","fromNode":"n1","toNode":"t1","label":"motivates"}]}
```

## Steps
1. Gather with `branch-extract` (depth 1-2). Use *every* included path as a `file` node (paths are vault-relative, exactly as the catalog printed them).
2. Add 1-3 `text` nodes for synthesis / open questions.
3. Layout: seed at (0,0); hop-1 nodes in a ring at radius ~600; hop-2 at ~1100. Width 400, height 300. Avoid overlaps by spreading angles.
4. Edges: one per real link with the link kind as label. Output ONLY the JSON in a ```json fence.
