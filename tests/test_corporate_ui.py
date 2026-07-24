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
    assert "Conversão de projeto em croqui" in page
    assert "Unidade de trabalho" in page
    assert "Caxias" in page
