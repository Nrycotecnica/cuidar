import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { Alerta, BotaoAcao, Campo, Carregando, Cartao, ErroBox } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ILUSTRATIVO, montarCena, TIPOS_COM_COTA_PROPRIA, type Cena, type P3 } from "../../lib/cena3d";
import { fmt, numero } from "../../lib/format";
import type { CtxProjeto } from "./Projeto";

const COR = { succao: "#c62828", descarga: "#78909c", semDiametro: "#bdbdbd", captor: "#2e7d32", filtro: "#6a1b9a", exaustor: "#1565c0", descarga_no: "#546e7a", equipamento: "#8d6e63", pilar: "#9e9e9e", obstaculo: "#ffb74d", piso: "#ffffff" };
const NOME_TIPO: Record<string, string> = { captor: "Captor", filtro: "Filtro", exaustor: "Exaustor", descarga: "Descarga", equipamento: "Equipamento" };

type Vista = "3d" | "oposta" | "cima" | "lateral";

// planta (x, y) + altura z → three.js (y para cima)
const V = (p: P3) => new THREE.Vector3(p[0], p[2], -p[1]);

function forma(pontos: number[][]) {
  const s = new THREE.Shape();
  pontos.forEach(([x, y], i) => (i ? s.lineTo(x, y) : s.moveTo(x, y)));
  return s;
}

function prisma(pontos: number[][], altura: number, cor: string, opacidade = 1) {
  const g = new THREE.ExtrudeGeometry(forma(pontos), { depth: altura, bevelEnabled: false });
  g.rotateX(-Math.PI / 2); // (x, y, z) → (x, z, −y): a extrusão vira altura
  const m = new THREE.MeshStandardMaterial({ color: cor, transparent: opacidade < 1, opacity: opacidade, roughness: 0.9 });
  return new THREE.Mesh(g, m);
}

function rotulo(texto: string, p: THREE.Vector3, classe = "rotulo-3d") {
  const div = document.createElement("div");
  div.className = classe;
  div.textContent = texto;
  const o = new CSS2DObject(div);
  o.position.copy(p);
  return o;
}

