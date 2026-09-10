// tools/ui/layout.js — make a compiled bear workflow legible in the ComfyUI UI.
//
// Plain browser JS, no bundler. Load it into the ComfyUI page (publish.py prints
// a bootstrap that fetches it from /api/userdata/bear%2Flayout.js), import the
// compiled API JSON with `app.loadApiJson(api, name)`, then call
//
//     layoutBearGraph(app, compiled._meta, {labels: {c: "L34 bent heavy open"}})
//
// It (a) classifies every node by role from its type, (b) lays the graph out as
// one horizontal band per `_meta.items` entry (left-to-right by data flow) with
// any shared nodes in a left column, (c) colours nodes by role and drops a
// legend, (d) bypasses debug taps (mode 4) so they cost nothing until you flip
// them on, (e) fits the canvas to the result. Returns a report for the console.
(function (global) {
  'use strict';

  // ---- palette: title-bar colour (color) + body colour (bgcolor) per role ----
  var PALETTE = {
    loader: { color: '#1f3350', bgcolor: '#2c4a75', label: 'Loader (model / CLIP / VAE / LoRA)' },
    input:  { color: '#1d4650', bgcolor: '#2a6673', label: 'Input (LoadImage / asset)' },
    prompt: { color: '#1f4a2a', bgcolor: '#2e6b3d', label: 'Prompt (text, concat, encode)' },
    sample: { color: '#5a3410', bgcolor: '#8a4f1a', label: 'Sample (latent, sampler, steps/cfg)' },
    decode: { color: '#164a4a', bgcolor: '#1f6b6b', label: 'Decode (VAE to image)' },
    cutout: { color: '#5c5010', bgcolor: '#8a7a1c', label: 'Cutout (rembg)' },
    recon:  { color: '#4d1f4a', bgcolor: '#73306f', label: 'Recon (image to 3D mesh)' },
    tap:    { color: '#3a3a3a', bgcolor: '#555555', label: 'Tap (debug save; purple = bypassed)' },
    output: { color: '#5a1f1f', bgcolor: '#8a2e2e', label: 'Output (deliverable save)' },
    other:  { color: '#333333', bgcolor: '#4a4a4a', label: 'Other' }
  };
  var ROLE_ORDER = Object.keys(PALETTE);
  var BAND_COLORS = ['#3f5159', '#4b4159', '#59503f', '#3f5943', '#593f4a'];

  // Node ids survive app.loadApiJson unchanged but as strings; key every map by String(id).
  function K(id) { return String(id); }

  function titleH() { return global.LiteGraph ? global.LiteGraph.NODE_TITLE_HEIGHT : 30; }

  function isTap(node) {
    if (!/^(SaveImage|SaveGLB)$/.test(node.type)) return false;
    var w = (node.widgets || []).find(function (w) { return w.name === 'filename_prefix'; });
    return !!w && typeof w.value === 'string' && w.value.indexOf('debug/') === 0;
  }

  // Role from the node type alone. Primitives/switches are resolved afterwards
  // from what they feed (see resolveFeeders).
  function roleFromType(node) {
    var t = node.type || '';
    if (/^(SaveImage|SaveGLB)$/.test(t)) return isTap(node) ? 'tap' : 'output';
    if (/^(Preview|Save)/.test(t)) return 'output';
    if (/^Load(Image|Video|Audio)/.test(t)) return 'input';
    if (/Loader/.test(t)) return 'loader';
    if (/rembg|RemoveBackground|Remove Background/i.test(t)) return 'cutout';
    if (/^(CLIPVisionEncode|Hunyuan3D|VoxelToMesh|VAEDecodeHunyuan3D|EmptyLatentHunyuan3D)/.test(t) ||
        /Hunyuan3D|Trellis|Pixal|Mesh/i.test(t)) return 'recon';
    if (/^VAEDecode/.test(t) || /Decode$/.test(t)) return 'decode';
    if (/^(StringConcatenate|CLIPTextEncode|PrimitiveString|StringConstant)/.test(t) ||
        /TextEncode|String/.test(t)) return 'prompt';
    if (/^(KSampler|Empty.*Latent|ModelSampling|SamplerCustom|BasicScheduler|RandomNoise|KSamplerSelect|LatentUpscale)/.test(t) ||
        /Sampler|Scheduler|Latent|Guider|Noise/.test(t)) return 'sample';
    return null; // undecided: resolve from consumers
  }

  function getLink(graph, linkId) {
    return graph.links instanceof Map ? graph.links.get(linkId) : graph.links[linkId];
  }

  function predecessors(graph, node) {
    var out = [];
    (node.inputs || []).forEach(function (inp) {
      if (inp.link == null) return;
      var l = getLink(graph, inp.link);
      if (l) out.push(K(l.origin_id !== undefined ? l.origin_id : l[1]));
    });
    return out;
  }

  function successors(graph, node) {
    var out = [];
    (node.outputs || []).forEach(function (o) {
      (o.links || []).forEach(function (linkId) {
        var l = getLink(graph, linkId);
        if (l) out.push(K(l.target_id !== undefined ? l.target_id : l[3]));
      });
    });
    return out;
  }

  // Undecided nodes (PrimitiveInt, ComfySwitchNode, ...) take the majority role
  // of what they feed, walking through other undecided nodes.
  function resolveFeeders(graph, nodes, roles) {
    var byId = new Map(nodes.map(function (n) { return [K(n.id), n]; }));
    var seen = new Set();
    function roleOf(id) {
      if (roles.get(id)) return roles.get(id);
      if (seen.has(id)) return 'other';
      seen.add(id);
      var counts = {};
      successors(graph, byId.get(id) || {}).forEach(function (s) {
        var r = roleOf(s);
        counts[r] = (counts[r] || 0) + 1;
      });
      var best = 'other', bestN = 0;
      Object.keys(counts).forEach(function (r) { if (counts[r] > bestN) { best = r; bestN = counts[r]; } });
      roles.set(id, best);
      return best;
    }
    nodes.forEach(function (n) { roleOf(K(n.id)); });
  }

  // Layering: ASAP longest-path depth, then pull every non-sink up against its
  // consumers (ALAP) so loaders/primitives sit next to what uses them.
  function layer(graph, nodes) {
    var ids = new Set(nodes.map(function (n) { return K(n.id); }));
    var byId = new Map(nodes.map(function (n) { return [K(n.id), n]; }));
    var asap = new Map();
    function depth(id) {
      if (asap.has(id)) return asap.get(id);
      asap.set(id, 0); // cycle guard
      var d = 0;
      predecessors(graph, byId.get(id)).forEach(function (p) {
        if (ids.has(p)) d = Math.max(d, depth(p) + 1);
      });
      asap.set(id, d);
      return d;
    }
    nodes.forEach(function (n) { depth(K(n.id)); });
    var order = nodes.slice().sort(function (a, b) { return asap.get(K(b.id)) - asap.get(K(a.id)); });
    var alap = new Map();
    order.forEach(function (n) {
      var succ = successors(graph, n).filter(function (s) { return ids.has(s); });
      if (!succ.length) { alap.set(K(n.id), asap.get(K(n.id))); return; }
      alap.set(K(n.id), Math.min.apply(null, succ.map(function (s) { return alap.get(s); })) - 1);
    });
    return alap;
  }

  function nodeH(node) { return node.size[1] + titleH(); }
  function ensureSize(node) {
    try {
      var s = node.computeSize();
      node.size = [Math.max(node.size[0], s[0]), Math.max(node.size[1], s[1])];
    } catch (e) { /* keep loaded size */ }
  }

  // Lay one band out with its top-left at (x0, y0). Returns {w, h}. Nodes go
  // into columns by ALAP depth and stack vertically within a column, ordered by
  // the average row of their predecessors (barycenter) so wires run rightwards.
  function placeBand(graph, nodes, roles, x0, y0, o) {
    var T = titleH();
    var depths = layer(graph, nodes);
    var cols = new Map();
    nodes.forEach(function (n) {
      var d = depths.get(K(n.id));
      if (!cols.has(d)) cols.set(d, []);
      cols.get(d).push(n);
    });
    var rank = new Map();
    var x = x0, maxH = 0;
    var ordered = Array.from(cols.keys()).sort(function (a, b) { return a - b; });
    ordered.forEach(function (d) {
      var col = cols.get(d);
      var key = function (n) {
        var preds = predecessors(graph, n).filter(function (p) { return rank.has(p); });
        var bary = preds.length ? preds.reduce(function (s, p) { return s + rank.get(p); }, 0) / preds.length : 1e6;
        return [bary, ROLE_ORDER.indexOf(roles.get(K(n.id))), Number(n.id) || 0];
      };
      col.sort(function (a, b) {
        var ka = key(a), kb = key(b);
        for (var i = 0; i < 3; i++) if (ka[i] !== kb[i]) return ka[i] - kb[i];
        return 0;
      });
      var y = y0 + T, w = 0;
      col.forEach(function (n, i) {
        ensureSize(n);
        n.pos = [x, y];
        rank.set(K(n.id), i);
        y += nodeH(n) + o.rowGap;
        w = Math.max(w, n.size[0]);
      });
      maxH = Math.max(maxH, y - o.rowGap - y0);
      x += w + o.colGap;
    });
    return { w: x - o.colGap - x0, h: maxH };
  }

  function groupFont(h, o) { return o.groupFont || Math.max(24, Math.min(64, Math.round(h / 16))); }
  function titleBar(font) { return Math.round(font * 1.4) + 10; }

  function makeGroup(graph, title, x, y, w, h, color, font) {
    var G = global.LGraphGroup || (global.LiteGraph && global.LiteGraph.LGraphGroup);
    if (!G) return null;
    var g = new G(title);
    g.pos = [x, y];
    g.size = [w, h];
    g.color = color;
    g.font_size = font || 24;
    graph.add(g);
    return g;
  }

  function makeNote(graph, title, text, x, y, w, h, colors) {
    var LG = global.LiteGraph;
    var n = LG.createNode('Note') || LG.createNode('MarkdownNote');
    if (!n) return null;
    n.title = title;
    n.pos = [x, y];
    n.size = [w, h];
    if (n.widgets && n.widgets[0]) n.widgets[0].value = text;
    if (colors) { n.color = colors.color; n.bgcolor = colors.bgcolor; }
    graph.add(n);
    return n;
  }

  function fitView(app, bounds, pad) {
    var canvas = app.canvas;
    var el = canvas.canvas;
    var rect = el.getBoundingClientRect();
    var cw = rect.width || el.width, ch = rect.height || el.height;
    var bw = bounds[2] - bounds[0] + 2 * pad, bh = bounds[3] - bounds[1] + 2 * pad;
    var scale = Math.max(0.05, Math.min(cw / bw, ch / bh, 1.5));
    canvas.ds.scale = scale;
    canvas.ds.offset = [-(bounds[0] - pad) + (cw / scale - bw) / 2, -(bounds[1] - pad) + (ch / scale - bh) / 2];
    canvas.setDirty(true, true);
  }

  function layoutBearGraph(app, meta, opts) {
    var o = Object.assign({
      labels: {}, colGap: 70, rowGap: 34, bandGap: 90, pad: 30, groupTitle: 44,
      legend: true, bypassTaps: true, sharedTitle: 'Shared models', name: null
    }, opts || {});
    meta = meta || {};
    var graph = app.graph;
    var T = titleH();
    var all = (graph._nodes || graph.nodes || []).slice();
    var byId = new Map(all.map(function (n) { return [K(n.id), n]; }));

    // remove any groups from a previous run
    (graph._groups || graph.groups || []).slice().forEach(function (g) { graph.remove(g); });

    // (a) roles
    var roles = new Map();
    all.forEach(function (n) { var r = roleFromType(n); if (r) roles.set(K(n.id), r); });
    resolveFeeders(graph, all, roles);

    // (b) bands: items from _meta, shared = everything else
    var items = meta.items || {};
    var inItem = new Set();
    var bands = [];
    Object.keys(items).forEach(function (id) {
      var nodes = (items[id].nodes || []).map(function (k) { return byId.get(K(k)); }).filter(Boolean);
      nodes.forEach(function (n) { inItem.add(K(n.id)); });
      bands.push({ id: id, nodes: nodes });
    });
    var shared = all.filter(function (n) { return !inItem.has(K(n.id)); });
    if (!bands.length) bands.push({ id: 'graph', nodes: shared.splice(0) });

    var x0 = 0, y0 = 0, maxX = 0, maxY = 0;
    var report = { roles: {}, bands: [], shared: shared.length, taps: [] };
    roles.forEach(function (r) { report.roles[r] = (report.roles[r] || 0) + 1; });

    // shared column on the left
    if (shared.length) {
      var sy = y0 + o.groupTitle + T, sw = 0;
      shared.sort(function (a, b) {
        return (ROLE_ORDER.indexOf(roles.get(K(a.id))) - ROLE_ORDER.indexOf(roles.get(K(b.id)))) || (Number(a.id) - Number(b.id));
      });
      shared.forEach(function (n) { ensureSize(n); n.pos = [x0 + o.pad, sy]; sy += nodeH(n) + o.rowGap; sw = Math.max(sw, n.size[0]); });
      var gh = sy - o.rowGap - y0 + o.pad;
      makeGroup(graph, o.sharedTitle, x0, y0, sw + 2 * o.pad, gh, '#2f3f4f');
      x0 += sw + 2 * o.pad + o.bandGap;
      maxY = Math.max(maxY, gh);
    }

    // one band per item
    var y = y0;
    bands.forEach(function (b, i) {
      var inner = placeBand(graph, b.nodes, roles, x0 + o.pad, y, o);
      var font = groupFont(inner.h, o), tH = titleBar(font);
      b.nodes.forEach(function (n) { n.pos = [n.pos[0], n.pos[1] + tH]; });
      var w = inner.w + 2 * o.pad, h = inner.h + tH + o.pad;
      var label = o.labels && o.labels[b.id];
      var title = label ? b.id + '  ·  ' + label : b.id;
      makeGroup(graph, title, x0, y, w, h, BAND_COLORS[i % BAND_COLORS.length], font);
      report.bands.push({ id: b.id, nodes: b.nodes.length, w: w, h: h });
      maxX = Math.max(maxX, x0 + w);
      y += h + o.bandGap;
    });
    maxY = Math.max(maxY, y - o.bandGap);

    // (d) taps bypassed by default
    all.forEach(function (n) {
      if (roles.get(K(n.id)) === 'tap') { report.taps.push(K(n.id)); if (o.bypassTaps) n.mode = 4; }
    });

    // (c) colours
    all.forEach(function (n) {
      var p = PALETTE[roles.get(K(n.id))] || PALETTE.other;
      n.color = p.color; n.bgcolor = p.bgcolor;
    });

    // legend: a strip of colour swatches under the last band, one Note per role
    if (o.legend && global.LiteGraph) {
      var used = ROLE_ORDER.filter(function (r) { return report.roles[r]; });
      var swW = 230, swH = 56, gap = 16;
      var ly = maxY + o.bandGap;
      var lx = o.pad;
      used.forEach(function (r) {
        makeNote(graph, r.toUpperCase(), PALETTE[r].label, lx, ly + o.groupTitle + T, swW, swH, PALETTE[r]);
        lx += swW + gap;
      });
      var howto = 'Taps (grey, purple tint) are debug saves, bypassed by default. ' +
        'To inspect an intermediate: select the tap, Ctrl+B to un-bypass, Run; upstream nodes are cache hits. ' +
        'Rebuild from source: python tools/build.py blueprints/<name>.yaml [--debug]';
      var hw = Math.max(lx - gap - o.pad, 700);
      makeNote(graph, 'How to read this graph', howto, o.pad, ly + o.groupTitle + T + swH + T + gap, hw, 80, null);
      var lh = o.groupTitle + T + swH + T + gap + 80 + o.pad;
      makeGroup(graph, 'Legend', 0, ly, hw + 2 * o.pad, lh, '#444444');
      maxY = ly + lh;
      maxX = Math.max(maxX, hw + 2 * o.pad);
    }

    graph.extra = graph.extra || {};
    graph.extra.bear = { name: o.name, built_at: meta.built_at || null, debug: !!meta.debug, blueprint: meta.blueprint || null };

    // (e) fit — now, and again shortly after: app.loadApiJson kicks off its own
    // animated fit-to-view of the pre-layout graph, which would otherwise win.
    layoutBearGraph.lastBounds = [0, 0, maxX, maxY];
    fitView(app, layoutBearGraph.lastBounds, 40);
    [400, 900].forEach(function (ms) { setTimeout(function () { fitView(app, layoutBearGraph.lastBounds, 40); }, ms); });
    report.bounds = layoutBearGraph.lastBounds;
    return report;
  }

  // Helpers for the console: fit the whole graph, or zoom to one item's band.
  layoutBearGraph.fit = function (app, bounds) { fitView(app, bounds || layoutBearGraph.lastBounds, 40); };
  layoutBearGraph.fitBand = function (app, id) {
    var g = (app.graph._groups || app.graph.groups || []).find(function (g) {
      return g.title === id || g.title.indexOf(id + '  ·') === 0;
    });
    if (!g) return false;
    fitView(app, [g.pos[0], g.pos[1], g.pos[0] + g.size[0], g.pos[1] + g.size[1]], 20);
    return true;
  };

  global.layoutBearGraph = layoutBearGraph;
  global.layoutBearGraph.PALETTE = PALETTE;
})(typeof window !== 'undefined' ? window : globalThis);
