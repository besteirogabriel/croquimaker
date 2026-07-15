from __future__ import annotations

import argparse
from pathlib import Path

from croqui_engine.core.pipeline import generate_outputs, process_pdf
from croqui_engine.storage.file_store import new_job_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Processa PDF RGE/CPFL com engine local.")
    parser.add_argument("pdf", help="Caminho do PDF")
    parser.add_argument("--job-id", default="", help="ID opcional do job")
    parser.add_argument("--gerar", action="store_true", help="Tambem gera PDF/PNG/XLS")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    job_id = args.job_id or new_job_id()
    payload = process_pdf(pdf_path, job_id)
    print(f"Job: {job_id}")
    print(f"TES: {payload.meta.get('tes_number', '')}")
    print(f"Municipio: {payload.meta.get('municipality', '')}")
    print(f"Postes: {len(payload.nodes)}")
    print(f"Vaos: {len(payload.spans)}")
    print(f"Equipamentos: {len(payload.equipment)}")
    print(f"Confianca: {payload.confidence_global:.2f}")
    if args.gerar:
        outputs = generate_outputs(payload, pdf_path)
        for key, value in outputs.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
