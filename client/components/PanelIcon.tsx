type PanelIconKind = "identity" | "rule" | "scope" | "guidance" | "test";

const paths: Record<PanelIconKind, string[]> = {
  identity: ["M7.5 5.5h9v13h-9z", "M10 9h4M10 12h4M10 15h2.5"],
  rule: ["M5 7h14M5 12h9M5 17h11", "m16.5 14.5 2 2 3.5-4"],
  scope: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "M3 12h18M12 3c2.2 2.5 3.3 5.5 3.3 9S14.2 18.5 12 21c-2.2-2.5-3.3-5.5-3.3-9S9.8 5.5 12 3Z"],
  guidance: ["M5 5h14v14H5z", "m8 12 2.2 2.2L16 8.5"],
  test: ["M8 3h8M10 3v6l-4.5 8.4A2.4 2.4 0 0 0 7.6 21h8.8a2.4 2.4 0 0 0 2.1-3.6L14 9V3", "M8 16h8"],
};

export function PanelIcon({ kind }: { kind: PanelIconKind }) {
  return (
    <svg className="panel-icon" aria-hidden="true" viewBox="0 0 24 24">
      {paths[kind].map((path) => <path d={path} key={path} />)}
    </svg>
  );
}
