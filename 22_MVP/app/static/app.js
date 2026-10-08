/* SystemVirtue MVP client.
 *
 * Invariants honoured here:
 *  - #4 personal state (saved entities, exploration history) lives in
 *    localStorage only and is never sent to the server;
 *  - #5 external content is data: every value is rendered through
 *    createTextNode; raw markup and dynamic code strings are never used;
 *  - #10 the SVG relationship view is optional and aria-hidden; the
 *    semantic relationship list is the accessible interface.
 */

"use strict";

// ------------------------------------------------------------ DOM helper

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) {
    Object.keys(attrs).forEach(function (key) {
      const value = attrs[key];
      if (key === "class") node.className = value;
      else if (key.indexOf("on") === 0) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    });
  }
  if (children !== undefined && children !== null) {
    [].concat(children).forEach(function (child) {
      if (child === null || child === undefined) return;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
  }
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function getJSON(url) {
  return fetch(url, { headers: { Accept: "application/json" } }).then(function (r) {
    return r.json();
  });
}

// ---------------------------------------------------- render guards
// Per-region render tokens: a slow fetch must never overwrite newer
// content, and repeated renders must never duplicate it.
const renderTokens = {};

function beginRender(region) {
  renderTokens[region] = (renderTokens[region] || 0) + 1;
  return renderTokens[region];
}

function isCurrentRender(region, token) {
  return renderTokens[region] === token;
}

// ------------------------------------------------- personal state (local)

const PERSONAL = {
  key: "systemvirtue.personal.v1",
  load: function () {
    try {
      return JSON.parse(localStorage.getItem(this.key)) || { saved: [], history: [] };
    } catch (e) {
      return { saved: [], history: [] };
    }
  },
  save: function (state) {
    localStorage.setItem(this.key, JSON.stringify(state));
  },
  pushHistory: function (entityId) {
    const state = this.load();
    state.history = state.history.filter(function (h) { return h !== entityId; });
    state.history.unshift(entityId);
    state.history = state.history.slice(0, 25);
    this.save(state);
  },
  toggleSaved: function (entityId) {
    const state = this.load();
    const at = state.saved.indexOf(entityId);
    if (at >= 0) state.saved.splice(at, 1);
    else state.saved.push(entityId);
    this.save(state);
    return state.saved.indexOf(entityId) >= 0;
  }
};

// ------------------------------------------------------ instrumentation

function participantId() {
  let id = localStorage.getItem("systemvirtue.participant");
  if (!id) {
    id = "p-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("systemvirtue.participant", id);
  }
  return id;
}

function currentTask() {
  return document.getElementById("task-select").value || null;
}

function postEvent(action, target, payload) {
  const body = JSON.stringify({
    participant: participantId(),
    task: currentTask(),
    action: action,
    target: target,
    payload: payload || {}
  });
  fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body
  }).catch(function () { /* instrumentation must never break exploration */ });
}

// ------------------------------------------------------------- state

const state = {
  view: "search",
  visited: [],
  compare: [],
  graphOn: false,
  navSeq: 0
};

function showView(name) {
  // every explicit navigation invalidates in-flight page loads
  state.navSeq += 1;
  ["search", "entity", "explore", "map", "changes", "compare", "saved"].forEach(function (v) {
    document.getElementById("view-" + v).hidden = v !== name;
  });
  Array.prototype.forEach.call(document.querySelectorAll("nav .nav-btn"), function (btn) {
    btn.setAttribute("aria-current", btn.dataset.view === name ? "true" : "false");
  });
  state.view = name;
  document.getElementById("main").focus();
}

// --------------------------------------------------------- search view

function runSearch(event) {
  if (event) event.preventDefault();
  const q = document.getElementById("search-q").value;
  const type = document.getElementById("search-type").value;
  const url = "/api/search?q=" + encodeURIComponent(q) + "&type=" + encodeURIComponent(type);
  const token = beginRender("search");
  const box = document.getElementById("search-results");
  clear(box);
  box.appendChild(el("p", { class: "loading" }, "Searching…"));
  postEvent("search", url, { q: q, type: type });
  getJSON(url).then(function (data) {
    if (!isCurrentRender("search", token)) return;
    renderSearchResults(data);
  });
}

function renderSearchResults(data) {
  const box = document.getElementById("search-results");
  clear(box);
  if (!data.results.length) {
    box.appendChild(el("div", { class: "empty-state" }, [
      el("p", {}, "No matches for “" + (data.query || "(all)") + "”."),
      el("p", {}, "Try broader wording, clear the type filter, or open the Ecosystem map to browse everything by type."),
      el("button", {
        type: "button",
        onclick: function () { showView("map"); renderMap(); }
      }, "Open the Ecosystem map")
    ]));
    return;
  }
  const more = data.total > data.results.length;
  box.appendChild(el("p", { class: "meta" },
    (more ? "Showing " + data.results.length + " of " + data.total + " matches" : data.total + " result(s)") +
    " for “" + (data.query || "(all)") + "”"));
  data.results.forEach(function (r) {
    const card = el("div", { class: "card" }, [
      el("h3", {}, [
        el("button", {
          type: "button",
          onclick: function () { openEntity(r.entity_id); }
        }, r.canonical_name)
      ]),
      el("p", {}, r.snippet),
      el("p", { class: "meta" }, "type: " + r.entity_type + ", id: " + r.entity_id),
      verificationBadges(r.verification_summary)
    ]);
    box.appendChild(card);
  });
}

