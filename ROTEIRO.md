# Roteiro da apresentação (18/11)

Uns 10 minutos. O painel é a tela principal.

## Antes de começar

- [ ] Ambiente instalado e `./scripts/demo.sh --sem-painel` rodado; ele preenche `runs/demo` em menos de 1 minuto.
- [ ] `paviscan painel --runs runs/demo` aberto no navegador em tela cheia.
- [ ] Internet para o mapa de fundo (Carto). Sem internet, a ortofoto e os buracos continuam aparecendo; só some o fundo de ruas.
- [ ] Plano B: se a imagem real falhar, a demo inteira funciona com o levantamento `sintetico`.

## 1. O problema (1 min)

Medir buraco em campo é lento e subjetivo. Com uma ortofoto de drone dá para localizar e medir cada panela de uma vez, em metros, e saber quais trechos estão piores. É um retrato da data do voo.

Na imagem: a regra do insumo. O buraco precisa de pelo menos 6 pixels de lado, então GSD de 5 cm/px ou melhor. Google Earth (15 a 50 cm) não serve.

## 2. Como funciona (2 min)

Fluxo: ortofoto + polígono da pista → detector → polígonos em UTM → medidas → segmentos de 20 m → painel.

O que vale dizer sobre o detector:

- Compara cada pixel com o asfalto em volta (fundo local de 2 m), e não com um limiar único para a imagem toda. Isso cancela sombra larga e variação de luz.
- O limiar é robusto (mediana + k × MAD). Explicar por que não Otsu: ele sempre divide a imagem em duas classes e inventaria buraco em pista boa.
- Filtros de forma em metros cortam faixa pintada, trinca e sombra. Um último filtro descarta mancha escura colada a objeto claro grande, que é para-brisa ou sombra de carro.
- Tudo atrás de uma interface `Detector`: o YOLO de segmentação entra no mesmo lugar sem mudar o resto.

## 3. Prova no sintético (2 min)

Levantamento `sintetico`, uma cena gerada com gabarito conhecido.

- 8 de 8 buracos, nenhum falso positivo, erro de área de 3 a 4%. Também nas seeds 11, 23 e 42 e com GSD de 1 a 5 cm.
- A cena tem de propósito faixa pintada, trinca e sombra larga, e nenhuma vira buraco. Em pista sem buraco, zero detecções.
- Mostrar: o mapa com as cores de severidade, o tooltip (área, largura x comprimento, confiança) e o gráfico por segmento.

## 4. Imagem real (3 min)

Levantamento da avenida em Manaus: 3 cm/px, 120 m, 6 segmentos.

- Mostrar o mapa e passar o mouse nas detecções.
- Ser honesto sobre o que aparece:
  - o caminhão escuro gera várias detecções;
  - a borda desgastada e a sarjeta geram manchas pequenas;
  - a sombra do poste também.
  - O filtro de veículo claro já tirou os para-brisas, que tinham confiança 1,0.
- Usar os filtros ao vivo:
  - subir a confiança mínima;
  - filtrar severidade;
  - escolher um segmento e ver os indicadores mudarem para aquele trecho.
- Mensagem: o método sem aprendizado acha tudo o que é escuro e compacto. O filtro de confiança e o polígono bem desenhado (sem sarjeta) resolvem boa parte. O resto pede o YOLO treinado.

## 5. Saídas (1 min)

- Baixar o XLSX e o GeoJSON pelo painel. O GeoJSON abre direto no QGIS, em UTM.
- "Processar nova imagem": escolher a ortofoto do acervo e processar ao vivo. Leva uns 5 s para 120 m de pista.

## 6. Limites e próximos passos (1 min)

- Limites: óleo, remendo, bueiro, poça e veículo escuro viram buraco. Não mede profundidade. Pista reta (o eixo vem do retângulo mínimo).
- Próximos passos:
  1. YOLO de segmentação do mestrado pela interface `Detector`.
  2. Upload de imagem pelo painel (o armazenamento no acervo já está pronto).
  3. Trecho com panelas reais para medir recall em campo.

## Perguntas prováveis

- **Por que não só watershed?** Watershed separa regiões que se tocam, mas não decide o que é buraco. Ele só entra para separar dois buracos colados.
- **E a severidade?** São faixas de área configuráveis (0,25 e 1 m²). É um filtro de trabalho, não classificação de norma.
- **Funciona com outra resolução?** Sim, todos os limiares estão em metros. Testado de 1 a 5 cm/px.
- **Imagem grande?** Lê por janelas e só a área da pista, nunca o raster inteiro. A ortofoto real tem 170 Mpx; os 120 m de avenida processam em uns 4 s com pico de ~225 MB de memória.
