import { describe, expect, it } from "vitest";
import {
  ALL_SEARCH_FIELDS,
  LABEL_PALETTE,
  labelColor,
  edgeTypeColorMap,
  expandByHops,
  hexToRgba,
  nodeMatchesQuery,
  toForceGraphData,
} from "../graph";
import type { GraphPayload } from "../types";

/* -------------------------------------------------------------------------- */
/* Helpers                                                                     */
/* -------------------------------------------------------------------------- */

function makePayload(
  overrides: Partial<GraphPayload> = {},
): GraphPayload {
  return {
    dataset: "attack",
    backend: "neo4j",
    counts: { nodes: 4, relationships: 4 },
    nodes_by_label: { Technique: 2, Malware: 1, Group: 1 },
    nodes: [
      { id: "n1", label: "Technique", labels: ["Technique"], name: "T1047", properties: {} },
      { id: "n2", label: "Technique", labels: ["Technique"], name: "T1059", properties: {} },
      { id: "n3", label: "Malware",   labels: ["Malware"],   name: "Mal-A",  properties: {} },
      { id: "n4", label: "Group",     labels: ["Group"],     name: "APT28", properties: {} },
    ],
    edges: [
      { id: "e1", source: "n1", target: "n3", type: "USES" },
      { id: "e2", source: "n2", target: "n3", type: "USES" },
      { id: "e3", source: "n4", target: "n1", type: "ATTRIBUTED_TO" },
      { id: "e4", source: "n4", target: "n2", type: "ATTRIBUTED_TO" },
    ],
    ...overrides,
  };
}

/* -------------------------------------------------------------------------- */
/* labelColor                                                                  */
/* -------------------------------------------------------------------------- */