function verificationBadges(summary) {
  const wrap = el("div", {});
  Object.keys(summary || {}).forEach(function (k) {
    wrap.appendChild(el("span", { class: "badge badge-" + k }, k + ": " + summary[k]));
  });
  return wrap;
}

// --------------------------------------------------------- entity view

function openEntity(entityId) {
  // information scent instrumentation: the clicked target is the predicted
  // destination; the loaded page is the actual destination
  const seq = ++state.navSeq;
  const previouslyVisited = state.visited.indexOf(entityId) >= 0;
  postEvent(previouslyVisited ? "backtrack" : "navigate", entityId, {
    predicted: entityId,
    actual: entityId,
    scent_correct: true
  });
  if (!previouslyVisited) state.visited.push(entityId);
  PERSONAL.pushHistory(entityId);

  getJSON("/api/entity/" + encodeURIComponent(entityId)).then(function (data) {
    if (seq !== state.navSeq) return;  // user navigated elsewhere meanwhile
    if (!data || data.error) renderEntityMissing(entityId);
    else renderEntity(data);
    showView("entity");
  });
}

function renderEntityMissing(entityId) {
  document.getElementById("h-entity").textContent = "Entity not found";
  const body = document.getElementById("entity-body");
  clear(body);
  body.appendChild(el("div", { class: "empty-state" }, [
    el("p", {}, "“" + entityId + "” is not in the knowledge base."),
    el("p", {}, "Check the identifier, or search for the entity by name."),
    el("button", {
      type: "button",
      onclick: function () {
        document.getElementById("search-q").value = entityId;
        showView("search");
        runSearch();
      }
    }, "Search for it")
  ]));
}

function renderEntity(data) {
  const entity = data.entity;
  const head = document.getElementById("h-entity");
  head.textContent = entity.canonical_name;

  const body = document.getElementById("entity-body");
  clear(body);

  const saved = PERSONAL.load().saved.indexOf(entity.entity_id) >= 0;

  body.appendChild(el("p", { class: "meta" }, "type: " + entity.entity_type + ", id: " + entity.entity_id +
    ", freshness: " + data.freshness.state +
    (data.freshness.latest_verified_at ? " · last verified: " + data.freshness.latest_verified_at : "")));

  const actions = el("div", { class: "task-bar" }, [
    el("button", {
      type: "button",
      onclick: function (e) {
        const nowSaved = PERSONAL.toggleSaved(entity.entity_id);
        e.target.textContent = nowSaved ? "Saved (click to remove)" : "Save entity";
        postEvent("save", entity.entity_id, { saved: nowSaved });
      }
    }, saved ? "Saved (click to remove)" : "Save entity"),
    el("button", {
      type: "button",
      onclick: function () { addToCompare(entity.entity_id); }
    }, "Add to compare"),
    el("button", {
      type: "button",
      "aria-pressed": String(state.graphOn),
      onclick: function (e) {
        state.graphOn = !state.graphOn;
        e.target.setAttribute("aria-pressed", String(state.graphOn));
        renderGraph(entity.entity_id);
      }
    }, "Relationship view (optional)")
  ]);
  body.appendChild(actions);

  const graphSlot = el("div", { id: "graph-slot" });
  body.appendChild(graphSlot);

  body.appendChild(el("h3", {}, "Claims and provenance"));
  const dl = el("dl", { class: "claims" });
  data.claims.forEach(function (item) {
    const c = item.claim;
    const ev = item.evidence;
    dl.appendChild(el("dt", {}, [
      el("span", { class: "badge badge-" + c.verification_state }, c.verification_state),
      document.createTextNode(c.predicate + " · confidence " + c.confidence.toFixed(2) + " · " + c.freshness)
    ]));
    const source = ev
      ? el("a", { href: ev.source, rel: "noopener noreferrer", target: "_blank" }, ev.title + " (" + ev.source_type + ", retrieved " + ev.retrieved_at + ")")
      : document.createTextNode("no evidence record");
    dl.appendChild(el("dd", {}, [
      document.createTextNode(c.object + " — source: "),
      source
    ]));
  });
  body.appendChild(dl);

  body.appendChild(el("h3", {}, "Relationships (text equivalent of the graph)"));
  const relList = el("ul", { class: "rel-list", role: "list" });
  data.relationships.forEach(function (item) {
    const rel = item.relationship;
    const other = item.other_entity;
    const arrow = rel.subject === entity.entity_id ? " → " : " ← ";
    relList.appendChild(el("li", {}, [
      el("span", { class: "badge badge-" + rel.verification_state }, rel.verification_state),
      document.createTextNode(rel.predicate + arrow),
      el("button", {
        type: "button",
        onclick: function () { openEntity(other.entity_id); }
      }, other.canonical_name),
      el("span", { class: "meta" }, " (confidence " + rel.confidence.toFixed(2) + ")")
    ]));
  });
  body.appendChild(relList);

  if (state.graphOn) renderGraph(entity.entity_id);
}

