# O Que o Sistema Ainda Nao Consegue Fazer

Data: 2026-06-25

Este documento lista, de forma objetiva, as capacidades que o sistema atual ainda nao entrega ou entrega apenas de forma parcial. A intencao e servir como base para novos prompts e requisitos tecnicos.

## Resumo Executivo

O sistema atual e uma aplicacao local funcional para upload, extracao heuristica, revisao manual, geracao best-effort de croqui, JSON, Excel simples e relatorio de dependencias. Ele ainda nao deve ser tratado como uma engine homologada de croqui tecnico automatico.

As maiores lacunas estao em:

- interpretacao confiavel de folhas de projeto quando o PDF vem fragmentado, escaneado ou com simbologia CAD complexa;
- simbologia oficial JOBEL/RGE/CPFL;
- reconstrucao real da topologia eletrica a partir de vetores e simbolos;
- editor visual completo para corrigir o croqui no canvas;
- Excel oficial e layout documental homologado;
- auditoria, gestao de usuarios, permissoes e fluxo de aprovacao em nivel de producao;
- validacoes tecnicas normativas;
- metricas de acuracia com base em amostras reais aprovadas.

## 1. Entrada de PDFs

### Nao consegue processar PDF escaneado com OCR confiavel

Estado atual: o pipeline usa PyMuPDF para texto/vetores. OCR nao fica ativo por padrao.

Impacto: PDFs em imagem, digitalizados, com baixa qualidade, rotacao ruim, sombras ou carimbos podem sair praticamente sem texto tecnico.

Requisito sugerido:

- implementar OCR local opcional;
- definir motor OCR permitido, por exemplo Tesseract local;
- criar controle na UI para ativar/desativar OCR por job;
- armazenar texto OCR separado do texto nativo;
- marcar confianca diferente para dados extraidos por OCR.

### Nao consegue tratar todos os tipos de PDF CAD

Estado atual: a extracao vetorial normaliza primitivas basicas (`line`, `polyline`, `rect`, `circle_like`, `curve`). Nao ha interpretacao completa de blocos CAD, layers, atributos, grupos, familias, estilos, escalas ou simbolos compostos.

Impacto: linhas e simbolos podem ser extraidos como milhares de primitivas soltas, sem significado tecnico.

Requisito sugerido:

- mapear padroes vetoriais reais dos PDFs da JOBEL;
- identificar layers/camadas quando disponiveis;
- agrupar primitivas proximas em simbolos;
- detectar escala/desenho, orientacao e legenda;
- criar classificadores deterministicos para simbolos compostos.

### Nao consegue validar automaticamente se o PDF enviado e o documento correto

Estado atual: o sistema aceita PDFs e tenta processar. Ele nao valida formalmente se o arquivo pertence ao fluxo RGE/CPFL esperado.

Impacto: arquivo errado pode gerar payload parcial, avisos genericos e saida revisavel sem bloquear.

Requisito sugerido:

- definir criterios obrigatorios minimos de documento valido;
- bloquear ou alertar quando TES, plano, croqui ou projeto estiverem ausentes;
- criar uma tela de pre-validacao antes do processamento completo.

## 2. Classificacao de Paginas

### Nao classifica paginas com acuracia homologada

Estado atual: a classificacao usa palavras-chave, orientacao e contagem de desenhos.

Impacto: paginas de projeto podem sair como `UNKNOWN`, e paginas administrativas podem ser confundidas quando o texto esta fragmentado.

Requisito sugerido:

- fornecer amostras reais com classificacao correta por pagina;
- ampliar regras por layouts reais;
- criar teste automatizado por tipo de folha;
- mostrar na UI os sinais que justificaram a classificacao;
- permitir lote de correcao manual.

### Nao separa subtipos tecnicos de folha de projeto

Estado atual: existe `PROJETO_REDE`, `CROQUI_RESUMIDO`, `DETALHE_TECNICO` e tipos administrativos. Nao ha taxonomia detalhada de folhas.

Impacto: folhas diferentes podem receber o mesmo tratamento mesmo exigindo parsers distintos.

Requisito sugerido:

- definir taxonomia oficial de paginas;
- adicionar tipos como planta, detalhe, situacao, materiais, legenda, diagrama, manobra, viabilidade;
- criar regras especificas por tipo.

