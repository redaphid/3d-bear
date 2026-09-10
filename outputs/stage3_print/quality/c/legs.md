## c: filling the gap between the hind legs (pitch 0.4, iso 0.5, 25000 faces, taubin x10)

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,632 | 5.31 | 0.00 | z 0-27 (859 mm²) |
| hull | yes | 0 | 24 | 28 | 0 | 29.7 | 24,072 | 3.32 | 1.98 | z 80-107 (329 mm²) |
| between | yes | 0 | 24 | 28 | 0 | 23.0 | 24,752 | 3.94 | 1.37 | z 0-27 (394 mm²) |
