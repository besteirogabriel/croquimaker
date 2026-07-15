# CroquiMaker V1 - Mapeamento do pipeline atual e contrato de output

Data: 2026-07-06.

Escopo: mapeamento tecnico do engine atual, pontos onde PDF/XLS sao decididos, onde o equipamento principal e inferido, onde cabecalhos sao preenchidos, onde PDF e XLS podem divergir, e proposta inicial do contrato de output final. Este documento nao altera logica executavel.

## Resumo executivo

O produto final atual ainda e comandado por `TechnicalPayload`, nao por um contrato de output. Esse payload e util como modelo intermediario, mas hoje ele pode aprovar um croqui cujo equipamento esperado aparece apenas como codigo secundario.

O equipamento principal e definido em duas camadas principais:

- texto da TES/plano de manobra em `croqui_engine/parser/tes_parser.py:9`, que pode gravar `payload.meta["main_switching_equipment"]`;
- heuristica espacial em `croqui_engine/core/pipeline.py:229`, acionada quando o campo textual nao existe, usando o cluster dominante de linhas vermelhas e os labels numericos do projeto.

Os outputs PDF e XLS consomem o mesmo `TechnicalPayload`, mas nao sao renderizados pela mesma superficie final:

- PDF final usa SVG/PyMuPDF via `croqui_engine/rendering/final_croqui_renderer.py:36` e `croqui_engine/rendering/svg_croqui_renderer.py:23`;
- XLS atual e gerado do zero por `croqui_engine/generators/excel_generator.py:181` e embute um BMP gerado por outro caminho de desenho em `croqui_engine/generators/excel_generator.py:466`.

A validacao atual nao e bloqueante por output final. `diff_report.json` em `croqui_engine/core/pipeline.py:141` verifica marcadores brutos proibidos no PDF, mas nao compara equipamento/cabecalho/foco contra referencia. O benchmark tecnico em `croqui_engine/benchmark/technical_metrics.py:7` usa `expected_code in detected_codes`, que e fraco para a V1 porque nao valida cabecalho nem foco principal.

Caso observado: `data/outputs/1d5195762b68/technical_payload.json` contem `main_switching_equipment: "TR 1297574"`, enquanto o caso de corpus `300001101207` espera `CROQUI TR 634087`. O codigo `634087` aparece em `equipment`, mas nao como principal. Mesmo assim `data/outputs/1d5195762b68/diff_report.json` marca `technical_score: 1.0` e `passed_acceptance: true`.

## Fluxo atual de ponta a ponta

### 1. Upload e persistencia inicial

Entrada:

- PDF enviado pelo usuario.

Modulos:

- `croqui_engine/app/routes/job_routes.py:56` (`upload`);
- `croqui_engine/storage/file_store.py` (`new_job_id`, `save_uploaded_pdf`, `job_upload_dir`, `job_output_dir`);
- `croqui_engine/core/pipeline.py:31` (`process_pdf`).

Saida:

- `data/uploads/<job_id>/original.pdf`;
- `data/uploads/<job_id>/original_filename.txt`;
- registro do job no SQLite;
- chamada sincrona para `process_pdf(pdf_path, job_id)`.

Observacao:

- A rota de upload apenas processa o payload. PDF/XLS finais sao gerados depois por download ou pela API de geracao.

### 2. Classificacao de paginas e thumbnails

Entrada:

- PDF original.

Modulos:

- `croqui_engine/ingestion/page_classifier.py:85` (`classify_pdf_pages`);
- `croqui_engine/ingestion/page_classifier.py:12` (`classify_page`);
- `croqui_engine/ingestion/page_renderer.py` (`render_all_thumbnails`).

Saida:

- lista de `PageInfo` em `payload.pages`;
- thumbnails em `data/uploads/<job_id>/pages/`.

Uso posterior:

- `PageInfo.kind` influencia validacao estrutural e fallback de pagina no PDF legado;
- nao ha contrato de output nesta etapa.

### 3. Extracao bruta de texto, coordenadas e vetores

Entrada:

- PDF original e paginas classificadas.

Modulos:

- `croqui_engine/extraction/raw_document.py:10` (`extract_raw_document`);
- `croqui_engine/extraction/text_extractor.py:8` (`extract_words`);
- `croqui_engine/extraction/text_extractor.py:36` (`extract_text_blocks`);
- `croqui_engine/extraction/vector_extractor.py:8` (`extract_drawings`).

