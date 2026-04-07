"use client";

import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type ColumnFiltersState,
} from "@tanstack/react-table";
import { useState, useMemo } from "react";
import { ChevronUp, ChevronDown, Download, Globe, Mail, Filter } from "lucide-react";
import clsx from "clsx";
import { ScoreBadge } from "./ScoreBadge";
import { StatusBadge } from "./StatusBadge";
import { api } from "@/lib/api";
import { LEAD_STATUSES } from "@/lib/constants";
import { OUTREACH_STATUS_LABELS } from "@/lib/constants";
import type { Lead, LeadStatus, OutreachStatus } from "@/lib/types";

const col = createColumnHelper<Lead>();

const SOURCE_COLORS: Record<string, string> = {
  yelp:        "bg-red-500/15 text-red-400 border-red-500/25",
  yellowpages: "bg-yellow-500/15 text-yellow-400 border-yellow-500/25",
  bbb:         "bg-blue-500/15 text-blue-400 border-blue-500/25",
  manta:       "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  superpages:  "bg-cyan-500/15 text-cyan-400 border-cyan-500/25",
};

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return <span className="text-zinc-700 text-xs">—</span>;
  const label = source === "yellowpages" ? "YP" : source.charAt(0).toUpperCase() + source.slice(1);
  return (
    <span className={clsx("inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border", SOURCE_COLORS[source] ?? "bg-zinc-800 text-zinc-400 border-zinc-700")}>
      {label}
    </span>
  );
}

interface Props {
  leads: Lead[];
  loading: boolean;
  onSelectLead: (lead: Lead) => void;
  selectedId: string | null;
}

