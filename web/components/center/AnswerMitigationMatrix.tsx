"use client";

import { useMemo } from "react";
import type { JoinPair, SynthesisView } from "@/lib/types";
import { labelColor } from "@/lib/graph";
import {
  buildMitigationMatrix,
  cellKey,
  isRenderableMatrix,
} from "@/lib/synthesisMatrix";
import type { EntityDetail } from "@/lib/synthesisGraph";
import { SHADOW } from "@/lib/ui";

/** Whether the technique×mitigation matrix is worth rendering, plus its
 *  counts. Lets the answer card decide if the Mitigation Matrix tab should
 *  appear (and its badge) without rendering the grid. */
export function mitigationMatrixMeta(synthesis: SynthesisView, joinPairs: JoinPair[]) {
  const matrix = buildMitigationMatrix(synthesis, joinPairs);
  return {
    renderable: isRenderableMatrix(matrix),
    techniqueCount: matrix.techniques.length,
    mitigationCount: matrix.mitigations.length,
    cellCount: matrix.cells.size,
  };
}

/** The technique×mitigation coverage grid (rendered inside the Mitigation
 *  Matrix tab): rows are the answer's ATT&CK techniques, columns its
 *  mitigations, and a filled cell marks a `mitigatedBy` relationship. The
 *  same topology the network plot draws, tabulated — coverage and gaps are
 *  visible at a glance instead of traced edge by edge. Renders nothing when
 *  there is no technique→mitigation story to grid. */
export function MitigationMatrixBody({
  synthesis,
  joinPairs,
  entityDetails,
}: {
  synthesis: SynthesisView;
  joinPairs: JoinPair[];
  /** id → {name, label, properties} projected from the turn's federated evidence. */
  entityDetails?: Map<string, EntityDetail>;
}) {
  const matrix = useMemo(
    () => buildMitigationMatrix(synthesis, joinPairs, entityDetails),
    [synthesis, joinPairs, entityDetails],
  );

  if (!isRenderableMatrix(matrix)) return null;

  const markColor = labelColor("Mitigation");
  const abstentions = synthesis.abstentions.length;

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr>
              <th
                scope="col"
                className="whitespace-nowrap pb-1.5 pr-3 align-bottom font-mono text-[9.5px] uppercase tracking-[0.06em] font-normal text-text-muted"
              >
                Technique
              </th>
              {matrix.mitigations.map((m) => (
                <th
                  key={m.id}
                  scope="col"
                  title={m.name}
                  className="whitespace-nowrap px-2 pb-1.5 text-center align-bottom font-mono text-[9.5px] uppercase tracking-[0.06em] font-normal text-text-muted"
                >
                  {m.id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.techniques.map((t) => (
              <tr key={t.id} style={{ boxShadow: SHADOW.insetBottom }}>
                <th scope="row" className="py-2 pr-3 align-top font-normal">
                  <span className="font-mono text-[10.5px] text-text-muted">{t.id}</span>
                  {t.name !== t.id && (
                    <span className="ml-1.5 text-[12px] leading-[1.5] text-text-soft">
                      {t.name}
                    </span>
                  )}
                </th>
                {matrix.mitigations.map((m) => {
                  const covered = matrix.cells.has(cellKey(t.id, m.id));
                  return (
                    <td
                      key={m.id}
                      className="px-2 py-2 text-center align-middle"
                      aria-label={
                        covered
                          ? `${m.id} mitigates ${t.id}`
                          : `${m.id} does not cover ${t.id}`
                      }
                    >
                      {covered ? (
                        <span
                          aria-hidden
                          className="inline-block h-2 w-2 rounded-full"
                          style={{ background: markColor }}
                        />
                      ) : (
                        <span aria-hidden className="font-mono text-[10px] text-text-soft">
                          ·
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="m-0 mt-2 font-mono text-[10.5px] leading-[1.5] text-text-muted">
        {matrix.provenanceExact
          ? "A filled cell is a MITIGATES relationship retrieved from the graph and verifier-checked."
          : "A filled cell is derived from claims citing both ids — not an exact graph relationship."}
        {" "}Hover a column header for the mitigation's name.
        {abstentions > 0 && ` Questions the sources couldn't answer aren't gridded here.`}
      </p>
    </div>
  );
}
