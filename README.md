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
postes a instalar. No desenho, cada ativo numerado recebe somente seu
identificador; estados como instalar, abrir ou desligar são mantidos somente
como dados internos e não alteram a aparência. Traço, preenchimento e cor são preservados
literalmente da aba `Simbologia`, sem variantes geradas por estado. Areas de
trabalho LM/LV, contornos, chamadas, caixas
de texto e observacoes operacionais nao sao adicionados. Ativos ausentes da
entrada nunca sao inferidos a partir de uma OS ou de um caso do corpus.

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

## Usuarios e projetos

Na primeira inicializacao, o sistema cria exatamente oito contas:

- `caxias1` e `caxias2`: acesso exclusivo ao projeto Caxias;
- `vacaria1` e `vacaria2`: acesso exclusivo ao projeto Vacaria;
- `admin1`, `admin2`, `admin3` e `admin4`: acesso aos dois projetos.

As senhas sao armazenadas somente como hash. Se
`CROQUIMAKER_BOOTSTRAP_PASSWORD` estiver vazio, cada conta recebe uma senha
aleatoria diferente. Consulte as credenciais iniciais no proprio servidor:

```bash
docker compose exec web python -m croquimaker.auth show-initial-credentials
```

Depois da distribuicao, redefina as senhas necessarias:

```bash
docker compose exec web python -m croquimaker.auth set-password caxias1
```

Os projetos e todos os seus arquivos ficam fisicamente isolados:

```text
generated/projects/caxias/jobs/
generated/projects/vacaria/jobs/
```

Usuarios regionais nao podem trocar de projeto. Administradores selecionam
Caxias ou Vacaria no cabecalho; o backend aplica a mesma selecao ao upload,
status e downloads. Para uma publicacao HTTPS, configure
`CROQUIMAKER_COOKIE_SECURE=1`.

## Persistencia, dashboard e auditoria

Depois do login, o dashboard apresenta indicadores, projetos recentes e a
atividade operacional. Os usuarios de Caxias e Vacaria visualizam somente os
registros da propria unidade; administradores recebem a visao consolidada das
duas unidades.

Cada envio cria um registro no banco operacional antes de entrar na fila. O PDF
de entrada, o resultado, o manifesto e os diagnosticos permanecem no volume
`croquimaker_generated`, inclusive depois de `docker compose down` e de
reinicializacoes do servidor. Processamentos interrompidos sao retomados quando
a aplicacao volta a iniciar.

Os arquivos recebem nomes individuais, por exemplo:

```text
PROJETO-CAXIAS-20260724T153000Z-A1B2C3D4E5.pdf
CROQUI-CAXIAS-20260724T153000Z-A1B2C3D4E5.pdf
```

O banco registra unidade, responsavel, datas, estado, nome original, nomes
tecnicos e hashes SHA-256 da entrada e da saida. A trilha de auditoria inclui
acessos, troca de unidade, criacao, inicio, conclusao, falha e downloads. Os
eventos sao encadeados por hash, e a tela de auditoria verifica a integridade da
cadeia e permite exportar os registros visiveis em CSV.

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
