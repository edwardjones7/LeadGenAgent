"use client";

import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import { ChevronUp, ChevronDown, Download } from "lucide-react";
import clsx from "clsx";
import { ScoreBadge } from "./ScoreBadge";
import { StatusBadge } from "./StatusBadge";
import { api } from "@/lib/api";
import type { Lead } from "@/lib/types";

const col = createColumnHelper<Lead>();

interface Props {
  leads: Lead[];
  loading: boolean;
  onSelectLead: (lead: Lead) => void;
  selectedId: string | null;
}

export function LeadsTable({ leads, loading, onSelectLead, selectedId }: Props) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "score", desc: true }]);

  const columns = [
    col.accessor("score", {
      header: "Score",
      cell: (info) => <ScoreBadge score={info.getValue()} />,
      size: 70,
    }),
    col.accessor("business_name", {
      header: "Business",
      cell: (info) => (
        <span className="font-medium text-zinc-100">{info.getValue()}</span>
      ),
    }),
    col.accessor((row) => `${row.city}, ${row.state}`, {
      id: "location",
      header: "Location",
      cell: (info) => <span className="text-zinc-400">{info.getValue()}</span>,
    }),
    col.accessor("phone", {
      header: "Phone",
      cell: (info) => (
        <span className="text-zinc-400 font-mono text-xs">{info.getValue() ?? "—"}</span>
      ),
    }),
    col.accessor("category", {
      header: "Category",
      cell: (info) => (
        <span className="capitalize text-zinc-500 text-xs">{info.getValue() ?? "—"}</span>
      ),
    }),
    col.accessor("status", {
      header: "Status",
      cell: (info) => <StatusBadge status={info.getValue() as Lead["status"]} />,
    }),
    col.accessor("created_at", {
      header: "Added",
      cell: (info) => {
        const val = info.getValue();
        if (!val) return <span className="text-zinc-600">—</span>;
        return (
          <span className="text-zinc-500 text-xs">
            {new Date(val).toLocaleDateString()}
          </span>
        );
      },
    }),
  ];

  const table = useReactTable({
    data: leads,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
      {/* Table header bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 shrink-0">
        <span className="text-sm text-zinc-400">
          <span className="text-zinc-100 font-semibold">{leads.length}</span> leads
        </span>
        <a
          href={api.exportUrl()}
          download
          className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 border border-zinc-700 hover:border-zinc-500 rounded px-2.5 py-1.5 transition-colors"
        >
          <Download size={12} />
          Export CSV
        </a>
      </div>

      {/* Table */}
      <div className="overflow-auto flex-1">
        {loading ? (
          <div className="flex items-center justify-center h-48 text-zinc-500 text-sm">
            Loading leads…
          </div>
        ) : leads.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-zinc-600 text-sm gap-2">
            <span>No leads yet.</span>
            <span className="text-xs">Run a search to find businesses.</span>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-zinc-800">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className={clsx(
                        "px-4 py-2.5 text-left text-xs text-zinc-500 uppercase tracking-wider select-none",
                        header.column.getCanSort() && "cursor-pointer hover:text-zinc-300"
                      )}
                      onClick={header.column.getToggleSortingHandler()}
                      style={{ width: header.getSize() }}
                    >
                      <span className="flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === "asc" && <ChevronUp size={12} />}
                        {header.column.getIsSorted() === "desc" && <ChevronDown size={12} />}
                      </span>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => onSelectLead(row.original)}
                  className={clsx(
                    "border-b border-zinc-800/50 cursor-pointer transition-colors",
                    row.original.id === selectedId
                      ? "bg-[#a200ff]/10"
                      : "hover:bg-zinc-800/40"
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-2.5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
