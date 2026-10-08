const cells = Array.from({ length: 35 }, (_, index) => index);

export function ConsistencyHeatmap() {
  return (
    <div className="heatmap" aria-label="Consistency heatmap">
      {cells.map((cell) => (
        <span key={cell} className={`heat-cell level-${cell % 5}`} />
      ))}
    </div>
  );
}
