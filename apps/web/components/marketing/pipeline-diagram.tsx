/**
 * Responsive pipeline explanation with a compact list on small screens and
 * the connected overview when enough width is available.
 */
export function PipelineDiagram() {
  const nodes = [
    { label: "Long video", sub: "YouTube / Vimeo" },
    { label: "Transcript", sub: "What people say" },
    { label: "Best moments", sub: "Hook + visuals" },
    { label: "Check", sub: "Real moment" },
    { label: "Vertical clips", sub: "1080×1920 + captions" },
  ];

  return (
    <figure aria-label="ClipFactory pipeline" className="w-full">
      <figcaption className="sr-only">
        From long video to publish-ready vertical shorts
      </figcaption>
      <ol className="grid gap-2 md:hidden">
        {nodes.map((node, index) => (
          <li
            key={node.label}
            className="grid grid-cols-[2.25rem_minmax(0,1fr)] gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-4"
          >
            <span className="font-mono text-xs text-[var(--color-brand)]">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0">
              <strong className="block text-sm">{node.label}</strong>
              <span className="mt-1 block text-xs text-[var(--color-muted-foreground)]">
                {node.sub}
              </span>
              {index === 2 ? (
                <span className="mt-3 inline-flex rounded-full border border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-2.5 py-1 text-[11px] font-semibold text-[var(--color-brand)]">
                  Audience brief applied here
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      <svg
        viewBox="0 0 1000 180"
        role="img"
        aria-labelledby="pipeline-title"
        className="hidden h-auto w-full text-[var(--color-foreground)] md:block"
      >
        <title id="pipeline-title">
          From long video to publish-ready vertical shorts
        </title>
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L10,5 L0,10 z" fill="currentColor" />
          </marker>
        </defs>

        {nodes.map((n, i) => {
          const x = 60 + i * 220;
          return (
            <g key={n.label}>
              <rect
                x={x - 60}
                y={50}
                width={140}
                height={70}
                rx={10}
                fill="var(--color-background)"
                stroke="currentColor"
                strokeWidth={1}
              />
              <text
                x={x}
                y={80}
                textAnchor="middle"
                fontSize={14}
                fontWeight={600}
                fill="currentColor"
              >
                {n.label}
              </text>
              <text
                x={x}
                y={100}
                textAnchor="middle"
                fontSize={11}
                fill="var(--color-muted-foreground)"
              >
                {n.sub}
              </text>
              {i < nodes.length - 1 && (
                <line
                  x1={x + 60}
                  y1={85}
                  x2={x + 160}
                  y2={85}
                  stroke="currentColor"
                  strokeWidth={1}
                  markerEnd="url(#arrow)"
                />
              )}
            </g>
          );
        })}

        {/* "Audience brief" feeding the best-moments box */}
        <g>
          <rect
            x={440}
            y={140}
            width={140}
            height={28}
            rx={6}
            fill="var(--color-brand-soft)"
            stroke="var(--color-brand)"
            strokeWidth={1}
          />
          <text
            x={510}
            y={159}
            textAnchor="middle"
            fontSize={11}
            fontWeight={600}
            fill="var(--color-brand)"
          >
            Audience brief
          </text>
          <line
            x1={510}
            y1={140}
            x2={510}
            y2={122}
            stroke="var(--color-brand)"
            strokeWidth={1}
            markerEnd="url(#arrow)"
          />
        </g>
      </svg>
    </figure>
  );
}