Saida:

- `data/outputs/<job_id>/raw_extraction.json`;
- `raw["words"]`, `raw["blocks"]`, `raw["drawings"]`, `raw["pages"]`, `raw["pdf"]`.

Uso posterior:

- texto bruto alimenta parsers;
- desenhos vetoriais alimentam `project_vector_trace`;
- palavras com bbox alimentam labels numericos e posicoes.

### 4. Parse textual e montagem inicial do payload

Entrada:

- `all_text` vindo de blocks/words;
- `words` convertidos para `ExtractedWord`.

Modulos:

- `croqui_engine/parser/tes_parser.py:9` (`parse_tes_text`);
- `croqui_engine/parser/project_text_parser.py:27` (`parse_project_text`);
- `croqui_engine/parser/tes_parser.py:75` (`parse_tes_equipment`);
- `croqui_engine/parser/equipment_parser.py:9` (`parse_equipment_from_text`);
- `croqui_engine/parser/equipment_parser.py:36` (`parse_equipment_from_words`);
- `croqui_engine/extraction/vector_trace.py:7` (`build_project_vector_trace`).

Saida:

- `payload.meta` com campos de TES, municipio, endereco, plano de manobra, acoes e possivel `main_switching_equipment`;
- listas de `Node`, `Span`, `Equipment`, `MaterialItem`, `WorkArea`;
- `payload.meta["project_numeric_labels"]`;
- `payload.meta["project_numeric_label_positions"]`;
- `payload.meta["project_vector_trace"]`.

Ponto critico:

- `parse_tes_text` escolhe um `main_switching_equipment` a partir de acoes de manobra, priorizando a primeira acao com status `abrir` ou `fechar` em `croqui_engine/parser/tes_parser.py:65`.
- Esse campo nao tem fonte/precedencia registrada. Depois, se ele existir, a heuristica espacial nao roda.

### 5. Inferencia de equipamento principal

Entrada:

- `parsed["equipment"]`;
- `payload.meta["project_vector_trace"]`;
- possivel `payload.meta["main_switching_equipment"]` vindo da TES.

Modulos:

- `croqui_engine/core/pipeline.py:80` decide se infere;
- `croqui_engine/core/pipeline.py:229` (`_infer_main_switching_equipment`);
- `croqui_engine/core/pipeline.py:269` (`_dominant_work_cluster`).

Regra atual:

- se `payload.meta["main_switching_equipment"]` ja existe, mantem;
- senao, coleta pontos de segmentos vermelhos;
- escolhe cluster dominante;
- calcula centro do cluster;
- ranqueia equipamentos por distancia do label ao centro;
- da prioridade a `TRANSFORMADOR` ate distancia 260;
- grava algo como `TR 1297574`.

Risco V1:

- a heuristica de proximidade pode escolher o equipamento visualmente proximo do traco vermelho, mas diferente do croqui final aprovado;
- nao ha contrato com fonte superior para impedir sobrescrita;
- se a heuristica escolher errado, os renderers tratam esse valor como verdade de cabecalho/foco.

### 6. Grafo, topologia e validacao estrutural

Entrada:

- nodes, spans, equipment e payload parcialmente preenchido.

Modulos:

- `croqui_engine/topology/graph_builder.py:9` (`build_graph`);
- `croqui_engine/topology/graph_builder.py:39` (`_add_fallback_reference_layout`);
- `croqui_engine/topology/graph_builder.py:85` (`_associate_equipment`);
- `croqui_engine/topology/graph_builder.py:102` (`_assign_missing_positions`);
- `croqui_engine/topology/graph_validator.py:23` (`validate_graph`);
- `croqui_engine/topology/graph_validator.py:180` (`calculate_confidence`).

Saida:

- `payload.nodes`, `payload.spans`, `payload.equipment`;
- `payload.validations`;
- `payload.confidence_global`.

Ponto critico:

- `validate_graph` emite warning `MAIN_SWITCHING_EQUIPMENT_NOT_FOUND` se o texto principal nao aparece nos equipamentos, mas nao bloqueia output;
- a validacao e de estrutura/confianca, nao de contrato final PDF/XLS;
- `build_graph` pode criar layout referencial quando faltam spans, mas esse modo ainda pode seguir para output final.

### 7. Artefatos intermediarios

Entrada:

- `TechnicalPayload` validado estruturalmente.

