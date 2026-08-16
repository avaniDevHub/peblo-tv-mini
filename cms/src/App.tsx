import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import type { Role } from "./lib/types";
import ShowsListPage from "./pages/ShowsListPage";
import ShowEditPage from "./pages/ShowEditPage";
import PublishPage from "./pages/PublishPage";

function RoleSwitcher() {
  const { role, setRole } = useAuth();
  return (
    <div className="row" style={{ gap: 8 }}>
      <span className="small muted">Signed in as</span>
      <select
        value={role}
        onChange={(e) => setRole(e.target.value as Role)}
        style={{ width: "auto" }}
        title="Demo role switcher — selects which bearer token the CMS sends"
      >
        <option value="admin">admin (can publish)</option>
        <option value="editor">editor (CRUD only)</option>
      </select>
    </div>
  );
}

export default function App() {
  return (
    <>
      <header className="topbar">
        <span className="brand">📺 Peblo TV — CMS</span>
        <nav className="row">
          <NavLink to="/shows" className={({ isActive }) => (isActive ? "active" : "")}>
            Shows
          </NavLink>
          <NavLink to="/publish" className={({ isActive }) => (isActive ? "active" : "")}>
            Publish
          </NavLink>
        </nav>
        <div className="spacer" />
        <RoleSwitcher />
      </header>
      <main className="container">
        <Routes>
          <Route path="/" element={<Navigate to="/shows" replace />} />
          <Route path="/shows" element={<ShowsListPage />} />
          <Route path="/shows/new" element={<ShowEditPage mode="new" />} />
          <Route path="/shows/:slug" element={<ShowEditPage mode="edit" />} />
          <Route path="/publish" element={<PublishPage />} />
          <Route path="*" element={<div className="state">Not found.</div>} />
        </Routes>
      </main>
    </>
  );
}