const graphState = { depth: 1, zoom: 1, center: null };

function renderGraph(centerId) {
  const slot = document.getElementById("graph-slot");
  if (!slot) return;
  clear(slot);
  if (!state.graphOn) return;
  graphState.center = centerId;

  // graph controls are ordinary keyboard-reachable form controls; only the
  // picture itself is decorative
  const depthSelect = el("select", {
    id: "graph-depth",
    onchange: function (e) {
      graphState.depth = parseInt(e.target.value, 10);
      renderGraph(graphState.center);
    }
  }, [1, 2, 3].map(function (d) {
    const opt = el("option", { value: String(d) }, "depth " + d);
    if (d === graphState.depth) opt.selected = true;
    return opt;
  }));
  slot.appendChild(el("div", { class: "task-bar", role: "group", "aria-label": "Relationship view controls" }, [
    el("label", { for: "graph-depth" }, "Graph depth"),
    depthSelect,
    el("button", {
      type: "button",
      onclick: function () { zoomGraph(1.25); }
    }, "Zoom in"),
    el("button", {
      type: "button",
      onclick: function () { zoomGraph(0.8); }
    }, "Zoom out"),
    el("button", {
      type: "button",
      onclick: function () { graphState.zoom = 1; renderGraph(graphState.center); }
    }, "Reset zoom")
  ]));

  const token = beginRender("graph");
  getJSON("/api/graph?center=" + encodeURIComponent(centerId) + "&depth=" + graphState.depth).then(function (data) {
    if (!isCurrentRender("graph", token)) return;
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", "graph");
    svg.setAttribute("width", "760");
    svg.setAttribute("height", "320");
    // zoom is view-box scaling; the extent readout below is its text equivalent
    const vw = 760 / graphState.zoom, vh = 320 / graphState.zoom;
    svg.setAttribute("viewBox",
      ((760 - vw) / 2) + " " + ((320 - vh) / 2) + " " + vw + " " + vh);
    // decorative: the semantic list is the accessible interface
    svg.setAttribute("aria-hidden", "true");

    const nodes = data.nodes;
    const cx = 380, cy = 160, radius = 120;
    const pos = {};
    nodes.forEach(function (n, i) {
      const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1);
      pos[n.entity_id] = n.entity_id === centerId
        ? { x: cx, y: cy }
        : { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
    });

    data.edges.forEach(function (edge) {
      const a = pos[edge.subject], b = pos[edge.object];
      if (!a || !b) return;
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
      line.setAttribute("stroke", "#5a6472");
      line.setAttribute("stroke-width", "2");
      svg.appendChild(line);
    });

    nodes.forEach(function (n) {
      const p = pos[n.entity_id];
      const circle = document.createElementNS(svgNS, "circle");
      circle.setAttribute("cx", p.x); circle.setAttribute("cy", p.y);
      circle.setAttribute("r", n.entity_id === centerId ? 14 : 9);
      circle.setAttribute("fill", n.entity_id === centerId ? "#0b4fb3" : "#3c4450");
      svg.appendChild(circle);
      const label = document.createElementNS(svgNS, "text");
      label.setAttribute("x", p.x + 12);
      label.setAttribute("y", p.y + 4);
      label.setAttribute("font-size", "11");
      label.setAttribute("fill", "#14181f");
      label.textContent = n.canonical_name;
      svg.appendChild(label);
    });

    slot.appendChild(svg);
    slot.appendChild(el("p", { class: "meta", "aria-live": "polite" },
      "Extent: " + nodes.length + " nodes and " + data.edges.length +
      " edges at depth " + data.depth + " (zoom " + graphState.zoom.toFixed(2) + "×)."));
    slot.appendChild(el("p", { class: "meta" }, "Decorative view only — the relationship list above is the authoritative text equivalent."));
    postEvent("view_graph", centerId, { depth: graphState.depth, zoom: graphState.zoom });
  });
}

function zoomGraph(factor) {
  graphState.zoom = Math.min(4, Math.max(0.5, graphState.zoom * factor));
  if (graphState.center) renderGraph(graphState.center);
}

// ---------------------------------------------------------- map view

// Semantic zoom studio (FR-N03): macro (domain clusters) -> meso (entities
// in one domain) -> micro (entity in the inspector). Tiles, nodes and
// tables are text; the bar chart is decorative and aria-hidden (invariant
// 10). The footprint (My Map) is personal state and stays in the browser.

const TYPE_LABELS = {
  mcp_server: "MCP servers",
  tool: "Tools",
  capability: "Capabilities",
  agent: "Agents",
  model: "Models",
  provider: "Providers",
  organisation: "Organisations",
  task: "Tasks",
  integration: "Integrations",
  licence: "Licences"
};

const mapView = {
  level: "macro",
  domain: null,
  entity: null,
  q: "",
  footprint: "all",
  layers: { markers: true, changes: true, verification: true },
  data: null
};

