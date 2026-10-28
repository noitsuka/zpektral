# Símbolo em forma de prisma

Aceita em outubro de 2026.

## Contexto

O símbolo anterior era um Z montado com barras de gráfico e um efeito de interferência ciano e magenta. Em 16 px virava uma mancha, e a forma não dizia nada sobre o que o site faz.

## Decisão

O símbolo é um Z que funciona como um prisma. A barra de cima é um feixe único, o preço anunciado. A diagonal é um bloco translúcido com as duas arestas longas marcadas. A barra de baixo se abre em linhas finas de comprimentos diferentes, uma por loja, e a mais curta, em ouro, é o menor total.

As linhas vêm do mesmo espectro de preços que já movia o favicon durante a busca (`nucleo/espectro.ts`), e a geometria fica em `nucleo/simbolo.ts`, usada pelo componente, pelo favicon ao vivo, pelo `icon.svg`, pelo ícone da Apple e pela imagem de compartilhamento. O "z" do nome usa a mesma inclinação da diagonal.

Em tamanho de aba o ícone usa três linhas mais grossas no lugar de quatro, para que cada uma ainda ocupe pelo menos um pixel com folga. Enquanto as lojas respondem, as linhas oscilam sem ouro e um brilho percorre o feixe; com movimento reduzido, o símbolo fica parado.

## Alternativas rejeitadas

- Linhas de emissão (um Z com marcas curtas na diagonal e uma marca alta em ouro): em 16 px as marcas viram pontos.
- Retícula (um Z dentro de cantoneiras, como as molduras da página): combina com a interface, mas não fala de preço nem de comparação.

## Consequências

O símbolo depende de cor só para a linha mais barata; em uma cor, o Z e o leque de linhas continuam legíveis. Qualquer mudança no desenho passa por `formaDoSimbolo`, coberta por `simbolo.test.ts`.
