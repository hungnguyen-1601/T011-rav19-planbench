import { useTranslation } from "@/lib/i18n";

export function TableSkeleton({
  rows = 4,
  columns = 5,
}: {
  rows?: number;
  columns?: number;
}) {
  const { t } = useTranslation();
  return (
    <div
      className="table-scroll"
      role="status"
      aria-busy="true"
      aria-label={t("skeleton.loadingTable")}
    >
      <table>
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i}>
                <div className="skeleton" style={{ height: 16, width: "70%" }} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, r) => (
            <tr key={r}>
              {Array.from({ length: columns }).map((_, c) => (
                <td key={c}>
                  <div
                    className="skeleton"
                    style={{
                      height: 14,
                      width: c === 0 ? "85%" : c === columns - 1 ? "40%" : "60%",
                    }}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PanelSkeleton({ height = 120 }: { height?: number }) {
  const { t } = useTranslation();
  return (
    <div
      className="panel"
      role="status"
      aria-busy="true"
      aria-label={t("skeleton.loadingData")}
      style={{ display: "grid", gap: 12 }}
    >
      <div className="skeleton" style={{ height: 24, width: "30%" }} />
      <div className="skeleton" style={{ height, width: "100%" }} />
    </div>
  );
}

export function LoadingState({
  message,
  inline = false,
}: {
  message?: string;
  inline?: boolean;
}) {
  const { t } = useTranslation();
  const text = message || t("common.loading");

  if (inline) {
    return (
      <span
        className="inline-loading"
        role="status"
        aria-busy="true"
        style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
      >
        <span className="spinner" aria-hidden="true" />
        <span>{text}</span>
      </span>
    );
  }

  return (
    <div
      className="loading-box"
      role="status"
      aria-busy="true"
      aria-label={text}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 10,
        padding: "24px 16px",
      }}
    >
      <span className="spinner" aria-hidden="true" />
      <span className="muted" style={{ fontSize: 14 }}>
        {text}
      </span>
    </div>
  );
}