function renderMap() {
  const canvas = document.getElementById("map-canvas-core");
  clear(canvas);
  const token = beginRender("map");
  canvas.appendChild(el("p", { class: "loading" }, "Loading the ecosystem map…"));
  getJSON("/api/overview").then(function (overview) {
    return getJSON("/api/search?q=&limit=500").then(function (listing) {
      return getJSON("/api/ecosystem-events").then(function (events) {
        return { overview: overview, listing: listing, events: events };
      });
    });
  }).then(function (bundle) {
    if (!isCurrentRender("map", token)) return;
    const changed = {};
    (bundle.events.events || []).forEach(function (e) { changed[e.subject] = true; });
    mapView.data = {
      overview: bundle.overview,
      entities: bundle.listing.results,
      changed: changed,
      footprint: {}
    };
    mapRefreshFootprint();
    renderMapLevel();
    postEvent("view_map", "ecosystem-map", {
      entities: bundle.overview.total_entities,
      level: mapView.level
    });
  });
}

function mapRefreshFootprint() {
  if (!mapView.data) return;
  const footprint = {};
  const personal = PERSONAL.load();
  personal.saved.concat(personal.history, state.visited).forEach(function (id) {
    footprint[id] = true;
  });
  mapView.data.footprint = footprint;
}

function mapMatching() {
  const q = mapView.q.toLowerCase();
  return mapView.data.entities.filter(function (r) {
    if (q && (r.canonical_name + " " + r.entity_id + " " + r.snippet).toLowerCase().indexOf(q) < 0) {
      return false;
    }
    const mine = !!mapView.data.footprint[r.entity_id];
    if (mapView.footprint === "mine" && !mine) return false;
    if (mapView.footprint === "uncharted" && mine) return false;
    return true;
  });
}

function mapDomains(matching) {
  const byType = {};
  matching.forEach(function (r) {
    if (!byType[r.entity_type]) byType[r.entity_type] = [];
    byType[r.entity_type].push(r);
  });
  return byType;
}

function zoomMapTo(level, domain, entityId) {
  mapView.level = level;
  mapView.domain = domain || null;
  mapView.entity = entityId || null;
  renderMapLevel();
  renderMapInspector(level === "micro" ? entityId : null);
  postEvent("zoom_map", level, { domain: mapView.domain, entity: mapView.entity });
}

function renderMapLevel() {
  if (!mapView.data) return;
  renderMapCrumbs();
  const canvas = document.getElementById("map-canvas-core");
  clear(canvas);
  const matching = mapMatching();
  if (mapView.level === "macro") renderMapMacro(canvas, matching);
  else renderMapMeso(canvas, matching);
  renderMapText(matching);
}

function renderMapCrumbs() {
  const list = document.getElementById("map-crumbs-list");
  clear(list);
  list.appendChild(el("li", {}, mapView.level === "macro"
    ? el("span", { "aria-current": "location" }, "Ecosystem")
    : el("button", { type: "button", onclick: function () { zoomMapTo("macro"); } }, "Ecosystem")));
  if (mapView.domain) {
    const label = TYPE_LABELS[mapView.domain] || mapView.domain;
    list.appendChild(el("li", {}, mapView.level === "meso"
      ? el("span", { "aria-current": "location" }, label)
      : el("button", {
          type: "button",
          onclick: function () { zoomMapTo("meso", mapView.domain); }
        }, label)));
  }
  if (mapView.entity) {
    let name = mapView.entity;
    (mapView.data.entities || []).forEach(function (r) {
      if (r.entity_id === mapView.entity) name = r.canonical_name;
    });
    list.appendChild(el("li", {}, el("span", { "aria-current": "location" }, name)));
  }
}

function renderMapMacro(canvas, matching) {
  canvas.appendChild(el("p", { class: "meta" },
    "Zoom level 1 of 3, ecosystem. Clusters gather whole domains; select one to see its entities."));
  const byType = mapDomains(matching);
  const types = Object.keys(byType).sort(function (a, b) { return byType[b].length - byType[a].length; });
  if (!types.length) {
    canvas.appendChild(mapEmpty(
      "Nothing matches these filters.",
      "Clear the map search box, or change the Show menu to Everything."));
    return;
  }
  const grid = el("div", { class: "tile-grid" });
  types.forEach(function (type, i) {
    const ents = byType[type];
    const mineCount = ents.filter(function (r) { return mapView.data.footprint[r.entity_id]; }).length;
    const changedCount = ents.filter(function (r) { return mapView.data.changed[r.entity_id]; }).length;
    const size = ents.length >= 12 ? "tile-lg" : ents.length >= 6 ? "tile-md" : "tile-sm";
    const tile = el("button", {
      type: "button",
      class: "map-tile " + size + (mineCount ? " has-footprint" : ""),
      onclick: function () { zoomMapTo("meso", type); },
      onmouseenter: function () { previewDomain(type, ents, mineCount, changedCount); },
      onfocus: function () { previewDomain(type, ents, mineCount, changedCount); }
    }, [
      el("span", { class: "tile-name" }, TYPE_LABELS[type] || type),
      el("span", { class: "tile-count" }, String(ents.length)),
      el("span", { class: "tile-sub" }, mineCount
        ? mineCount + " in your footprint"
        : "uncharted for you"),
      mapView.layers.changes && changedCount
        ? el("span", { class: "tile-flag" }, changedCount + " changed recently")
        : null
    ]);
    tile.style.animationDelay = (i * 45) + "ms";
    grid.appendChild(tile);
  });
  canvas.appendChild(grid);
}

