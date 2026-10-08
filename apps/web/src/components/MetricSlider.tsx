type MetricSliderProps = {
  label: string;
  value: number;
  onChange: (value: number) => void;
};

export function MetricSlider({ label, value, onChange }: MetricSliderProps) {
  return (
    <label className="metric-slider">
      <span>
        {label}
        <strong>{value}</strong>
      </span>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
