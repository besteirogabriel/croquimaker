# Catálogo de símbolos RGE

`rge_symbol_catalog.json` contém os vetores extraídos diretamente da aba
`Simbologia` de `data/templates/croqui_template.xls`.

O catálogo deve ser regenerado quando o Excel de referência mudar:

```bash
python scripts/extract_rge_symbol_catalog.py
```

O gerador valida o nome da aba e registra o SHA-256 do Excel de origem. Símbolos
sem correspondência no catálogo não recebem um desenho genérico improvisado.
