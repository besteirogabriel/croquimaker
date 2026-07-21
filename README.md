# Croquimaker MVP

Aplicacao local para receber um PDF de projeto, interpretar a topologia no schema de grafo preservado do legado, gerar o croqui em PDF e disponibilizar Excel quando houver template real.

## Login

```bash
docker compose --profile login run --rm codex-login
```

## Iniciar

```bash
docker compose up --build web
```

Acesse `http://localhost:8081`.

Para usar outra porta livre:

```bash
CROQUIMAKER_HOST_PORT=8082 docker compose up --build web
```

Para publicar especificamente em `8080`, somente se ela estiver livre:

```bash
CROQUIMAKER_HOST_PORT=8080 docker compose up --build web
```

## Desenvolvimento

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -q
```

Para teste local sem login externo:

```bash
CROQUIMAKER_PROVIDER=fake docker compose up --build web
```

## Corpus

```bash
python3 scripts/build_corpus_manifest.py
```

O manifesto fica em `data/corpus/manifest.json`. O template Excel foi derivado de um arquivo real do corpus e documentado em `data/templates/README.md`.
