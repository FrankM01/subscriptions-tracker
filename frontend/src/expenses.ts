import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { ExpenseCategory } from "./types";

export function expenseError(error: unknown): string {
  return error instanceof ApiError ? error.message : "No se pudo guardar. Intenta nuevamente.";
}

export function expenseQuantity(value: string): string | null {
  const normalized = value.trim().replace(",", ".");
  return /^[0-9]{1,6}(\.[0-9]{1,3})?$/.test(normalized) && Number(normalized) > 0 ? normalized : null;
}

export function useExpenseCategories() {
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    api.listExpenseCategories().then((value) => { if (active) setCategories(value); })
      .catch((caught: unknown) => { if (active) setError(caught instanceof ApiError ? caught.message : "No se pudieron cargar las categorías."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [revision]);
  return { categories, loading, error, reload: () => setRevision((value) => value + 1) };
}
