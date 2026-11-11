import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Carregando } from "./components/ui";
import { useAuth } from "./lib/auth";
import Login from "./pages/Login";
import Painel from "./pages/Painel";
import Clientes from "./pages/Clientes";
import Visitas from "./pages/Visitas";
import Projetos from "./pages/Projetos";
import Projeto from "./pages/projeto/Projeto";
import Catalogo from "./pages/Catalogo";
import Antigos from "./pages/Antigos";
import Admin from "./pages/Admin";

export default function App() {
  const { usuario, carregando } = useAuth();
  if (carregando) return <Carregando texto="Iniciando…" />;
  if (!usuario) return <Login />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Painel />} />
        <Route path="/clientes" element={<Clientes />} />
        <Route path="/visitas" element={<Visitas />} />
        <Route path="/visitas/:id" element={<Visitas />} />
        <Route path="/projetos" element={<Projetos />} />
        <Route path="/projetos/:id" element={<Projeto />} />
        <Route path="/projetos/:id/:aba" element={<Projeto />} />
        <Route path="/catalogo" element={<Catalogo />} />
        <Route path="/catalogo/:aba" element={<Catalogo />} />
        <Route path="/antigos" element={<Antigos />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
