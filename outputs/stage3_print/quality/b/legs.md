## b: filling the gap between the hind legs (pitch 0.4, iso 0.5, 25000 faces, taubin x10)

`hull` stands the bear in the convex hull of the leg band (from where the slices split into two legs up to the crotch + 4 mm, sunk 4 mm into a slab if there is one); `between` clips that hull to the feet's footprint so only the gap itself is filled. Support % of the printed piece.

| variant | solid | legs from z | crotch z | block to z | sunk | added cm³ | tris | support % | saved | worst band |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | yes | - | - | - | - | 0.0 | 23,120 | 2.71 | 0.00 | z 0-27 (650 mm²) |
| hull | yes | 13 | 30 | 34 | 4 | 34.0 | 23,064 | 1.48 | 1.22 | z 27-53 (222 mm²) |
| between | yes | 13 | 30 | 34 | 4 | 27.8 | 22,348 | 1.38 | 1.32 | z 27-53 (219 mm²) |