Modulos:

- `croqui_engine/generators/json_exporter.py`;
- `croqui_engine/vision/overlay_renderer.py`;
- `croqui_engine/core/pipeline.py:31`.

Saida:

- `data/outputs/<job_id>/technical_payload.json`;
- overlays em `data/outputs/<job_id>/overlays/`;
- retorno do payload para rota de upload.

### 8. Revisao online e payload revisado

Entrada:

- payload JSON no frontend/API.

Modulos:

- `croqui_engine/app/routes/api_routes.py:26` (`get_payload`);
- `croqui_engine/app/routes/api_routes.py:38` (`update_payload`);
- `croqui_engine/topology/graph_builder.py:9`;
- `croqui_engine/topology/graph_validator.py:23`.

Saida:

- `data/outputs/<job_id>/technical_payload_reviewed.json`;
- status `NEEDS_REVIEW`.

Risco V1:

- a API edita `TechnicalPayload`, nao um estado final/contrato de output;
- ao salvar revisao, o grafo e reconstruido e validado, mas nao existe validacao bloqueante de PDF/XLS;
- a exportacao posterior ainda recebe `TechnicalPayload`.

### 9. Geracao de outputs

Entrada:

- `TechnicalPayload`;
- opcionalmente `pdf_path` original.

Modulos:

- `croqui_engine/core/pipeline.py:98` (`generate_outputs`);
- `croqui_engine/corpus/reference_outputs.py:38` (`generate_reference_outputs_if_available`);
- `croqui_engine/generators/excel_generator.py:134` (`generate_excel`);
- `croqui_engine/rendering/svg_croqui_renderer.py:17` (`generate_svg_croqui`);
- `croqui_engine/rendering/final_croqui_renderer.py:36` (`generate_final_croqui_pdf`);
- fallback `croqui_engine/generators/pdf_croqui_generator.py:11` (`generate_croqui_pdf`);
- `croqui_engine/core/pipeline.py:141` (`_write_diff_report`).

Saida:

- `data/outputs/<job_id>/croqui_final.pdf`;
- `data/outputs/<job_id>/croqui_final.png`;
- `data/outputs/<job_id>/croqui_final.svg` quando o caminho SVG roda;
- `data/outputs/<job_id>/croqui_final.xls`;
- `data/outputs/<job_id>/technical_payload_reviewed.json`;
- `data/outputs/<job_id>/diff_report.json`.

Decisao principal:

- se `settings.use_corpus_reference_outputs` estiver ativo e o PDF bater com o corpus, o sistema copia PDF/XLS aprovados do corpus;
- caso contrario, gera XLS local, SVG, PDF final e preview;
- se SVG/PDF final falhar, cai para o gerador ReportLab legado.

Risco V1:

- copiar output de referencia e util para demonstracao/auditoria, mas mascara fidelidade do engine se usado como geracao normal;
- `_strip_internal_corpus_markers` remove metadados de corpus antes da geracao local, eliminando sinais que deveriam alimentar contrato/validacao;
- `diff_report.json` nao valida equipamento principal nem paridade PDF/XLS.

## Onde o desenho final e montado

### PDF final principal

Modulos:

- `croqui_engine/rendering/final_croqui_renderer.py:36`;
- `croqui_engine/rendering/svg_croqui_renderer.py:23`.

Decisoes:

- `svg_croqui_renderer._network` em `croqui_engine/rendering/svg_croqui_renderer.py:120` escolhe renderizacao por trace limpo, trace focado ou payload;
- `_focused_trace` em `croqui_engine/rendering/svg_croqui_renderer.py:575` concentra segmentos por pontos vermelhos ou pelo codigo principal;
- `_trace_work_area` em `croqui_engine/rendering/svg_croqui_renderer.py:646` posiciona area vermelha pelo `main_code` quando possivel, senao por pontos vermelhos;
- `_main_equipment_code` em `croqui_engine/rendering/svg_croqui_renderer.py:859` deriva o foco a partir do label principal.

Risco:

- quando `main_switching_equipment` esta errado, o foco e a area de trabalho podem apontar para o equipamento errado;
- quando o trace esta em `clean_project_trace`, a logica privilegia o codigo principal para area de trabalho, o que reforca erro de contrato.

### PDF fallback ReportLab

Modulos:

