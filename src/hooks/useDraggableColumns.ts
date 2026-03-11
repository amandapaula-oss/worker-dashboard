import { useState, useRef, useCallback } from "react";

/**
 * Hook que habilita reordenação de colunas por drag-and-drop em tabelas Ant Design.
 * Uso: const cols = useDraggableColumns(minhasColunas);
 */
export function useDraggableColumns<T extends { key?: string | number }>(columns: T[]): T[] {
  const [order, setOrder] = useState<number[]>(() => columns.map((_, i) => i));
  const dragFrom = useRef<number | null>(null);

  const getOrderedIndex = useCallback(
    (colIndex: number) => order.indexOf(colIndex),
    [order]
  );

  return order.map((colIdx, orderPos) => {
    const col = columns[colIdx];
    return {
      ...col,
      onHeaderCell: (column: any) => {
        const original = (col as any).onHeaderCell ? (col as any).onHeaderCell(column) : {};
        return {
          ...original,
          draggable: true,
          style: { ...(original.style || {}), cursor: "grab", userSelect: "none" },
          onDragStart: (e: React.DragEvent<HTMLElement>) => {
            dragFrom.current = orderPos;
            e.dataTransfer.effectAllowed = "move";
          },
          onDragOver: (e: React.DragEvent<HTMLElement>) => {
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
        };
      },
    } as T;
  });
}