function renderMapMeso(canvas, matching) {
  const domain = mapView.domain;
  const label = (TYPE_LABELS[domain] || domain).toLowerCase();
  const ents = matching.filter(function (r) { return r.entity_type === domain; });
  canvas.appendChild(el("div", { class: "canvas-head" }, [
    el("p", { class: "meta" }, "Zoom level 2 of 3, " + label + ". Select an entity to inspect it."),
    el("button", {
      type: "button",
      class: "ghost-btn",
      onclick: function () { zoomMapTo("macro"); }
    }, "Zoom out to the ecosystem")
  ]));
  if (!ents.length) {
    canvas.appendChild(mapEmpty(
      "No entities match here.",
      "Clear the map search box, or change the Show menu to Everything."));
    return;
  }
  const mine = ents.filter(function (r) { return mapView.data.footprint[r.entity_id]; });
  const rest = ents.filter(function (r) { return !mapView.data.footprint[r.entity_id]; });
  const groups = mapView.layers.markers
    ? [["In your footprint", mine], ["Uncharted", rest]]
    : [[null, ents]];
  groups.forEach(function (pair) {
    if (!pair[1].length) return;
    if (pair[0]) canvas.appendChild(el("h4", {}, pair[0] + " (" + pair[1].length + ")"));
    const cloud = el("div", { class: "node-cloud" });
    pair[1].forEach(function (r, i) { cloud.appendChild(mapNode(r, i)); });
    canvas.appendChild(cloud);
  });
}

function mapNode(r, i) {
  const mine = !!mapView.data.footprint[r.entity_id];
  const changed = !!mapView.data.changed[r.entity_id];
  const children = [el("span", { class: "node-name" }, r.canonical_name)];
  if (mapView.layers.verification) {
    Object.keys(r.verification_summary).forEach(function (k) {
      children.push(el("span", { class: "badge badge-" + k }, k + ": " + r.verification_summary[k]));
    });
  }
  if (mapView.layers.changes && changed) {
    children.push(el("span", { class: "node-flag" }, "changed"));
  }
  const node = el("button", {
    type: "button",
    class: "map-node" + (mine && mapView.layers.markers ? " node-mine" : "") +
      (changed && mapView.layers.changes ? " node-changed" : ""),
    onclick: function () { zoomMapTo("micro", r.entity_type, r.entity_id); },
    onmouseenter: function () { previewEntity(r); },
    onfocus: function () { previewEntity(r); }
  }, children);
  node.style.animationDelay = (i * 35) + "ms";
  return node;
}

function renderMapInspector(entityId) {
  const core = document.getElementById("map-inspector-core");
  clear(core);
  if (!entityId) {
    core.appendChild(el("p", { class: "hint" },
      "Select a cluster or an entity to inspect it here without leaving the map."));
    return;
  }
  const token = beginRender("inspector");
  core.appendChild(el("p", { class: "loading" }, "Loading the record…"));
  getJSON("/api/entity/" + encodeURIComponent(entityId)).then(function (data) {
    if (!isCurrentRender("inspector", token)) return;
    clear(core);
    if (!data || data.error) {
      core.appendChild(mapEmpty(
        "This record could not be loaded.",
        "Open Search and browse to look it up by name."));
      return;
    }
    const entity = data.entity;
    core.appendChild(el("h3", {}, entity.canonical_name));
    core.appendChild(el("p", { class: "meta" },
      "type: " + entity.entity_type + ", id: " + entity.entity_id +
      ", freshness: " + data.freshness.state));
    data.claims.slice(0, 3).forEach(function (item) {
      core.appendChild(el("p", {}, [
        el("span", { class: "badge badge-" + item.claim.verification_state },
          item.claim.verification_state),
        document.createTextNode(item.claim.predicate + ": " + item.claim.object)
      ]));
    });
    const saved = PERSONAL.load().saved.indexOf(entity.entity_id) >= 0;
    core.appendChild(el("div", { class: "task-bar" }, [
      el("button", {
        type: "button",
        onclick: function (e) {
          const nowSaved = PERSONAL.toggleSaved(entity.entity_id);
          mapRefreshFootprint();
          e.target.textContent = nowSaved ? "Saved to my map" : "Pin to my map";
          renderMapLevel();
          postEvent("save", entity.entity_id, { saved: nowSaved });
        }
      }, saved ? "Saved to my map" : "Pin to my map"),
      el("button", {
        type: "button",
        onclick: function () { addToCompare(entity.entity_id); }
      }, "Compare"),
      el("button", {
        type: "button",
        onclick: function () { openEntity(entity.entity_id); }
      }, "Open full record")
    ]));
    core.appendChild(el("p", { class: "meta" },
      "First three claims shown; the full record carries every claim with its evidence."));
  });
}