- `croqui_engine/generators/pdf_croqui_generator.py:11`;
- `croqui_engine/generators/pdf_croqui_generator.py:114` (`_header`);
- `croqui_engine/generators/pdf_croqui_generator.py:151` (`_draw_graph`);
- `croqui_engine/generators/pdf_croqui_generator.py:224` (`_draw_project_sheet`).

Decisoes:

- se `source_pdf_path` existe, o PDF fallback desenha a folha do projeto bruto dentro do output;
- o campo "Equipamento" no cabecalho fallback usa diretamente `payload.meta.get("main_switching_equipment", "")`, sem fallback para primeiro equipamento.

Risco:

- fallback pode divergir muito do PDF principal e do XLS;
- se `main_switching_equipment` faltar, PDF fallback pode ficar sem equipamento enquanto XLS preenche pelo primeiro equipamento ativo.

### XLS atual

Modulos:

- `croqui_engine/generators/excel_generator.py:134`;
- `croqui_engine/generators/excel_generator.py:181` (`_generate_structured_xls`);
- `croqui_engine/generators/excel_generator.py:335` (`_write_xls_header`);
- `croqui_engine/generators/excel_generator.py:356` (`_write_xls_drawing_area`);
- `croqui_engine/generators/excel_generator.py:466` (`_insert_final_croqui_drawing`);
- `croqui_engine/rendering/final_croqui_renderer.py:53` (`generate_croqui_drawing_bmp`).

Decisoes:

- `generate_excel` sempre chama `_generate_structured_xls`;
- `template_path` e `source_pdf_path` sao recebidos, mas nao governam o caminho ativo;
- o desenho do XLS e um BMP gerado por `final_croqui_renderer`, nao a mesma pagina SVG/PDF final.

Risco:

- apesar de existir `_generate_from_template` em `croqui_engine/generators/excel_generator.py:149`, ela nao e usada;
- o XLS atual nao preserva estilos/merges/print area do XLS aprovado, salvo aproximacoes codificadas;
- desenho e cabecalho podem divergir visualmente do PDF.

## Onde o cabecalho e preenchido

Campos atuais de cabecalho:

- departamento: `payload.meta["department"]`;
- municipio: `payload.meta["municipality"]`;
- equipamento: `_main_equipment_label(payload)` ou `payload.meta["main_switching_equipment"]`;
- data do levantamento: `payload.meta["survey_date"]`;
- levantador/responsavel: `payload.meta["surveyor"]` ou `payload.meta["levantador"]`.

Pontos de preenchimento:

- PDF/SVG principal: `croqui_engine/rendering/svg_croqui_renderer.py:78`;
- PDF ReportLab principal/fallback: `croqui_engine/rendering/final_croqui_renderer.py:92` e `croqui_engine/generators/pdf_croqui_generator.py:114`;
- XLS estruturado: `croqui_engine/generators/excel_generator.py:335`;
- XLS aba "Dados": `croqui_engine/generators/excel_generator.py:204`;
- XLS template nao usado: `croqui_engine/generators/excel_generator.py:149`.

Ponto critico:

- existem tres implementacoes de `_main_equipment_label` em `excel_generator.py:409`, `final_croqui_renderer.py:519` e `svg_croqui_renderer.py:845`;
- essas funcoes priorizam `payload.meta["main_switching_equipment"]`, mas caem para o primeiro equipamento ativo;
- o PDF fallback em `pdf_croqui_generator.py:122` nao usa o mesmo fallback.

## Onde PDF e XLS divergem ou podem divergir

1. Superficie de desenho:
   - PDF usa SVG/PyMuPDF;
   - XLS embute BMP gerado por PIL/ReportLab-like helper.

2. Uso de template:
   - o XLS aprovado do corpus e perfilado por ground truth, mas nao dirige a geracao local;
   - `generate_excel` ignora o caminho de template existente.

3. Cabecalho:
   - helpers de equipamento principal sao duplicados;
   - fallback PDF pode deixar equipamento vazio enquanto XLS preenche pelo primeiro ativo.

4. Modo corpus:
   - `generate_reference_outputs_if_available` pode copiar PDF e XLS de referencia;
   - se o modo local roda, os metadados de corpus sao removidos antes da geracao.

5. Validacao:
   - PDF e XLS nao sao reabertos para comparar cabecalho final;
   - nao ha regra atual `PDF equipment == XLS equipment`;
   - nao ha regra atual `primary_focus_code == expected_primary_focus_code`.

