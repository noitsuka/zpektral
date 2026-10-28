from dataclasses import dataclass

from app.busca import ServicoBusca
from app.modelos import Endereco, Oferta, RelatorioFonte
from app.ordenacao import Facetas
from app.saude import SaudeFonte


@dataclass(slots=True)
class InfoFonte:
    id: str
    nome: str
    ativa: bool
    saude: SaudeFonte | None = None


@dataclass(slots=True)
class PaginaBusca:
    consulta: str
    endereco: Endereco | None
    pronto: bool
    pendentes: list[str]
    total: int
    pagina: int
    por_pagina: int
    paginas: int
    ofertas: list[Oferta]
    facetas: Facetas
    fontes: list[RelatorioFonte]
    tempo_ms: int
    cache: bool


def info_das_fontes(servico: ServicoBusca) -> list[InfoFonte]:
    saude = servico.saude.retrato()
    return [InfoFonte(s.id, s.nome, s.ativa, saude.get(s.id)) for s in servico.fontes]
