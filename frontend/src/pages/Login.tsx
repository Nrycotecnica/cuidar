import { useState } from "react";
import { FaixaAmbiente, Logo, Rodape } from "../components/Layout";
import { NOME_SOFTWARE, SUBTITULO } from "../lib/marca";
import { ErroBox } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { entrar } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<unknown>(null);
  const [ocupado, setOcupado] = useState(false);
  return (
    <div className="login-pagina">
      <FaixaAmbiente />
      <form
        className="login-caixa"
        onSubmit={async (e) => {
          e.preventDefault();
          setOcupado(true);
          setErro(null);
          try {
            await entrar(email, senha);
          } catch (er) {
            setErro(er);
          } finally {
            setOcupado(false);
          }
        }}
      >
        <div className="marca">
          <Logo />
          <div>
            <div className="marca-nome">{NOME_SOFTWARE}</div>
            <div className="marca-sub">{SUBTITULO}</div>
          </div>
        </div>
        <label className="campo">
          <span className="rotulo">E-mail</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required name="email" />
        </label>
        <label className="campo">
          <span className="rotulo">Senha</span>
          <input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" required name="senha" />
        </label>
        <ErroBox erro={erro} />
        <button className="btn btn-primario" type="submit" disabled={ocupado}>{ocupado ? "Entrando…" : "Entrar"}</button>
        <p className="nota">Os resultados do software são preliminares até a aprovação de um engenheiro responsável.</p>
      </form>
      <Rodape />
    </div>
  );
}
