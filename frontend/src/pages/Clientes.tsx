import { useState } from "react";
import { Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox, SeloDemo } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useCarregar } from "../lib/hooks";

const VAZIO = { nome: "", industria: "", cnpj: "", endereco: "", contato_nome: "", contato_telefone: "", contato_email: "", atividade: "", observacoes: "" };

export default function Clientes() {
  const { pode } = useAuth();
  const { dados, erro, recarregar } = useCarregar(() => api.get<any[]>("/clientes"));
  const [form, setForm] = useState<any | null>(null);
  const [erroForm, setErroForm] = useState<unknown>(null);
  const [filtro, setFiltro] = useState("");
  if (erro) return <Alerta tipo="erro">{erro}</Alerta>;
  if (!dados) return <Carregando />;
  const lista = dados.filter((c) => `${c.nome} ${c.industria || ""} ${c.contato_nome || ""}`.toLowerCase().includes(filtro.toLowerCase()));
  const salvar = async () => {
    setErroForm(null);
    try {
      if (form.id) await api.put(`/clientes/${form.id}`, form);
      else await api.post("/clientes", form);
      setForm(null);
      recarregar();
    } catch (e) {
      setErroForm(e);
    }
  };
  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });
  return (
    <div>
      <div className="cabecalho">
        <div><h1>Clientes</h1><div className="sub">{dados.length} cadastrado(s)</div></div>
        <div className="acoes">
          <input placeholder="Buscar…" value={filtro} onChange={(e) => setFiltro(e.target.value)} style={{ width: 220 }} />
          {pode("clientes.editar") && <button className="btn btn-primario" onClick={() => setForm({ ...VAZIO })}>Novo cliente</button>}
        </div>
      </div>
      {form && (
        <Cartao titulo={form.id ? "Editar cliente" : "Novo cliente"}>
          <div className="grade g3">
            <Campo rotulo="Nome do cliente *"><input value={form.nome || ""} onChange={set("nome")} /></Campo>
            <Campo rotulo="Indústria / unidade"><input value={form.industria || ""} onChange={set("industria")} /></Campo>
            <Campo rotulo="CNPJ"><input value={form.cnpj || ""} onChange={set("cnpj")} /></Campo>
            <Campo rotulo="Atividade industrial"><input value={form.atividade || ""} onChange={set("atividade")} /></Campo>
            <Campo rotulo="Responsável / contato"><input value={form.contato_nome || ""} onChange={set("contato_nome")} /></Campo>
            <Campo rotulo="Telefone"><input value={form.contato_telefone || ""} onChange={set("contato_telefone")} /></Campo>
            <Campo rotulo="E-mail"><input value={form.contato_email || ""} onChange={set("contato_email")} /></Campo>
          </div>
          <div className="grade g2" style={{ marginTop: 10 }}>
            <Campo rotulo="Endereço do empreendimento"><textarea value={form.endereco || ""} onChange={set("endereco")} /></Campo>
            <Campo rotulo="Observações"><textarea value={form.observacoes || ""} onChange={set("observacoes")} /></Campo>
          </div>
          <ErroBox erro={erroForm} />
          <div className="acoes" style={{ marginTop: 10 }}>
            <BotaoAcao className="btn btn-primario" onClick={salvar}>Salvar</BotaoAcao>
            <button className="btn" onClick={() => setForm(null)}>Cancelar</button>
          </div>
        </Cartao>
      )}
      <Cartao>
        <table>
          <thead><tr><th>Cliente</th><th>Indústria</th><th>Atividade</th><th>Contato</th><th>Telefone</th><th></th></tr></thead>
          <tbody>
            {lista.map((c) => (
              <tr key={c.id}>
                <td>{c.nome} <SeloDemo ativo={c.demonstrativo} /></td>
                <td>{c.industria}</td>
                <td>{c.atividade}</td>
                <td>{c.contato_nome}</td>
                <td>{c.contato_telefone}</td>
                <td>{pode("clientes.editar") && <button className="btn btn-mini" onClick={() => setForm(c)}>Editar</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Cartao>
    </div>
  );
}
