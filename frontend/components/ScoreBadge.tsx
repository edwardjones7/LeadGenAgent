import clsx from "clsx";

interface Props {
  score: number;
  large?: boolean;
}

export function ScoreBadge({ score, large = false }: Props) {
  const color =
    score >= 9
      ? "text-[#a200ff] border-[#a200ff] shadow-[0_0_10px_rgba(162,0,255,0.4)]"
      : score >= 7
      ? "text-red-400 border-red-400"
      : score >= 4
      ? "text-amber-400 border-amber-400"
      : "text-zinc-400 border-zinc-600";

  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center border rounded font-mono font-bold",
        large ? "w-12 h-12 text-xl" : "w-8 h-6 text-xs",
        color
      )}
    >
      {score}
    </span>
  );
}
