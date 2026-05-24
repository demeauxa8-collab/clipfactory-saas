/**
 * Inline SVG that explains the pipeline in one glance.
 * Five nodes left-to-right, connected with arrows.
 * Pure SVG, no dependency, no animation in V1 to keep CLS at zero.
 */
export function PipelineDiagram() {
  const nodes = [
    { label: "Long video", sub: "YouTube / Vimeo" },
    { label: "Transcript", sub: "Whisper" },
    { label: "Story arcs", sub: "DeepSeek + Gemini" },
    { label: "Verify", sub: "No hallucination" },
    { label: "Vertical shorts", sub: "1080×1920 + captions" },
  ];

  return (
    <figure aria-label="ClipFactory pipeline" className="overflow-x-auto">
      <svg
        viewBox="0 0 1000 180"
        role="img"
        aria-labelledby="pipeline-title"
        className="h-auto w-full min-w-[720px] text-[var(--color-foreground)]"
      >
        <title id="pipeline-title">From long video to publish-ready vertical shorts</title>
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

        {/* "Campaign brief" feeding the third box (story arcs) */}
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
            Campaign brief
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
