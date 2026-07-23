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
-> linhas, postes e equipamentos comprovados
-> croqui A4 horizontal
```

Mapa, lotes, cotas, tabelas e carimbo nao participam da fonte geometrica. A
identificacao semantica nao cria coordenadas nem altera identificadores. O
desenho final preserva os numeros e simbolos de transformadores, chaves e demais
ativos comprovados no PDF recebido, alem de diferenciar postes existentes e
postes a instalar. Areas de trabalho, contornos e observacoes operacionais nao
sao adicionados. Ativos ausentes da entrada nunca sao inferidos a partir de uma
OS ou de um caso do corpus.

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

A avaliacao de viabilidade nao exige preenchimento do operador. O sistema aplica
automaticamente o perfil padrao observado nos croquis RGE: `Sim` nas nove
primeiras linhas e `Nao` na pergunta de cancelamento ou reprogramacao. O rodape
e o percentual sao preenchidos durante a geracao do PDF.

O download de Excel permanece desabilitado. O arquivo anteriormente usado era
uma copia de um croqui real de outro projeto e podia contaminar o resultado. Ele
so deve voltar quando houver um template canonico vazio e um gerador que edite a
mesma cena usada no PDF.