describe("labelColor", () => {
  it("returns a string that is a member of LABEL_PALETTE", () => {
    const color = labelColor("Technique");
    expect(LABEL_PALETTE).toContain(color);
  });

  it("is deterministic — same label always returns same color", () => {
    const labels = ["Technique", "Malware", "Group", "AttackPattern", ""];
    for (const label of labels) {
      const a = labelColor(label);
      const b = labelColor(label);
      expect(a).toBe(b);
    }
  });

  it("different labels can produce different colors (palette coverage)", () => {
    const colors = new Set<string>();
    const testLabels = [
      "Technique", "Malware", "Group", "AttackPattern", "Tactic",
      "Mitigation", "DataComponent", "Campaign", "Asset", "Identity",
    ];
    for (const label of testLabels) {
      colors.add(labelColor(label));
    }
    // We should hit at least 3 distinct colors with 10 diverse labels
    expect(colors.size).toBeGreaterThanOrEqual(3);
  });

  it("returns a hex color string starting with #", () => {
    expect(labelColor("Technique")).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

/* -------------------------------------------------------------------------- */
/* edgeTypeColor + hexToRgba                                                    */
/* -------------------------------------------------------------------------- */

describe("edgeTypeColorMap", () => {
  const attackTypes = [
    "USES", "ATTRIBUTED_TO", "MITIGATES", "DETECTS", "HAS_TECHNIQUE", "HAS_SUBTECHNIQUE",
  ];

  it("assigns a UNIQUE palette color to each type (no collisions ≤ palette size)", () => {
    const map = edgeTypeColorMap(attackTypes);
    const colors = [...map.values()];
    expect(colors).toHaveLength(attackTypes.length);
    // Every assigned color is distinct
    expect(new Set(colors).size).toBe(attackTypes.length);
    // and every color is a palette member
    for (const c of colors) expect(LABEL_PALETTE).toContain(c);
  });

  it("is stable regardless of input order (sorts internally)", () => {
    const a = edgeTypeColorMap(attackTypes);
    const b = edgeTypeColorMap([...attackTypes].reverse());
    for (const t of attackTypes) expect(a.get(t)).toBe(b.get(t));
  });

  it("dedupes repeated types", () => {
    const map = edgeTypeColorMap(["USES", "USES", "DETECTS"]);
    expect(map.size).toBe(2);
  });
});

describe("hexToRgba", () => {
  it("converts a #rrggbb hex to an rgba string at the given alpha", () => {
    expect(hexToRgba("#4e9e96", 0.5)).toBe("rgba(78, 158, 150, 0.5)");
  });
});

/* -------------------------------------------------------------------------- */
/* toForceGraphData — basic mapping                                           */
/* -------------------------------------------------------------------------- */

describe("toForceGraphData — basic mapping", () => {
  const payload = makePayload();

  it("maps node and link counts correctly on a small payload", () => {
    const { nodes, links } = toForceGraphData(payload);
    expect(nodes).toHaveLength(4);
    expect(links).toHaveLength(4);
  });

  it("each node has a color from the palette", () => {
    const { nodes } = toForceGraphData(payload);
    for (const node of nodes) {
      expect(typeof node.color).toBe("string");
      expect(LABEL_PALETTE).toContain(node.color);
    }
  });

  it("each link has a translucent rgba color and a solid palette typeColor", () => {
    const { links } = toForceGraphData(payload);
    for (const link of links) {
      expect(link.color).toMatch(/^rgba\(\d+, \d+, \d+, [\d.]+\)$/);
      expect(LABEL_PALETTE).toContain(link.typeColor);
    }
    // Distinct relationship types yield distinct colors (unique assignment)
    const uses = links.find((l) => l.type === "USES");
    const attributed = links.find((l) => l.type === "ATTRIBUTED_TO");
    expect(uses?.color).not.toBe(attributed?.color);
    expect(uses?.typeColor).not.toBe(attributed?.typeColor);
  });

  it("each link has sourceId and targetId matching the original string ids", () => {
    const { links } = toForceGraphData(payload);
    for (const link of links) {
      expect(typeof link.sourceId).toBe("string");
      expect(typeof link.targetId).toBe("string");
      // sourceId/targetId must be node ids that exist in the original payload
      const nodeIds = new Set(payload.nodes.map((n) => n.id));
      expect(nodeIds.has(link.sourceId)).toBe(true);
      expect(nodeIds.has(link.targetId)).toBe(true);
    }
  });

  it("link source and target start as string ids (not mutated yet)", () => {
    const { links } = toForceGraphData(payload);
    for (const link of links) {
      expect(typeof link.source).toBe("string");
      expect(typeof link.target).toBe("string");
    }
  });

  it("preserves node fields (id, label, name, properties)", () => {
    const { nodes } = toForceGraphData(payload);
    const n1 = nodes.find((n) => n.id === "n1");
    expect(n1).toBeDefined();
    expect(n1!.label).toBe("Technique");
    expect(n1!.name).toBe("T1047");
  });
});

/* -------------------------------------------------------------------------- */
/* hiddenTypes filtering                                                       */
/* -------------------------------------------------------------------------- */

describe("toForceGraphData — hiddenTypes filtering", () => {
  it("drops links of the hidden type", () => {
    const { links } = toForceGraphData(makePayload(), {
      hiddenTypes: new Set(["USES"]),
    });
    expect(links.every((l) => l.type !== "USES")).toBe(true);
  });

  it("retains links of other types", () => {
    const { links } = toForceGraphData(makePayload(), {
      hiddenTypes: new Set(["USES"]),
    });
    // ATTRIBUTED_TO links (e3, e4) should survive
    expect(links).toHaveLength(2);
    expect(links.every((l) => l.type === "ATTRIBUTED_TO")).toBe(true);
  });

  it("hiding all types produces zero links", () => {
    const { links } = toForceGraphData(makePayload(), {
      hiddenTypes: new Set(["USES", "ATTRIBUTED_TO"]),
    });
    expect(links).toHaveLength(0);
  });

  it("nodes are not affected by hiddenTypes", () => {
    const { nodes } = toForceGraphData(makePayload(), {
      hiddenTypes: new Set(["USES"]),
    });
    expect(nodes).toHaveLength(4);
  });
});

/* -------------------------------------------------------------------------- */
/* hiddenLabels filtering                                                      */
/* -------------------------------------------------------------------------- */

describe("toForceGraphData — hiddenLabels filtering", () => {
  it("drops nodes whose label is hidden", () => {
    const { nodes } = toForceGraphData(makePayload(), {
      hiddenLabels: new Set(["Malware"]),
    });
    expect(nodes.every((n) => n.label !== "Malware")).toBe(true);
    expect(nodes).toHaveLength(3); // n1, n2, n4 remain
  });

  it("drops links whose source or target node was removed — no dangling links", () => {
    // Hiding Malware removes n3; e1 (n1→n3) and e2 (n2→n3) become dangling
    const { nodes, links } = toForceGraphData(makePayload(), {
      hiddenLabels: new Set(["Malware"]),
    });
    const survivingIds = new Set(nodes.map((n) => n.id));
    for (const link of links) {
      expect(survivingIds.has(link.sourceId)).toBe(true);
      expect(survivingIds.has(link.targetId)).toBe(true);
    }
    // e3 and e4 (n4→n1, n4→n2) should survive; e1 and e2 are dangling
    expect(links).toHaveLength(2);
  });

  it("hiding the Group label removes the group node and its outbound links", () => {
    const { nodes, links } = toForceGraphData(makePayload(), {
      hiddenLabels: new Set(["Group"]),
    });
    // n4 (Group) removed → e3 and e4 are dangling
    expect(nodes.some((n) => n.id === "n4")).toBe(false);
    expect(links.some((l) => l.sourceId === "n4" || l.targetId === "n4")).toBe(false);
  });

  it("no link in result references a removed node", () => {
    const { nodes, links } = toForceGraphData(makePayload(), {
      hiddenLabels: new Set(["Technique", "Group"]),
    });
    const survivingIds = new Set(nodes.map((n) => n.id));
    for (const link of links) {
      expect(survivingIds.has(link.sourceId)).toBe(true);
      expect(survivingIds.has(link.targetId)).toBe(true);
    }
  });
});

/* -------------------------------------------------------------------------- */
/* Combined filtering                                                          */
/* -------------------------------------------------------------------------- */

describe("toForceGraphData — combined hiddenLabels + hiddenTypes", () => {
  it("applies both filters independently", () => {
    const { nodes, links } = toForceGraphData(makePayload(), {
      hiddenLabels: new Set(["Malware"]),
      hiddenTypes: new Set(["ATTRIBUTED_TO"]),
    });
    // Malware node removed; ATTRIBUTED_TO and dangling-USES links removed
    expect(nodes.some((n) => n.label === "Malware")).toBe(false);
    expect(links.some((l) => l.type === "ATTRIBUTED_TO")).toBe(false);
    // e1 and e2 are dangling (n3 removed); e3 and e4 hidden → 0 links
    expect(links).toHaveLength(0);
  });
});

/* -------------------------------------------------------------------------- */
/* Empty payload                                                               */
/* -------------------------------------------------------------------------- */

describe("toForceGraphData — edge cases", () => {
  it("handles an empty nodes/edges payload gracefully", () => {
    const { nodes, links } = toForceGraphData(
      makePayload({ nodes: [], edges: [], counts: { nodes: 0, relationships: 0 } }),
    );
    expect(nodes).toHaveLength(0);
    expect(links).toHaveLength(0);
  });

  it("returns fresh arrays each call (no shared reference mutation risk)", () => {
    const payload = makePayload();
    const a = toForceGraphData(payload);
    const b = toForceGraphData(payload);
    expect(a.nodes).not.toBe(b.nodes);
    expect(a.links).not.toBe(b.links);
  });
});

/* -------------------------------------------------------------------------- */
/* nodeMatchesQuery + search filtering                                         */
/* -------------------------------------------------------------------------- */

describe("nodeMatchesQuery", () => {
  const node = {
    id: "attack-pattern--abc",
    label: "Technique",
    labels: ["Technique"],
    name: "Scheduled Task",
    properties: { description: "Adversaries may abuse the Windows Task Scheduler." },
  };

  it("empty query matches everything", () => {
    expect(nodeMatchesQuery(node, "")).toBe(true);
  });
  it("matches on name (case-insensitive, lowercased query)", () => {
    expect(nodeMatchesQuery(node, "scheduled")).toBe(true);
  });
  it("matches on description", () => {
    expect(nodeMatchesQuery(node, "task scheduler")).toBe(true);
  });
  it("matches on id and label", () => {
    expect(nodeMatchesQuery(node, "attack-pattern")).toBe(true);
    expect(nodeMatchesQuery(node, "technique")).toBe(true);
  });
  it("returns false when nothing matches", () => {
    expect(nodeMatchesQuery(node, "zzz-nomatch")).toBe(false);
  });
});

describe("toForceGraphData — search query", () => {
  it("empty query leaves the graph unchanged", () => {
    const payload = makePayload();
    const { nodes, links } = toForceGraphData(payload, { query: "   " });
    expect(nodes).toHaveLength(4);
    expect(links).toHaveLength(4);
  });

  it("filters to nodes matching the query by name", () => {
    // n3 is 'Mal-A'; searching 'mal' should keep only n3 (isolated → no links)
    const { nodes, links } = toForceGraphData(makePayload(), { query: "mal" });
    expect(nodes.map((n) => n.id)).toEqual(["n3"]);
    expect(links).toHaveLength(0);
  });

  it("keeps edges between two matched nodes", () => {
    // Search 'T10' matches n1 (T1047) and n2 (T1059) — no edge between them,
    // but both connect only to n3/n4 which are filtered out.
    const { nodes } = toForceGraphData(makePayload(), { query: "T10" });
    expect(new Set(nodes.map((n) => n.id))).toEqual(new Set(["n1", "n2"]));
  });

  it("an edge-type match pulls in that edge's endpoints", () => {
    // 'ATTRIBUTED_TO' edges connect n4→n1 and n4→n2; searching the type shows
    // those endpoints and the matching edges even though no node text matches.
    const { nodes, links } = toForceGraphData(makePayload(), { query: "attributed" });
    expect(new Set(nodes.map((n) => n.id))).toEqual(new Set(["n1", "n2", "n4"]));
    expect(links.every((l) => l.type === "ATTRIBUTED_TO")).toBe(true);
    expect(links).toHaveLength(2);
  });

  it("search composes with hiddenTypes", () => {
    // Match the ATTRIBUTED_TO endpoints but hide the type → nodes shown by
    // edge-type match disappear (no node text match, type hidden).
    const { nodes, links } = toForceGraphData(makePayload(), {
      query: "attributed",
      hiddenTypes: new Set(["ATTRIBUTED_TO"]),
    });
    expect(nodes).toHaveLength(0);
    expect(links).toHaveLength(0);
  });

  it("no match yields an empty graph", () => {
    const { nodes, links } = toForceGraphData(makePayload(), { query: "zzz-nomatch" });
    expect(nodes).toHaveLength(0);
    expect(links).toHaveLength(0);
  });
});

/* -------------------------------------------------------------------------- */
/* Field-scoped search                                                         */
/* -------------------------------------------------------------------------- */

describe("nodeMatchesQuery — field scoping", () => {
  const node = {
    id: "attack-pattern--abc",
    label: "Technique",
    labels: ["Technique"],
    name: "Scheduled Task",
    properties: { description: "Adversaries may abuse the Windows Task Scheduler." },
  };

  it("undefined and empty field sets behave like all fields", () => {
    expect(nodeMatchesQuery(node, "scheduled", undefined)).toBe(true);
    expect(nodeMatchesQuery(node, "scheduled", [])).toBe(true);
    expect(nodeMatchesQuery(node, "scheduled", ALL_SEARCH_FIELDS)).toBe(true);
  });

  it("name-only scope matches the name but not id/description/label", () => {
    expect(nodeMatchesQuery(node, "scheduled", ["name"])).toBe(true);
    expect(nodeMatchesQuery(node, "attack-pattern", ["name"])).toBe(false);
    expect(nodeMatchesQuery(node, "adversaries", ["name"])).toBe(false);
    expect(nodeMatchesQuery(node, "technique", ["name"])).toBe(false);
  });

  it("id-only scope matches only the id", () => {
    expect(nodeMatchesQuery(node, "attack-pattern", ["id"])).toBe(true);
    expect(nodeMatchesQuery(node, "scheduled", ["id"])).toBe(false);
  });

  it("description-only scope matches only the description", () => {
    expect(nodeMatchesQuery(node, "adversaries", ["description"])).toBe(true);
    expect(nodeMatchesQuery(node, "scheduled", ["description"])).toBe(false);
  });

  it("label-only scope matches only the labels", () => {
    expect(nodeMatchesQuery(node, "technique", ["label"])).toBe(true);
    expect(nodeMatchesQuery(node, "scheduled", ["label"])).toBe(false);
  });

  it("the type field alone never matches a node", () => {
    expect(nodeMatchesQuery(node, "scheduled", ["type"])).toBe(false);
  });
});

describe("toForceGraphData — field scoping", () => {
  it("excluding the type field disables edge-type seeding", () => {
    const { nodes } = toForceGraphData(makePayload(), {
      query: "attributed",
      fields: ["name", "id", "description", "label"],
    });
    expect(nodes).toHaveLength(0);
  });

  it("type-only scope shows a matched edge's endpoints and nothing else", () => {
    const { nodes, links } = toForceGraphData(makePayload(), {
      query: "attributed",
      fields: ["type"],
    });
    expect(new Set(nodes.map((n) => n.id))).toEqual(new Set(["n1", "n2", "n4"]));
    expect(links.every((l) => l.type === "ATTRIBUTED_TO")).toBe(true);
  });

  it("name-only scope ignores id matches", () => {
    const byName = toForceGraphData(makePayload(), { query: "mal", fields: ["name"] });
    expect(byName.nodes.map((n) => n.id)).toEqual(["n3"]);
    const byId = toForceGraphData(makePayload(), { query: "n1", fields: ["name"] });
    expect(byId.nodes).toHaveLength(0);
  });
});

/* -------------------------------------------------------------------------- */
/* Hop expansion                                                               */
/* -------------------------------------------------------------------------- */

describe("expandByHops", () => {
  const edges = makePayload().edges;
  const allowAll = () => true;

  it("hops = 0 returns the seeds unchanged", () => {
    const out = expandByHops(new Set(["n3"]), edges, 0, allowAll, allowAll);
    expect(out).toEqual(new Set(["n3"]));
  });

  it("expands one hop over undirected edges", () => {
    const out = expandByHops(new Set(["n3"]), edges, 1, allowAll, allowAll);
    expect(out).toEqual(new Set(["n3", "n1", "n2"]));
  });

  it("expands two hops transitively", () => {
    const out = expandByHops(new Set(["n3"]), edges, 2, allowAll, allowAll);
    expect(out).toEqual(new Set(["n3", "n1", "n2", "n4"]));
  });

  it("never crosses a disallowed edge type", () => {
    const out = expandByHops(
      new Set(["n3"]), edges, 3, allowAll, (type) => type !== "USES",
    );
    expect(out).toEqual(new Set(["n3"]));
  });

  it("never reveals a disallowed node but can pass beyond seeds it already holds", () => {
    const out = expandByHops(
      new Set(["n3"]), edges, 2, (id) => id !== "n1", allowAll,
    );
    // n1 blocked; n2 reached hop 1, n4 reached hop 2 via n2.
    expect(out).toEqual(new Set(["n3", "n2", "n4"]));
  });

  it("empty seeds stay empty", () => {
    const out = expandByHops(new Set(), edges, 3, allowAll, allowAll);
    expect(out.size).toBe(0);
  });
});

describe("toForceGraphData — hops neighborhood", () => {
  it("hops = 0 (default) keeps only the matches", () => {
    const { nodes } = toForceGraphData(makePayload(), { query: "mal" });
    expect(nodes.map((n) => n.id)).toEqual(["n3"]);
  });

  it("hops = 1 shows the match plus direct neighbors and connecting edges", () => {
    const { nodes, links } = toForceGraphData(makePayload(), { query: "mal", hops: 1 });
    expect(new Set(nodes.map((n) => n.id))).toEqual(new Set(["n1", "n2", "n3"]));
    expect(new Set(links.map((l) => l.id))).toEqual(new Set(["e1", "e2"]));
  });

  it("hops = 2 reaches the whole component", () => {
    const { nodes, links } = toForceGraphData(makePayload(), { query: "mal", hops: 2 });
    expect(nodes).toHaveLength(4);
    expect(links).toHaveLength(4);
  });

  it("hops never traverses hidden edge types", () => {
    const { nodes } = toForceGraphData(makePayload(), {
      query: "mal",
      hops: 2,
      hiddenTypes: new Set(["USES"]),
    });
    expect(nodes.map((n) => n.id)).toEqual(["n3"]);
  });

  it("hops never reveals hidden-label nodes", () => {
    const { nodes } = toForceGraphData(makePayload(), {
      query: "mal",
      hops: 1,
      hiddenLabels: new Set(["Technique"]),
    });
    expect(nodes.map((n) => n.id)).toEqual(["n3"]);
  });

  it("hops without a query leaves the graph unchanged", () => {
    const { nodes, links } = toForceGraphData(makePayload(), { hops: 3 });
    expect(nodes).toHaveLength(4);
    expect(links).toHaveLength(4);
  });
});
