"""
app.py — Interface web do Gerador de Croqui RGE/CPFL
Fluxo: upload PDF → extração automática → editor → gerar PDF/Excel
"""
import os, sys, uuid, threading, json
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify

sys.path.insert(0, os.path.dirname(__file__))

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'saida_web')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

jobs = {}   # job_id → dict


# ─────────────────────────────────────────────
#  ROTAS
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/extrair', methods=['POST'])
def extrair():
    """Etapa 1: recebe o PDF e extrai dados. Retorna dados para o editor."""
    if 'projeto' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    arquivo = request.files['projeto']
    if not arquivo.filename.lower().endswith('.pdf'):
        return jsonify({'erro': 'Envie um arquivo PDF'}), 400

    job_id = str(uuid.uuid4())[:8]
    nome_pdf = f"{job_id}_{arquivo.filename}"
    caminho_pdf = os.path.join(UPLOAD_DIR, nome_pdf)
    arquivo.save(caminho_pdf)

    jobs[job_id] = {
        'status': 'extraindo',
        'mensagem': 'Lendo o projeto...',
        'caminho_pdf': caminho_pdf,
    }

    t = threading.Thread(target=_extrair_bg, args=(job_id, caminho_pdf))
    t.daemon = True
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/interpretar', methods=['POST'])
def interpretar():
    """Interpretação por IA: recebe PDF e envia ao Claude API."""
    if 'projeto' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    arquivo = request.files['projeto']
    if not arquivo.filename.lower().endswith('.pdf'):
        return jsonify({'erro': 'Envie um arquivo PDF'}), 400

    api_key = request.form.get('api_key', '').strip() or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return jsonify({'erro': 'ANTHROPIC_API_KEY não configurada. Informe a chave no campo acima.'}), 400

    job_id = str(uuid.uuid4())[:8]
    nome_pdf = f"{job_id}_{arquivo.filename}"
    caminho_pdf = os.path.join(UPLOAD_DIR, nome_pdf)
    arquivo.save(caminho_pdf)

    jobs[job_id] = {
        'status': 'interpretando',
        'mensagem': 'Enviando para IA Claude...',
        'caminho_pdf': caminho_pdf,
    }

    t = threading.Thread(target=_interpretar_bg, args=(job_id, caminho_pdf, api_key))
    t.daemon = True
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/gerar', methods=['POST'])
def gerar():
    """Etapa 2: recebe dados (payload antigo ou projeto_json da IA) e gera o PDF."""
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({'erro': 'Dados inválidos'}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'status': 'gerando',
        'mensagem': 'Gerando croqui...',
    }

    t = threading.Thread(target=_gerar_bg, args=(job_id, payload))
    t.daemon = True
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/status/<job_id>')
def status(job_id):
    if job_id not in jobs:
        return jsonify({'erro': 'Job não encontrado'}), 404
    return jsonify(jobs[job_id])


@app.route('/download/<job_id>/<tipo>')
def download(job_id, tipo):
    if job_id not in jobs:
        return jsonify({'erro': 'Job não encontrado'}), 404
    for arq in jobs[job_id].get('arquivos', []):
        if tipo == 'pdf' and arq.endswith('.pdf'):
            return send_file(arq, as_attachment=True, download_name=os.path.basename(arq))
        if tipo == 'xls' and arq.endswith('.xls'):
            return send_file(arq, as_attachment=True, download_name=os.path.basename(arq))
    return jsonify({'erro': 'Arquivo não disponível'}), 404


# ─────────────────────────────────────────────
#  BACKGROUND: INTERPRETAÇÃO IA
# ─────────────────────────────────────────────

def _interpretar_bg(job_id: str, caminho_pdf: str, api_key: str):
    try:
        from interpretador_ia import interpretar_pdf

        def progresso(msg):
            jobs[job_id]['mensagem'] = msg

        projeto = interpretar_pdf(caminho_pdf, api_key=api_key, progresso=progresso)

        jobs[job_id].update({
            'status': 'interpretado',
            'mensagem': f"{len(projeto.get('nos', []))} nós, {len(projeto.get('trechos', []))} trechos extraídos pela IA",
            'projeto_json': projeto,
        })

    except Exception as e:
        import traceback
        jobs[job_id].update({
            'status': 'erro',
            'mensagem': f'Erro na interpretação: {str(e)}',
            'detalhe': traceback.format_exc(),
        })


