import clsx from "clsx";

interface Props {
  score: number;
  large?: boolean;
}

export function ScoreBadge({ score, large = false }: Props) {
  const tier =
    score >= 9 ? "hot"
    : score >= 7 ? "high"
    : score >= 4 ? "mid"
    : "low";

  const styles = {
    hot: "text-[#d580ff] border-[#a200ff]/70 bg-[#a200ff]/10 shadow-[0_0_12px_rgba(162,0,255,0.5)]",
    high: "text-red-400 border-red-500/50 bg-red-500/10",
    mid: "text-amber-400 border-amber-500/50 bg-amber-500/10",
    low: "text-zinc-500 border-zinc-700 bg-zinc-800/50",
  };

  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center border rounded font-mono font-bold tabular-nums",
        large ? "w-12 h-12 text-xl rounded-lg" : "w-8 h-6 text-xs",
        styles[tier]
      )}
    >
      {score}
    </span>
  );
}
