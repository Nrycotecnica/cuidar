"""Testes de integração da API (critérios de aceitação do MVP)."""

import io

import ezdxf
import pytest

from app.cad.dxf_export import validar_dxf


def _projeto_demo(client, h, codigo="DEMO-0001"):
    return next(p for p in client.get("/api/projetos", headers=h).json() if p["codigo"] == codigo)


def test_saude_e_versao(client):
    assert client.get("/api/saude").json()["status"] == "ok"
    v = client.get("/api/versao").json()
    assert v["versao"] and v["versao_motor"]


def test_login_invalido_e_rota_protegida(client):
    assert client.post("/api/auth/login", json={"email": "x@y.com", "senha": "errada"}).status_code == 401
    assert client.get("/api/projetos").status_code == 401


def test_permissoes_por_perfil(client, usuarios):
    # técnico de campo não cria projeto, mas registra visita
    r = client.post("/api/projetos", headers=usuarios["tecnico_campo"], json={"nome": "X", "modulo": "poeira"})
    assert r.status_code == 403
    r = client.post("/api/visitas", headers=usuarios["tecnico_campo"], json={"dados": {"tipo_sistema": "poeira"}})
    assert r.status_code == 200
    # orçamentista não edita dados técnicos de exaustor
    ex = client.get("/api/exaustores", headers=usuarios["orcamentista"]).json()[0]
    assert client.put(f"/api/exaustores/{ex['id']}", headers=usuarios["orcamentista"], json={"modelo": "x"}).status_code == 403
    assert client.put(f"/api/exaustores/{ex['id']}", headers=usuarios["orcamentista"], json={"preco": 1234.5}).status_code == 200
    # projetista não aprova parâmetro; não gerencia usuários
    par = client.get("/api/parametros", headers=usuarios["projetista"]).json()[0]
    assert client.post(f"/api/parametros/{par['id']}/aprovar", headers=usuarios["projetista"]).status_code == 403
    assert client.get("/api/usuarios", headers=usuarios["projetista"]).status_code == 403


def test_cadastro_projeto_persiste(client, usuarios):
    h = usuarios["projetista"]
    c = client.post("/api/clientes", headers=h, json={"nome": "Cliente Teste", "industria": "Metalúrgica"}).json()
    p = client.post("/api/projetos", headers=h, json={"nome": "Projeto persistente", "modulo": "fumos", "cliente_id": c["id"]}).json()
    r = client.put(f"/api/projetos/{p['id']}/entradas", headers=h, json={"temperatura_c": {"valor": 35, "status": "confirmado"}})
    assert r.status_code == 200
    # projetista não pode confirmar: fica não confirmado
    assert r.json()["entradas"]["temperatura_c"]["status"] == "nao_confirmado"
    r = client.put(f"/api/projetos/{p['id']}/entradas", headers=usuarios["engenheiro"], json={"temperatura_c": {"valor": 35, "status": "confirmado"}})
    assert r.json()["entradas"]["temperatura_c"]["status"] == "confirmado"
    again = client.get(f"/api/projetos/{p['id']}", headers=h).json()
    assert again["nome"] == "Projeto persistente" and again["cliente_nome"] == "Cliente Teste"
    hist = client.get(f"/api/projetos/{p['id']}/historico", headers=h).json()
    assert any(a["acao"] == "editar_entradas" for a in hist)


def test_importar_e_visualizar_dxf(client, usuarios):
    h = usuarios["projetista"]
    p = _projeto_demo(client, h)
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    doc.layers.add("PILAR")
    msp.add_lwpolyline([(0, 0), (20000, 0), (20000, 10000), (0, 10000)], close=True)
    msp.add_lwpolyline([(5000, 5000), (5300, 5000), (5300, 5300), (5000, 5300)], close=True, dxfattribs={"layer": "PILAR"})
    msp.add_circle((1000, 1000), 300)
    blk = doc.blocks.new("MAQ")
    blk.add_line((0, 0), (1000, 0))
    msp.add_blockref("MAQ", (8000, 2000))
    buf = io.StringIO()
    doc.write(buf)
    r = client.post(f"/api/projetos/{p['id']}/plantas", headers=h, files={"arquivo": ("teste.dxf", buf.getvalue().encode(), "application/dxf")})
    assert r.status_code == 200, r.text
    pl = r.json()
    assert pl["n_entidades"] == 4  # polilinhas, círculo e linha expandida do bloco
    assert pl["escala_m_por_unidade"] == pytest.approx(0.001)
    assert pl["escala_confirmada"] is False
    full = client.get(f"/api/plantas/{pl['id']}", headers=h).json()
    assert {c["nome"] for c in full["geometria"]["camadas"]} >= {"0", "PILAR"}
    assert len(full["deteccoes"]["pilares"]) == 1
    # sem escala confirmada não pode ser usada no ambiente
    assert client.post(f"/api/plantas/{pl['id']}/aplicar-ambiente", headers=h).status_code == 409