6. Extensao/formato:
   - o requisito fala em XLSX, mas o engine atual emite `.xls` via `xlwt`;
   - o contrato deve aceitar referencia `.xls`/`.xlsx`, mas a V1 precisa decidir o formato final suportado.

## Onde corpus e reference outputs entram

### Registro do corpus

Modulos:

- `croqui_engine/corpus/discovery.py:52` (`discover_case`);
- `croqui_engine/corpus/discovery.py:14` (`EQUIPMENT_RE`);
- `croqui_engine/corpus/registry.py`;
- `croqui_engine/corpus/matcher.py:24` (`find_project_match`).

Dados:

- o tipo/codigo esperado vem principalmente do nome do PDF/XLS aprovado, por exemplo `CROQUI TR 634087.xls`;
- `find_project_match` liga o PDF bruto ao caso do corpus por SHA-256.

### Ground truth

Modulos:

- `croqui_engine/ground_truth/target_builder.py:13`;
- `croqui_engine/ground_truth/pdf_target_extractor.py:9`;
- `croqui_engine/ground_truth/xls_target_extractor.py:9`.

Dados:

- `target_payload.json`;
- `target_pdf_objects.json`;
- `target_xls_profile.json`.

Limite atual:

- `pdf_target_extractor` registra texto e marca tokens de cabecalho como presentes, mas nao extrai valores estruturados de `Equipamento`, `Municipio`, `Data` etc.;
- `xls_target_extractor` guarda celulas, merges e valores, incluindo o campo AP5 com `TR 634087` no caso `300001101207`, mas esse valor ainda nao vira contrato de output.

### Benchmark

Modulos:

- `croqui_engine/benchmark/runner.py:39`;
- `croqui_engine/benchmark/technical_metrics.py:7`;
- `croqui_engine/benchmark/metrics.py:4`.

Fluxo:

- constroi target do caso;
- roda `process_pdf`;
- roda `generate_outputs`;
- compara visual, texto e tecnico;
- escreve `comparison.json`.

Falha atual:

- tecnica usa presenca de codigo em `payload.active_equipment()`;
- nao valida equipamento de cabecalho, foco primario, area vermelha, nem paridade PDF/XLS.

## Contrato de output proposto

O contrato deve ser o objeto soberano que define o que significa um croqui final correto. Ele nao substitui imediatamente `TechnicalPayload`; ele deve ser carregado antes da inferencia de equipamento/foco e deve travar campos vindos de fontes superiores.

Modelo minimo proposto:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class CroquiOutputContract(BaseModel):
    contract_version: str = "v1-output-contract"

    expected_equipment_type: str | None = None
    expected_equipment_code: str | None = None
    expected_equipment_label: str | None = None

    expected_header: dict[str, str] = Field(default_factory=dict)
    expected_visible_codes: list[str] = Field(default_factory=list)
    expected_primary_focus_code: str | None = None
    expected_required_codes: list[str] = Field(default_factory=list)
    expected_forbidden_primary_codes: list[str] = Field(default_factory=list)

    reference_pdf_path: str | None = None
    reference_xlsx_path: str | None = None
    reference_case_id: str | None = None

    source_priority: list[str] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    blocking_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

Campos adicionais recomendados:

- `field_sources`: registra fonte por campo, por exemplo `{"expected_equipment_label": "target_xls:AP5"}`;
- `blocking_rules`: lista regras que devem impedir exportacao final;
- `warnings`: inconsistencias nao bloqueantes do contrato;
- `contract_version`: permite evoluir o JSON lateral.

### Prioridade de fontes

Prioridade obrigatoria:

1. `target_xls`/`target_xlsx` do corpus, quando existir:
   - extrair cabecalho de celulas conhecidas ou perfiladas;
   - no XLS atual do corpus, `Croqui v1!AP5` aparece como campo de equipamento em casos como `300001101207`;
   - preencher `expected_equipment_label`, `expected_equipment_type`, `expected_equipment_code`, `expected_header`, `reference_xlsx_path`.

2. `target_pdf` do corpus, quando existir:
   - extrair valor de cabecalho por coordenadas/regex, nao apenas "present";
   - preencher `reference_pdf_path`, `expected_header`, `expected_visible_codes`.

3. nome do arquivo ideal:
   - usar regex equivalente a `EQUIPMENT_RE`;
   - preencher tipo/codigo se XLS/PDF nao derem valor mais confiavel.

