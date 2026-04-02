import clsx from "clsx";
import type { LeadStatus } from "@/lib/types";

interface Props {
  status: LeadStatus;
}

const styles: Record<LeadStatus, string> = {
  New: "bg-[#a200ff]/20 text-[#c060ff] border-[#a200ff]/40",
  Contacted: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  Closed: "bg-zinc-700/40 text-zinc-400 border-zinc-600/40",
};

export function StatusBadge({ status }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border",
        styles[status]
      )}
    >
      {status}
    </span>
  );
}