def test_dxf_invalido(client, usuarios):
    p = _projeto_demo(client, usuarios["projetista"])
    r = client.post(f"/api/projetos/{p['id']}/plantas", headers=usuarios["projetista"], files={"arquivo": ("ruim.dxf", b"isto nao e dxf", "application/dxf")})
    assert r.status_code == 422


def test_dwg_sem_conversor_informa(client, usuarios):
    p = _projeto_demo(client, usuarios["projetista"])
    r = client.post(f"/api/projetos/{p['id']}/plantas", headers=usuarios["projetista"], files={"arquivo": ("a.dwg", b"AC1032....", "application/acad")})
    assert r.status_code == 422 and "DXF" in r.json()["detail"]


def test_pdf_exige_calibracao(client, usuarios):
    from reportlab.pdfgen import canvas
    h = usuarios["projetista"]
    p = _projeto_demo(client, h)
    b = io.BytesIO()
    cv = canvas.Canvas(b, pagesize=(842, 595))
    cv.rect(100, 100, 500, 300)
    cv.drawString(100, 500, "ESCALA 1:50")
    cv.save()
    pl = client.post(f"/api/projetos/{p['id']}/plantas", headers=h, files={"arquivo": ("p.pdf", b.getvalue(), "application/pdf")}).json()
    assert pl["origem"] == "pdf" and not pl["escala_confirmada"] and pl["escala_m_por_unidade"] is None
    assert pl["sugestao_escala"]["denominador"] == 50
    r = client.put(f"/api/plantas/{pl['id']}/escala", headers=h, json={"p1": [100, 100], "p2": [600, 100], "distancia_m": 8.82})
    assert r.status_code == 200 and r.json()["escala_confirmada"]
    assert r.json()["escala_m_por_unidade"] == pytest.approx(8.82 / 500)


def test_curva_exaustor_cadastrar_consultar(client, usuarios):
    h = usuarios["engenheiro"]
    curva = [{"vazao_m3h": 1000, "pressao_pa": 1500}, {"vazao_m3h": 3000, "pressao_pa": 1300}, {"vazao_m3h": 5000, "pressao_pa": 900}]
    r = client.post("/api/exaustores", headers=h, json={"codigo": "T-01", "modelo": "Teste", "tipo": "centrifugo_radial", "curva": curva})
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    q = client.get(f"/api/exaustores/{eid}/curva?vazao_m3h=2000&temperatura_c=20&altitude_m=0", headers=h).json()
    fr = q["fator_densidade"]
    assert q["consulta"]["pressao_pa"] == pytest.approx(1400 * fr)
    q = client.get(f"/api/exaustores/{eid}/curva?vazao_m3h=9000", headers=h).json()
    assert q["consulta"]["pressao_pa"] is None  # sem extrapolação
    bad = client.post("/api/exaustores", headers=h, json={"codigo": "T-02", "modelo": "x", "tipo": "axial", "curva": [{"vazao_m3h": 1, "pressao_pa": 1}]})
    assert bad.status_code == 422


