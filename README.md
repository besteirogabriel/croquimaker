# CroquiMaker JOBEL

Sistema local para transformar projetos elétricos em croquis JOBEL/RGE, revisar o resultado no navegador e regenerar PDF e Excel a partir da mesma revisão técnica.

## Fluxo operacional

1. O engenheiro envia o PDF do projeto.
2. O backend extrai os equipamentos e decide automaticamente o equipamento principal e o foco da isolação.
3. O croqui gerado abre diretamente no editor; não existe etapa obrigatória de escolha manual antes da geração.
4. O engenheiro pode mover, incluir ou remover elementos, trocar o equipamento principal, editar cabeçalho, rótulos, redes e área de trabalho.
5. Ao regenerar, o backend usa exatamente o grafo editado, sem executar a inferência novamente.
6. Cada geração é registrada como uma revisão e produz PDF, XLS e XLSX coerentes.

O Excel usa um croqui oficial como template e clona objetos da aba `Simbologia`. Poste, equipamento, linha, área de trabalho e rótulo permanecem objetos separados; a planilha não é uma captura de tela do editor. O logo RGE também vem do template oficial.

## Execução com Docker

```bash
cp .env.example .env
docker compose up --build
```

Abra `http://localhost:5000`.

Os projetos e usuários existentes continuam na base SQLite montada em `./data`. O dashboard separa os projetos por Caxias do Sul e Vacaria e atualiza a cidade usando o município extraído ou corrigido no editor.

## Configuração importante

- `SECRET_KEY`: segredo de sessão do backend.
- `CROQUI_ADMIN_EMAIL` e `CROQUI_ADMIN_PASSWORD`: acesso administrativo inicial.
- `CROQUI_EXCEL_TEMPLATE_PATH`: caminho opcional para um XLS oficial com as abas `Croqui` e `Simbologia`.
- `CROQUI_GOLDEN_CORPUS_PATH`: corpus homologado usado para decisões exatas e seleção automática de template.
- `CROQUI_USE_CORPUS_REFERENCE_OUTPUTS=false`: mantém a geração ativa; os pares oficiais são usados como referência, não copiados como resposta.

O engine de decisão desta versão funciona offline. Nenhuma chave de API é enviada ou gravada no frontend. Se um provedor de IA for conectado depois, a chave deve existir somente no `.env` do backend e nunca em variáveis `VITE_*`.

## Desenvolvimento

Backend:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app croqui_engine.app.web run --host=0.0.0.0 --port=5000
```

Editor:

```bash
cd frontend
npm ci
npm run test
npm run build
```

Testes do engine:

```bash
pytest -q
```

O container inclui LibreOffice Calc/Draw porque a conversão dos objetos oficiais entre XLS, XLSX e PDF faz parte do pipeline de saída.
