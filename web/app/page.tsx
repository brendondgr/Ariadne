import { WorkbenchProvider } from "@/components/workbench/WorkbenchContext";
import { Workbench } from "@/components/workbench/Workbench";

export default function Page() {
  return (
    <WorkbenchProvider>
      <Workbench />
    </WorkbenchProvider>
  );
}
