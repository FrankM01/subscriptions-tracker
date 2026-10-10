import { NavLink, Outlet } from "react-router-dom";
import { formatDate, todayInLima } from "../format";
import { Icon } from "./Icon";

export function Shell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/" aria-label="Control Budget, ir al panel">
          <span className="brand-mark"><span /></span>
          <span className="brand-copy"><strong>Control Budget</strong><small>Tu espacio personal</small></span>
        </NavLink>
        <div className="sidebar-label">GESTIÓN</div>
        <nav className="main-nav" aria-label="Navegación principal">
          <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            <Icon name="overview" /><span>Resumen</span>
          </NavLink>
          <NavLink to="/suscripciones" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
            <Icon name="subscriptions" /><span>Suscripciones</span>
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <span className="local-dot" />
          <span><strong>Guardado localmente</strong><small>Tus datos permanecen en este equipo</small></span>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="mobile-brand"><span className="brand-mark"><span /></span><strong>Control Budget</strong></div>
          <div className="topbar-date"><span className="date-indicator" />{formatDate(todayInLima())}</div>
        </header>
        <div className="page-content"><Outlet /></div>
      </main>
      <nav className="mobile-nav" aria-label="Navegación principal">
        <NavLink to="/" end className={({ isActive }) => `mobile-nav-link${isActive ? " active" : ""}`}>
          <Icon name="overview" /><span>Resumen</span>
        </NavLink>
        <NavLink to="/suscripciones" className={({ isActive }) => `mobile-nav-link${isActive ? " active" : ""}`}>
          <Icon name="subscriptions" /><span>Suscripciones</span>
        </NavLink>
      </nav>
    </div>
  );
}
