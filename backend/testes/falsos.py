import asyncio

from app.fontes.base import ContextoBusca, Previa
from app.modelos import Frete, Loja, Oferta, StatusFrete


class FonteFalsa:
    def __init__(
        self,
        id: str,
        ofertas: list[tuple] = (),
        *,
        atraso: float = 0,
        erro: Exception | None = None,
        ativa: bool = True,
        previa_apos: float | None = None,
    ):
        self.id = id
        self.nome = id.title()
        self._ofertas = list(ofertas)
        self._atraso = atraso
        self._erro = erro
        self._ativa = ativa
        self._previa_apos = previa_apos
        self.chamadas = 0

    @property
    def ativa(self) -> bool:
        return self._ativa

    async def buscar(self, ctx: ContextoBusca, previa: Previa | None = None) -> list[Oferta]:
        self.chamadas += 1
        if previa is not None and self._previa_apos is not None:
            await asyncio.sleep(self._previa_apos)
            previa(self._montar(ctx, Frete(StatusFrete.CALCULANDO)))
        await asyncio.sleep(self._atraso)
        if self._erro:
            raise self._erro
        frete = (
            Frete(StatusFrete.CALCULADO, valor=1000, prazo="até 3 dias úteis", prazo_dias=3)
            if ctx.endereco
            else Frete(StatusFrete.SEM_CEP)
        )
        return self._montar(ctx, frete)

    def _montar(self, ctx: ContextoBusca, frete: Frete) -> list[Oferta]:
        return [
            Oferta(
                id=f"{self.id}:{n}",
                titulo=titulo,
                link=f"https://{self.id}.example/{n}",
                loja=Loja(self.id, self.nome),
                preco=preco,
                frete=frete,
                relevancia=ctx.relevancia_de(titulo),
                ean=ean[0] if ean else None,
            ).consolidar()
            for n, (titulo, preco, *ean) in enumerate(self._ofertas)
        ]
