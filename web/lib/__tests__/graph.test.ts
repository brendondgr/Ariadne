import { describe, expect, it } from "vitest";
import {
  LABEL_PALETTE,
  labelColor,
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
