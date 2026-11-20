import json
import logging
import httpx
import pytest
from app.config import Settings
from app.tools import build_default_registry
from app.tools.base import ToolError
from app.tools.web_search import MAX_RESULTS_LIMIT, SNIPPET_CHARS, WebSearchTool

API_KEY = "tvly-clave-de-prueba"

TAVILY_RESPONSE = {
    "results": [
        {
            "title": "Acme Logística abre nuevo centro",
            "url": "https://noticias.test/acme",
            "content": "Acme inauguró un centro.",
            "score": 0.9,
        },
        {
            "title": "Perfil de Laura Gómez",
            "url": "https://perfiles.test/laura",
            "content": "Directora de Operaciones.",
            "score": 0.8,
        },
    ]
}

class FakeTavily:
    def __init__(self, status: int = 200, payload=None):
        self.status = status
        self.payload = TAVILY_RESPONSE if payload is None else payload
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.payload)

    def tool(self) -> WebSearchTool:
        client = httpx.Client(transport=httpx.MockTransport(self))
        return WebSearchTool(API_KEY, client=client)

def test_formatea_los_resultados_como_lista_numerada():
    result = FakeTavily().tool().execute("Acme Logística")
    assert result.startswith("1. Acme Logística abre nuevo centro")
    assert "URL: https://noticias.test/acme" in result
    assert "2. Perfil de Laura Gómez" in result

def test_envia_la_consulta_y_la_clave_como_documenta_la_api():
    server = FakeTavily()
    server.tool().execute("  Acme Logística  ", max_results=3)
    request = server.requests[0]
    assert str(request.url) == "https://api.tavily.com/search"
    assert request.method == "POST"
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    body = json.loads(request.content)
    assert body["query"] == "Acme Logística"  # sin espacios sobrantes
    assert body["max_results"] == 3

@pytest.mark.parametrize(("asked", "sent"), [(0, 1), (-5, 1), (100, MAX_RESULTS_LIMIT), (4, 4)])
def test_acota_max_results(asked, sent):
    server = FakeTavily()
    server.tool().execute("x", max_results=asked)
    assert json.loads(server.requests[0].content)["max_results"] == sent

def test_recorta_los_resumenes_largos():
    payload = {"results": [{"title": "T", "url": "https://x.test", "content": "z" * 5000}]}
    result = FakeTavily(payload=payload).tool().execute("x")
    assert "truncado" in result
    assert len(result) < SNIPPET_CHARS + 200

def test_tolera_resultados_incompletos():
    result = FakeTavily(payload={"results": [{"url": "https://x.test"}]}).tool().execute("x")
    assert "(sin título)" in result

@pytest.mark.parametrize("payload", [{"results": []}, {}, []])
def test_sin_resultados(payload):
    assert "No se encontraron resultados" in FakeTavily(payload=payload).tool().execute("x")

def test_consulta_vacia():
    with pytest.raises(ToolError, match="vacía"):
        FakeTavily().tool().execute("   ")

@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "rechazó la clave"),
        (403, "rechazó la clave"),
        (429, "límite de uso"),
        (500, "HTTP 500"),
    ],
)
def test_errores_http_se_traducen_a_mensajes_claros(status, message):
    with pytest.raises(ToolError, match=message):
        FakeTavily(status=status).tool().execute("x")

def test_los_errores_nunca_incluyen_la_clave():
    for status in (401, 429, 500):
        with pytest.raises(ToolError) as error:
            FakeTavily(status=status).tool().execute("x")
        assert API_KEY not in str(error.value)

def test_respuesta_que_no_es_json():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="<html>"))
    )
    with pytest.raises(ToolError, match="respuesta inválida"):
        WebSearchTool(API_KEY, client=client).execute("x")

def test_timeout_y_error_de_conexion():
    def timeout(request):
        raise httpx.ConnectTimeout("lento", request=request)

    def down(request):
        raise httpx.ConnectError("caído", request=request)

    with pytest.raises(ToolError, match="tardó demasiado"):
        WebSearchTool(API_KEY, client=httpx.Client(transport=httpx.MockTransport(timeout))).execute(
            "x"
        )
    with pytest.raises(ToolError, match="No se pudo conectar"):
        WebSearchTool(API_KEY, client=httpx.Client(transport=httpx.MockTransport(down))).execute(
            "x"
        )

# ------------------------------------------------------------------ fábrica del registro
def make_settings(**overrides) -> Settings:
    # _env_file=None: el resultado no depende del .env de quien ejecute los tests.
    return Settings(
        _env_file=None, database_url="postgresql+psycopg://x:x@localhost/x", **overrides
    )

def test_con_clave_se_registran_las_tres_herramientas():
    registry = build_default_registry(make_settings(tavily_api_key=API_KEY))
    assert registry.names() == ["buscar_web", "leer_archivo", "leer_pagina"]

def test_sin_clave_no_se_ofrece_buscar_web(caplog):
    with caplog.at_level(logging.WARNING):
        registry = build_default_registry(make_settings(tavily_api_key=""))
    assert registry.names() == ["leer_archivo", "leer_pagina"]
    assert "TAVILY_API_KEY" in caplog.text

def test_la_clave_no_aparece_al_imprimir_la_configuracion():
    settings = make_settings(tavily_api_key=API_KEY)
    assert API_KEY not in repr(settings)
    assert API_KEY not in str(settings)
    assert settings.tavily_api_key.get_secret_value() == API_KEY

def test_los_esquemas_del_registro_son_validos_para_la_api_de_claude():
    registry = build_default_registry(make_settings(tavily_api_key=API_KEY))
    for schema in registry.schemas():
        assert set(schema) == {"name", "description", "input_schema"}
        assert schema["input_schema"]["type"] == "object"
        assert schema["description"]