def test_importar_exaustores_csv(client, usuarios):
    csv = "codigo;modelo;tipo;unidade_vazao;unidade_pressao;vazao;pressao;potencia_kw\nIMP-1;Importado;axial;m3/h;mmca;1000;30;0,5\nIMP-1;;;;;2000;20;0,7\n"
    r = client.post("/api/exaustores/importar", headers=usuarios["engenheiro"], files={"arquivo": ("c.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200 and r.json()["criados"] == ["IMP-1"], r.text
    ex = next(e for e in client.get("/api/exaustores", headers=usuarios["engenheiro"]).json() if e["codigo"] == "IMP-1")
    assert ex["curva"][0]["pressao_pa"] == pytest.approx(30 * 9.80665)


def test_fluxo_rede_calculo_exportacao(client, usuarios):
    h = usuarios["projetista"]
    p = _projeto_demo(client, h)
    r = client.post(f"/api/projetos/{p['id']}/rede/rotear", headers=h, json={})
    assert r.status_code == 200, r.text
    rede = r.json()["rede"]["dados"]
    assert len([s for s in rede["segments"]]) >= 5
    # edição: trava um trecho e salva
    rede["segments"][0]["travado"] = True
    assert client.put(f"/api/projetos/{p['id']}/rede", headers=h, json={"dados": rede}).status_code == 200
    r = client.post(f"/api/projetos/{p['id']}/calcular", headers=h, json={})
    assert r.status_code == 200, r.text
    c = r.json()
    res = c["resultados"]
    assert res["vazao_total_m3h"] > 0 and res["pressao_total_ventilador_pa"] > 0
    assert res["selecao_exaustor"]["selecionado"] is not None
    # reprodutibilidade: recalcular sem mudanças gera o mesmo hash e resultados
    c2 = client.post(f"/api/projetos/{p['id']}/calcular", headers=h, json={}).json()
    assert c2["hash_entradas"] == c["hash_entradas"]
    assert c2["resultados"]["pressao_total_ventilador_pa"] == res["pressao_total_ventilador_pa"]
    # exportações
    r = client.get(f"/api/calculos/{c['id']}/dxf", headers=h)
    assert r.status_code == 200
    v = validar_dxf(r.content)
    assert v["erros"] == 0 and v["insunits"] == 4
    assert {"VENT-DUTO", "VENT-COTA", "VENT-CAPTOR", "VENT-EXAUSTOR"} <= set(v["camadas"])
    assert "VENT_EXAUSTOR" in v["blocos"]
    for ext, magic in (("desenho.pdf", b"%PDF"), ("memorial.pdf", b"%PDF"), ("lista.pdf", b"%PDF"), ("lista.xlsx", b"PK")):
        r = client.get(f"/api/calculos/{c['id']}/{ext}", headers=h)
        assert r.status_code == 200 and r.content.startswith(magic), ext
    r = client.get(f"/api/calculos/{c['id']}/lista.csv", headers=h)
    assert "PRELIMINAR" in r.content.decode("utf-8-sig")
    lista = client.get(f"/api/calculos/{c['id']}/lista", headers=h).json()
    cats = {i["categoria"] for i in lista["itens"]}
    assert {"Dutos", "Curvas", "Flanges", "Captores", "Exaustores"} <= cats
    assert lista["liberado"] is False


def test_tecnico_nao_ve_custos(client, usuarios):
    p = _projeto_demo(client, usuarios["tecnico_campo"])
    calcs = client.get(f"/api/projetos/{p['id']}/calculos", headers=usuarios["tecnico_campo"]).json()
    lista = client.get(f"/api/calculos/{calcs[0]['id']}/lista", headers=usuarios["tecnico_campo"]).json()
    assert lista["total_custo"] is None


def test_aprovacao_bloqueada_para_demo_e_parametros(client, usuarios):
    h = usuarios["engenheiro"]
    p = _projeto_demo(client, h)
    assert client.post(f"/api/projetos/{p['id']}/status", headers=h, json={"acao": "enviar_revisao"}).status_code == 200
    r = client.post(f"/api/projetos/{p['id']}/status", headers=h, json={"acao": "aprovar"})
    assert r.status_code == 409
    pend = r.json()["detail"]["pendencias"]
    assert any("demonstrativo" in x for x in pend)
    assert any("Parâmetro técnico sem aprovação" in x for x in pend)
    assert any("Segurança" in x for x in pend)  # poeira combustível declarada
    client.post(f"/api/projetos/{p['id']}/status", headers=h, json={"acao": "voltar_rascunho"})


def test_parametro_demo_nao_aprova_sem_referencia(client, usuarios):
    h = usuarios["engenheiro"]
    par = next(x for x in client.get("/api/parametros", headers=h).json() if x["chave"] == "k_saida")
    assert client.post(f"/api/parametros/{par['id']}/aprovar", headers=h).status_code == 409
    r = client.put(f"/api/parametros/{par['id']}", headers=h, json={"valor": 1.0, "referencia": "Conservação de energia: perda de saída = 1 VP"})
    assert r.json()["status"] == "proposto"
    assert client.post(f"/api/parametros/{par['id']}/aprovar", headers=h).json()["status"] == "aprovado"


def _rede_simples():
    return {"nodes": [
        {"id": "c1", "type": "captor", "x": 0, "y": 0, "label": "C1", "captor": {"tipo": "vazao_informada", "vazao_m3h": 3000, "entrada": "flangeada"}},
        {"id": "c2", "type": "captor", "x": 0, "y": 5, "label": "C2", "captor": {"tipo": "vazao_informada", "vazao_m3h": 3000, "entrada": "flangeada"}},
        {"id": "j", "type": "juncao", "x": 5, "y": 0},
        {"id": "f", "type": "exaustor", "x": 12, "y": 0},
        {"id": "d", "type": "descarga", "x": 12, "y": 5}],
        "segments": [{"id": "s1", "from": "c1", "to": "j"}, {"id": "s2", "from": "c2", "to": "j", "path": [[5, 5]]},
                     {"id": "s3", "from": "j", "to": "f"}, {"id": "s4", "from": "f", "to": "d"}]}


def test_aprovacao_completa_com_dados_reais(client, usuarios):
    """Projeto não demonstrativo, entradas confirmadas, parâmetros e exaustor aprovados → aprova e libera."""
    eng = usuarios["engenheiro"]
    adm = usuarios["administrador"]
    p = client.post("/api/projetos", headers=eng, json={"nome": "Real", "modulo": "fumos"}).json()
    ent = {"temperatura_c": {"valor": 30, "status": "confirmado"}, "altitude_m": {"valor": 0, "status": "confirmado"},
           "contaminante": {"valor": "solda", "status": "confirmado"}, "material_dutos": {"valor": "galvanizado", "status": "confirmado"}}
    assert client.put(f"/api/projetos/{p['id']}/entradas", headers=eng, json=ent).status_code == 200
    assert client.put(f"/api/projetos/{p['id']}/rede", headers=eng, json={"dados": _rede_simples()}).status_code == 200
    # aprova os parâmetros usados (fornecendo referência) e um exaustor real cadastrado
    calc = client.post(f"/api/projetos/{p['id']}/calcular", headers=eng, json={}).json()
    for pu in calc["resultados"]["parametros_usados"]:
        par = next(x for x in client.get("/api/parametros", headers=eng).json() if x["chave"] == pu["chave"])
        if par["status"] != "aprovado":
            client.put(f"/api/parametros/{par['id']}", headers=eng, json={"valor": par["valor"], "referencia": "Referência de teste automatizado"})
            assert client.post(f"/api/parametros/{par['id']}/aprovar", headers=eng).status_code == 200
    curva = [{"vazao_m3h": 3000, "pressao_pa": 380, "potencia_kw": 0.6}, {"vazao_m3h": 6000, "pressao_pa": 320, "potencia_kw": 0.9},
             {"vazao_m3h": 9000, "pressao_pa": 150, "potencia_kw": 1.1}]
    ex = client.post("/api/exaustores", headers=eng, json={"codigo": "REAL-1", "modelo": "Real", "tipo": "centrifugo_limite", "curva": curva, "potencia_motor_kw": 1.5}).json()
    assert client.post(f"/api/exaustores/{ex['id']}/aprovar", headers=eng).status_code == 200
    r = client.post(f"/api/projetos/{p['id']}/calcular", headers=eng, json={"exaustor_id": ex["id"]})
    assert r.status_code == 200, r.text
    calc = r.json()
    assert calc["resultados"]["selecao_exaustor"]["selecionado"]["codigo"] == "REAL-1", calc["resultados"]["selecao_exaustor"]
    pend = client.get(f"/api/projetos/{p['id']}/pendencias", headers=eng).json()["pendencias"]
    assert pend == [], pend
    # projetista não aprova
    client.post(f"/api/projetos/{p['id']}/status", headers=eng, json={"acao": "enviar_revisao"})
    assert client.post(f"/api/projetos/{p['id']}/status", headers=usuarios["projetista"], json={"acao": "aprovar"}).status_code == 403
    r = client.post(f"/api/projetos/{p['id']}/status", headers=eng, json={"acao": "aprovar", "calculo_id": calc["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "aprovado"
    # aprovado não pode ser editado
    assert client.put(f"/api/projetos/{p['id']}/rede", headers=eng, json={"dados": _rede_simples()}).status_code == 409
    assert client.post(f"/api/projetos/{p['id']}/status", headers=eng, json={"acao": "liberar_fabricacao"}).json()["status"] == "liberado_fabricacao"
    lista = client.get(f"/api/calculos/{calc['id']}/lista", headers=adm).json()
    assert lista["liberado"] is True
    assert "APROVADO" in client.get(f"/api/calculos/{calc['id']}/memorial.pdf", headers=eng).headers["content-disposition"]


def test_controle_fumaca_incendio_sempre_bloqueia(client, usuarios):
    eng = usuarios["engenheiro"]
    p = client.post("/api/projetos", headers=eng, json={"nome": "Fumaça", "modulo": "fumos"}).json()
    r = client.put(f"/api/projetos/{p['id']}/seguranca", headers=eng, json={"riscos": {"controle_fumaca_incendio": True}})
    assert r.json()["avaliacao"]["liberado"] is False
    assert r.json()["avaliacao"]["bloqueios"]


def test_renovacao(client, usuarios):
    h = usuarios["projetista"]
    p = _projeto_demo(client, h, "DEMO-0002")
    r = client.post(f"/api/projetos/{p['id']}/calcular", headers=h, json={})
    assert r.status_code == 200
    res = r.json()["resultados"]
    assert res["vazao_exaustao_m3h"] > res["vazao_insuflamento_m3h"]  # pressão negativa
    assert res["opcoes_equipamento"]


def test_visita_faltantes_e_criar_projeto(client, usuarios):
    h = usuarios["tecnico_campo"]
    v = client.post("/api/visitas", headers=h, json={"dados": {"tipo_sistema": "poeira", "comprimento_m": 20, "largura_m": 10,
                                                                "pontos_emissao": [{"nome": "Serra", "x": 2, "y": 3, "tipo": "vazao_informada", "vazao_m3h": 1200}]}}).json()
    assert "Pé-direito" in v["faltantes"]
    assert any("Ponto de emissão 1" in f for f in v["faltantes"])
    r = client.post(f"/api/visitas/{v['id']}/criar-projeto", headers=usuarios["projetista"], json={})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["entradas"]["comprimento_m"]["status"] == "nao_confirmado"
    rede = client.get(f"/api/projetos/{p['id']}/rede", headers=h).json()
    assert rede["dados"]["nodes"][0]["type"] == "captor"


def test_upload_arquivo_e_projeto_antigo(client, usuarios):
    h = usuarios["projetista"]
    a = client.post("/api/antigos", headers=h, json={"nome": "Antigo 2018", "dados": {"vazao_total_m3h": 5000, "pressao_total_pa": 2000}}).json()
    r = client.post("/api/arquivos", headers=h, data={"projeto_antigo_id": str(a["id"]), "categoria": "memorial"},
                    files={"arquivo": ("memorial.pdf", b"%PDF-1.4 teste", "application/pdf")})
    assert r.status_code == 200
    a2 = client.get(f"/api/antigos/{a['id']}", headers=h).json()
    assert len(a2["arquivos"]) == 1
    dl = client.get(f"/api/arquivos/{a2['arquivos'][0]['id']}/download", headers=h)
    assert dl.content == b"%PDF-1.4 teste"
    p = _projeto_demo(client, h)
    cmp = client.get(f"/api/antigos/{a['id']}/comparar/{p['id']}", headers=h).json()
    assert cmp["grandezas"]["vazao_total_m3h"]["referencia"] == 5000
    assert cmp["observacoes"]
    assert client.post("/api/arquivos", headers=h, files={"arquivo": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 422


def test_assistente_modo_regras(client, usuarios):
    h = usuarios["projetista"]
    assert client.get("/api/assistente/status", headers=h).json()["modo"] == "regras"
    p = _projeto_demo(client, h)
    r = client.post(f"/api/projetos/{p['id']}/assistente", headers=h, json={"mensagens": [{"role": "user", "content": "O que falta para aprovar?"}]}).json()
    assert r["modo"] == "regras" and "pendencias" in r["ferramentas"]


def test_admin_versao_e_auditoria(client, admin):
    v = client.get("/api/admin/versao", headers=admin).json()
    assert v["versao_motor"]
    assert client.get("/api/admin/versoes", headers=admin).json()
    assert client.get("/api/admin/auditoria", headers=admin).json()


def test_parametro_demo_continua_demo_com_referencia_demo(client, usuarios):
    from app.engine.demo_params import REF
    h = usuarios["engenheiro"]
    par = next(x for x in client.get("/api/parametros", headers=h).json() if x["chave"] == "fator_coifa")
    r = client.put(f"/api/parametros/{par['id']}", headers=h, json={"valor": 1.5, "referencia": REF}).json()
    assert r["demonstrativo"] is True
    assert client.post(f"/api/parametros/{par['id']}/aprovar", headers=h).status_code == 409


def test_cotas_da_rede_salvam_sobrevivem_ao_editor_e_entram_no_calculo(client, usuarios):
    h = usuarios["projetista"]
    p = _projeto_demo(client, h)
    rede = client.get(f"/api/projetos/{p['id']}/rede", headers=h).json()["dados"]
    sem = client.post(f"/api/projetos/{p['id']}/calcular", headers=h, json={}).json()["resultados"]
    for n in rede["nodes"]:
        n["z_m"] = 1.2 if n["type"] == "captor" else 4.5 if n["type"] == "descarga" else None if n["type"] in ("juncao", "ponto") else 0.8
    rede["cotas"] = {"rede_m": 4.0}
    assert client.put(f"/api/projetos/{p['id']}/rede", headers=h, json={"dados": rede}).status_code == 200
    # o editor de planta salva só nós e trechos: a cota da rede não pode sumir
    sem_cotas = {"nodes": rede["nodes"], "segments": rede["segments"]}
    salvo = client.put(f"/api/projetos/{p['id']}/rede", headers=h, json={"dados": sem_cotas}).json()["dados"]
    assert salvo["cotas"] == {"rede_m": 4.0}
    com = client.post(f"/api/projetos/{p['id']}/calcular", headers=h, json={}).json()["resultados"]
    assert com["pressao_succao_pa"] > sem["pressao_succao_pa"]
    assert any(t["pernas_verticais"] for t in com["trechos"])
    # cota em milímetros por engano é recusada (4000 m de descida)
    rede["cotas"] = {"rede_m": 4000}
    r = client.put(f"/api/projetos/{p['id']}/rede", headers=h, json={"dados": rede})
    assert r.status_code == 422 and "metros" in r.text


def _png_b64(w=320, h=200, cor=(40, 120, 200)):
    import base64
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (w, h), cor).save(b, "PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def test_apresentacao_pdf_para_o_cliente(client, usuarios):
    h = usuarios["projetista"]
    p = _projeto_demo(client, h)
    assert client.post(f"/api/projetos/{p['id']}/rede/rotear", headers=h, json={}).status_code == 200
    c = client.post(f"/api/projetos/{p['id']}/calcular", headers=h, json={}).json()
    img = {"geral": _png_b64(), "oposta": _png_b64(), "cima": _png_b64(cor=(200, 200, 200)), "lateral": _png_b64()}
    r = client.post(f"/api/calculos/{c['id']}/apresentacao.pdf", headers=h, json={"imagens": img})
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF") and "apresentacao" in r.headers["content-disposition"]
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(r.content)
    assert len(doc) == 4  # capa, vistas, resumo técnico, observações
    texto = "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    assert "DEMONSTRATIVO" in texto and "Desenvolvido por Diego Pereira" in texto
    assert "Resumo técnico" in texto and "Pontos de captação" in texto
    # documento do cliente: sem preço/custo do catálogo
    assert "R$" not in texto and "custo" not in texto.lower()
    # só a vista geral: pula a página de vistas
    r = client.post(f"/api/calculos/{c['id']}/apresentacao.pdf", headers=h, json={"imagens": {"geral": img["geral"]}})
    assert len(pdfium.PdfDocument(r.content)) == 3
    # imagem que não é PNG e falta da vista geral são recusadas
    assert client.post(f"/api/calculos/{c['id']}/apresentacao.pdf", headers=h, json={"imagens": {"geral": "data:image/png;base64,aGVsbG8="}}).status_code == 422
    assert client.post(f"/api/calculos/{c['id']}/apresentacao.pdf", headers=h, json={"imagens": {"cima": img["cima"]}}).status_code == 422
    # rede mudou depois do cálculo: recusa, para a imagem nova não sair com números velhos
    rede = client.get(f"/api/projetos/{p['id']}/rede", headers=h).json()["dados"]
    assert client.put(f"/api/projetos/{p['id']}/rede", headers=h, json={"dados": rede}).status_code == 200
    r = client.post(f"/api/calculos/{c['id']}/apresentacao.pdf", headers=h, json={"imagens": img})
    assert r.status_code == 409 and "Calcule de novo" in r.text
