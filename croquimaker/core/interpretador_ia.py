import base64
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import fitz

from .schema import PROJECT_SCHEMA, assert_schema, sanitizar_projeto


DEFAULT_MODEL = os.getenv("CROQUIMAKER_CODEX_MODEL", "gpt-5.6-sol")
DEFAULT_TIMEOUT = int(os.getenv("CROQUIMAKER_TIMEOUT_SECONDS", "240"))


def _system_prompt() -> str:
    return (
        "Você é um engenheiro eletricista especialista em projetos de redes RGE/CPFL e em croquis Jobel. "
        "Você deve converter projeto elétrico PDF em JSON técnico para um motor Python de croqui.\n\n"
        "PRINCÍPIO CENTRAL:\n"
        "A geometria do croqui já foi extraída deterministicamente dos vetores CAD do PDF. "
        "Azul representa MT e verde representa BT. Você deve identificar apenas o equipamento "
        "principal, todos os equipamentos relevantes, seus números, ações e os nós descritos no texto. "
        "Nunca invente coordenadas x/y e nunca redesenhe a rede. Deixe x e y vazios.\n\n"
        "RESTRIÇÃO DO CROQUI:\n"
        "O desenho final contém linhas MT/BT, postes e equipamentos elétricos comprovados pelo projeto. "
        "Não proponha áreas de trabalho LM/LV, contornos, destaques ou observações operacionais. "
        "Símbolos de transformadores, chaves, religadores e postes novos devem ser preservados quando "
        "houver evidência no projeto.\n\n"
        "REGRAS DE EXTRAÇÃO OBRIGATÓRIAS:\n"
        "- Use SOMENTE pontos com legenda técnica clara: P1, P2, P3 etc. Não use ruas, endereços, clientes, números soltos ou textos livres como nós.\n"
        "- Todo vão explícito Vx-y deve virar trecho Px -> Py. Exemplo V5-6 => de P5 para P6.\n"
        "- Extraia todos os Vx-y explícitos. Eles são a base do grafo elétrico.\n"
        "- Todo de/para de trechos deve existir em nos.id.\n"
        "- Todo equipamento deve apontar para um no_id existente.\n"
        "- Se o texto/OCR estiver confuso, use as imagens das páginas para confirmar P, V, símbolos e localização.\n\n"
        "NÓS:\n"
        "Tipos permitidos: POSTE_EXISTENTE, POSTE_NOVO.\n"
        "Marque POSTE_NOVO quando houver símbolo preenchido/preto/semicírculo ou texto: poste a instalar, poste será instalado, substituir poste, implantação, instalar poste, novo, Ifv associado a instalação/substituição.\n\n"
        "TRECHOS:\n"
        "Tipos permitidos: MT, BT, MT_NOVA, BT_NOVA, MT_RECONDUTORADA, BT_RECONDUTORADA, MT_COMPLEMENTADA, BT_COMPLEMENTADA, AUX.\n"
        "- MT/Primária: linha tracejada no padrão do croqui RGE.\n"
        "- BT/Secundária: linha contínua.\n"
        "- Se houver '- cabo antigo' e '+ cabo novo', classifique como RECONDUTORADA.\n"
        "- Se texto mencionar complementação, use COMPLEMENTADA.\n"
        "- Se rede projetada nova, use NOVA.\n"
        "Preencha cabo com o cabo novo/ativo mais relevante: 3E70, 3E150-2A, 3S04, 3P70(A70), etc.\n\n"
        "EQUIPAMENTOS:\n"
        "Tipos permitidos:\n"
        "TRANSFORMADOR_RGE, TRANSFORMADOR_PARTICULAR, CHAVE_FUSIVEL_COM_CARGA, CHAVE_FUSIVEL_SEM_CARGA, "
        "CHAVE_FUSIVEL_RELIGADORA, CHAVE_FACA_COM_CARGA, CHAVE_FACA_SEM_CARGA, CHAVE_FACA_TRIPOLAR_COM_CARGA, "
        "CHAVE_FACA_TRIPOLAR_SEM_CARGA, RELIGADOR, SECCIONALIZADORA, BANCO_CAPACITOR, REGULADOR_TENSAO, "
        "CHAVE_OLEO_UNIPOLAR, CHAVE_OLEO_TRIPOLAR, ATERRAMENTO_BT, ATERRAMENTO_AT, SECCIONAMENTO_PRIMARIO, "
        "SECCIONAMENTO_SECUNDARIO, PASSAGEM_PRIMARIO, PASSAGEM_SECUNDARIO, PASSAGEM_PRIMARIO_SECUNDARIO, "
        "FIM_REDE_PRIMARIA, FIM_REDE_SECUNDARIA, CRUZAMENTO_COM_CONEXAO, CRUZAMENTO_SEM_CONEXAO, "
        "ENCABECAMENTO_PRIMARIO, ENCABECAMENTO_SECUNDARIO, ELEMENTO_RETIRAR, ELEMENTO_DESLOCAR, ESTAI, MEDIDOR_PRIMARIO.\n"
        "Use codigo para números operativos: TR 689726, FU 626460, RL/R3 116079, FC 1110594.\n"
        "Extraia todos os códigos de equipamentos que pertençam ao trecho do serviço, não apenas o principal.\n"
        "Use estado para ABRIR, FECHAR, DESLIGAR, LIGAR, INSTALAR, RETIRAR, SUBSTITUIR, NA, NF, "
        "COM CARGA, SEM CARGA, FONTE ou CARGA quando a ação estiver explícita.\n\n"
        "VALIDAÇÃO FINAL ANTES DE RESPONDER:\n"
        "1) Nunca inventar nós que não aparecem como P#.\n"
        "2) Nunca criar trecho sem Vx-y explícito, exceto AUX para ligar equipamento visualmente quando necessário.\n"
        "3) Não reduzir a rede a P1-P2-P3 se existem outros vãos no projeto.\n"
        "4) Para projetos com várias páginas, unir todos os vãos de todas as páginas.\n"
        "5) Todos os campos x/y devem permanecer vazios; coordenadas pertencem ao extrator vetorial.\n"
        "6) Retorne somente JSON válido conforme schema, sem markdown."
    )