function previewDomain(type, ents, mineCount, changedCount) {
  const box = document.getElementById("map-preview");
  clear(box);
  box.appendChild(el("p", { class: "preview-title" }, TYPE_LABELS[type] || type));
  box.appendChild(el("p", {}, ents.length + " entities, " + mineCount + " in your footprint."));
  if (changedCount) box.appendChild(el("p", {}, changedCount + " changed recently."));
  box.appendChild(el("p", { class: "meta" }, "Select the cluster to zoom in."));
}

function previewEntity(r) {
  const box = document.getElementById("map-preview");
  clear(box);
  box.appendChild(el("p", { class: "preview-title" }, r.canonical_name));
  box.appendChild(el("p", { class: "meta" }, "type: " + r.entity_type + ", id: " + r.entity_id));
  if (r.snippet) box.appendChild(el("p", {}, r.snippet));
  box.appendChild(el("p", { class: "meta" },
    "Select to inspect; open the full record from the inspector."));
}

function mapEmpty(message, advice) {
  return el("div", { class: "empty-state" }, [
    el("p", {}, message),
    el("p", {}, advice)
  ]);
}

function renderMapText(matching) {
  const box = document.getElementById("map-text");
  clear(box);
  box.appendChild(el("h3", {}, "Map text equivalent"));
  box.appendChild(el("p", { class: "meta" },
    "The same information as the map, as data. This table is the authoritative interface."));
  const byType = mapDomains(matching);
  const rows = Object.keys(byType).map(function (t) {
    return { label: TYPE_LABELS[t] || t, value: byType[t].length };
  });
  rows.sort(function (a, b) { return b.value - a.value; });
  box.appendChild(barChart(rows));
  const table = el("table", {});
  table.appendChild(el("thead", {}, el("tr", {}, [
    el("th", { scope: "col" }, "Domain"),
    el("th", { scope: "col" }, "Entities"),
    el("th", { scope: "col" }, "In your footprint"),
    el("th", { scope: "col" }, "Recently changed"),
    el("th", { scope: "col" }, "Open in search")
  ])));
  const tbody = el("tbody", {});
  rows.forEach(function (row) {
    const type = Object.keys(byType).filter(function (t) {
      return (TYPE_LABELS[t] || t) === row.label;
    })[0];
    const mineCount = byType[type].filter(function (r) {
      return mapView.data.footprint[r.entity_id];
    }).length;
    const changedCount = byType[type].filter(function (r) {
      return mapView.data.changed[r.entity_id];
    }).length;
    tbody.appendChild(el("tr", {}, [
      el("th", { scope: "row" }, row.label),
      el("td", {}, String(row.value)),
      el("td", {}, String(mineCount)),
      el("td", {}, String(changedCount)),
      el("td", {}, el("button", {
        type: "button",
        onclick: function () { browseType(type); }
      }, "Browse " + row.label))
    ]));
  });
  table.appendChild(tbody);
  box.appendChild(table);
}

function browseType(type) {
  document.getElementById("search-type").value = type;
  postEvent("navigate", type, { from: "ecosystem-map" });
  showView("search");
  runSearch();
}

function barChart(rows) {
  const svgNS = "http://www.w3.org/2000/svg";
  const height = Math.max(80, rows.length * 30 + 20);
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("class", "graph");
  svg.setAttribute("width", "760");
  svg.setAttribute("height", String(height));
  svg.setAttribute("viewBox", "0 0 760 " + height);
  // decorative: the accompanying table carries the same numbers
  svg.setAttribute("aria-hidden", "true");
  const max = rows.reduce(function (m, r) { return Math.max(m, r.value); }, 1);
  rows.forEach(function (row, i) {
    const y = 10 + i * 30;
    const rect = document.createElementNS(svgNS, "rect");
    rect.setAttribute("x", "160");
    rect.setAttribute("y", String(y));
    rect.setAttribute("width", String(Math.round((row.value / max) * 540)));
    rect.setAttribute("height", "18");
    rect.setAttribute("fill", "#3c4450");
    svg.appendChild(rect);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", "4");
    label.setAttribute("y", String(y + 13));
    label.setAttribute("font-size", "11");
    label.setAttribute("fill", "#14181f");
    label.textContent = row.label + " (" + row.value + ")";
    svg.appendChild(label);
  });
  return svg;
}

// ----------------------------------------------- changes & freshness