## 3. Extracao de Texto

### Nao entende texto fragmentado em todos os casos

Estado atual: os parsers leem texto bruto, blocos e palavras por linha. PDF CAD pode quebrar uma frase em letras, colunas, spans fora de ordem ou textos sobrepostos.

Impacto: campos como municipio, equipamento principal, descricao, etapas de manobra e cabos podem ficar incompletos ou errados.

Requisito sugerido:

- implementar reconstrução de leitura por coordenadas;
- detectar colunas, tabelas e blocos;
- ordenar texto por regioes da pagina;
- criar parser de tabelas TES/CPFL/RGE;
- armazenar evidencias por campo extraido.

### Nao extrai todas as informacoes da TES

Estado atual: o parser extrai alguns campos e algumas acoes como abrir/fechar FC/FU, retirar FU e instalar TR.

Impacto: qualquer frase fora dos padroes atuais pode ficar ausente. Condicoes especiais, responsaveis, equipes, horarios, risco, impedimentos e observacoes podem nao ser estruturados.

Requisito sugerido:

- listar todos os campos obrigatorios da TES;
- criar schema completo de TES;
- criar exemplos reais por variacao de texto;
- adicionar validacoes por campo obrigatorio.

## 4. Extracao de Equipamentos

### Nao reconhece todos os tipos de equipamentos

Estado atual: foco em transformador, chave fusivel, chave de comando/faca e alguns codigos por regex/catalogo heuristico.

Impacto: religadores, reguladores, chaves especificas, aterramentos, estais, estruturas, postes especiais, materiais e outros elementos podem ser ignorados ou classificados genericamente.

Requisito sugerido:

- fornecer lista oficial de equipamentos e abreviacoes;
- mapear sinonimos e formas de escrita;
- criar catalogo YAML/Excel oficial;
- adicionar testes por tipo de equipamento.

### Nao associa equipamento a poste com confianca alta em todos os casos

Estado atual: associacao e feita por proximidade de bbox quando existe coordenada, por fallback quando ha um unico no, ou manualmente na revisao.

Impacto: equipamentos podem aparecer sem poste ou vinculados a um no de referencia, especialmente quando nao ha coordenadas confiaveis.

Requisito sugerido:

- criar algoritmo espacial por pagina de projeto;
- usar vetores/simbolos para localizar equipamento;
- usar conectividade do grafo para associar equipamento ao poste;
- permitir associacao visual por clique/drag na UI.

## 5. Extracao de Postes e Vaos

### Nao reconstrói topologia real quando nao ha marcadores P/V claros

Estado atual: parser depende muito de padroes `P123`, `V1-2`, comprimentos e cabos reconheciveis em texto.

Impacto: quando o desenho usa simbologia sem labels textuais claros, o sistema cria topologia parcial ou fallback por equipamentos.

Requisito sugerido:

- detectar postes por simbolos vetoriais;
- detectar linhas de rede e conexoes por geometria;
- inferir nos por intersecoes e proximidade;
- vincular labels textuais aos elementos graficos proximos;
- validar com amostras reais aprovadas.

### Nao interpreta corretamente todos os cabos, fases e comprimentos

Estado atual: cabos sao extraidos por regex limitada. Comprimento depende de padrao textual com metros.

Impacto: cabos podem ficar vazios, incorretos ou fora de padrao; comprimentos podem faltar.

Requisito sugerido:

- fornecer lista oficial de padroes de cabo/material;
- definir gramatica de anotacoes de vao;
- criar normalizador de cabos;
- validar comprimentos por escala/desenho quando texto faltar.

## 6. Interpretacao Vetorial e Simbologia

### Nao usa simbologia oficial

Estado atual: `default_rge_heuristic.yaml` e explicitamente heuristico.

Impacto: o sistema nao pode afirmar conformidade normativa ou oficial.

Requisito sugerido:

- receber simbologia oficial da JOBEL/RGE/CPFL;
- implementar importador de catalogo oficial;
- versionar catalogo;
- registrar qual versao do catalogo foi usada em cada job.

### Nao reconhece simbolos complexos por desenho

Estado atual: as primitivas vetoriais sao extraidas, mas nao ha classificador completo de simbolos.

Impacto: chaves, transformadores, postes, estais, aterramentos e equipamentos desenhados podem nao ser interpretados quando nao ha texto proximo.

