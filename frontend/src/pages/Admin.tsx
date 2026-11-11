import { useState } from "react";
import { Abas, Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox, Selo } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dataHora } from "../lib/format";
import { useCarregar } from "../lib/hooks";

function Versao() {
  const { dados } = useCarregar(() => Promise.all([api.get("/admin/versao"), api.get<any[]>("/admin/versoes")]));
  if (!dados) return <Carregando />;
  const [v, hist] = dados;
  return (
    <>
      <Cartao titulo="Versão instalada">
        <table><tbody>
          <tr><th>Ambiente</th><td>{v.ambiente}</td></tr>
          <tr><th>Versão do software</th><td>{v.versao}</td></tr>
          <tr><th>Commit (git)</th><td><code>{v.git_sha}</code></td></tr>
          <tr><th>Data do build</th><td>{v.data_build || "—"}</td></tr>
          <tr><th>Motor de cálculo</th><td>{v.versao_motor}</td></tr>
          <tr><th>Migração do banco</th><td><code>{v.migracao_banco || "—"}</code></td></tr>
          <tr><th>Banco de dados</th><td>{v.banco}</td></tr>
        </tbody></table>
      </Cartao>
      <Cartao titulo="Histórico de atualizações neste ambiente">
        <table>
          <thead><tr><th>Implantada em</th><th>Versão</th><th>Commit</th><th>Ambiente</th><th>Notas</th></tr></thead>
          <tbody>{hist.map((h) => <tr key={h.id}><td>{dataHora(h.implantado_em)}</td><td>{h.versao}</td><td><code>{String(h.git_sha).slice(0, 12)}</code></td><td>{h.ambiente}</td><td>{h.notas}</td></tr>)}</tbody>
        </table>
      </Cartao>
    </>
  );
}

function Usuarios() {
  const { pode } = useAuth();
  const { dados, erro, recarregar } = useCarregar(() => Promise.all([api.get<any[]>("/usuarios"), api.get("/perfis")]));
  const [form, setForm] = useState<any>(null);
  const [erroF, setErroF] = useState<unknown>(null);
  if (!pode("usuarios.gerenciar")) return <Alerta tipo="info">Somente administradores gerenciam usuários.</Alerta>;
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const [usuarios, perfis] = dados;
  const salvar = async () => {
    setErroF(null);
    try {
      if (form.id) {
        const c: any = { nome: form.nome, perfil: form.perfil, ativo: form.ativo, registro_profissional: form.registro_profissional || null };
        if (form.senha) c.senha = form.senha;
        await api.put(`/usuarios/${form.id}`, c);
      } else await api.post("/usuarios", form);
      setForm(null);
      recarregar();
    } catch (e) { setErroF(e); }
  };
  return (
    <>
      {form && (
        <Cartao titulo={form.id ? `Editar ${form.email}` : "Novo usuário"}>
          <div className="grade g3">
            <Campo rotulo="E-mail"><input value={form.email || ""} disabled={!!form.id} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Campo>
            <Campo rotulo="Nome"><input value={form.nome || ""} onChange={(e) => setForm({ ...form, nome: e.target.value })} /></Campo>
            <Campo rotulo="Perfil">
              <select value={form.perfil} onChange={(e) => setForm({ ...form, perfil: e.target.value })}>
                {Object.entries(perfis.perfis).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}
              </select>
            </Campo>
            <Campo rotulo="Registro profissional (CREA/CFT)"><input value={form.registro_profissional || ""} onChange={(e) => setForm({ ...form, registro_profissional: e.target.value })} /></Campo>
            <Campo rotulo={form.id ? "Nova senha (opcional)" : "Senha (mín. 8)"}><input type="password" value={form.senha || ""} onChange={(e) => setForm({ ...form, senha: e.target.value })} /></Campo>
            {form.id && <label><input type="checkbox" checked={form.ativo} onChange={(e) => setForm({ ...form, ativo: e.target.checked })} /> Ativo</label>}
          </div>
          <ErroBox erro={erroF} />
          <div className="acoes" style={{ marginTop: 8 }}><BotaoAcao className="btn btn-primario" onClick={salvar}>Salvar</BotaoAcao><button className="btn" onClick={() => setForm(null)}>Cancelar</button></div>
        </Cartao>
      )}
      <Cartao titulo="Usuários" acoes={<button className="btn btn-primario" onClick={() => setForm({ perfil: "projetista" })}>Novo usuário</button>}>
        <table>
          <thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Registro</th><th>Situação</th><th></th></tr></thead>
          <tbody>{usuarios.map((u) => (
            <tr key={u.id}><td>{u.nome}</td><td>{u.email}</td><td>{u.perfil_nome}</td><td>{u.registro_profissional}</td>
              <td>{u.ativo ? <Selo tipo="ok">ativo</Selo> : <Selo tipo="erro">inativo</Selo>}</td>
              <td><button className="btn btn-mini" onClick={() => setForm({ ...u, senha: "" })}>Editar</button></td></tr>
          ))}</tbody>
        </table>
      </Cartao>
      <Cartao titulo="Matriz de permissões">
        <div className="tabela-rolagem">
          <table>
            <thead><tr><th>Permissão</th>{Object.values(perfis.perfis).map((p: any) => <th key={p}>{p}</th>)}</tr></thead>
            <tbody>{Object.entries(perfis.permissoes).map(([k, v]) => (
              <tr key={k}><td>{v as string}</td>{Object.keys(perfis.perfis).map((pf) => <td key={pf} style={{ textAlign: "center" }}>{perfis.matriz[pf].includes(k) ? "✔" : ""}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      </Cartao>
    </>
  );
}

function Auditoria() {
  const [ent, setEnt] = useState("");
  const { dados, erro } = useCarregar(() => api.get<any[]>(`/admin/auditoria?limite=500${ent ? `&entidade=${ent}` : ""}`), [ent]);
  return (
    <Cartao titulo="Auditoria geral" acoes={
      <select value={ent} onChange={(e) => setEnt(e.target.value)} style={{ width: 200 }}>
        <option value="">Todas as entidades</option>
        {["projeto", "usuario", "cliente", "visita", "exaustor", "componente", "parametro", "arquivo", "projeto_antigo"].map((x) => <option key={x}>{x}</option>)}
      </select>}>
      <ErroBox erro={erro} />
      {!dados ? <Carregando /> : (
        <div className="tabela-rolagem">
          <table>
            <thead><tr><th>Data</th><th>Usuário</th><th>Ação</th><th>Entidade</th><th>Detalhes</th></tr></thead>
            <tbody>{dados.map((a) => <tr key={a.id}><td>{dataHora(a.criado_em)}</td><td>{a.usuario_nome}</td><td>{a.acao}</td><td>{a.entidade} {a.entidade_id}</td>
              <td><code style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{a.detalhes ? JSON.stringify(a.detalhes).slice(0, 300) : ""}</code></td></tr>)}</tbody>
          </table>
        </div>
      )}
    </Cartao>
  );
}

export default function Admin() {
  const [aba, setAba] = useState("versao");
  const { usuario } = useAuth();
  return (
    <div>
      <div className="cabecalho"><div><h1>Administração</h1><div className="sub">Conectado como {usuario?.nome}</div></div></div>
      <Abas abas={[{ id: "versao", rotulo: "Versão e atualizações" }, { id: "usuarios", rotulo: "Usuários e permissões" }, { id: "auditoria", rotulo: "Auditoria" }]} ativa={aba} onChange={setAba} />
      {aba === "versao" && <Versao />}
      {aba === "usuarios" && <Usuarios />}
      {aba === "auditoria" && <Auditoria />}
    </div>
  );
}
