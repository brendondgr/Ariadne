import type { FederatedEvidence } from "@/lib/types";
import { CodeBlock } from "@/components/ui/CodeBlock";

/** The full federated bundle — `evidence.to_dict()`. */
export function RawJsonTab({ federated }: { federated: FederatedEvidence }) {
  return (
    <div>
      <div className="mb-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
        FederatedEvidence · evidence.to_dict()
      </div>
      <CodeBlock code={JSON.stringify(federated, null, 2)} lang="json" className="text-[10.5px] leading-[1.7]" />
    </div>
  );
}