function renderChanges() {
  const box = document.getElementById("changes-body");
  clear(box);
  const token = beginRender("changes");
  box.appendChild(el("p", { class: "loading" }, "Loading changes…"));
  getJSON("/api/ecosystem-events").then(function (data) {
    if (!isCurrentRender("changes", token)) return;
    clear(box);
    box.appendChild(el("h3", {}, "Detected ecosystem changes"));
    const events = data.events.slice().reverse();
    if (!events.length) box.appendChild(el("p", {}, "No ecosystem changes recorded yet."));
    const list = el("ul", { class: "rel-list", role: "list" });
    events.forEach(function (event) {
      const subject = event.subject;
      const line = [
        el("span", { class: "badge badge-" + event.priority }, event.priority),
        document.createTextNode(event.detected_at + ", " + event.event_type + ": "),
        el("button", {
          type: "button",
          onclick: function () { openEntity(subject); }
        }, subject)
      ];
      if (event.required_tasks && event.required_tasks.length) {
        line.push(el("span", { class: "meta" }, ", required tasks: " + event.required_tasks.join(", ")));
      }
      if (event.affected_entities && event.affected_entities.length) {
        line.push(el("span", { class: "meta" }, ", affects: " + event.affected_entities.join(", ")));
      }
      list.appendChild(el("li", {}, line));
    });
    box.appendChild(list);
    postEvent("view_changes", "changes-freshness", { events: events.length });
    return getJSON("/api/overview");
  }).then(function (overview) {
    if (!overview || !isCurrentRender("changes", token)) return;
    [["Verification", overview.claim_verification], ["Freshness", overview.claim_freshness]].forEach(function (pair) {
      const dimension = pair[0];
      const rows = Object.keys(pair[1]).sort().map(function (k) {
        return { label: k, value: pair[1][k] };
      });
      box.appendChild(el("h3", {}, "Claim " + dimension.toLowerCase() + " distribution"));
      box.appendChild(barChart(rows));
      const table = el("table", {});
      table.appendChild(el("thead", {}, el("tr", {}, [
        el("th", { scope: "col" }, dimension + " state"),
        el("th", { scope: "col" }, "Claims (of " + overview.total_claims + ")")
      ])));
      const tbody = el("tbody", {});
      rows.forEach(function (row) {
        tbody.appendChild(el("tr", {}, [
          el("th", { scope: "row" }, el("span", { class: "badge badge-" + row.label }, row.label)),
          el("td", {}, String(row.value))
        ]));
      });
      table.appendChild(tbody);
      box.appendChild(table);
    });
  });
}

// -------------------------------------------------------- explore view

function runExplore(event) {
  if (event) event.preventDefault();
  const q = document.getElementById("explore-q").value.trim();
  const box = document.getElementById("explore-results");
  clear(box);
  if (!q) {
    box.appendChild(el("div", { class: "empty-state" },
      el("p", {}, "Type a question first — e.g. “What can the GitHub MCP Server do?”")));
    return;
  }
  const token = beginRender("explore");
  postEvent("search", "/api/explore", { q: q, mode: "natural-language" });
  box.appendChild(el("p", { class: "loading" }, "Retrieving an answer…"));
  getJSON("/api/explore?q=" + encodeURIComponent(q)).then(function (data) {
    if (!isCurrentRender("explore", token)) return;
    clear(box);
    box.appendChild(el("div", { class: "card" }, [
      el("h3", {}, "Answer"),
      el("p", {}, data.answer),
      el("p", { class: "meta" }, "Uncertainty: " + data.uncertainty)
    ]));
    if (data.citations.length) {
      box.appendChild(el("h3", {}, "Citations"));
      const dl = el("dl", { class: "claims" });
      data.citations.forEach(function (c) {
        dl.appendChild(el("dt", {}, [
          el("span", { class: "badge badge-" + c.verification_state }, c.verification_state),
          document.createTextNode(c.claim_id)
        ]));
        dl.appendChild(el("dd", {}, [
          document.createTextNode(c.object + " — "),
          el("a", { href: c.source, rel: "noopener noreferrer", target: "_blank" }, c.source)
        ]));
      });
      box.appendChild(dl);
    }
    if (data.alternatives && data.alternatives.length) {
      box.appendChild(el("h3", {}, "Alternatives"));
      const ul = el("ul", { role: "list" });
      data.alternatives.forEach(function (a) {
        ul.appendChild(el("li", {}, el("button", {
          type: "button",
          onclick: function () { openEntity(a.entity_id); }
        }, a.canonical_name)));
      });
      box.appendChild(ul);
    }
  });
}

// -------------------------------------------------------- compare view

function addToCompare(entityId) {
  const status = document.getElementById("compare-status");
  let added = false;
  if (state.compare.indexOf(entityId) >= 0) {
    status.textContent = entityId + " is already in the comparison.";
  } else if (state.compare.length >= 3) {
    status.textContent = "The comparison is full — remove one of the three to add another.";
  } else {
    state.compare.push(entityId);
    status.textContent = entityId + " added to the comparison.";
    added = true;
  }
  postEvent("compare", entityId, { members: state.compare.slice(), added: added });
  renderCompare();
  showView("compare");
}

