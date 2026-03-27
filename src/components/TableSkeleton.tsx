import React from "react";
import { Skeleton } from "antd";

export default function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div style={{ background: "#fff", borderRadius: 10, padding: "1rem 1.2rem", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, borderBottom: "1px solid #f0f0f0", paddingBottom: 12 }}>
        {[30, 20, 15, 15, 10, 10].map((w, i) => (
          <Skeleton.Input key={i} active size="small" style={{ width: `${w}%`, minWidth: 40 }} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{ display: "flex", gap: 12, marginBottom: 10 }}>
          {[30, 20, 15, 15, 10, 10].map((w, j) => (
            <Skeleton.Input key={j} active size="small" style={{ width: `${w}%`, minWidth: 40, opacity: 1 - i * 0.08 }} />
          ))}
        </div>
      ))}
    </div>
  );
}
