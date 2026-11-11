"""Laço de ferramentas do assistente com cliente simulado (sem chamada real à API)."""

from types import SimpleNamespace as NS

import anthropic

from app.assistant import service


class FakeMessages:
    def __init__(self):
        self.chamadas = []

    def create(self, **kw):
        self.chamadas.append(kw)
        if len(self.chamadas) == 1:
            return NS(stop_reason="tool_use", content=[
                NS(type="text", text="Vou consultar."),
                NS(type="tool_use", id="tu_1", name="pendencias", input={}),
                NS(type="tool_use", id="tu_2", name="ultimo_calculo", input={}),
            ])
        return NS(stop_reason="end_turn", content=[NS(type="text", text="Resposta final baseada nas ferramentas.")])


class FakeClient:
    def __init__(self, *a, **k):
        self.beta = NS(messages=FakeMessages())


def test_laco_ferramentas(client, usuarios, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste-falso")
    h = usuarios["projetista"]
    p = next(x for x in client.get("/api/projetos", headers=h).json() if x["codigo"] == "DEMO-0001")
    r = client.post(f"/api/projetos/{p['id']}/assistente", headers=h,
                    json={"mensagens": [{"role": "user", "content": "O que falta?"}]}).json()
    assert r["modo"] == "ia"
    assert r["ferramentas"] == ["pendencias", "ultimo_calculo"]
    assert r["resposta"] == "Resposta final baseada nas ferramentas."
    seg = fake.beta.messages.chamadas[1]
    resultados = seg["messages"][-1]["content"]
    assert [x["tool_use_id"] for x in resultados] == ["tu_1", "tu_2"]  # todos os resultados numa única mensagem
    assert seg["model"] == service.get_settings().anthropic_model
    nomes = {t["name"] for t in seg["tools"]}
    assert not any(n.startswith(("aprovar", "liberar", "alterar", "salvar")) for n in nomes)  # só leitura