Requisito sugerido:

- criar biblioteca local de templates vetoriais;
- agrupar primitivas por bbox/proximidade;
- comparar formas com tolerancia;
- permitir calibracao por amostras reais.

### Nao diferencia automaticamente estados de rede com confianca

Estado atual: status pode sair como `instalar`, `retirar`, `abrir`, `fechar`, `existente`, `indeterminado`, mas nao ha leitura normativa completa de cor, layer, tracejado e legenda.

Impacto: rede nova, existente, retirada, deslocada, provisoria ou energizada pode ser mal classificada.

Requisito sugerido:

- receber regras de cor, linha, layer e tracejado;
- mapear legenda oficial;
- validar estado por texto e por vetor;
- mostrar evidencias no payload.

## 7. Grafo e Topologia

### Nao garante que o grafo representa a rede real

Estado atual: quando faltam vaos, o sistema cria layout referencial a partir dos equipamentos. Esse fallback e util para gerar uma saida revisavel, mas nao representa vao confirmado.

Impacto: PDF pode parecer um croqui, mas conter ligacoes apenas referenciais.

Requisito sugerido:

- separar visualmente grafo real e grafo referencial;
- exigir confirmacao manual para fallback;
- criar regra para impedir aprovacao automatica com spans `REFERENCIA_REVISAO`;
- criar editor visual para redesenhar a topologia.

### Nao calcula topologia eletrica avançada

Estado atual: grafo e basicamente conectividade entre nos e vaos extraidos.

Impacto: nao ha analise de radialidade, alimentador, chaveamento, fluxo, seccionamento, trechos energizados, interferencias ou consistencia eletrica completa.

Requisito sugerido:

- definir regras eletricas que devem ser verificadas;
- modelar alimentadores, fases e tensoes;
- validar chaveamento e plano de manobra contra topologia.

## 8. Validacoes Tecnicas

### Nao possui validacoes normativas oficiais

Estado atual: valida ausencias basicas como pagina de projeto, croqui resumido, span sem endpoints, cabo/comprimento vazio e equipamento sem poste.

Impacto: erros tecnicos importantes podem passar sem alerta.

Requisito sugerido:

- listar validacoes obrigatorias JOBEL/RGE/CPFL;
- definir severidade de cada regra;
- definir criterios bloqueantes para aprovacao;
- adicionar mensagens de acao corretiva.

### Confianca global ainda e heuristica

Estado atual: confianca e calculada por media ponderada fixa de TES, equipamentos, vaos, postes e associacao.

Impacto: o score pode parecer preciso, mas nao e uma metrica estatistica calibrada.

Requisito sugerido:

- criar dataset de amostras com resultado esperado;
- medir precision/recall por campo;
- calibrar pesos de confianca;
- mostrar confianca por origem/evidencia.

## 9. Editor Manual e Revisao Visual

### Nao possui editor grafico completo de croqui

Estado atual: a revisao permite edicao textual de metadados, paginas, postes, equipamentos, vaos e JSON. O overlay e imagem estatica.

Impacto: operador nao consegue arrastar poste, desenhar vao, ligar equipamento por clique, ajustar simbolo visualmente ou editar diretamente no canvas.

Requisito sugerido:

- implementar canvas interativo;
- permitir adicionar/mover/remover postes;
- desenhar e editar vaos;
- associar equipamentos por clique;
- salvar coordenadas revisadas;
- regenerar overlay em tempo real ou apos salvar.

### Nao existe controle completo de revisao por item

Estado atual: ha campos `approved` e `deleted`, mas nao ha workflow rico por item, historico visivel, comentarios ou comparacao antes/depois.

Impacto: auditoria da revisao fica limitada ao `revision_log` no JSON.

Requisito sugerido:

- criar comentarios por item;
- registrar antes/depois por campo alterado;
- mostrar historico na UI;
- exigir justificativa para alteracoes criticas;
- exportar trilha de auditoria.

## 10. Geracao do Croqui PDF/PNG

### Nao gera croqui final homologado

Estado atual: gera PDF/PNG best-effort e revisavel, com layout tecnico proprio.

Impacto: o resultado ainda nao deve ser usado como documento final oficial sem revisao/homologacao.