function montarObjetos(cena: Cena, ambiente: any): THREE.Group {
  const g = new THREE.Group();
  const altPilar = cena.peDireito ?? cena.cotaRede + 1;
  if (ambiente?.contorno?.length > 2) {
    const piso = new THREE.Mesh(new THREE.ShapeGeometry(forma(ambiente.contorno)), new THREE.MeshStandardMaterial({ color: COR.piso, side: THREE.DoubleSide, roughness: 1 }));
    piso.geometry.rotateX(-Math.PI / 2);
    piso.position.y = -0.01;
    g.add(piso);
    const borda = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ambiente.contorno.map(([x, y]: number[]) => new THREE.Vector3(x, 0, -y))), new THREE.LineBasicMaterial({ color: "#555" }));
    g.add(borda);
  }
  for (const q of ambiente?.pilares || []) g.add(prisma(q.pontos, altPilar, COR.pilar));
  for (const q of ambiente?.obstaculos || []) {
    const m = prisma(q.pontos, ILUSTRATIVO.obstaculo, COR.obstaculo, 0.55);
    g.add(m);
    if (q.nome) {
      const xs = q.pontos.map((z: number[]) => z[0]), ys = q.pontos.map((z: number[]) => z[1]);
      g.add(rotulo(q.nome, V([(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2, ILUSTRATIVO.obstaculo + 0.2]), "rotulo-3d rotulo-3d-suave"));
    }
  }
  for (const q of ambiente?.bloqueios || []) {
    const m = prisma(q.pontos, 0.02, "#c62828", 0.25);
    g.add(m);
  }

  const eixoY = new THREE.Vector3(0, 1, 0);
  for (const t of cena.tubos) {
    const cor = !t.diametroInformado ? COR.semDiametro : t.lado === "descarga" ? COR.descarga : COR.succao;
    const mat = new THREE.MeshStandardMaterial({ color: cor, metalness: 0.35, roughness: 0.45 });
    const r = t.diametroM / 2;
    const pts = t.pontos.map(V);
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i];
      const dir = new THREE.Vector3().subVectors(b, a);
      const L = dir.length();
      if (L < 1e-6) continue;
      const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, L, 24), mat);
      m.position.copy(a).addScaledVector(dir, 0.5);
      m.quaternion.setFromUnitVectors(eixoY, dir.normalize());
      m.userData = { trecho: t.id };
      g.add(m);
    }
    // joelhos: esfera do mesmo raio esconde a emenda entre cilindros
    for (let i = 1; i < pts.length - 1; i++) {
      const s = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 12), mat);
      s.position.copy(pts[i]);
      g.add(s);
    }
  }

  for (const p of cena.pecas) {
    const pos = V(p.pos);
    let m: THREE.Object3D | null = null;
    if (p.tipo === "captor") {
      // coifa: boca para baixo, ligação ao duto no topo (na cota informada)
      m = new THREE.Mesh(new THREE.ConeGeometry(0.4, 0.45, 4, 1, true), new THREE.MeshStandardMaterial({ color: COR.captor, side: THREE.DoubleSide, metalness: 0.2 }));
      m.rotation.y = Math.PI / 4;
      m.position.set(pos.x, pos.y - 0.22, pos.z);
    } else if (p.tipo === "filtro" || p.tipo === "equipamento") {
      const alt = Math.max(pos.y + 0.8, 2.0);
      m = new THREE.Mesh(new THREE.BoxGeometry(1.6, alt, 1.6), new THREE.MeshStandardMaterial({ color: p.tipo === "filtro" ? COR.filtro : COR.equipamento, roughness: 0.6 }));
      m.position.set(pos.x, alt / 2, pos.z);
    } else if (p.tipo === "exaustor") {
      const grupo = new THREE.Group();
      const voluta = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.7, 0.6, 32), new THREE.MeshStandardMaterial({ color: COR.exaustor, metalness: 0.3, roughness: 0.4 }));
      voluta.rotation.x = Math.PI / 2;
      voluta.position.copy(pos);
      grupo.add(voluta);
      if (pos.y > 0.75) {
        const base = new THREE.Mesh(new THREE.BoxGeometry(1.0, pos.y - 0.7, 0.8), new THREE.MeshStandardMaterial({ color: "#607d8b" }));
        base.position.set(pos.x, (pos.y - 0.7) / 2, pos.z);
        grupo.add(base);
      }
      m = grupo;
    } else if (p.tipo === "descarga") {
      m = new THREE.Mesh(new THREE.ConeGeometry(0.35, 0.3, 24), new THREE.MeshStandardMaterial({ color: COR.descarga_no }));
      m.position.set(pos.x, pos.y + 0.2, pos.z);
    }
    if (m) g.add(m);
    g.add(rotulo(p.semCota ? `${p.rotulo} (sem cota)` : p.rotulo, new THREE.Vector3(pos.x, pos.y + 0.7, pos.z), p.semCota ? "rotulo-3d rotulo-3d-alerta" : "rotulo-3d"));
  }
  return g;
}

