import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ExpenseCategoryForm } from "../components/ExpenseForms";
import { EmptyState, ErrorState, LoadingState } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { expenseError, useExpenseCategories } from "../expenses";
import type { ExpenseCategory, ExpenseSubcategory } from "../types";

type Editor = { kind: "category"; category?: ExpenseCategory } | { kind: "subcategory"; parent: ExpenseCategory; subcategory?: ExpenseSubcategory } | null;

export function ExpenseCategories() {
  const catalog = useExpenseCategories();
  const [editor, setEditor] = useState<Editor>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const disabled = !!editor || busy || catalog.loading;
  function saved() { setEditor(null); setNotice("Categoría guardada."); catalog.reload(); }
  async function toggle(category: ExpenseCategory, child?: ExpenseSubcategory) {
    if (busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (child) await api.updateExpenseSubcategory(category.category_id, child.subcategory_id, { is_active: !child.is_active });
      else await api.updateExpenseCategory(category.category_id, { is_active: !category.is_active });
      setNotice(`${child ? "Subcategoría" : "Categoría"} ${ (child ?? category).is_active ? "archivada" : "reactivada"}. Los gastos históricos se conservan.`);
      catalog.reload();
    } catch (caught) { setError(expenseError(caught)); }
    finally { setBusy(false); }
  }
  return <>
    <Link className="back-link" to="/gastos">Volver a gastos diarios</Link>
    <div className="page-heading"><div><h1>Categorías de gastos</h1><p>Organiza tus gastos en categorías y subcategorías propias.</p></div><button className="button button-primary" type="button" disabled={disabled} onClick={() => { setNotice(""); setEditor({ kind: "category" }); }}><Icon name="plus" />Nueva categoría</button></div>
    <p className="utility-help">Archivar impide nuevas asignaciones, pero conserva el historial y sus importes. Una subcategoría no cambia de categoría principal.</p>
    {notice && <p className="utility-notice" role="status">{notice}</p>}
    {error && <div className="form-error" role="alert">{error}</div>}
    {editor?.kind === "category" && <ExpenseCategoryForm category={editor.category} onCancel={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === "subcategory" && <ExpenseCategoryForm key={editor.subcategory?.subcategory_id ?? editor.parent.category_id} parentId={editor.parent.category_id} subcategory={editor.subcategory} onCancel={() => setEditor(null)} onSaved={saved} />}
    {catalog.loading ? <LoadingState label="Cargando categorías…" /> : catalog.error ? <ErrorState message={catalog.error} onRetry={catalog.reload} /> : catalog.categories.length === 0 ? <EmptyState title="Aún no hay categorías" message="Crea tu primera categoría para comenzar a registrar gastos." /> : <section className="list-panel" aria-label="Catálogo de categorías"><ul className="expense-category-list">{catalog.categories.map((category) => <li key={category.category_id}>
      <div className="expense-category-heading"><div className="utility-row-copy"><h2>{category.name}</h2><small>{category.is_active ? "Activa" : "Archivada"}</small></div><div className="utility-entry-actions">
        <button className="button button-quiet button-small" type="button" disabled={disabled} aria-label={`Renombrar categoría ${category.name}`} onClick={() => setEditor({ kind: "category", category })}>Renombrar</button>
        <button className="button button-quiet button-small" type="button" disabled={disabled} aria-label={`${category.is_active ? "Archivar" : "Reactivar"} categoría ${category.name}`} onClick={() => void toggle(category)}>{category.is_active ? "Archivar" : "Reactivar"}</button>
        <button className="button button-quiet button-small" type="button" disabled={disabled || !category.is_active} aria-label={`Agregar subcategoría a ${category.name}`} onClick={() => setEditor({ kind: "subcategory", parent: category })}>Agregar subcategoría</button>
      </div></div>
      {category.subcategories.length === 0 ? <p className="utility-help">Sin subcategorías. Puedes registrar gastos solo con esta categoría.</p> : <ul className="expense-subcategory-list">{category.subcategories.map((child) => <li key={child.subcategory_id}><div className="utility-row-copy"><strong>{child.name}</strong><small>{!child.is_active ? "Archivada" : !category.is_active ? "No disponible: categoría principal archivada" : "Activa"}</small></div><div className="utility-entry-actions"><button className="button button-quiet button-small" type="button" disabled={disabled} aria-label={`Renombrar subcategoría ${child.name} de ${category.name}`} onClick={() => setEditor({ kind: "subcategory", parent: category, subcategory: child })}>Renombrar</button><button className="button button-quiet button-small" type="button" disabled={disabled || !category.is_active && !child.is_active} aria-label={`${child.is_active ? "Archivar" : "Reactivar"} subcategoría ${child.name} de ${category.name}`} onClick={() => void toggle(category, child)}>{child.is_active ? "Archivar" : "Reactivar"}</button></div></li>)}</ul>}
    </li>)}</ul></section>}
  </>;
}
