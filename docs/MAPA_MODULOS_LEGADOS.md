# Mapa de Modulos Legados para Nova Arquitetura

| Legado | Nova area | Situacao |
| --- | --- | --- |
| `projeto_legado/flask_app_legacy.py` | `croqui_engine/app/web.py` e rotas em `croqui_engine/app/routes/` | `app.py` agora e wrapper do app novo; Flask antigo preservado apenas para auditoria. |
| `projeto_legado/cli_legacy.py` | `croqui_engine/cli/process_pdf.py` | `main.py` agora e wrapper CLI novo; CLI antigo preservado apenas para auditoria. |
| `projeto_legado/ai_interpreter_original_disabled.py.txt` | Nenhum fluxo operacional | Desativado e preservado como texto para auditoria. |
| `projeto_legado/extrator.py` | `extraction/`, `parser/`, `topology/` | Regex e heuristicas reaproveitadas conceitualmente. |
| `projeto_legado/extrator_v3.py` | `extraction/text_extractor.py` e `vector_extractor.py` | PyMuPDF adotado como base. |
| `projeto_legado/extrator_posicional.py` | `parser/spatial.py`, `topology/graph_builder.py` | Associacao espacial inicial recriada em modelo Pydantic. |
| `projeto_legado/topologia.py` | `topology/graph_builder.py`, `graph_validator.py` | Grafo modularizado e validado. |
| `projeto_legado/gerador_pdf.py` | `generators/pdf_croqui_generator.py` | Geracao ReportLab reimplementada para `TechnicalPayload`. |
| `projeto_legado/gerador_croqui_v2.py` | `generators/pdf_croqui_generator.py` | Ideias visuais reaproveitadas. |
| `projeto_legado/gerador_croqui_v3.py` | `generators/pdf_croqui_generator.py` | Payload legado substituido por Pydantic. |
| `projeto_legado/gerador_croqui_v4.py` | `topology/graph_builder.py` e `pdf_croqui_generator.py` | Ideias de layout ortogonal reaproveitadas. |
| `projeto_legado/gerador_excel.py` | `generators/excel_generator.py` | Modo simples e stub de template oficial. |
| `projeto_legado/debug_*.py` | `docs/AUDITORIA_PROJETO_ATUAL.md` | Mantidos como referencia exploratoria fora do fluxo. |
