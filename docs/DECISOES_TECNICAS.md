# Decisoes Tecnicas Iniciais

1. IA externa removida do fluxo principal.
2. Engine local deterministica como nucleo do sistema.
3. JSON tecnico (`TechnicalPayload`) como contrato interno.
4. UI, PDF e Excel sao consequencias do JSON tecnico.
5. Revisao humana obrigatoria quando a confianca for baixa ou houver validacoes relevantes.
6. Simbologia RGE/CPFL inicial marcada como heuristica ate fornecimento oficial pela JOBEL.
7. PyMuPDF e a base principal para texto, coordenadas, renderizacao e vetores.
8. Grafo eletrico construido principalmente a partir de vaos `Vx-y`.
9. PDF final deve ser best-effort e nunca falhar apenas por payload parcial.
10. Artefatos por job ficam em `data/uploads/<job_id>` e `data/outputs/<job_id>`.
11. Banco local SQLite armazena usuarios, jobs, status e caminhos de saida.
12. Logs por job registram processamento e falhas.
