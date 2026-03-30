import React, { useState, useRef, useEffect } from "react";
import { Button, Popover, Checkbox, Divider } from "antd";
import { SettingOutlined } from "@ant-design/icons";
import { theme } from "../theme";

/**
 * Hook que habilita:
 * - Reordenação de colunas por drag-and-drop
 * - Redimensionamento por arraste na borda direita do header
 * - Visibilidade de colunas (mostrar/ocultar via popover)
 * - Persistência das preferências no localStorage (quando tableId fornecido)
 *
 * Retorna: [colunas processadas, botão de configuração]
 */
export function useDraggableColumns<T extends { key?: string | number; dataIndex?: string; width?: number; title?: any }>(
  columns: T[],
  tableId?: string,
  options?: { sectionLabel?: string; extraContent?: React.ReactNode }
): [T[], React.ReactNode] {
  const storageKey = tableId ? `tbl:${tableId}` : null;

  function loadSaved(field: string, def: any) {
    if (!storageKey) return def;
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      return saved[field] ?? def;
    } catch { return def; }
  }

  const getColKey = (col: T, idx: number) => String(col.key ?? col.dataIndex ?? idx);

  const [order, setOrder] = useState<number[]>(() => {
    const saved: number[] | null = loadSaved("order", null);
    if (saved && saved.length === columns.length) return saved;
    return columns.map((_, i) => i);
  });

  const [widths, setWidths] = useState<Record<string, number>>(() => loadSaved("widths", {}));
  const [hidden, setHidden] = useState<Set<string>>(() => new Set<string>(loadSaved("hidden", [])));

  // Reset order when columns array changes size
  useEffect(() => {
    setOrder(columns.map((_, i) => i));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columns.length]);

  // Persist settings to localStorage
  useEffect(() => {
    if (!storageKey) return;
    localStorage.setItem(storageKey, JSON.stringify({
      order,
      widths,
      hidden: Array.from(hidden),
    }));
  }, [order, widths, hidden, storageKey]);

  const dragFrom = useRef<number | null>(null);
  const resizing = useRef(false);
  const resizeStartX = useRef(0);
  const resizeStartW = useRef(0);
  const resizeKey = useRef("");

  const orderedIndices = order.filter(i => i < columns.length);
  const visibleIndices = orderedIndices.filter(i => !hidden.has(getColKey(columns[i], i)));

  const processedColumns = visibleIndices.map((colIdx, visPos) => {
    const col = columns[colIdx];
    const key = getColKey(col, colIdx);
    const currentWidth = widths[key] ?? (col.width as number | undefined);

    return {
      ...col,
      width: currentWidth,
      onHeaderCell: (column: any) => {
        const original = (col as any).onHeaderCell ? (col as any).onHeaderCell(column) : {};
        return {
          ...original,
          style: { ...(original.style || {}), position: "relative", userSelect: "none" },
          draggable: true,
          onDragStart: (e: React.DragEvent<HTMLElement>) => {
            if (resizing.current) { e.preventDefault(); return; }
            dragFrom.current = visPos;
            e.dataTransfer.effectAllowed = "move";
          },
          onDragOver: (e: React.DragEvent<HTMLElement>) => {
            if (resizing.current) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            (e.currentTarget as HTMLElement).style.borderLeft = `2px solid ${theme.accent}`;
          },
          onDragLeave: (e: React.DragEvent<HTMLElement>) => {
            (e.currentTarget as HTMLElement).style.borderLeft = "";
          },
          onDrop: (e: React.DragEvent<HTMLElement>) => {
            e.preventDefault();
            (e.currentTarget as HTMLElement).style.borderLeft = "";
            if (dragFrom.current === null || dragFrom.current === visPos) return;
            // Reorder within visible subset, then reconstruct full order
            const newVisible = [...visibleIndices];
            const [moved] = newVisible.splice(dragFrom.current, 1);
            newVisible.splice(visPos, 0, moved);
            // Slot newVisible back into the full order
            const newOrder = [...orderedIndices];
            let vi = 0;
            for (let i = 0; i < newOrder.length; i++) {
              if (!hidden.has(getColKey(columns[newOrder[i]], newOrder[i]))) {
                newOrder[i] = newVisible[vi++];
              }
            }
            setOrder(newOrder);
            dragFrom.current = null;
          },
          onDragEnd: (e: React.DragEvent<HTMLElement>) => {
            (e.currentTarget as HTMLElement).style.borderLeft = "";
            dragFrom.current = null;
          },
          onMouseMove: (e: React.MouseEvent<HTMLElement>) => {
            const th = e.currentTarget;
            const rect = th.getBoundingClientRect();
            th.style.cursor = e.clientX > rect.right - 8 ? "col-resize" : "grab";
          },
          onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
            if (!resizing.current) (e.currentTarget as HTMLElement).style.cursor = "";
          },
          onMouseDown: (e: React.MouseEvent<HTMLElement>) => {
            const th = e.currentTarget;
            const rect = th.getBoundingClientRect();
            if (e.clientX > rect.right - 8) {
              e.preventDefault();
              e.stopPropagation();
              resizing.current = true;
              resizeStartX.current = e.clientX;
              resizeStartW.current = rect.width;
              resizeKey.current = key;
              const onMove = (me: MouseEvent) => {
                const newW = Math.max(1, resizeStartW.current + (me.clientX - resizeStartX.current));
                setWidths(prev => ({ ...prev, [resizeKey.current]: newW }));
              };
              const onUp = () => {
                resizing.current = false;
                document.removeEventListener("mousemove", onMove);
                document.removeEventListener("mouseup", onUp);
              };
              document.addEventListener("mousemove", onMove);
              document.addEventListener("mouseup", onUp);
            }
          },
        };
      },
    } as T;
  });

  const resetView = () => {
    const defaultOrder = columns.map((_, i) => i);
    setOrder(defaultOrder);
    setWidths({});
    setHidden(new Set());
  };

  const toggleHidden = (key: string) => {
    setHidden(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const colCheckboxes = (
    <div style={{ minWidth: 160 }}>
      {columns.map((col, idx) => {
        const key = getColKey(col, idx);
        const label = typeof col.title === "string"
          ? col.title
          : String(col.dataIndex ?? col.key ?? idx);
        return (
          <div key={key} style={{ padding: "3px 0" }}>
            <Checkbox checked={!hidden.has(key)} onChange={() => toggleHidden(key)}>
              {label}
            </Checkbox>
          </div>
        );
      })}
      <Divider style={{ margin: "8px 0" }} />
      <Button size="small" block onClick={resetView} style={{ color: "#6b7fa3" }}>
        Resetar visualização
      </Button>
    </div>
  );

  const popoverContent = options?.extraContent ? (
    <div style={{ minWidth: 160 }}>
      {options.extraContent}
      {options.sectionLabel && (
        <div style={{ fontWeight: 600, fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: 0.4, color: "#6b7fa3", marginTop: 10, marginBottom: 4 }}>
          {options.sectionLabel}
        </div>
      )}
      {colCheckboxes}
    </div>
  ) : (
    <div style={{ minWidth: 160 }}>
      {options?.sectionLabel && (
        <div style={{ fontWeight: 600, fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: 0.4, color: "#6b7fa3", marginBottom: 4 }}>
          {options.sectionLabel}
        </div>
      )}
      {colCheckboxes}
    </div>
  );

  const settingsButton = (
    <Popover
      trigger="click"
      placement="bottomRight"
      title={options?.extraContent ? "Configurações" : "Colunas visíveis"}
      content={popoverContent}
    >
      <Button
        icon={<SettingOutlined />}
        size="small"
        type="text"
        title="Configurar colunas"
        style={{ color: "#6b7fa3" }}
      />
    </Popover>
  );

  return [processedColumns, settingsButton];
}