Requisito sugerido:

- receber modelo visual oficial;
- definir cabecalho/rodape, quadro de revisoes, escala, legenda, layers, cores e simbolos;
- criar criterios de aceite do PDF;
- comparar PDF gerado com croquis aprovados.

### Nao preserva layout original do desenho

Estado atual: o grafo e redesenhado por posicoes extraidas ou layout automatico. Nao ha garantia de reproduzir geometria CAD original.

Impacto: o croqui final pode ficar topologicamente simplificado ou diferente da planta original.

Requisito sugerido:

- definir se o objetivo e croqui esquematico ou planta fiel;
- para planta fiel, usar coordenadas vetoriais reais;
- para esquematico, definir regras de layout ortogonal;
- permitir ajuste manual do layout final.

### Nao renderiza todos os elementos esperados

Estado atual: PDF exibe grafo, equipamentos principais, vaos e validacoes. Elementos como legenda completa, materiais, areas, observacoes, detalhes, tabelas e simbologia oficial ainda sao limitados.

Requisito sugerido:

- listar todos os elementos obrigatorios no PDF;
- definir posicao e formato de cada bloco;
- incluir materiais, legenda, area de trabalho, responsaveis, equipes e assinatura quando aplicavel.

## 11. Exportacao Excel

### Nao preenche o Excel oficial da JOBEL de forma completa

Estado atual: quando ha template, apenas alguns campos fixos sao preenchidos; sem template, gera `.xls` simples com abas tecnicas.

Impacto: Excel pode nao servir para fluxo operacional real.

Requisito sugerido:

- fornecer template oficial sem dados sensiveis;
- mapear celulas e abas;
- definir campos obrigatorios;
- preservar formulas, formatacao e macros se houver;
- validar arquivo gerado com usuarios da JOBEL.

### Nao exporta `.xlsx` moderno com formulas/tabelas completas

Estado atual: geracao usa formato `.xls`.

Impacto: limitacoes de linhas, colunas, estilo e compatibilidade.

Requisito sugerido:

- definir se formato final deve ser `.xls` ou `.xlsx`;
- se `.xlsx`, migrar para openpyxl/xlsxwriter;
- criar testes de abertura e validacao.

## 12. JSON Tecnico e Contrato de Dados

### Schema ainda e inicial

Estado atual: `TechnicalPayload` cobre paginas, nodes, spans, equipment, work_areas, materials, validations e meta generico.

Impacto: campos oficiais podem ficar em `meta` sem contrato rigido; consumidores externos podem nao ter estabilidade suficiente.

Requisito sugerido:

- definir contrato JSON oficial;
- versionar schema;
- separar TES, projeto, manobra, materiais, auditoria e saidas;
- publicar exemplos validos e invalidos;
- criar validacao JSON Schema.

### Nao exporta pacote completo padronizado

Estado atual: arquivos ficam em `data/outputs/<job_id>/`, e ha ZIP apenas para overlays.

Impacto: nao ha pacote unico com manifesto, hashes, payload, PDF, Excel, log e auditoria.

Requisito sugerido:

- criar export ZIP completo;
- incluir manifesto;
- incluir checksums;
- incluir versao do sistema/catalogo;
- incluir trilha de auditoria.

## 13. UI, Usuarios e Permissoes

### Nao possui gestao completa de usuarios

Estado atual: cria admin inicial automaticamente. Roles existem no modelo, mas nao ha tela de cadastro, edicao, bloqueio, troca de senha ou convite.

Impacto: operacao real dependeria de acesso manual ao banco/config.

Requisito sugerido:

- tela de usuarios;
- criar/editar/desativar usuarios;
- redefinicao de senha;
- politicas de senha;
- logs de login;
- roles configuraveis.

### Nao possui fluxo formal de aprovacao tecnica

Estado atual: ha botao de aprovar extracao e gerar saidas. Nao ha assinatura, revisao dupla, status por etapa, rejeicao com motivo ou bloqueios por severidade.

Impacto: a aprovacao ainda e operacionalmente simples demais para ambiente auditavel.

Requisito sugerido:

- definir workflow oficial;
- exigir aprovador engineer/admin;
- bloquear aprovacao com erros criticos;
- registrar assinatura tecnica;
- permitir rejeitar e reabrir job.

### Nao possui dashboard operacional completo

