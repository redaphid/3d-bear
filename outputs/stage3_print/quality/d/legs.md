## d: filling the gap between the hind legs (pitch 0.4, iso 0.5, 25000 faces, taubin x10)

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,578 | 4.46 | 0.00 | z 27-53 (984 mm²) |
| hull | yes | 17 | 34 | 38 | 4 | 51.4 | 23,368 | 3.13 | 1.32 | z 80-107 (560 mm²) |
| between | yes | 17 | 34 | 38 | 4 | 39.4 | 24,202 | 3.08 | 1.38 | z 80-107 (560 mm²) |
