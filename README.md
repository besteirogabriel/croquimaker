# Croquimaker

Aplicacao local para receber um PROJETO PDF vetorial e gerar um croqui a partir
da geometria CAD real da rede.

O pipeline preserva as coordenadas do projeto:

```text
PDF vetorial
-> condutores CAD (azul=MT, verde=BT)
-> projeto limpo
-> identificacao semantica
-> grafo de conectividade
-> subgrafo relacionado ao servico
-> somente linhas e postes
-> croqui A4 horizontal
```

Mapa, lotes, cotas, tabelas e carimbo nao participam da fonte geometrica. A
identificacao semantica nao cria coordenadas. O desenho final nao adiciona
areas de trabalho, contornos, legendas ou equipamentos inferidos.

## Login inicial

```bash
docker compose --profile login run --rm codex-login
```

## Iniciar

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f web
```

Acesse `http://localhost:8080`.

Para usar outra porta:

```bash
CROQUIMAKER_HOST_PORT=8082 docker compose up -d
```

## Desenvolvimento e testes

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

Teste local sem login externo:

```bash
CROQUIMAKER_PROVIDER=fake docker compose up --build web
```

Cada job grava internamente `clean_projeto.pdf`, `clean_projeto.png`, inventario
de cores, extracao geometrica e `network_selection.json` para auditoria. O JSON
registra componentes, ancoras, postes, trechos selecionados e avisos de cobertura.
Quando o projeto nao contem geometria suficiente ou o equipamento principal nao
pode ser posicionado, o diagnostico fica como `needs_review`; o motor nao completa
a rede com coordenadas inventadas. O cache inclui a versao do motor, impedindo o
reaproveitamento de resultados do gerador antigo.

Antes do envio, a interface permite informar as dez respostas da avaliacao de
viabilidade. Respostas ausentes permanecem como `Nao Avaliado`; o sistema nao
confirma automaticamente verificacoes de seguranca que nao constam do projeto.
O percentual reproduz a formula observada na planilha oficial RGE.

O download de Excel permanece desabilitado. O arquivo anteriormente usado era
uma copia de um croqui real de outro projeto e podia contaminar o resultado. Ele
so deve voltar quando houver um template canonico vazio e um gerador que edite a
mesma cena usada no PDF.
