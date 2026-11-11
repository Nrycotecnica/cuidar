"""Modelos de dados (SQLAlchemy 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def agora() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(200))
    senha_hash: Mapped[str] = mapped_column(String(200))
    perfil: Mapped[str] = mapped_column(String(40))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    registro_profissional: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    usuario_nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acao: Mapped[str] = mapped_column(String(80), index=True)
    entidade: Mapped[str] = mapped_column(String(80), index=True)
    entidade_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    detalhes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, index=True)


class Cliente(TimestampMixin, Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    industria: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(30), nullable=True)
    endereco: Mapped[str | None] = mapped_column(Text, nullable=True)
    contato_nome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contato_telefone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contato_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    atividade: Mapped[str | None] = mapped_column(String(200), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    demonstrativo: Mapped[bool] = mapped_column(Boolean, default=False)


class Projeto(TimestampMixin, Base):
    __tablename__ = "projetos"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    modulo: Mapped[str] = mapped_column(String(20))  # poeira | fumos | renovacao
    status: Mapped[str] = mapped_column(String(30), default="rascunho")
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Dados de entrada com status de confirmação: {campo: {valor, unidade, status, fonte}}
    entradas: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ambiente: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # contorno, obstáculos, pilares (m)
    riscos: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checklist_seguranca: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    exaustor_id: Mapped[int | None] = mapped_column(ForeignKey("exaustores.id"), nullable=True)
    demonstrativo: Mapped[bool] = mapped_column(Boolean, default=False)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    aprovado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculo_aprovado_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cliente: Mapped[Cliente | None] = relationship()


class Visita(TimestampMixin, Base):
    __tablename__ = "visitas"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    projeto_id: Mapped[int | None] = mapped_column(ForeignKey("projetos.id"), nullable=True)
    data: Mapped[str | None] = mapped_column(String(20), nullable=True)
    responsavel_visita: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dados: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)


class Arquivo(Base):
    __tablename__ = "arquivos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(300))
    tipo_mime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tamanho: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    chave: Mapped[str] = mapped_column(String(300))
    categoria: Mapped[str] = mapped_column(String(40), default="documento")  # planta|foto|video|documento|memorial|...
    projeto_id: Mapped[int | None] = mapped_column(ForeignKey("projetos.id"), nullable=True)
    visita_id: Mapped[int | None] = mapped_column(ForeignKey("visitas.id"), nullable=True)
    projeto_antigo_id: Mapped[int | None] = mapped_column(ForeignKey("projetos_antigos.id"), nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    enviado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Planta(TimestampMixin, Base):
    """Planta importada (DXF/PDF/imagem) com geometria normalizada e calibração."""
    __tablename__ = "plantas"
    id: Mapped[int] = mapped_column(primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projetos.id"))
    arquivo_id: Mapped[int] = mapped_column(ForeignKey("arquivos.id"))
    nome: Mapped[str] = mapped_column(String(300))
    origem: Mapped[str] = mapped_column(String(20))  # dxf | pdf | imagem | dwg
    unidade_original: Mapped[str | None] = mapped_column(String(20), nullable=True)
    escala_m_por_unidade: Mapped[float | None] = mapped_column(Float, nullable=True)
    escala_confirmada: Mapped[bool] = mapped_column(Boolean, default=False)
    escala_info: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    geometria: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # entidades em unidades do desenho
    deteccoes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # paredes, pilares, máquinas (editáveis)
    imagem_arquivo_id: Mapped[int | None] = mapped_column(ForeignKey("arquivos.id"), nullable=True)
    pagina: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Exaustor(TimestampMixin, Base):
    __tablename__ = "exaustores"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    modelo: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(60))  # centrifugo_radial | centrifugo_limite | axial | parede ...
    rotacao_rpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    potencia_motor_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
    rendimento: Mapped[float | None] = mapped_column(Float, nullable=True)
    diametro_rotor_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    boca_entrada_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    boca_saida: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dimensoes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    materiais: Mapped[str | None] = mapped_column(String(200), nullable=True)
    temperatura_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    limites: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    densidade_referencia: Mapped[float] = mapped_column(Float, default=1.2)
    tipo_pressao_curva: Mapped[str] = mapped_column(String(10), default="estatica")
    curva: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{vazao_m3h, pressao_pa, potencia_kw?, rendimento?}]
    preco: Mapped[float | None] = mapped_column(Float, nullable=True)
    custo_fabricacao: Mapped[float | None] = mapped_column(Float, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    demonstrativo: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="proposto")  # proposto | aprovado


class ComponenteDuto(TimestampMixin, Base):
    __tablename__ = "componentes_duto"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    categoria: Mapped[str] = mapped_column(String(40), index=True)
    descricao: Mapped[str] = mapped_column(String(300))
    forma: Mapped[str] = mapped_column(String(20), default="circular")
    diametro_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    diametro2_mm: Mapped[float | None] = mapped_column(Float, nullable=True)  # reduções/derivações
    largura_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    altura_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    espessura_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    material: Mapped[str | None] = mapped_column(String(60), nullable=True)
    comprimento_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    angulo_graus: Mapped[float | None] = mapped_column(Float, nullable=True)
    coef_perda_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    massa_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    unidade: Mapped[str] = mapped_column(String(10), default="un")
    custo_unitario: Mapped[float | None] = mapped_column(Float, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    demonstrativo: Mapped[bool] = mapped_column(Boolean, default=False)


class ParametroTecnico(TimestampMixin, Base):
    __tablename__ = "parametros_tecnicos"
    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    categoria: Mapped[str] = mapped_column(String(80), default="Geral")
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor: Mapped[Any] = mapped_column(JSON)
    unidade: Mapped[str | None] = mapped_column(String(40), nullable=True)
    referencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposto")
    aprovado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demonstrativo: Mapped[bool] = mapped_column(Boolean, default=False)


class Rede(TimestampMixin, Base):
    __tablename__ = "redes"
    id: Mapped[int] = mapped_column(primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projetos.id"), index=True)
    nome: Mapped[str] = mapped_column(String(200), default="Rede principal")
    dados: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # {nodes, segments}
    configuracao: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    versao: Mapped[int] = mapped_column(Integer, default=1)


class Calculo(Base):
    __tablename__ = "calculos"
    id: Mapped[int] = mapped_column(primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projetos.id"), index=True)
    rede_id: Mapped[int | None] = mapped_column(ForeignKey("redes.id"), nullable=True)
    rede_versao: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tipo: Mapped[str] = mapped_column(String(30))  # rede | renovacao | alternativas
    versao_motor: Mapped[str] = mapped_column(String(20))
    versao_app: Mapped[str] = mapped_column(String(40))
    hash_entradas: Mapped[str] = mapped_column(String(64))
    entradas: Mapped[dict[str, Any]] = mapped_column(JSON)
    resultados: Mapped[dict[str, Any]] = mapped_column(JSON)
    situacao: Mapped[str] = mapped_column(String(20))  # ok | com_bloqueios
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class ProjetoAntigo(TimestampMixin, Base):
    __tablename__ = "projetos_antigos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cliente: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modulo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    # dados técnicos de referência: vazao_total_m3h, pressao_total_pa, exaustor, diametros, comprimento_total_m...
    dados: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    desempenho_real: Mapped[str | None] = mapped_column(Text, nullable=True)
    confiabilidade: Mapped[str] = mapped_column(String(20), default="nao_verificado")
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)


class Versao(Base):
    """Histórico de versões implantadas neste ambiente."""
    __tablename__ = "versoes"
    __table_args__ = (UniqueConstraint("versao", "git_sha", name="uq_versao_sha"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    versao: Mapped[str] = mapped_column(String(40))
    git_sha: Mapped[str] = mapped_column(String(64))
    ambiente: Mapped[str] = mapped_column(String(30))
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    implantado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
