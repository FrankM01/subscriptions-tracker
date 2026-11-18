import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { Dashboard } from "./pages/Dashboard";
import { SubscriptionDetail } from "./pages/SubscriptionDetail";
import { Subscriptions } from "./pages/Subscriptions";
import { Utilities } from "./pages/Utilities";
import { UtilityDetail } from "./pages/UtilityDetail";
import { Debts } from "./pages/Debts";
import { DebtDetail } from "./pages/DebtDetail";

function NotFound() {
  return <div className="not-found"><div className="eyebrow">PÁGINA NO ENCONTRADA</div><h1>Este camino no existe</h1><p>Vuelve al resumen y seguimos desde ahí.</p><a className="button button-primary" href="/">Ir al resumen</a></div>;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Dashboard />} />
          <Route path="suscripciones" element={<Subscriptions />} />
          <Route path="suscripciones/:subscriptionId" element={<SubscriptionDetail />} />
          <Route path="servicios" element={<Utilities />} />
          <Route path="servicios/:utilityId" element={<UtilityDetail />} />
          <Route path="deudas" element={<Debts />} />
          <Route path="deudas/:debtId" element={<DebtDetail />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
