import { useId, useState } from "react";
import { useExpenseSummary } from "../expenses";
import { formatDate, formatMoney } from "../format";
import type { ExpenseGroupTotal, ExpenseSummaryFilters } from "../types";
import { EmptyState, ErrorState, LoadingState } from "./Feedback";

function GroupChart({ title, groups, subcategories = false }: { title: string; groups: ExpenseGroupTotal[]; subcategories?: boolean }) {
  const id = useId();
  const max = Math.max(1, ...groups.map((group) => Number(group.total_amount)));
  const name = (group: ExpenseGroupTotal) => subcategories ? `${group.category_name} · ${group.subcategory_name ?? "Sin subcategoría"}` : group.category_name;
  return <section className="expense-chart" aria-labelledby={id}>
    <h3 id={id}>{title}</h3>
    <ul className="expense-bars" aria-label={`Gráfico: ${title}`}>{groups.map((group) => <li key={`${group.category_id}-${group.subcategory_id ?? "none"}`}>
      <div><span>{name(group)}</span><strong>{formatMoney(group.total_amount)}</strong></div>
      <svg viewBox="0 0 600 12" preserveAspectRatio="none" aria-hidden="true"><rect className="expense-bar-track" width="600" height="12" rx="3" /><rect className="expense-bar-fill" width={Number(group.total_amount) / max * 600} height="12" rx="3" /></svg>
    </li>)}</ul>
    <details className="expense-chart-data"><summary>Ver tabla: {title.toLocaleLowerCase("es")}</summary><div className="expense-table-wrap"><table><caption>{title}: importes de gastos vigentes</caption><thead><tr><th scope="col">{subcategories ? "Categoría · Subcategoría" : "Categoría"}</th><th scope="col">Gastos</th><th scope="col">Total</th></tr></thead><tbody>{groups.map((group) => <tr key={`${group.category_id}-${group.subcategory_id ?? "none"}`}><th scope="row">{name(group)}</th><td>{group.count}</td><td>{formatMoney(group.total_amount)}</td></tr>)}</tbody></table></div></details>
  </section>;
}

export function ExpenseAnalysis({ filters }: { filters: ExpenseSummaryFilters }) {
  const { summary, loading, error, reload } = useExpenseSummary(filters);
  const [cumulative, setCumulative] = useState(false);
  const id = useId();
  if (loading) return <LoadingState label="Cargando análisis de gastos…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!summary) return null;
  const values = summary.days.map((day) => Number(cumulative ? day.cumulative_amount : day.total_amount));
  const max = Math.max(1, ...values);
  const x = (index: number) => 45 + index / Math.max(1, values.length - 1) * 630;
  const y = (value: number) => 195 - value / max * 165;
  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(" ");
  return <section className="expense-analysis" aria-label="Análisis mensual de gastos">
    <div className="expense-analysis-total"><div><h2>Total del período</h2><p>Solo gastos vigentes que coinciden con los filtros. Los anulados están excluidos.</p></div><div><strong>{formatMoney(summary.total_amount)}</strong><span>{summary.count} {summary.count === 1 ? "gasto" : "gastos"}</span></div></div>
    {summary.count === 0 ? <EmptyState title="No hay gastos vigentes con estos filtros" message="Selecciona otro mes, ajusta los filtros o registra un gasto desde Movimientos. No se proyectan gastos futuros." /> : <>
      <GroupChart title="Por categoría" groups={summary.categories} />
      <GroupChart title="Por subcategoría" groups={summary.subcategories} subcategories />
      <section className="expense-chart" aria-labelledby={id}>
        <div className="expense-chart-heading"><h3 id={id}>Evolución del gasto</h3><div className="expense-mode" role="group" aria-label="Tipo de evolución"><button className="button button-quiet" type="button" aria-pressed={!cumulative} onClick={() => setCumulative(false)}>Diario</button><button className="button button-quiet" type="button" aria-pressed={cumulative} onClick={() => setCumulative(true)}>Acumulado</button></div></div>
        <p className="utility-help">{cumulative ? "Suma acumulada desde el primer día del mes. Los días sin gastos mantienen el acumulado." : "Importe registrado cada día. Los días transcurridos sin gastos muestran cero."} No se incluyen días futuros.</p>
        <p className="expense-chart-scale">Escala máxima: {formatMoney(String(max))}</p>
        <svg className="expense-timeline" viewBox="0 0 720 210" role="img" aria-label={`Evolución ${cumulative ? "acumulada" : "diaria"} del gasto en soles; datos completos en la tabla siguiente`}>
          <line x1="45" x2="675" y1="195" y2="195" className="expense-axis" />
          <line x1="45" x2="675" y1="30" y2="30" className="expense-axis" />
          <polyline points={points} className="expense-line" />
          {values.map((value, index) => <circle key={index} cx={x(index)} cy={y(value)} r="3" className="expense-point"><title>{formatDate(summary.days[index].expense_date)}: {formatMoney(cumulative ? summary.days[index].cumulative_amount : summary.days[index].total_amount)}</title></circle>)}
        </svg>
        <div className="expense-chart-days" aria-hidden="true"><span>Día 1</span><span>Día {summary.days.length}</span></div>
        <details className="expense-chart-data"><summary>Ver tabla de evolución diaria y acumulada</summary><div className="expense-table-wrap"><table><caption>Evolución del gasto: días transcurridos del período</caption><thead><tr><th scope="col">Fecha</th><th scope="col">Gastos</th><th scope="col">Diario</th><th scope="col">Acumulado</th></tr></thead><tbody>{summary.days.map((day) => <tr key={day.expense_date}><th scope="row">{formatDate(day.expense_date)}</th><td>{day.count}</td><td>{formatMoney(day.total_amount)}</td><td>{formatMoney(day.cumulative_amount)}</td></tr>)}</tbody></table></div></details>
      </section>
    </>}
  </section>;
}
