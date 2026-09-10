## o: filling the gap between the hind legs (pitch 0.4, iso 0.5, 25000 faces, taubin x10)

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,690 | 6.33 | 0.00 | z 0-27 (1478 mm²) |
| hull | yes | 0 | 24 | 28 | 0 | 34.3 | 23,954 | 4.10 | 2.23 | z 53-80 (643 mm²) |
| between | yes | 0 | 24 | 28 | 0 | 27.3 | 24,670 | 4.59 | 1.74 | z 0-27 (810 mm²) |