export function LeadsTable({ leads, loading, onSelectLead, selectedId }: Props) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "score", desc: true }]);
  const [statusFilter, setStatusFilter] = useState<LeadStatus | "All">("All");
  const [minScore, setMinScore] = useState(0);
  const [showFilters, setShowFilters] = useState(false);

  const filtered = useMemo(() => {
    return leads.filter((l) => {
      if (statusFilter !== "All" && l.status !== statusFilter) return false;
      if (l.score < minScore) return false;
      return true;
    });
  }, [leads, statusFilter, minScore]);

  const columns = [
    col.accessor("score", {
      header: "Score",
      cell: (info) => <ScoreBadge score={info.getValue()} />,
      size: 72,
    }),
    col.accessor("business_name", {
      header: "Business",
      cell: (info) => (
        <span className="font-medium text-zinc-100 leading-tight">{info.getValue()}</span>
      ),
    }),
    col.accessor((row) => `${row.city}, ${row.state}`, {
      id: "location",
      header: "Location",
      cell: (info) => <span className="text-zinc-500 text-xs">{info.getValue()}</span>,
      size: 140,
    }),
    col.accessor("phone", {
      header: "Phone",
      cell: (info) => (
        <span className="text-zinc-500 font-mono text-xs">{info.getValue() ?? "—"}</span>
      ),
      size: 130,
    }),
    col.accessor("email", {
      header: "",
      id: "has_email",
      cell: (info) =>
        info.getValue() ? (
          <span title={info.getValue() ?? ""}><Mail size={13} className="text-[#a200ff] opacity-80" /></span>
        ) : (
          <Mail size={13} className="text-zinc-800" />
        ),
      size: 32,
      enableSorting: false,
    }),
    col.accessor("website_url", {
      header: "",
      id: "has_website",
      cell: (info) =>
        info.getValue() ? (
          <Globe size={13} className="text-emerald-500 opacity-80" />
        ) : (
          <Globe size={13} className="text-zinc-800" />
        ),
      size: 32,
      enableSorting: false,
    }),
    col.accessor("source", {
      header: "Source",
      cell: (info) => <SourceBadge source={info.getValue()} />,
      size: 90,
      enableSorting: false,
    }),
    col.accessor("outreach_status", {
      header: "",
      id: "outreach",
      cell: (info) => {
        const v = (info.getValue() ?? "idle") as OutreachStatus;
        if (v === "idle") return null;
        const dot =
          v === "bounced"
            ? "bg-red-500"
            : v.startsWith("emailed")
            ? "bg-emerald-500"
            : "bg-amber-400";
        return (
          <span
            className={`block w-1.5 h-1.5 rounded-full ${dot}`}
            title={OUTREACH_STATUS_LABELS[v] ?? v}
          />
        );
      },
      size: 20,
      enableSorting: false,
    }),
    col.accessor("status", {
      header: "Status",
      cell: (info) => <StatusBadge status={info.getValue() as LeadStatus} />,
      size: 100,
    }),
  ];

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const activeFilters = (statusFilter !== "All" ? 1 : 0) + (minScore > 0 ? 1 : 0);

  return (
    <div className="flex flex-col h-full min-w-0 overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800/80 shrink-0 gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm text-zinc-500">
            <span className="text-zinc-200 font-semibold tabular-nums">{filtered.length}</span>
            {filtered.length !== leads.length && (
              <span className="text-zinc-600"> / {leads.length}</span>
            )}{" "}
            leads
          </span>

          <button
            onClick={() => setShowFilters((v) => !v)}
            className={clsx(
              "flex items-center gap-1.5 text-xs px-2.5 py-1 rounded border transition-all",
              showFilters || activeFilters > 0
                ? "border-[#a200ff]/40 text-[#c060ff] bg-[#a200ff]/10"
                : "border-zinc-800 text-zinc-500 hover:border-zinc-600 hover:text-zinc-300"
            )}
          >
            <Filter size={11} />
            Filter
            {activeFilters > 0 && (
              <span className="bg-[#a200ff] text-white rounded-full w-4 h-4 text-[9px] flex items-center justify-center font-bold">
                {activeFilters}
              </span>
            )}
          </button>
        </div>

        <a
          href={api.exportUrl()}
          download
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-200 border border-zinc-800 hover:border-zinc-600 rounded px-2.5 py-1 transition-colors"
        >
          <Download size={11} />
          Export CSV
        </a>
      </div>

      {/* Filter bar */}
      {showFilters && (
        <div className="flex items-center gap-4 px-4 py-2.5 border-b border-zinc-800/60 bg-zinc-900/30 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-widest">Status</span>
            <div className="flex gap-1">
              {(["All", ...LEAD_STATUSES] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s as LeadStatus | "All")}
                  className={clsx(
                    "px-2.5 py-1 rounded text-xs border transition-all",
                    statusFilter === s
                      ? "bg-[#a200ff]/15 border-[#a200ff]/40 text-[#c060ff]"
                      : "border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                  )}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="h-4 w-px bg-zinc-800" />

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-600 uppercase tracking-widest">Min score</span>
            <div className="flex gap-1">
              {[0, 5, 7, 9].map((n) => (
                <button
                  key={n}
                  onClick={() => setMinScore(n)}
                  className={clsx(
                    "px-2 py-1 rounded text-xs border transition-all font-mono",
                    minScore === n
                      ? "bg-[#a200ff]/15 border-[#a200ff]/40 text-[#c060ff]"
                      : "border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300"
                  )}
                >
                  {n === 0 ? "Any" : `${n}+`}
                </button>
              ))}
            </div>
          </div>

          {activeFilters > 0 && (
            <>
              <div className="h-4 w-px bg-zinc-800" />
              <button
                onClick={() => { setStatusFilter("All"); setMinScore(0); }}
                className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors"
              >
                Clear
              </button>
            </>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-auto flex-1">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-zinc-600">
            <div className="w-6 h-6 border-2 border-[#a200ff]/30 border-t-[#a200ff] rounded-full animate-spin" />
            <span className="text-sm">Loading leads…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-zinc-600 gap-3">
            <div className="w-12 h-12 rounded-xl border border-zinc-800 flex items-center justify-center">
              <Globe size={20} className="text-zinc-700" />
            </div>
            <div className="text-center">
              <p className="text-sm text-zinc-500">
                {leads.length > 0 ? "No leads match your filters" : "No leads yet"}
              </p>
              <p className="text-xs text-zinc-700 mt-1">
                {leads.length > 0 ? "Try adjusting the filters above" : "Run a search to find businesses"}
              </p>
            </div>
          </div>
        ) : (
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 z-10">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-zinc-800/80 bg-[#0c0c12]">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className={clsx(
                        "px-3 py-2.5 text-left text-[10px] text-zinc-600 uppercase tracking-wider select-none font-medium",
                        header.column.getCanSort() && "cursor-pointer hover:text-zinc-300 transition-colors"
                      )}
                      onClick={header.column.getToggleSortingHandler()}
                      style={{ width: header.column.getSize() }}
                    >
                      <span className="flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === "asc" && <ChevronUp size={10} className="text-[#a200ff]" />}
                        {header.column.getIsSorted() === "desc" && <ChevronDown size={10} className="text-[#a200ff]" />}
                      </span>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => {
                const isSelected = row.original.id === selectedId;
                const isHot = row.original.score >= 9;
                return (
                  <tr
                    key={row.id}
                    onClick={() => onSelectLead(row.original)}
                    className={clsx(
                      "border-b border-zinc-800/40 cursor-pointer transition-colors group",
                      isSelected
                        ? "bg-[#a200ff]/8 border-l-2 border-l-[#a200ff]/50"
                        : isHot
                        ? "hover:bg-[#a200ff]/5"
                        : "hover:bg-zinc-800/30"
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className="px-3 py-2.5"
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
