# Projeto Legado

Esta pasta guarda o codigo antigo e scripts exploratorios preservados para auditoria tecnica.

O fluxo operacional atual da aplicacao JOBEL usa `croqui_engine/`, `app.py` e `main.py`. Nada desta pasta deve ser importado pelo app novo.

## Conteudo

- `flask_app_legacy.py`: Flask antigo com fluxo upload/extracao/geracao.
- `cli_legacy.py`: CLI antigo.
- `extrator*.py`: extratores originais e experimentais.
- `gerador*.py`: geradores PDF/Excel/croqui anteriores.
- `debug_*.py` e `analisa_croqui_real.py`: scripts de investigacao.
- `ai_interpreter_original_disabled.py.txt`: interpretador Claude preservado como texto desativado.
- `ai_interpreter_disabled.py`: stub seguro que falha fechado.
- `logs/`: logs antigos movidos da raiz.

## Regra

Manter esta pasta fora do fluxo principal. Se alguma ideia daqui for reaproveitada, migrar a logica para um modulo novo em `croqui_engine/` com testes.