Estado atual: dashboard mostra contagens e lista recente.

Impacto: nao ha filtros avancados, busca por TES, municipio, status, responsavel, periodo, confianca ou alertas.

Requisito sugerido:

- filtros e busca;
- paginacao;
- ordenacao;
- exportacao de lista;
- indicadores de produtividade e qualidade.

## 14. Processamento, Escalabilidade e Robustez

### Nao processa jobs em background real

Estado atual: upload processa PDF no request HTTP.

Impacto: PDFs grandes podem travar a requisicao, dar timeout ou prejudicar outros usuarios.

Requisito sugerido:

- fila local de jobs;
- worker separado;
- progresso por etapa;
- cancelamento/reprocessamento;
- retentativas controladas.

### Nao possui controle robusto de concorrencia

Estado atual: SQLite e armazenamento local atendem uso local simples.

Impacto: uso simultaneo por varios operadores pode gerar gargalos ou conflitos.

Requisito sugerido:

- definir numero esperado de usuarios;
- considerar Postgres para producao;
- criar lock por job;
- impedir edicao simultanea sem aviso.

### Nao possui observabilidade de producao

Estado atual: ha logs por job, mas nao ha painel de erros, metricas, traces ou alertas.

Impacto: diagnostico de falhas em producao sera manual.

Requisito sugerido:

- logs estruturados;
- tela de eventos por job;
- metricas de tempo por etapa;
- captura de excecoes;
- relatorio de falhas recorrentes.

## 15. Seguranca e Conformidade

### Nao implementa politicas completas de seguranca

Estado atual: login basico local com Flask-Login e senha hash. Nao ha MFA, bloqueio por tentativas, expiracao de sessao configuravel, CSRF completo em endpoints JSON ou politica refinada.

Impacto: para producao corporativa, controles ainda sao insuficientes.

Requisito sugerido:

- politicas de senha;
- bloqueio por tentativas;
- timeout de sessao;
- CSRF nos endpoints de alteracao;
- cabecalhos de seguranca;
- HTTPS/reverse proxy documentado.

### Nao possui politica de retencao e descarte

Estado atual: uploads e outputs ficam em disco local indefinidamente.

Impacto: acumulo de PDFs sensiveis e risco de retencao indevida.

Requisito sugerido:

- definir periodo de retencao;
- criar rotina de limpeza;
- arquivamento seguro;
- exclusao auditavel;
- configuracao por ambiente.

### Nao possui criptografia de arquivos em repouso

Estado atual: arquivos ficam em `data/uploads` e `data/outputs`.

Impacto: acesso ao filesystem expoe PDFs e saidas.

Requisito sugerido:

- definir se precisa criptografar em repouso;
- armazenar chave fora do repositorio;
- registrar acesso/download.

## 16. Docker, Instalacao e Ambiente

### Docker ainda precisa ser validado em ambiente alvo

Estado atual: Dockerfile e docker-compose existem. O ambiente local usado teve Python 3.14, enquanto o alvo documentado e Python 3.12.

Impacto: pode haver diferencas de dependencias, especialmente pacotes com extensoes nativas.

Requisito sugerido:

- validar build Docker limpo;
- fixar versao Python suportada;
- criar script de smoke test Docker;
- documentar instalacao em Windows/Linux.

### Nao existe instalador final para usuario nao tecnico

Estado atual: execucao exige terminal, Python/Docker e configuracao manual.

Impacto: implantacao por operadores pode ser dificil.

Requisito sugerido:

- definir forma de distribuicao;
- criar instalador local ou pacote Docker simplificado;
- criar scripts de inicializacao/parada;
- documentar backup/restauracao.

## 17. Testes e Qualidade

### Testes ainda sao sinteticos e limitados

Estado atual: existem testes para classificacao, parser TES, parser de vaos, grafo e relatorio. Eles nao cobrem fluxo completo com muitos PDFs reais.

Impacto: regressao em casos reais pode passar despercebida.

Requisito sugerido:

- criar suite com PDFs reais anonimizados;
- incluir outputs esperados;
- medir acuracia por campo;
- testar UI/API;
- testar geracao PDF/Excel;
- testar Docker.

### Nao existe benchmark de acuracia

Estado atual: nao ha baseline formal por documento real aprovado.