def _extrair_pdf_bundle(caminho_pdf: str) -> dict:
    doc = fitz.open(caminho_pdf)
    try:
        texto = "".join(page.get_text() for page in doc)[:90000]
        imagens = []
        image_paths = []
        tempdir = tempfile.mkdtemp(prefix="croquimaker_pages_")
        for i, page in enumerate(doc):
            if i >= 4:
                break
            pix = page.get_pixmap(dpi=120)
            raw = pix.tobytes("png")
            imagens.append("data:image/png;base64," + base64.standard_b64encode(raw).decode())
            path = Path(tempdir) / f"page_{i + 1}.png"
            path.write_bytes(raw)
            image_paths.append(str(path))
        return {"text": texto, "images": imagens, "image_paths": image_paths}
    finally:
        doc.close()


def interpretar_pdf(caminho_pdf: str, progresso=None, additional_image_paths: list[str] | None = None) -> dict:
    if progresso:
        progresso("Lendo projeto")
    bundle = _extrair_pdf_bundle(caminho_pdf)
    images = list(bundle["image_paths"][:3])
    for path in additional_image_paths or []:
        if path not in images:
            images.append(path)
    return interpretar_texto(bundle["text"], images[:4], progresso=progresso)


def interpretar_texto(texto_pdf: str, imagens: list | None = None, progresso=None) -> dict:
    if os.getenv("CROQUIMAKER_PROVIDER", "codex").lower() == "fake":
        return sanitizar_projeto(_fake_response(texto_pdf))
    if progresso:
        progresso("Construindo croqui")
    obj = _run_codex(texto_pdf[:90000], imagens or [])
    assert_schema(obj)
    return sanitizar_projeto(obj)


def _run_codex(texto_pdf: str, image_paths: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="croquimaker_codex_") as td:
        schema_path = Path(td) / "schema.json"
        out_path = Path(td) / "resposta.json"
        schema_path.write_text(json.dumps(PROJECT_SCHEMA, ensure_ascii=False), encoding="utf-8")
        prompt = (
            _system_prompt()
            + "\n\nAnalise este projeto elétrico RGE/CPFL e gere o JSON estruturado para croqui automático.\n\n"
            + "TEXTO EXTRAÍDO DO PDF:\n"
            + texto_pdf
            + "\n\nRetorne SOMENTE JSON válido, sem markdown, sem explicações. "
            + "Estrutura obrigatória: {meta, nos, trechos, equipamentos, textos}. "
            + "Preencha campos desconhecidos com string vazia."
        )
        cmd = [
            "codex", "exec",
            "--model", DEFAULT_MODEL,
            "-c", 'model_reasoning_effort="high"',
            "--output-schema", str(schema_path),
            "--output-last-message", str(out_path),
            "--skip-git-repo-check",
        ]
        for img in image_paths[:4]:
            cmd.extend(["--image", img])
        cmd.append("-")
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        env.pop("ANTHROPIC_API_KEY", None)
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            env=env,
            timeout=DEFAULT_TIMEOUT,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-4000:] or proc.stdout[-4000:] or "Falha no processamento")
        raw = out_path.read_text(encoding="utf-8") if out_path.exists() else proc.stdout
        raw = re.sub(r"^```\w*\n?", "", raw.strip())
        raw = re.sub(r"\n?```$", "", raw).strip()
        return json.loads(raw)


def _fake_response(texto_pdf: str) -> dict:
    spans = []
    for a, b in re.findall(r"\bV\s*(\d+)\s*[-–]\s*(\d+)\b", texto_pdf, re.I):
        spans.append((int(a), int(b)))
    if not spans:
        spans = [(1, 2), (2, 3)]
    ids = sorted({p for span in spans for p in span})
    return {
        "meta": {"tipo": "MVP", "equipamento": "Teste"},
        "nos": [{"id": f"P{i}", "tipo": "POSTE_EXISTENTE", "label": f"P{i}"} for i in ids],
        "trechos": [{"de": f"P{a}", "para": f"P{b}", "tipo": "MT", "cabo": ""} for a, b in spans],
        "equipamentos": [{"tipo": "TRANSFORMADOR_RGE", "codigo": "TR TESTE", "no_id": f"P{ids[0]}"}],
        "textos": [],
    }
