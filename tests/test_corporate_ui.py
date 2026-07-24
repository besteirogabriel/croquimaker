def test_login_usa_identidade_visual_da_jobel(app_module_with_auth):
    client = app_module_with_auth.app.test_client()

    response = client.get("/login")
    logo = client.get("/static/img/jobel_logo.png")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert logo.status_code == 200
    assert logo.content_type == "image/png"
    assert "JOBEL Engenharia" in page
    assert "/static/img/jobel_logo.png" in page
    assert "Acesso corporativo" in page
    assert "brand-mark" not in page


def test_painel_autenticado_usa_logo_e_contexto_da_unidade(
    app_module_with_auth,
    login_client,
):
    client = app_module_with_auth.app.test_client()
    login_client(client, "caxias1")

    response = client.get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "/static/img/jobel_logo.png" in page
    assert "CroquiMaker" in page
    assert "Dashboard operacional" in page
    assert "Projetos recentes" in page
    assert "Caxias" in page

    generator = client.get("/novo").get_data(as_text=True)
    assert "Conversão de projeto em croqui" in generator
    assert "Unidade de trabalho" in generator


def test_login_reserva_altura_para_exibir_logo_completo(app_module_with_auth):
    client = app_module_with_auth.app.test_client()

    css = client.get("/static/styles.css").get_data(as_text=True)

    assert ".brand-logo-login" in css
    assert "height: 132px" in css
    assert "transform: translate(-50%, -47%)" in css