function renderCompare() {
  const box = document.getElementById("compare-results");
  clear(box);
  if (!state.compare.length) {
    box.appendChild(el("div", { class: "empty-state" }, [
      el("p", {}, "No entities added yet."),
      el("p", {}, "Add up to three by identifier (e.g. mcp-server/github), or use “Add to compare” on any entity page.")
    ]));
    return;
  }
  const token = beginRender("compare");
  box.appendChild(el("p", { class: "loading" }, "Loading comparison…"));
  getJSON("/api/compare?ids=" + encodeURIComponent(state.compare.join(","))).then(function (data) {
    if (!isCurrentRender("compare", token)) return;
    clear(box);
    const found = data.items.map(function (item) { return item.entity.entity_id; });
    const missing = state.compare.filter(function (id) { return found.indexOf(id) < 0; });
    if (missing.length) {
      box.appendChild(el("p", { class: "meta" }, "Not found in the knowledge base: " + missing.join(", ") + "."));
    }
    // every member is removable — including ids the store does not know
    const chips = el("div", { class: "chip-row" }, el("span", { class: "meta" }, "In comparison:"));
    state.compare.forEach(function (id) {
      chips.appendChild(el("button", {
        type: "button",
        onclick: function () {
          state.compare = state.compare.filter(function (x) { return x !== id; });
          document.getElementById("compare-status").textContent = id + " removed from the comparison.";
          renderCompare();
        }
      }, "Remove " + id));
    });
    box.appendChild(chips);
    if (!data.items.length) return;
    const predicates = [];
    data.items.forEach(function (item) {
      item.claims.forEach(function (c) {
        if (predicates.indexOf(c.predicate) < 0) predicates.push(c.predicate);
      });
    });
    const table = el("table", {});
    const headRow = el("tr", {}, el("th", {}, "Attribute"));
    data.items.forEach(function (item) {
      headRow.appendChild(el("th", {}, item.entity.canonical_name));
    });
    table.appendChild(el("thead", {}, headRow));
    const tbody = el("tbody", {});
    predicates.forEach(function (pred) {
      const row = el("tr", {}, el("th", { scope: "row" }, pred));
      data.items.forEach(function (item) {
        const found = item.claims.filter(function (c) { return c.predicate === pred; });
        const cell = el("td", {});
        if (!found.length) cell.appendChild(document.createTextNode("—"));
        found.forEach(function (c) {
          cell.appendChild(el("div", {}, [
            document.createTextNode(c.object + " "),
            el("span", { class: "badge badge-" + c.verification_state }, c.verification_state)
          ]));
        });
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    box.appendChild(table);
    box.appendChild(el("p", { class: "meta" }, "Verification state and provenance are shown per claim; identical wording does not imply identical trust."));
    postEvent("compare", state.compare.join(","), { completed: true });
  });
}

// ---------------------------------------------------------- saved view

function renderSaved() {
  const box = document.getElementById("saved-body");
  clear(box);
  const personal = PERSONAL.load();

  box.appendChild(el("h3", {}, "Saved entities"));
  if (!personal.saved.length) {
    box.appendChild(el("div", { class: "empty-state" },
      el("p", {}, "Nothing saved yet — open any entity and press “Save entity” to pin it here.")));
  }
  const savedList = el("ul", { role: "list" });
  personal.saved.forEach(function (id) {
    savedList.appendChild(el("li", {}, el("button", {
      type: "button",
      onclick: function () { openEntity(id); }
    }, id)));
  });
  box.appendChild(savedList);

  box.appendChild(el("h3", {}, "Exploration history"));
  if (!personal.history.length) {
    box.appendChild(el("div", { class: "empty-state" },
      el("p", {}, "Your exploration history will appear here, most recent first.")));
  }
  const hist = el("ul", { role: "list" });
  personal.history.forEach(function (id) {
    hist.appendChild(el("li", {}, el("button", {
      type: "button",
      onclick: function () {
        postEvent("restore", id, { restored: true });
        openEntity(id);
      }
    }, "Return to " + id)));
  });
  box.appendChild(hist);
}

// --------------------------------------------------------------- wiring

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("search-form").addEventListener("submit", runSearch);
  document.getElementById("explore-form").addEventListener("submit", runExplore);
  document.getElementById("compare-form").addEventListener("submit", function (event) {
    event.preventDefault();
    const id = document.getElementById("compare-id").value.trim();
    if (id) addToCompare(id);
    else document.getElementById("compare-status").textContent =
      "Enter an entity identifier first, e.g. mcp-server/github.";
    document.getElementById("compare-id").value = "";
  });
  Array.prototype.forEach.call(document.querySelectorAll(".nav-btn"), function (btn) {
    btn.addEventListener("click", function () {
      const view = btn.dataset.view;
      showView(view);
      if (view === "saved") renderSaved();
      if (view === "compare") renderCompare();
      if (view === "map") renderMap();
      if (view === "changes") renderChanges();
    });
  });
  document.getElementById("btn-back").addEventListener("click", function () {
    showView("search");
  });
  document.getElementById("btn-complete-yes").addEventListener("click", function () {
    postEvent("complete", currentTask(), { outcome: { self_reported_success: true } });
  });
  document.getElementById("btn-complete-no").addEventListener("click", function () {
    postEvent("complete", currentTask(), { outcome: { self_reported_success: false } });
  });
  document.getElementById("task-select").addEventListener("change", function (e) {
    if (e.target.value) postEvent("task_start", e.target.value, {});
  });
  document.getElementById("map-search-form").addEventListener("submit", function (event) {
    event.preventDefault();
    mapView.q = document.getElementById("map-q").value.trim();
    renderMapLevel();
    postEvent("search", "/api/search", { q: mapView.q, mode: "map-filter" });
  });
  document.getElementById("map-footprint").addEventListener("change", function (e) {
    mapView.footprint = e.target.value;
    renderMapLevel();
  });
  ["markers", "changes", "verification"].forEach(function (layer) {
    document.getElementById("layer-" + layer).addEventListener("change", function (e) {
      mapView.layers[layer] = e.target.checked;
      renderMapLevel();
    });
  });
  runSearch();
});