export default function Vista3D({ ctx }: { ctx: CtxProjeto }) {
  const { projeto: p } = ctx;
  const { pode } = useAuth();
  const editavel = pode("projetos.editar") && !["aprovado", "liberado_fabricacao"].includes(p.status);
  const [rede, setRede] = useState<any>(null);
  const [calc, setCalc] = useState<any>(null);
  const [cotaRede, setCotaRede] = useState("");
  const [cotasNos, setCotasNos] = useState<Record<string, string>>({});
  const [sujo, setSujo] = useState(false);
  const [erro, setErro] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const caixa = useRef<HTMLDivElement>(null);
  const motor = useRef<{ renderer: THREE.WebGLRenderer; cena: THREE.Scene; camera: THREE.PerspectiveCamera; controles: OrbitControls; grupo: THREE.Group | null; enquadrar: (vista?: Vista) => void; redimensionar: () => void } | null>(null);

  const carregar = async () => {
    const r = await api.get<any>(`/projetos/${p.id}/rede`);
    setRede(r);
    const z: Record<string, string> = {};
    for (const n of r.dados?.nodes || []) if (TIPOS_COM_COTA_PROPRIA.has(n.type)) z[n.id] = n.z_m != null ? fmt(n.z_m, 2) : "";
    setCotasNos(z);
    setCotaRede(r.dados?.cotas?.rede_m != null ? fmt(r.dados.cotas.rede_m, 2) : "");
    setSujo(false);
  };
  useEffect(() => { carregar().catch(setErro); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [p.id]);
  useEffect(() => {
    if (ctx.calcId) api.get(`/calculos/${ctx.calcId}`).then(setCalc).catch(() => setCalc(null));
    else setCalc(null);
  }, [ctx.calcId]);

  // rede com as cotas digitadas (ainda não salvas) — a prévia acompanha a digitação
  const dadosEditados = useMemo(() => {
    if (!rede) return null;
    const nodes = (rede.dados?.nodes || []).map((n: any) => {
      if (!(n.id in cotasNos)) return n;
      const v = numero(cotasNos[n.id]);
      const { z_m: _, ...resto } = n;
      return v === null ? resto : { ...resto, z_m: v };
    });
    const c = numero(cotaRede);
    return { ...rede.dados, nodes, cotas: { ...(rede.dados?.cotas || {}), rede_m: c } };
  }, [rede, cotasNos, cotaRede]);

  const calcAtual = calc && rede && calc.tipo === "rede" && calc.rede_versao === rede.versao && !sujo;
  const peDireito = numero(String(p.entradas?.pe_direito_m?.valor ?? "")) ?? null;
  // Diâmetros: do último cálculo de rede mesmo se a rede mudou depois (salvar as
  // cotas já o deixa desatualizado e a vista ficaria toda cinza); o painel avisa.
  const calcRede = calc && calc.tipo === "rede" ? calc : null;
  const cena = useMemo(() => (dadosEditados ? montarCena(dadosEditados, calcRede?.resultados ?? null, peDireito) : null), [dadosEditados, calcRede, peDireito]);

  // motor 3D: criado uma vez, quando a caixa existe. Enquanto a rede carrega a
  // aba mostra "Carregando…" e a caixa nem está na página — por isso depende de
  // `pronto` (na primeira versão dependia de nada e a vista ficava em branco).
  const pronto = rede !== null;
  const enquadrado = useRef(false);
  useEffect(() => {
    const el = caixa.current;
    if (!pronto || !el) return;
    let renderer: THREE.WebGLRenderer;
    try {
      // preserveDrawingBuffer: necessário para "Baixar imagem" ler o quadro já desenhado
      renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    } catch {
      setErro(new Error("Este computador/navegador não conseguiu abrir a vista 3D (WebGL indisponível). Atualize o navegador ou o driver de vídeo."));
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    const css = new CSS2DRenderer();
    css.domElement.className = "camada-rotulos-3d";
    el.appendChild(css.domElement);
    const cena3 = new THREE.Scene();
    cena3.background = new THREE.Color("#eef2f6");
    cena3.add(new THREE.HemisphereLight("#ffffff", "#8a8f99", 1.6));
    const sol = new THREE.DirectionalLight("#ffffff", 1.6);
    sol.position.set(30, 60, 20);
    cena3.add(sol);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
    const controles = new OrbitControls(camera, renderer.domElement);
    controles.enableDamping = true;
    const enquadrar = (vista: Vista = "3d") => {
      const g = motor.current?.grupo;
      const caixaG = g ? new THREE.Box3().setFromObject(g) : new THREE.Box3(new THREE.Vector3(0, 0, -10), new THREE.Vector3(20, 5, 0));
      const centro = caixaG.getCenter(new THREE.Vector3());
      const raio = Math.max(caixaG.getSize(new THREE.Vector3()).length() / 2, 3);
      // de cima: lente quase "tele" (12°) para a planta não sair em perspectiva —
      // com 45° os pilares altos perto das paredes pareciam tombados para fora
      // lateral: 20° pelo mesmo motivo, com as alturas sem distorção
      camera.fov = vista === "cima" ? 12 : vista === "lateral" ? 20 : 45;
      const d = raio / Math.sin((camera.fov * Math.PI) / 360) * 0.9;
      controles.target.copy(centro);
      if (vista === "cima") camera.position.set(centro.x, centro.y + d, centro.z + 0.001);
      else if (vista === "lateral") camera.position.set(centro.x, centro.y + d * 0.05, centro.z + d);
      else if (vista === "oposta") camera.position.set(centro.x - d * 0.55, centro.y + d * 0.55, centro.z - d * 0.62);
      else camera.position.set(centro.x + d * 0.55, centro.y + d * 0.55, centro.z + d * 0.62);
      camera.near = d / 100;
      camera.far = d * 20;
      camera.updateProjectionMatrix();
      // A distância pela esfera envolvente deixa o modelo pequeno e fora do centro
      // (a planta é larga e baixa, e o centro da caixa não cai no centro da
      // imagem em perspectiva). Mede onde as peças caem na imagem, centraliza e
      // aproxima até ocuparem ~88% do quadro; três passadas porque a
      // perspectiva não é linear.
      if (g) {
        // cantos de CADA peça, não da caixa do conjunto: o canto da caixa geral
        // fica no ar (topo do pilar sobre o canto do piso)
        const cantos: THREE.Vector3[] = [];
        g.updateMatrixWorld(true);
        g.traverse((o: any) => {
          if (!o.isMesh) return;
          const b = new THREE.Box3().setFromObject(o);
          for (let i = 0; i < 8; i++) cantos.push(new THREE.Vector3(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z));
        });
        const alvo = centro.clone();
        const direita = new THREE.Vector3(), cima = new THREE.Vector3();
        for (let passada = 0; passada < 3 && cantos.length; passada++) {
          // a câmera só é apontada para o alvo no controles.update(); sem isto a
          // medida sai com a orientação anterior
          camera.lookAt(alvo);
          camera.updateMatrixWorld();
          let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
          for (const q of cantos) {
            const n = q.clone().project(camera);
            x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y);
          }
          const ext = Math.max((x1 - x0) / 2, (y1 - y0) / 2);
          if (!(ext > 0.02 && ext < 20)) break;
          const dist = camera.position.distanceTo(alvo);
          const meiaAlt = Math.tan((camera.fov * Math.PI) / 360) * dist;
          direita.setFromMatrixColumn(camera.matrixWorld, 0);
          cima.setFromMatrixColumn(camera.matrixWorld, 1);
          const desloc = direita.multiplyScalar(((x0 + x1) / 2) * meiaAlt * camera.aspect).add(cima.multiplyScalar(((y0 + y1) / 2) * meiaAlt));
          alvo.add(desloc);
          camera.position.add(desloc);
          camera.position.sub(alvo).multiplyScalar(ext / 0.88).add(alvo);
        }
        controles.target.copy(alvo);
      }
      controles.update();
    };
    const redimensionar = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h);
      css.setSize(w, h);
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
    };
    redimensionar();
    const ro = new ResizeObserver(redimensionar);
    ro.observe(el);
    let quadro = 0;
    const animar = () => {
      quadro = requestAnimationFrame(animar);
      controles.update();
      renderer.render(cena3, camera);
      css.render(cena3, camera);
    };
    animar();
    motor.current = { renderer, cena: cena3, camera, controles, grupo: null, enquadrar, redimensionar };
    return () => {
      cancelAnimationFrame(quadro);
      ro.disconnect();
      controles.dispose();
      descartar(motor.current?.grupo);
      renderer.dispose();
      el.innerHTML = "";
      motor.current = null;
      enquadrado.current = false;
    };
  }, [pronto]);

  // troca o conteúdo quando a rede/cotas/cálculo mudam, sem mexer na câmera
  useEffect(() => {
    const m = motor.current;
    if (!m || !cena) return;
    if (m.grupo) { m.cena.remove(m.grupo); descartar(m.grupo); }
    m.grupo = montarObjetos(cena, p.ambiente);
    m.cena.add(m.grupo);
    if (!enquadrado.current) { m.enquadrar(); enquadrado.current = true; }
  }, [cena, p.ambiente, pronto]);

  const salvar = async () => {
    setErro(null); setMsg(null);
    for (const [id, v] of Object.entries(cotasNos)) if (v.trim() && numero(v) === null) throw new Error(`Cota de ${id} inválida: use número em metros (ex.: 1,20)`);
    if (cotaRede.trim() && numero(cotaRede) === null) throw new Error("Cota da rede inválida: use número em metros (ex.: 4,50)");
    await api.put(`/projetos/${p.id}/rede`, { dados: dadosEditados });
    await carregar();
    setMsg("Cotas salvas. Recalcule na aba Rede de dutos: as descidas agora entram no comprimento, nas curvas e na escolha do exaustor.");
  };

  // Fotos para a apresentação: mesma cena, em alta resolução e fundo branco, com
  // os rótulos pintados na imagem (na tela eles são HTML por cima do 3D e não
  // sairiam na foto).
  const fotografar = (vistas: Vista[]): Record<string, string> => {
    const m = motor.current;
    if (!m) throw new Error("A vista 3D ainda não abriu.");
    const W = 2400, H = 1500;
    const cam = { pos: m.camera.position.clone(), alvo: m.controles.target.clone(), fov: m.camera.fov };
    const fundo = m.cena.background;
    const razao = m.renderer.getPixelRatio();
    const fotos: Record<string, string> = {};
    try {
      m.renderer.setPixelRatio(1);
      m.cena.background = new THREE.Color("#ffffff");
      for (const v of vistas) {
        // a lateral é larga e baixa: foto em faixa, senão sobra branco em cima e embaixo
        const h = v === "lateral" ? 800 : H;
        m.renderer.setSize(W, h, false);
        m.camera.aspect = W / h;
        m.enquadrar(v);
        m.renderer.render(m.cena, m.camera);
        fotos[v === "3d" ? "geral" : v] = comRotulos(m.renderer.domElement, m.grupo, m.camera, W, h);
      }
    } finally {
      m.cena.background = fundo;
      m.renderer.setPixelRatio(razao);
      m.redimensionar();
      m.camera.fov = cam.fov;
      m.camera.position.copy(cam.pos);
      m.controles.target.copy(cam.alvo);
      m.camera.updateProjectionMatrix();
      m.controles.update();
    }
    return fotos;
  };

  const gerarApresentacao = async () => {
    setErro(null);
    try {
      const imagens = fotografar(["3d", "oposta", "cima", "lateral"]);
      await api.baixar(`/calculos/${calc.id}/apresentacao.pdf`, `${p.codigo}-apresentacao.pdf`, { imagens });
    } catch (e) { setErro(e); }
  };

  const baixarImagem = () => {
    const m = motor.current;
    if (!m) return;
    m.renderer.render(m.cena, m.camera);
    const a = document.createElement("a");
    a.href = m.renderer.domElement.toDataURL("image/png");
    a.download = `${p.codigo || "projeto"}-3d.png`;
    a.click();
  };

  if (!rede) return erro ? <ErroBox erro={erro} /> : <Carregando />;
  const nosComCota = (rede.dados?.nodes || []).filter((n: any) => TIPOS_COM_COTA_PROPRIA.has(n.type));
  const totalVertical = cena ? cena.tubos.reduce((s, t) => s + t.verticalM, 0) : 0;
  const semDiametro = cena ? cena.tubos.filter((t) => !t.diametroInformado).length : 0;

  return (
    <div className="lado-a-lado">
      <div>
        <div className="ferramentas">
          <button className="btn btn-mini" onClick={() => motor.current?.enquadrar()}>Vista 3D</button>
          <button className="btn btn-mini" onClick={() => motor.current?.enquadrar("oposta")}>Lado oposto</button>
          <button className="btn btn-mini" onClick={() => motor.current?.enquadrar("cima")}>Vista de cima</button>
          <button className="btn btn-mini" onClick={() => motor.current?.enquadrar("lateral")}>Vista lateral</button>
          <button className="btn btn-mini" onClick={baixarImagem}>Baixar imagem (PNG)</button>
        </div>
        <div className="vista-3d" ref={caixa} data-testid="vista-3d" />
        <div className="legenda-rede">
          <span style={{ ["--c" as any]: COR.succao }}>Duto de sucção</span><span style={{ ["--c" as any]: COR.descarga }}>Descarga</span>
          <span style={{ ["--c" as any]: COR.semDiametro }}>Sem diâmetro definido</span><span style={{ ["--c" as any]: COR.captor }}>Captor</span>
          <span style={{ ["--c" as any]: COR.filtro }}>Filtro</span><span style={{ ["--c" as any]: COR.exaustor }}>Exaustor</span>
          <span style={{ ["--c" as any]: COR.pilar }}>Pilar</span><span style={{ ["--c" as any]: COR.obstaculo }}>Obstáculo</span>
        </div>
        <p className="nota">Arraste para girar · botão direito (ou Ctrl + arrastar) para deslocar · roda do mouse para aproximar.</p>
      </div>
      <div className="pilha">
        {pode("exportar") && (
          <Cartao titulo="Apresentação para o cliente">
            <p className="nota" style={{ marginTop: 0 }}>PDF com capa, quatro vistas 3D, resumo técnico (sem preços) e observações. A situação do projeto (preliminar, aprovado ou demonstrativo) sai em todas as páginas.</p>
            <BotaoAcao className="btn btn-primario" disabled={!calcAtual} onClick={gerarApresentacao}>Gerar apresentação (PDF)</BotaoAcao>
            {!calcAtual && <p className="nota">{calcRede ? "A rede mudou desde o último cálculo." : "Ainda não há cálculo da rede."} Calcule na aba Rede de dutos para gerar a apresentação com números e imagens da mesma versão.</p>}
          </Cartao>
        )}
        {cena?.ilustrativa ? (
          <Alerta tipo="aviso">
            Este projeto ainda não tem cotas. As alturas mostradas são <b>só ilustrativas</b> (rede a {fmt(cena.cotaRede, 1)} m, captores a {fmt(ILUSTRATIVO.captor, 1)} m) e <b>não entram no cálculo</b>. Informe a cota da rede e as cotas abaixo para valerem.
          </Alerta>
        ) : (
          <Alerta tipo="info">Descidas e subidas verticais: <b>{fmt(totalVertical, 2)} m</b> no total{calcAtual ? ", já consideradas no cálculo atual." : " — recalcule para que entrem no cálculo."}</Alerta>
        )}
        {cena && cena.semCota.length > 0 && (
          <Alerta tipo="aviso">Sem cota (a descida até eles não entra no cálculo): {cena.semCota.join(", ")}.</Alerta>
        )}
        <Cartao titulo="Cotas (metros, a partir do piso)">
          <Campo rotulo="Cota do eixo da rede principal" dica={peDireito ? `Pé-direito informado: ${fmt(peDireito, 2)} m` : "Pé-direito não informado nos dados do projeto"}>
            <input inputMode="decimal" value={cotaRede} disabled={!editavel} placeholder="ex.: 4,50" onChange={(e) => { setCotaRede(e.target.value); setSujo(true); setMsg(null); }} />
          </Campo>
          <table className="tabela" style={{ marginTop: 8 }}>
            <thead><tr><th>Item</th><th>Tipo</th><th>Cota (m)</th></tr></thead>
            <tbody>
              {nosComCota.map((n: any) => (
                <tr key={n.id}>
                  <td>{n.label || n.id}</td>
                  <td>{NOME_TIPO[n.type] || n.type}</td>
                  <td><input style={{ width: 80 }} inputMode="decimal" value={cotasNos[n.id] ?? ""} disabled={!editavel}
                    placeholder={n.type === "captor" ? "boca" : n.type === "descarga" ? "topo" : "bocal"}
                    onChange={(e) => { setCotasNos({ ...cotasNos, [n.id]: e.target.value }); setSujo(true); setMsg(null); }} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="nota">Captor: altura da ligação da coifa ao duto. Filtro/exaustor: altura do bocal. Descarga: topo da chaminé. Cada diferença entre o item e a rede vira um trecho vertical com uma curva de 90° no cálculo.</p>
          {editavel && (
            <div className="acoes" style={{ marginTop: 8 }}>
              <BotaoAcao className="btn btn-primario" disabled={!sujo} onClick={async () => { try { await salvar(); } catch (e) { setErro(e); } }}>Salvar cotas</BotaoAcao>
              {sujo && <BotaoAcao className="btn" onClick={async () => { await carregar(); setMsg(null); }}>Descartar</BotaoAcao>}
            </div>
          )}
          {sujo && <Alerta tipo="aviso">Cotas alteradas e ainda não salvas (a vista já mostra a mudança).</Alerta>}
          <ErroBox erro={erro} />
          {msg && <Alerta tipo="ok">{msg}</Alerta>}
        </Cartao>
        <Cartao titulo="O que a vista mostra">
          <ul className="nota" style={{ margin: 0, paddingLeft: 18 }}>
            <li>Diâmetros: {calcAtual ? `do cálculo nº ${calc.id}.` : calcRede ? `do cálculo nº ${calc.id}, feito antes da última mudança na rede — recalcule.` : "dos trechos (nenhum cálculo ainda)."}{semDiametro > 0 && ` ${semDiametro} trecho(s) sem diâmetro, em cinza, desenhados com 200 mm só para aparecer.`}</li>
            <li>Pilares até o {cena?.peDireito ? "pé-direito" : "topo da rede + 1 m (pé-direito não informado)"}; obstáculos com {fmt(ILUSTRATIVO.obstaculo, 1)} m (altura ilustrativa).</li>
            <li>Coifas, filtro e exaustor são símbolos, sem as dimensões reais do equipamento.</li>
            <li>Dutos retangulares aparecem como tubo de mesma área.</li>
          </ul>
        </Cartao>
      </div>
    </div>
  );
}

function comRotulos(gl: HTMLCanvasElement, grupo: THREE.Group | null, camera: THREE.Camera, W: number, H: number): string {
  const tela = document.createElement("canvas");
  tela.width = W;
  tela.height = H;
  const c = tela.getContext("2d");
  if (!c) return gl.toDataURL("image/png");
  c.drawImage(gl, 0, 0, W, H);
  c.font = "600 26px system-ui, sans-serif";
  c.textAlign = "center";
  c.textBaseline = "middle";
  const p = new THREE.Vector3();
  grupo?.traverse((o) => {
    if (!(o instanceof CSS2DObject)) return;
    o.getWorldPosition(p).project(camera);
    if (p.z > 1 || Math.abs(p.x) > 1 || Math.abs(p.y) > 1) return; // atrás da câmera ou fora do quadro
    const x = (p.x + 1) / 2 * W, y = (1 - p.y) / 2 * H;
    const texto = o.element.textContent || "";
    const alerta = o.element.classList.contains("rotulo-3d-alerta");
    const suave = o.element.classList.contains("rotulo-3d-suave");
    const w = c.measureText(texto).width + 20, h = 38;
    c.fillStyle = "rgba(255,255,255,.9)";
    c.strokeStyle = alerta ? "#e57373" : "#c9d2dc";
    c.lineWidth = 2;
    c.beginPath();
    c.roundRect(x - w / 2, y - h / 2, w, h, 8);
    c.fill();
    c.stroke();
    c.fillStyle = alerta ? "#b71c1c" : suave ? "#a04000" : "#1d2733";
    c.fillText(texto, x, y + 1);
  });
  return tela.toDataURL("image/png");
}

function descartar(g: THREE.Object3D | null | undefined) {
  g?.traverse((o: any) => {
    o.geometry?.dispose?.();
    const m = o.material;
    if (Array.isArray(m)) m.forEach((x) => x.dispose());
    else m?.dispose?.();
    if (o instanceof CSS2DObject) o.element.remove();
  });
}
