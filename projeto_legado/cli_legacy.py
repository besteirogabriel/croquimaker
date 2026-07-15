"""
main.py - Interface principal do sistema gerador de croqui.

Uso:
    python main.py <caminho_projeto.pdf> [--saida <pasta>] [--template <arquivo.xls>]
    python main.py --setup   # Configura template a partir dos exemplos
"""
import sys
import os
import argparse
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(
        description="Gerador de Croqui RGE/CPFL a partir de Projeto Elétrico PDF"
    )
    parser.add_argument("projeto", nargs="?", help="Caminho do PDF do projeto elétrico")
    parser.add_argument("--saida", "-o", default=".", help="Pasta de saída (padrão: pasta atual)")
    parser.add_argument("--template", "-t", help="Caminho do template .xls")
    parser.add_argument("--setup", action="store_true", help="Configura template a partir dos exemplos")
    parser.add_argument("--so-pdf", action="store_true", help="Gera apenas o PDF (sem Excel)")
    parser.add_argument("--so-excel", action="store_true", help="Gera apenas o Excel (sem PDF)")
    parser.add_argument("--debug", action="store_true", help="Exibe dados extraídos do projeto")

    args = parser.parse_args()

    # Configurar template
    if args.setup:
        _configurar_template()
        return

    if not args.projeto:
        parser.print_help()
        return

    if not os.path.exists(args.projeto):
        print(f"ERRO: Arquivo não encontrado: {args.projeto}")
        sys.exit(1)

    # Importa módulos após verificar argumentos
    from extrator import extrair_projeto
    from gerador_pdf import gerar_croqui_pdf
    from gerador_excel import gerar_croqui_excel

    print(f"\n{'='*60}")
    print(f"GERADOR DE CROQUI RGE/CPFL")
    print(f"{'='*60}")
    print(f"Projeto: {args.projeto}")

    # Extrai dados do projeto
    print("\n[1/3] Extraindo dados do projeto...")
    dados = extrair_projeto(args.projeto)

    print(f"  Nota: {dados.nota}")
    print(f"  Município: {dados.municipio}")
    print(f"  Equipamento: {dados.equipamento_principal}")
    print(f"  Transformadores: {len(dados.transformadores)}")
    print(f"  Postes: {len(dados.postes)}")
    print(f"  Vãos: {len(dados.vaos)}")
    print(f"  IDs extras: {dados.equipamentos_ids[:10]}")

    if args.debug:
        _exibir_debug(dados)

    # Gera nome base dos arquivos de saída
    os.makedirs(args.saida, exist_ok=True)
    equip_nome = dados.equipamento_principal.replace(' ', '_') if dados.equipamento_principal else "croqui"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_base = f"croqui_{equip_nome}_{timestamp}"

    # Gera PDF
    if not args.so_excel:
        print("\n[2/3] Gerando PDF do croqui...")
        caminho_pdf = os.path.join(args.saida, f"{nome_base}.pdf")
        try:
            gerar_croqui_pdf(dados, caminho_pdf)
            print(f"  [OK] PDF: {caminho_pdf}")
        except Exception as e:
            print(f"  [ERRO] Ao gerar PDF: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()

    # Gera Excel
    if not args.so_pdf:
        print("\n[3/3] Gerando Excel do croqui...")
        from gerador_excel import TEMPLATE_FILE
        template = args.template or TEMPLATE_FILE

        if not os.path.exists(template):
            print(f"  ⚠ Template não configurado. Execute: python main.py --setup")
            print(f"    Ou use: python main.py --so-pdf (apenas PDF)")
        else:
            caminho_xls = os.path.join(args.saida, f"{nome_base}.xls")
            try:
                gerar_croqui_excel(dados, caminho_xls, template)
                print(f"  [OK] Excel: {caminho_xls}")
            except Exception as e:
                print(f"  [ERRO] Ao gerar Excel: {e}")
                if args.debug:
                    import traceback
                    traceback.print_exc()

    print(f"\n{'='*60}")
    print("Concluído!")


def _configurar_template():
    """Configura o template copiando de um arquivo de exemplo."""
    exemplos = [
        r"E:\Projetos\CLAUDE IA\Croqui\Projeto 1 + Croqui\croqui TR 689692 tes.xls",
        r"E:\Projetos\CLAUDE IA\Croqui\Projeto 2 + Croqui\croqui fu 626460.xls",
        r"E:\Projetos\CLAUDE IA\Croqui\Projeto 3 + Croqui\croqui rl 116079 TES 01.xls",
        r"E:\Projetos\CLAUDE IA\Croqui\Projeto 4 + Croqui\croqui TR 691446.xls",
        r"E:\Projetos\CLAUDE IA\Croqui\Projeto 5 + Croqui\croqui FU 626634.xls",
    ]

    from gerador_excel import copiar_template_de_exemplo

    for ex in exemplos:
        if os.path.exists(ex):
            print(f"Usando template: {ex}")
            copiar_template_de_exemplo(ex)
            print("Template configurado com sucesso!")
            print("Agora você pode gerar croquis com: python main.py <projeto.pdf>")
            return

    print("ERRO: Nenhum arquivo de template encontrado.")
    print("Verifique se os exemplos estão em:")
    for ex in exemplos:
        print(f"  {ex}")


def _exibir_debug(dados):
    print("\n--- DADOS EXTRAÍDOS (DEBUG) ---")
    print(f"  Cliente: {dados.cliente}")
    print(f"  Obra: {dados.obra}")
    print(f"  Endereço: {dados.endereco}")
    print(f"  Projetista: {dados.projetista}")
    print(f"  Data: {dados.data}")
    print(f"  Departamento: {dados.departamento}")
    print()
    for tr in dados.transformadores:
        print(f"  TR {tr.numero}: {tr.kva} kVA {tr.tensao}")
    print()
    for p in dados.postes[:10]:
        novo = "[NOVO]" if p.novo else ""
        rem = "[REMOVER]" if p.remover else ""
        print(f"  {p.id} {p.tipo} {novo} {rem}")
    if len(dados.postes) > 10:
        print(f"  ... e mais {len(dados.postes)-10} postes")
    print()
    for v in dados.vaos[:10]:
        print(f"  {v.origem}-{v.destino}: {v.cabo} {v.comprimento}m")
    if len(dados.vaos) > 10:
        print(f"  ... e mais {len(dados.vaos)-10} vãos")
    print("-------------------------------")


if __name__ == "__main__":
    main()
