"use client";

import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { MenuIcon } from "@/components/ui/icons";

/** Hamburger that opens the conversations drawer on small screens (<md). */
export function MobileMenuButton() {
  const { setLeftOpen } = useWorkbench();
  return (
    <button
      type="button"
      onClick={() => setLeftOpen(true)}
      aria-label="Open conversations"
      className="flex h-9 w-9 items-center justify-center rounded-lg border-0 bg-transparent text-text-muted shadow-border-strong hover:text-primary md:hidden"
    >
      <MenuIcon />
    </button>
  );
}
