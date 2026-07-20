# CroquiMaker JOBEL

Sistema local para transformar projetos elétricos em croquis JOBEL/RGE, revisar o resultado no navegador e regenerar PDF e Excel a partir da mesma revisão técnica.

## Fluxo operacional

1. O engenheiro envia o PDF do projeto.
2. O engine local extrai, decide o equipamento principal, monta o posicionamento e valida o resultado.
3. Somente se a decisão local estiver incompleta, ambígua, com baixa confiança ou bloqueada pela validação, o backend envia o PDF e o contexto técnico à OpenAI.
4. A proposta da OpenAI volta ao engine local e passa novamente pelas mesmas regras de decisão, foco e validação. Ela nunca é aceita sem essa revalidação.
5. O backend clona os objetos oficiais da aba `Simbologia` para a aba `Croqui` e gera o XLSX/XLS editável.
6. O PDF é convertido da primeira aba desse mesmo Excel; SVG é apenas a prévia do editor e nunca é fonte do PDF ou do Excel.
7. O croqui abre no editor para o engenheiro mover, incluir ou remover elementos, trocar o equipamento principal e ajustar cabeçalho, rótulos, redes e área de trabalho.
8. Ao regenerar, o backend usa exatamente o posicionamento editado, sem executar nova inferência, recria o Excel oficial e deriva novamente o PDF dele.
9. Cada geração é registrada como uma revisão.

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

O engine local é sempre o caminho principal e funciona offline. A OpenAI é um fallback opcional do backend; a chave nunca é enviada, gravada ou exposta no frontend.

- `CROQUI_OPENAI_FALLBACK=true`: habilita a escalada automática quando a validação local não consegue concluir.
- `CROQUI_OPENAI_FALLBACK_CONFIDENCE=0.72`: confiança mínima abaixo da qual o backend pode escalar.
- `OPENAI_API_KEY`: chave secreta lida apenas pelo processo Python no backend.
- `OPENAI_MODEL`: modelo usado no fallback estruturado.

Não use prefixo `VITE_` na chave e não a inclua em imagens ou no repositório. Sem `OPENAI_API_KEY`, o sistema continua com o engine local e encaminha casos não resolvidos para revisão humana.

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