Impacto: nao e possivel dizer objetivamente se a engine melhorou ou piorou.

Requisito sugerido:

- criar corpus homologado;
- comparar payload gerado vs payload esperado;
- medir por TES, equipamento, poste, vao, cabo, topologia e pagina;
- publicar relatorio de acuracia.

## 18. Funcionalidades Explicitamente Fora do Escopo Atual

Estas funcionalidades nao existem hoje e precisam de requisito proprio se forem desejadas:

- envio para IA externa no fluxo principal;
- interpretacao por modelo local de visao/IA;
- OCR automatico;
- desenho manual completo em canvas;
- importador completo de simbologia oficial;
- editor de catalogo visual;
- reconhecimento completo de simbolos vetoriais;
- integracao com sistemas JOBEL/RGE/CPFL;
- assinatura digital;
- notificacoes por e-mail;
- backup/restauracao pela UI;
- multiempresa/multitenancy;
- API publica versionada;
- processamento em lote;
- comparacao lado a lado entre croqui gerado e croqui aprovado;
- relatorio de divergencias tecnico;
- exportacao CAD/DXF/DWG;
- exportacao SVG editavel;
- modo offline instalavel com atualizacao automatica.

## 19. Dependencias de Requisito Que Precisam Vir da JOBEL

Para evoluir de ferramenta revisavel para sistema operacional confiavel, ainda faltam:

- PDFs reais representativos por tipo de caso;
- croquis finais aprovados correspondentes;
- classificacao correta das paginas desses PDFs;
- template Excel oficial;
- aba de simbologia completa;
- lista oficial de materiais;
- lista oficial de equipamentos e abreviacoes;
- regras de rede nova/existente/retirada/deslocada;
- regras de cor, tracejado, layer e legenda;
- normas/GEDs aplicaveis;
- layout oficial de PDF/croqui;
- criterios de aceite;
- politicas de usuario, aprovacao e assinatura;
- politica de retencao dos arquivos;
- ambiente alvo de instalacao.

## 20. Sugestoes de Prompts/Requisitos Para a Proxima Rodada

### Prompt 1: OCR local

Implementar OCR local opcional com Tesseract para paginas sem texto nativo, preservando evidencias e confianca por origem.

### Prompt 2: Classificador calibrado por amostras

Criar dataset de classificacao de paginas com PDFs reais em `croquisreais/`, arquivo esperado em JSON e testes automatizados de acuracia.

### Prompt 3: Editor visual de topologia

Criar canvas interativo na tela de revisao para adicionar/mover/remover postes, desenhar vaos, associar equipamentos e salvar coordenadas revisadas.

### Prompt 4: Simbologia oficial

Implementar importador de simbologia/material/equipamento a partir de Excel oficial da JOBEL, com versionamento e uso nos parsers.

### Prompt 5: Excel oficial

Mapear e preencher o template Excel oficial da JOBEL, preservando formatacao, formulas e abas.

### Prompt 6: Validacoes normativas

Implementar motor de regras tecnicas configuravel, com severidade, bloqueio de aprovacao e mensagens de correcao.

### Prompt 7: Auditoria e aprovacao

Criar fluxo de aprovacao com historico por campo, comentario, assinatura tecnica, bloqueios por erro e relatorio de auditoria.

### Prompt 8: Job queue

Mover processamento para fila local com worker, progresso por etapa, cancelamento, retentativa e logs visiveis na UI.

### Prompt 9: Pacote de exportacao

Criar ZIP final com PDF, Excel, JSON, overlays, logs, auditoria, manifesto e checksums.

### Prompt 10: Benchmark de acuracia

Criar ferramenta de comparacao entre payload gerado e payload esperado para medir acuracia por campo e por PDF.

## 21. Criterio Honesto de Uso Hoje

O sistema hoje consegue ajudar como:

- ferramenta local de triagem;
- extrator inicial de dados;
- gerador de croqui revisavel;
- base para revisao humana;
- prototipo auditavel para evolucao tecnica.

O sistema ainda nao deve ser vendido ou tratado como:

- gerador automatico final homologado;
- substituto da revisao tecnica;
- validador normativo completo;
- interpretador confiavel de todos os PDFs RGE/CPFL;
- ferramenta pronta para producao multiusuario sem controles adicionais.