# ─────────────────────────────────────────────
#  BACKGROUND: EXTRAÇÃO
# ─────────────────────────────────────────────

def _extrair_bg(job_id: str, caminho_pdf: str):
    try:
        from extrator_v3 import extrair_dados

        dados = extrair_dados(caminho_pdf)

        eqs_list = []
        for eq in dados.equipamentos:
            kva_label = f"{eq.kva} kVA" if eq.kva > 0 else (eq.label or '')
            eqs_list.append({
                'id':    eq.id,
                'tipo':  eq.tipo,
                'kva':   eq.kva,
                'label': eq.label,
                'novo':  eq.novo,
            })

        jobs[job_id].update({
            'status': 'extraido',
            'mensagem': f'{len(eqs_list)} equipamentos encontrados',
            'departamento':          dados.departamento,
            'municipio':             dados.municipio,
            'equipamento_principal': dados.equipamento_principal,
            'data':                  dados.data,
            'equipamentos':          eqs_list,
        })

    except Exception as e:
        import traceback
        jobs[job_id].update({
            'status': 'erro',
            'mensagem': f'Erro na extração: {str(e)}',
            'detalhe': traceback.format_exc(),
        })


# ─────────────────────────────────────────────
#  BACKGROUND: GERAÇÃO
# ─────────────────────────────────────────────

def _gerar_bg(job_id: str, payload: dict):
    try:
        meta = payload.get('meta')
        meta = meta if isinstance(meta, dict) else {}
        equip = (payload.get('equipamento_principal') or
                 meta.get('equipamento') or 'croqui').replace(' ', '_')
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        base = f"croqui_{equip}_{ts}"
        arquivos = []

        jobs[job_id]['mensagem'] = 'Desenhando croqui...'
        caminho_pdf = os.path.join(OUTPUT_DIR, f"{base}.pdf")

        # Novo formato: tem 'nos' e 'trechos' → usar gerador v4
        if 'nos' in payload and 'trechos' in payload:
            from gerador_croqui_v4 import gerar_croqui_v4
            gerar_croqui_v4(payload, caminho_pdf)
        else:
            # Formato legado
            from gerador_croqui_v3 import gerar_croqui_from_payload
            gerar_croqui_from_payload(payload, caminho_pdf)

        arquivos.append(caminho_pdf)

        # Excel legado (se template existir)
        try:
            from gerador_excel import gerar_croqui_excel, TEMPLATE_FILE
            from extrator import DadosProjeto
            if os.path.exists(TEMPLATE_FILE):
                jobs[job_id]['mensagem'] = 'Gerando Excel...'
                caminho_xls = os.path.join(OUTPUT_DIR, f"{base}.xls")
                meta = payload.get('meta', {})
                dados_compat = DadosProjeto()
                dados_compat.municipio             = payload.get('municipio') or meta.get('municipio', '')
                dados_compat.departamento          = payload.get('departamento') or meta.get('departamento', '')
                dados_compat.equipamento_principal = payload.get('equipamento_principal') or meta.get('equipamento', '')
                dados_compat.data                  = payload.get('data') or meta.get('data_levantamento', '')
                dados_compat.obra                  = ''
                gerar_croqui_excel(dados_compat, caminho_xls)
                arquivos.append(caminho_xls)
        except Exception:
            pass

        jobs[job_id].update({
            'status': 'concluido',
            'mensagem': 'Croqui gerado com sucesso!',
            'arquivos': arquivos,
            'tem_excel': any(a.endswith('.xls') for a in arquivos),
        })

    except Exception as e:
        import traceback
        jobs[job_id].update({
            'status': 'erro',
            'mensagem': f'Erro na geração: {str(e)}',
            'detalhe': traceback.format_exc(),
        })


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "="*55)
    print("  GERADOR DE CROQUI RGE/CPFL - Interface Web")
    print("="*55)
    print("  Acesse: http://localhost:5000")
    print("  Para encerrar: Ctrl+C")
    print("="*55 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5000)
