# Auditoria Tecnica e Baseline do Projeto

Data da auditoria: 2026-06-24.

## Estrutura Original Observada

Arquivos principais na raiz antes da modularizacao:

- `app.py`: Flask legado com upload, extracao, rota `/interpretar` via Claude e geracao PDF/Excel.
- `main.py`: CLI legado para extrair projeto e gerar PDF/Excel.
- `interpretador_ia.py`: integracao operacional com Anthropic/Claude, preservada desativada em `projeto_legado/ai_interpreter_original_disabled.py.txt`.
- `extrator.py`, `extrator_v3.py`, `extrator_posicional.py`: extratores deterministas com pdfplumber/PyMuPDF.
- `topologia.py`: construcao inicial de grafo.
- `gerador_pdf.py`, `gerador_croqui_v2.py`, `gerador_croqui_v3.py`, `gerador_croqui_v4.py`: geradores ReportLab experimentais.
- `gerador_excel.py`: preenchimento de template `.xls`.
- `debug_*.py`, `analisa_croqui_real.py`: scripts exploratorios.
- `croquisreais/`: pasta local criada com PDFs reais para validacao manual.

O diretorio nao estava versionado como repositorio Git no momento da auditoria.

Depois da reorganizacao, os scripts antigos e exploratorios foram isolados em `projeto_legado/`. A raiz mantem apenas os wrappers atuais `app.py` e `main.py`, que apontam para a nova arquitetura `croqui_engine/`.

## Rotas Flask Legadas

O `app.py` antigo expunha:

- `GET /`
- `POST /extrair`
- `POST /interpretar`
- `POST /gerar`
- `GET /status/<job_id>`
- `GET /download/<job_id>/<tipo>`

Problema central: `/interpretar` salvava PDF localmente e acionava `interpretador_ia.interpretar_pdf`, enviando texto/imagens para Claude.

## Funcoes de Extracao Existentes

- `extrator.extrair_projeto`: extracao por pdfplumber, reconstruindo linhas e buscando transformadores, postes e vaos.
- `extrator_v3.extrair_dados`: extracao PyMuPDF por spans/palavras.
- `extrator_posicional.extrair_rede_posicional`: reconstrucao de IDs por caracteres e coordenadas.
- Scripts de debug exploravam `page.get_drawings()`, OCR e comparacao com croquis reais.

## Funcoes de Geracao Existentes

- `gerador_pdf.gerar_croqui_pdf`
- `gerador_croqui_v2.gerar_croqui`
- `gerador_croqui_v3.gerar_croqui_from_payload`
- `gerador_croqui_v4.gerar_croqui_v4`
- `gerador_excel.gerar_croqui_excel`

## Dependencias Inferidas

Imports observados: Flask, PyMuPDF/fitz, pdfplumber, ReportLab, xlrd, xlwt, xlutils, Pillow, pytesseract em script de debug, dataclasses e bibliotecas padrao.

Dependencia critica removida do fluxo principal: `anthropic`.

## Problemas Encontrados

- Dependencia operacional de IA externa.
- Dados sensiveis poderiam sair do ambiente local na rota `/interpretar`.
- Estado de jobs em memoria, sem persistencia.
- Ausencia de login e perfis.
- Arquitetura em scripts soltos.
- Falta de contrato JSON central.
- Falta de testes automatizados.
- Docker/configuracao ausentes.
- Templates HTML antigos nao existiam no diretorio atual.

## Riscos Tecnicos

- PDFs CAD podem fragmentar texto e coordenadas.
- Simbologia oficial nao esta disponivel.
- Associacao espacial entre equipamento e poste ainda exige calibracao.
- Excel oficial depende de template homologado.
- Sem amostras aprovadas, metricas de acuracia sao preliminares.

## Pontos de Reaproveitamento

- Regex de transformadores, FC/FU, postes e vaos.
- Experiencia com PyMuPDF em `projeto_legado/extrator_v3.py`.
- Ideias de layout ortogonal em `projeto_legado/gerador_croqui_v4.py`.
- Estrutura de Excel `.xls` em `projeto_legado/gerador_excel.py`.
- Tabela de viabilidade e convencoes visuais dos geradores legados.

## Acao Executada

O codigo legado foi movido para `projeto_legado/`, incluindo `flask_app_legacy.py`, `cli_legacy.py`, extratores, geradores e scripts de debug. O interpretador Claude foi preservado como texto desativado em `projeto_legado/ai_interpreter_original_disabled.py.txt`, e o modulo seguro `projeto_legado/ai_interpreter_disabled.py` falha fechado sem importar SDK externo.
