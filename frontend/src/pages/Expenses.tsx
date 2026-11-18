import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { ExpenseForm } from "../components/ExpenseForms";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { expenseError, useExpenseCategories } from "../expenses";
import { formatDate, formatMoney, todayInLima } from "../format";
import type { Expense, ExpensePage } from "../types";
import { formatUtilityPeriod, parseUtilityPeriod } from "../utilities";

type Editor = { kind: "new" } | { kind: "edit" | "void" | "restore"; expense: Expense } | null;
const PAGE_SIZE = 50;

export function Expenses() {
  const [params, setParams] = useSearchParams();
  const period = parseUtilityPeriod(params.get("period")) ? params.get("period")! : todayInLima().slice(0, 7);
  const categoryId = params.get("category_id") ?? "";
  const subcategoryId = params.get("subcategory_id") ?? "";
  const search = params.get("search") ?? "";
  const state = params.get("state") === "voided" ? "voided" : params.get("state") === "all" ? "all" : "active";
  const pageNumber = Number(params.get("page") ?? 1);
  const page = Number.isSafeInteger(pageNumber) && pageNumber > 0 && pageNumber <= 1000000 ? pageNumber : 1;
  const catalog = useExpenseCategories();
  const [result, setResult] = useState<ExpensePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [editor, setEditor] = useState<Editor>(null);
  const [busy, setBusy] = useState(false);
  const [searchDraft, setSearchDraft] = useState(search);
  useEffect(() => { setSearchDraft(search); }, [search]);

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    const selected = parseUtilityPeriod(period)!;
    api.listExpenses({ ...selected, category_id: categoryId || undefined, subcategory_id: subcategoryId || undefined,
      search, state, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }).then((value) => {
      if (!active) return;
      if (value.total_count > 0 && value.items.length === 0 && page > 1) {
        setParams((current) => { const next = new URLSearchParams(current); next.set("page", String(Math.ceil(value.total_count / PAGE_SIZE))); return next; }, { replace: true });
      } else setResult(value);
    }).catch((caught: unknown) => { if (active) setError(caught instanceof ApiError ? caught.message : "No se pudieron cargar los gastos."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [period, categoryId, subcategoryId, search, state, page, revision, setParams]);

  function changeFilters(fields: Record<string, string>) {
    setNotice("");
    setParams((current) => {
      const next = new URLSearchParams(current); next.delete("page");
      Object.entries(fields).forEach(([key, value]) => { if (value) next.set(key, value); else next.delete(key); });
      return next;
    });
  }
  function saved(expense: Expense, another: boolean) {
    setNotice(`Gasto guardado. Mostrando ${formatUtilityPeriod(expense.expense_date.slice(0, 7))}.`);
    setActionError("");
    if (!another) setEditor(null);
    setParams({ period: expense.expense_date.slice(0, 7) });
    setRevision((value) => value + 1);
  }
  async function changeState(expense: Expense, restore: boolean) {
    if (busy) return;
    setBusy(true); setActionError("");
    try {
      if (restore) await api.restoreExpense(expense.expense_id);
      else await api.voidExpense(expense.expense_id);
      setEditor(null); setNotice(restore ? "Gasto restaurado." : "Gasto anulado. Puedes recuperarlo desde el filtro Anulados.");
      setRevision((value) => value + 1);
    } catch (caught) { setActionError(expenseError(caught)); }
    finally { setBusy(false); }
  }

  const selectedCategory = catalog.categories.find((item) => item.category_id === categoryId);
  const available = catalog.categories.some((item) => item.is_active) && !catalog.loading && !catalog.error;
  const groups = new Map<string, Expense[]>();
  result?.items.forEach((expense) => groups.set(expense.expense_date, [...(groups.get(expense.expense_date) ?? []), expense]));
  const disabled = !!editor || busy;

  return <>
    <div className="page-heading"><div><h1>Gastos diarios</h1><p>Registra lo que gastas y organiza cada compra por categoría.</p></div>
      <div className="detail-actions"><Link className="button button-quiet" to="/gastos/categorias">Administrar categorías</Link><button className="button button-primary" type="button" disabled={disabled || !available} onClick={() => { setNotice(""); setEditor({ kind: "new" }); }}><Icon name="plus" />Nuevo gasto</button></div>
    </div>
    {notice && <p className="utility-notice" role="status">{notice}</p>}
    {catalog.loading ? <LoadingState label="Cargando categorías…" /> : catalog.error ? <ErrorState message={catalog.error} onRetry={catalog.reload} /> : !available && <p className="utility-notice">Crea o reactiva una categoría para registrar gastos. <Link className="text-link" to="/gastos/categorias">Administrar categorías</Link></p>}
    {editor?.kind === "new" && <ExpenseForm categories={catalog.categories} onCancel={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === "edit" && <ExpenseForm key={editor.expense.expense_id} expense={editor.expense} categories={catalog.categories} onCancel={() => setEditor(null)} onSaved={saved} />}
    {(editor?.kind === "void" || editor?.kind === "restore") && <section className="utility-editor" aria-label={editor.kind === "void" ? "Anular gasto" : "Restaurar gasto"} tabIndex={-1} ref={(node) => { node?.focus(); }}>
      <h2>{editor.kind === "void" ? "Anular" : "Restaurar"} gasto</h2>
      <p>{editor.expense.description} · {formatMoney(editor.expense.total_amount)} · {formatDate(editor.expense.expense_date)}.</p>
      <p>{editor.kind === "void" ? "Se excluirá de los totales y análisis. El registro se conserva y se puede restaurar." : "Volverá a contarse como gasto vigente, conservando su fecha, importe y clasificación original."}</p>
      {actionError && <div className="form-error" role="alert">{actionError}</div>}
      <div className="form-actions"><button className="button button-quiet" disabled={busy} type="button" onClick={() => { setEditor(null); setActionError(""); }}>Cancelar</button><button className="button button-primary" disabled={busy} type="button" onClick={() => void changeState(editor.expense, editor.kind === "restore")}>{busy ? "Guardando…" : editor.kind === "void" ? "Confirmar anulación" : "Restaurar gasto"}</button></div>
    </section>}
    <section className="expense-filters" aria-label="Filtros de gastos">
      <div className="utility-controls">
        <label className="field"><span>Mes de gastos</span><input required type="month" min="1900-01" max="9999-12" disabled={disabled} value={period} onChange={(event) => { if (parseUtilityPeriod(event.target.value)) changeFilters({ period: event.target.value }); }} /></label>
        <label className="field"><span>Filtrar categoría</span><select disabled={disabled || catalog.loading || !!catalog.error} value={categoryId} onChange={(event) => changeFilters({ category_id: event.target.value, subcategory_id: "" })}><option value="">Todas las categorías</option>{catalog.categories.map((category) => <option key={category.category_id} value={category.category_id}>{category.name}{!category.is_active ? " (archivada)" : ""}</option>)}</select></label>
        <label className="field"><span>Filtrar subcategoría</span><select disabled={disabled || !categoryId} value={subcategoryId} onChange={(event) => changeFilters({ subcategory_id: event.target.value })}><option value="">Todas las subcategorías</option>{selectedCategory?.subcategories.map((child) => <option key={child.subcategory_id} value={child.subcategory_id}>{child.name}{!child.is_active || !selectedCategory.is_active ? " (archivada)" : ""}</option>)}</select></label>
        <label className="field"><span>Estado de gastos</span><select disabled={disabled} value={state} onChange={(event) => changeFilters({ state: event.target.value })}><option value="active">Vigentes</option><option value="voided">Anulados</option><option value="all">Todos</option></select></label>
      </div>
      <form className="expense-search" onSubmit={(event) => { event.preventDefault(); changeFilters({ search: searchDraft.trim() }); }}>
        <label className="field"><span>Buscar descripción</span><input type="search" disabled={disabled} maxLength={200} value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} /></label><button type="submit" className="button button-quiet" disabled={disabled}>Buscar</button>
        <button type="button" className="button button-quiet" disabled={disabled} onClick={() => { setSearchDraft(""); setParams({ period }); }}>Limpiar filtros</button>
      </form>
    </section>
    {loading ? <LoadingState label="Cargando gastos…" /> : error ? <ErrorState message={error} onRetry={() => setRevision((value) => value + 1)} /> : result && <section className="list-panel" aria-label="Historial de gastos">
      <div className="list-toolbar utility-catalog-toolbar"><h2>Movimientos</h2><span className="results-count">{result.total_count} {result.total_count === 1 ? "gasto" : "gastos"}</span></div>
      {result.items.length === 0 ? <EmptyState title="No hay gastos con estos filtros" message="Selecciona otro mes o registra un gasto. Los anulados se consultan desde Estado de gastos." action={!disabled && available && state === "active" ? { label: "Registrar gasto", onClick: () => setEditor({ kind: "new" }) } : undefined} /> : <div className="expense-days">{[...groups].map(([day, expenses]) => <section className="expense-day" key={day} aria-label={formatDate(day)}>
        <h3>{formatDate(day)}</h3><ul className="utility-history-list">{expenses.map((expense) => {
          const category = catalog.categories.find((item) => item.category_id === expense.category_id);
          const child = category?.subcategories.find((item) => item.subcategory_id === expense.subcategory_id);
          return <li className="utility-history-row" key={expense.expense_id}>
            <div className="utility-row-copy"><strong>{expense.description}</strong><small>{category?.name ?? "Categoría no disponible"} · {expense.subcategory_id ? child?.name ?? "Subcategoría no disponible" : "Sin subcategoría"}</small><small>Cantidad: {Number(expense.quantity).toLocaleString("es-PE", { maximumFractionDigits: 3 })}{category && (!category.is_active || child && !child.is_active) ? " · clasificación archivada" : ""}</small>{expense.is_voided && <span className="status-badge badge-inactive">Anulado · fuera de totales</span>}{expense.notes && <p className="utility-notes">{expense.notes}</p>}</div>
            <strong className="utility-history-amount">{formatMoney(expense.total_amount)}</strong>
            <div className="utility-entry-actions">{!expense.is_voided && <button className="button button-quiet button-small" type="button" disabled={disabled || catalog.loading || !!catalog.error} onClick={() => { setActionError(""); setEditor({ kind: "edit", expense }); }} aria-label={`Editar gasto ${expense.description}`}>Editar</button>}
              <button className="button button-quiet button-small" type="button" disabled={disabled} onClick={() => { setActionError(""); setEditor({ kind: expense.is_voided ? "restore" : "void", expense }); }} aria-label={`${expense.is_voided ? "Restaurar" : "Anular"} gasto ${expense.description}`}>{expense.is_voided ? "Restaurar" : "Anular"}</button>
            </div>
          </li>;
        })}</ul>
      </section>)}</div>}
      {result.total_count > 0 && <nav className="expense-pagination" aria-label="Páginas de gastos"><button className="button button-quiet" type="button" disabled={disabled || page === 1} onClick={() => setParams((current) => { const next = new URLSearchParams(current); next.set("page", String(page - 1)); return next; })}>Anterior</button><span>Página {page} de {Math.max(1, Math.ceil(result.total_count / PAGE_SIZE))}</span><button className="button button-quiet" type="button" disabled={disabled || page * PAGE_SIZE >= result.total_count} onClick={() => setParams((current) => { const next = new URLSearchParams(current); next.set("page", String(page + 1)); return next; })}>Siguiente</button></nav>}
    </section>}
  </>;
}
