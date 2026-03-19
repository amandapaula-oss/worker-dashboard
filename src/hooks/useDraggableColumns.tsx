import React, { useState, useRef } from "react";

/**
 * Hook que habilita reordenação de colunas por drag-and-drop
 * E redimensionamento por arraste na borda direita do header.
 */
export function useDraggableColumns<T extends { key?: string | number; dataIndex?: string; width?: number }>(columns: T[]): T[] {
  const [order, setOrder] = useState<number[]>(() => columns.map((_, i) => i));
  const [widths, setWidths] = useState<Record<string, number>>({});
  const dragFrom = useRef<number | null>(null);
  const resizing = useRef(false);
  const resizeStartX = useRef(0);
  const resizeStartW = useRef(0);
  const resizeKey = useRef("");

  return order.map((colIdx, orderPos) => {
    const col = columns[colIdx];
    const key = String(col.key ?? col.dataIndex ?? colIdx);
    const currentWidth = widths[key] ?? (col.width as number | undefined);

    return {
      ...col,
      width: currentWidth,
      onHeaderCell: (column: any) => {
        const original = (col as any).onHeaderCell ? (col as any).onHeaderCell(column) : {};
        return {
          ...original,
          style: { ...(original.style || {}), position: "relative", userSelect: "none" },
          // Drag-to-reorder (only when not resizing)
          draggable: true,
          onDragStart: (e: React.DragEvent<HTMLElement>) => {
            if (resizing.current) { e.preventDefault(); return; }
            dragFrom.current = orderPos;
            e.dataTransfer.effectAllowed = "move";
          },
          onDragOver: (e: React.DragEvent<HTMLElement>) => {
            if (resizing.current) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            (e.currentTarget as HTMLElement).style.borderLeft = "2px solid #2d50a0";
          },
          onDragLeave: (e: React.DragEvent<HTMLElement>) => {
            (e.currentTarget as HTMLElement).style.borderLeft = "";
          },
          onDrop: (e: React.DragEvent<HTMLElement>) => {
            e.preventDefault();
            (e.currentTarget as HTMLElement).style.borderLeft = "";
            if (dragFrom.current === null || dragFrom.current === orderPos) return;
            const newOrder = [...order];
            const [moved] = newOrder.splice(dragFrom.current, 1);
            newOrder.splice(orderPos, 0, moved);
            setOrder(newOrder);
            dragFrom.current = null;
          },
          onDragEnd: (e: React.DragEvent<HTMLElement>) => {
            (e.currentTarget as HTMLElement).style.borderLeft = "";
            dragFrom.current = null;
          },
          // Resize via mousedown on the right edge
          onMouseMove: (e: React.MouseEvent<HTMLElement>) => {
            const th = e.currentTarget;
            const rect = th.getBoundingClientRect();
            if (e.clientX > rect.right - 8) {
              th.style.cursor = "col-resize";
            } else {
              th.style.cursor = "grab";
            }
          },
          onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
            if (!resizing.current) (e.currentTarget as HTMLElement).style.cursor = "";
          },
          onMouseDown: (e: React.MouseEvent<HTMLElement>) => {
            const th = e.currentTarget;
            const rect = th.getBoundingClientRect();
            if (e.clientX > rect.right - 8) {
              // Start resize
              e.preventDefault();
              e.stopPropagation();
              resizing.current = true;
              resizeStartX.current = e.clientX;
              resizeStartW.current = rect.width;
              resizeKey.current = key;

              const onMove = (me: MouseEvent) => {
                const delta = me.clientX - resizeStartX.current;
                const newW = Math.max(50, resizeStartW.current + delta);
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
}
