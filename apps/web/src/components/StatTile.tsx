type StatTileProps = {
  label: string;
  value: string;
  tone?: "blue" | "green" | "amber" | "rose";
};

export function StatTile({ label, value, tone = "blue" }: StatTileProps) {
  return (
    <article className={`stat-tile ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
