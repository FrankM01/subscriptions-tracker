import { useRef, useState, type FormEvent } from "react";
import { api } from "../api";
import { expenseError, expenseQuantity } from "../expenses";
import { todayInLima } from "../format";
import type { Expense, ExpenseCategory, ExpenseSubcategory } from "../types";
import { personalAmount } from "../utilities";

export function ExpenseForm({ expense, categories, onCancel, onSaved }: {
  expense?: Expense; categories: ExpenseCategory[]; onCancel: () => void;
  onSaved: (value: Expense, another: boolean) => void;
}) {
  const [description, setDescription] = useState(expense?.description ?? "");
  const [quantity, setQuantity] = useState(expense?.quantity ?? "1");
  const [amount, setAmount] = useState(expense?.total_amount ?? "");
  const [expenseDate, setExpenseDate] = useState(expense?.expense_date ?? todayInLima());
  const [categoryId, setCategoryId] = useState(expense?.category_id ?? "");
  const [subcategoryId, setSubcategoryId] = useState(expense?.subcategory_id ?? "");
  const [notes, setNotes] = useState(expense?.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const descriptionInput = useRef<HTMLInputElement>(null);
  const category = categories.find((item) => item.category_id === categoryId);
  const child = category?.subcategories.find((item) => item.subcategory_id === subcategoryId);
  const unchangedClassification = !!expense && categoryId === expense.category_id && (subcategoryId || null) === expense.subcategory_id;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    const another = !expense && submitter instanceof HTMLButtonElement && submitter.value === "another";
    const normalized = personalAmount(amount);
    const normalizedQuantity = expenseQuantity(quantity);
    if (!description.trim()) { setError("Escribe el producto o la descripción del gasto."); return; }
    if (!normalized) { setError("Ingresa el importe total positivo, con hasta dos decimales y máximo S/ 9,999,999.99."); return; }
    if (!normalizedQuantity) { setError("Ingresa una cantidad positiva con hasta tres decimales y máximo 999,999.999."); return; }
    if (!expenseDate || expenseDate < "1900-01-01" || expenseDate > todayInLima()) { setError("La fecha debe ser entre 1900 y hoy en Lima."); return; }
    if (!category) { setError("Selecciona una categoría."); return; }
    if (!unchangedClassification && (!category.is_active || subcategoryId && (!child || !child.is_active))) {
      setError("Selecciona una categoría y subcategoría disponibles. Puedes conservar la clasificación archivada original al corregir otros campos."); return;
    }
    pending.current = true; setBusy(true); setError("");
    try {
      const input = { description: description.trim(), quantity: normalizedQuantity, total_amount: normalized,
        expense_date: expenseDate, category_id: categoryId, subcategory_id: subcategoryId || null, notes: notes.trim() || null };
      const result = expense ? await api.updateExpense(expense.expense_id, input) : await api.createExpense(input);
      if (another) {
        setDescription(""); setQuantity("1"); setAmount(""); setCategoryId(""); setSubcategoryId(""); setNotes("");
      }
      onSaved(result, another);
      if (another) requestAnimationFrame(() => descriptionInput.current?.focus());
    } catch (caught) { setError(expenseError(caught)); }
    finally { pending.current = false; setBusy(false); }
  }

  const title = expense ? "Editar gasto" : "Nuevo gasto";
  return <section className="utility-editor expense-editor" aria-label={title}>
    <h2>{title}</h2>
    <form onSubmit={(event) => void submit(event)}>
      {error && <div className="form-error" role="alert">{error}</div>}
      <fieldset className="utility-fields form-stack" disabled={busy}>
        <legend className="sr-only">{title}</legend>
        <label className="field"><span>Producto o descripción</span><input ref={descriptionInput} autoFocus required maxLength={200} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Ej. Almuerzo" /></label>
        <div className="form-grid">
          <label className="field"><span>Cantidad</span><input required inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} aria-describedby="expense-quantity-help" /></label>
          <label className="field"><span>Importe total (S/)</span><input required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" aria-describedby="expense-total-help" /></label>
        </div>
        <p className="utility-help" id="expense-quantity-help">La cantidad admite fracciones, por ejemplo 0.5.</p>
        <p className="utility-help" id="expense-total-help">Es el total que pagaste; no se multiplica por la cantidad. Dos bebidas por S/ 6 registran S/ 6.</p>
        <label className="field"><span>Fecha del gasto</span><input required type="date" min="1900-01-01" max={todayInLima()} value={expenseDate} onChange={(event) => setExpenseDate(event.target.value)} /></label>
        <div className="form-grid">
          <label className="field"><span>Categoría del gasto</span><select required value={categoryId} onChange={(event) => { setCategoryId(event.target.value); setSubcategoryId(""); }}>
            <option value="">Selecciona una categoría</option>
            {categories.filter((item) => item.is_active || item.category_id === expense?.category_id).map((item) => <option key={item.category_id} value={item.category_id}>{item.name}{!item.is_active ? " (archivada)" : ""}</option>)}
          </select></label>
          <label className="field"><span>Subcategoría del gasto (opcional)</span><select value={subcategoryId} disabled={!categoryId} onChange={(event) => setSubcategoryId(event.target.value)}>
            <option value="">Sin subcategoría</option>
            {category?.subcategories.filter((item) => category.is_active && item.is_active || item.subcategory_id === expense?.subcategory_id).map((item) => <option key={item.subcategory_id} value={item.subcategory_id}>{item.name}{!category.is_active || !item.is_active ? " (archivada)" : ""}</option>)}
          </select></label>
        </div>
        {expense && (!category?.is_active || child && !child.is_active) && <p className="utility-notice">La clasificación original está archivada. Puedes conservarla para corregir el gasto o seleccionar otra disponible.</p>}
        <label className="field"><span>Notas (opcional)</span><textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
        <div className="form-actions expense-form-actions">
          <button className="button button-quiet" type="button" onClick={onCancel}>Cancelar</button>
          {!expense && <button className="button button-quiet" type="submit" value="another">Guardar y agregar otro</button>}
          <button className="button button-primary" type="submit" value="save">{busy ? "Guardando…" : "Guardar gasto"}</button>
        </div>
      </fieldset>
    </form>
  </section>;
}

