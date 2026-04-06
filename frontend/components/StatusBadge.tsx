import clsx from "clsx";
import type { LeadStatus } from "@/lib/types";

interface Props {
  status: LeadStatus;
}

const config: Record<LeadStatus, { dot: string; pill: string }> = {
  New:       { dot: "bg-[#a200ff]", pill: "bg-[#a200ff]/10 text-[#c878ff] border-[#a200ff]/30" },
  Contacted: { dot: "bg-blue-400",  pill: "bg-blue-500/10 text-blue-300 border-blue-500/30" },
  Closed:    { dot: "bg-zinc-600",  pill: "bg-zinc-800/60 text-zinc-500 border-zinc-700/50" },
};

export function StatusBadge({ status }: Props) {
  const { dot, pill } = config[status] ?? config.New;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border", pill)}>
      <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", dot)} />
      {status}
    </span>
  );
}
