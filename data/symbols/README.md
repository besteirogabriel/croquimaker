# Catálogo de símbolos RGE

`rge_symbol_catalog.json` contém os vetores extraídos diretamente da aba
`Simbologia` de `data/templates/croqui_template.xls`.

`project_to_croqui_map.json` registra o DE-PARA revisado entre as famílias
vetoriais encontradas no PDF do projeto e esses símbolos oficiais. Os códigos
`ICON-xxx` são somente referências auditáveis da revisão; a classificação em
produção usa geometria, cor e topologia e não depende desses códigos.

O catálogo deve ser regenerado quando o Excel de referência mudar:

```bash
python scripts/extract_rge_symbol_catalog.py
```

O gerador valida o nome da aba e registra o SHA-256 do Excel de origem. Símbolos
sem correspondência no catálogo não recebem um desenho genérico improvisado.