export function ExpenseCategoryForm({ category, subcategory, parentId, onCancel, onSaved }: {
  category?: ExpenseCategory; subcategory?: ExpenseSubcategory; parentId?: string;
  onCancel: () => void; onSaved: () => void;
}) {
  const [name, setName] = useState(subcategory?.name ?? category?.name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const title = `${category || subcategory ? "Renombrar" : "Nueva"} ${parentId ? "subcategoría" : "categoría"}`;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const normalized = name.trim().replace(/\s+/g, " ");
    if (!normalized) { setError("Escribe un nombre."); return; }
    pending.current = true; setBusy(true); setError("");
    try {
      if (parentId) {
        if (subcategory) await api.updateExpenseSubcategory(parentId, subcategory.subcategory_id, { name: normalized });
        else await api.createExpenseSubcategory(parentId, normalized);
      } else if (category) await api.updateExpenseCategory(category.category_id, { name: normalized });
      else await api.createExpenseCategory(normalized);
      onSaved();
    } catch (caught) { setError(expenseError(caught)); }
    finally { pending.current = false; setBusy(false); }
  }
  return <section className="utility-editor" aria-label={title}>
    <h2>{title}</h2>
    <form onSubmit={(event) => void submit(event)}>
      {error && <div className="form-error" role="alert">{error}</div>}
      <fieldset className="utility-fields form-stack" disabled={busy}>
        <legend className="sr-only">{title}</legend>
        <label className="field"><span>Nombre</span><input autoFocus required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <div className="form-actions"><button className="button button-quiet" type="button" onClick={onCancel}>Cancelar</button><button className="button button-primary" type="submit">{busy ? "Guardando…" : "Guardar nombre"}</button></div>
      </fieldset>
    </form>
  </section>;
}