4. registry/ground truth:
   - usar `GoldenCase.equipment_type_from_name`, `equipment_code_from_name` e caminhos.

5. plano de execucao do projeto:
   - usar `parse_tes_actions`;
   - fonte menor que corpus, maior que inferencia espacial.

6. cabecalho textual do projeto:
   - usar campos textualizados do PDF bruto, se houver.

7. inferencia espacial:
   - ultima fonte;
   - nunca pode sobrescrever campos definidos por fontes anteriores.

### Normalizacao proposta

Regras:

- `expected_equipment_label` deve ser normalizado como `<TIPO> <CODIGO>`, por exemplo `TR 634087`;
- `expected_equipment_type` deve usar abreviaturas finais `TR`, `FU`, `FC`, `RL`, `SC`;
- `expected_equipment_code` deve conter apenas digitos;
- `expected_primary_focus_code` deve ser igual ao codigo principal esperado quando o contrato define equipamento;
- `expected_required_codes` deve incluir pelo menos o codigo principal e outros codigos obrigatorios extraidos do ideal;
- `expected_forbidden_primary_codes` deve incluir candidatos proximos que nao podem virar principal quando ja houver referencia, por exemplo `1297574` no caso `TR 634087`.

### Regras bloqueantes minimas

O contrato deve gerar bloqueio se:

- PDF final tem equipamento de cabecalho diferente de `expected_equipment_label`;
- XLS final tem equipamento de cabecalho diferente de `expected_equipment_label`;
- PDF e XLS divergem entre si em equipamento, municipio, data ou responsavel;
- `primary_focus_code` diverge de `expected_primary_focus_code`;
- codigo esperado aparece apenas como secundario, mas outro codigo e o principal;
- o desenho/foco usa codigo presente em `expected_forbidden_primary_codes`;
- o output local esta em status bloqueado, mas mesmo assim tenta gravar `croqui_final`.

## Ponto de integracao proposto no pipeline

Sem implementar ainda, a sequencia ideal para a V1 e:

1. criar `CroquiOutputContract` no inicio de `process_pdf`, com `pdf_path` e `job_id`;
2. carregar match de corpus e referencias antes de parser/heuristica;
3. depois de extrair texto, enriquecer contrato com TES/cabecalho bruto apenas nos campos ainda nao definidos por fonte superior;
4. escolher equipamento principal por uma funcao central que recebe `contract`, `parsed["equipment"]` e `project_vector_trace`;
5. gravar no payload somente o resultado resolvido, com fonte;
6. renderizar PDF e XLS a partir do mesmo estado final resolvido;
7. reabrir PDF/XLS gravados e validar campos criticos;
8. escrever `output_validation_report.json`;
9. so disponibilizar `croqui_final.*` como final quando status for `PASSED`.

## Relatorio lateral proposto

Arquivo:

- `data/outputs/<job_id>/output_validation_report.json`

Forma minima:

```json
{
  "contract": {
    "expected_equipment_label": "TR 634087",
    "expected_equipment_source": "target_xls:AP5",
    "reference_case_id": "300001101207"
  },
  "generated": {
    "pdf_header_equipment": "TR 1297574",
    "xls_header_equipment": "TR 1297574",
    "primary_focus_code": "1297574",
    "visible_codes": ["1297574", "634087"]
  },
  "validation": {
    "status": "BLOCKED",
    "blocking_errors": [
      {
        "code": "PRIMARY_EQUIPMENT_MISMATCH",
        "expected": "TR 634087",
        "generated": "TR 1297574"
      }
    ],
    "warnings": []
  }
}
```

## Lacunas e decisoes para a proxima etapa

- Definir se a V1 entrega `.xls` ou `.xlsx`; hoje o codigo escreve `.xls`.
- Implementar extracao estruturada do cabecalho do XLS aprovado, usando celulas/merges do perfil.
- Melhorar extracao do cabecalho do PDF aprovado para valor real, nao apenas presenca de tokens.
- Centralizar `_main_equipment_label` em um unico modulo orientado pelo contrato.
- Remover a regra fraca `expected_code in detected_codes` das metricas criticas.
- Separar modo `CORPUS_REFERENCE_APPROVED` de modo `GENERATED_LOCAL_LIVE` no relatorio, para evitar mascarar fidelidade do engine.
- Garantir que editor/exportacao nao reexecute inferencia automatica sobre estado revisado.

