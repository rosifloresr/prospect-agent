import httpx
import pytest
from app.tools.base import ToolError
from app.tools.read_page import MAX_BYTES, MAX_REDIRECTS, ReadPageTool, extract_text, is_public_ip

# Un "DNS de mentira": los tests no dependen de internet ni de tu red.
FAKE_DNS = {
    "example.test": ["93.184.216.34"],
    "interna.test": ["10.0.0.5"],
    "mixto.test": ["93.184.216.34", "127.0.0.1"],  # una IP pública y otra interna
    "localhost": ["127.0.0.1"],
}

HTML = """
<html><head><title>Acme Logística</title><style>body{color:red}</style></head>
<body>
  <nav>Inicio | Contacto | Blog</nav>
  <script>alert('no debería aparecer')</script>
  <h1>Acme Logística</h1>
  <p>Líder en   transporte   de última milla.</p>
  <footer>© 2026 Acme</footer>
</body></html>
"""

def fake_resolver(host: str) -> list[str]:
    if host not in FAKE_DNS:
        raise ToolError(f"No se pudo resolver el dominio '{host}'.")
    return FAKE_DNS[host]

class Server:
    """Servidor falso: registra cada petición y responde con lo que le indiquemos."""

    def __init__(self, response_factory):
        self.requests: list[str] = []
        self._factory = response_factory

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        return self._factory(request)

    def tool(self, **kwargs) -> ReadPageTool:
        client = httpx.Client(transport=httpx.MockTransport(self), follow_redirects=False)
        return ReadPageTool(client=client, resolver=fake_resolver, **kwargs)

def html_response(body: str = HTML, **headers):
    return lambda _req: httpx.Response(
        200, text=body, headers={"content-type": "text/html", **headers}
    )

# ------------------------------------------------------------------ lectura
def test_extrae_titulo_y_texto_principal():
    result = Server(html_response()).tool().execute("https://example.test/")
    assert "Título: Acme Logística" in result
    assert "Líder en transporte de última milla." in result  # espacios múltiples colapsados
    assert "URL: https://example.test/" in result

def test_descarta_scripts_estilos_menus_y_pie():
    result = Server(html_response()).tool().execute("https://example.test/")
    assert "alert" not in result
    assert "color:red" not in result
    assert "Inicio | Contacto" not in result
    assert "© 2026" not in result

def test_lee_texto_plano():
    server = Server(
        lambda _r: httpx.Response(200, text="hola mundo", headers={"content-type": "text/plain"})
    )
    assert "hola mundo" in server.tool().execute("https://example.test/robots.txt")

def test_respeta_la_codificacion_declarada():
    body = "<html><title>Ñandú</title><body><p>camión</p></body></html>".encode("latin-1")
    server = Server(
        lambda _r: httpx.Response(
            200, content=body, headers={"content-type": "text/html; charset=latin-1"}
        )
    )
    result = server.tool().execute("https://example.test/")
    assert "Ñandú" in result
    assert "camión" in result

def test_trunca_el_texto_devuelto():
    long_html = "<html><body><p>" + "palabra " * 5000 + "</p></body></html>"
    result = Server(html_response(long_html)).tool(max_chars=200).execute("https://example.test/")
    assert "truncado" in result
    assert len(result) < 400

def test_no_descarga_mas_de_los_bytes_maximos():
    big = "a" * (MAX_BYTES * 3)
    server = Server(
        lambda _r: httpx.Response(200, text=big, headers={"content-type": "text/plain"})
    )
    result = server.tool(max_chars=10**9).execute("https://example.test/")
    assert len(result) <= MAX_BYTES + 100

def test_una_pagina_sin_texto_legible_es_un_error():
    only_script = "<html><body><script>var x = 1;</script></body></html>"
    with pytest.raises(ToolError, match="no tiene texto legible"):
        Server(html_response(only_script)).tool().execute("https://example.test/")

# ------------------------------------------------------------------ errores de red
@pytest.mark.parametrize("status", [404, 500])
def test_errores_http_se_informan(status):
    server = Server(
        lambda _r: httpx.Response(status, text="x", headers={"content-type": "text/html"})
    )
    with pytest.raises(ToolError, match=f"HTTP {status}"):
        server.tool().execute("https://example.test/")

def test_rechaza_tipos_de_contenido_no_soportados():
    server = Server(
        lambda _r: httpx.Response(
            200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"}
        )
    )
    with pytest.raises(ToolError, match="Tipo de contenido no soportado: application/pdf"):
        server.tool().execute("https://example.test/archivo.pdf")

def test_timeout_se_informa_sin_detalles_internos():
    def boom(request):
        raise httpx.ReadTimeout("tiempo agotado", request=request)

    with pytest.raises(ToolError, match="tardó demasiado"):
        Server(boom).tool().execute("https://example.test/")

def test_error_de_conexion_se_informa():
    def boom(request):
        raise httpx.ConnectError("conexión rechazada", request=request)

    with pytest.raises(ToolError, match="No se pudo descargar"):
        Server(boom).tool().execute("https://example.test/")

# ------------------------------------------------------------------ SSRF: URLs bloqueadas
BLOCKED_URLS = [
    "file:///etc/passwd",
    "ftp://example.test/archivo",
    "javascript:alert(1)",
    "example.test/sin-esquema",
    "http://",
    "http://127.0.0.1/",
    "http://localhost/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "http://[::ffff:100.64.0.1]/",
    "http://0.0.0.0/",
    "http://10.0.0.1/",
    "http://172.16.0.1/",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",  # metadatos de la nube: el blanco clásico de SSRF
    "http://100.64.0.1/",
    "http://224.0.0.1/",  # multicast
    "http://interna.test/",  # un dominio que resuelve a una IP privada
    "http://mixto.test/",  # una sola IP interna alcanza para bloquear
    "http://example.test:22/",
    "http://example.test:8080/",
    "http://example.test:99999/",
]

@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_bloquea_urls_peligrosas_sin_hacer_ninguna_peticion(url):
    server = Server(html_response())
    with pytest.raises(ToolError):
        server.tool().execute(url)
    assert server.requests == []  # la petición ni siquiera salió


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1/", "http://169.254.169.254/", "http://interna.test/"]
)
def test_los_mensajes_de_bloqueo_no_revelan_la_red_interna(url):
    with pytest.raises(ToolError) as error:
        Server(html_response()).tool().execute(url)
    assert "bloqueada por seguridad" in str(error.value)
    assert "10.0.0.5" not in str(error.value)

@pytest.mark.parametrize(
    "url", ["http://example.test/", "http://example.test:80/", "https://example.test:443/x?q=1"]
)
def test_permite_urls_publicas(url):
    assert "Acme" in Server(html_response()).tool().execute(url)

@pytest.mark.parametrize("host", ["localhost", "0x7f000001", "2130706433", "127.1", "0177.0.0.1"])
def test_con_el_resolver_real_bloquea_localhost_y_sus_disfraces(host):
    # Sin fake_resolver: usa el DNS del sistema, que entiende estas formas de escribir 127.0.0.1.
    # Si el sistema no las resuelve, también termina en ToolError: en ningún caso se conecta.
    with pytest.raises(ToolError):
        ReadPageTool().execute(f"http://{host}/")

# ------------------------------------------------------------------ SSRF: redirecciones
def test_bloquea_una_redireccion_hacia_una_ip_interna():
    def respond(request):
        if request.url.host == "example.test":
            return httpx.Response(
                302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
            )
        return httpx.Response(200, text="SECRETO", headers={"content-type": "text/plain"})

    server = Server(respond)
    with pytest.raises(ToolError, match="bloqueada por seguridad"):
        server.tool().execute("https://example.test/")
    assert server.requests == ["https://example.test/"]  # el segundo salto nunca se pidió

def test_bloquea_una_redireccion_hacia_un_dominio_interno():
    server = Server(
        lambda _r: httpx.Response(301, headers={"location": "http://interna.test/admin"})
    )
    with pytest.raises(ToolError, match="bloqueada por seguridad"):
        server.tool().execute("https://example.test/")
    assert server.requests == ["https://example.test/"]

def test_sigue_redirecciones_relativas_legitimas():
    def respond(request):
        if request.url.path == "/viejo":
            return httpx.Response(302, headers={"location": "/nuevo"})
        return httpx.Response(200, text="contenido nuevo", headers={"content-type": "text/plain"})

    server = Server(respond)
    assert "contenido nuevo" in server.tool().execute("https://example.test/viejo")
    assert server.requests == ["https://example.test/viejo", "https://example.test/nuevo"]

def test_corta_los_bucles_de_redireccion():
    server = Server(
        lambda _r: httpx.Response(302, headers={"location": "https://example.test/otra"})
    )
    with pytest.raises(ToolError, match="demasiadas veces"):
        server.tool().execute("https://example.test/")
    assert len(server.requests) == MAX_REDIRECTS + 1

def test_redireccion_con_destino_vacio():
    server = Server(lambda _r: httpx.Response(302, headers={"location": ""}))
    with pytest.raises(ToolError, match="destino vacío"):
        server.tool().execute("https://example.test/")

# ------------------------------------------------------------------ utilidades
@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("93.184.216.34", True),
        ("8.8.8.8", True),
        ("2606:4700:4700::1111", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("172.31.255.255", False),
        ("192.168.0.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("0.0.0.0", False),
        ("224.0.0.1", False),
        ("::1", False),
        ("fe80::1", False),
        ("fe80::1%eth0", False),
        ("fc00::1", False),
        ("::ffff:127.0.0.1", False),
        ("::ffff:10.0.0.1", False),
        # Mapeadas cuya IPv4 interna Python NO bloquea por sí solo: solo las detecta el desenvolvimiento.
        ("::ffff:100.64.0.1", False),
        ("::ffff:224.0.0.1", False),
        ("::ffff:8.8.8.8", True),
    ],
)
def test_is_public_ip(address, expected):
    assert is_public_ip(address) is expected

def test_extract_text_devuelve_titulo_y_texto_limpio():
    title, text = extract_text(HTML)
    assert title == "Acme Logística"
    assert text == "Acme Logística\nLíder en transporte de última milla."

def test_extract_text_sin_titulo():
    title, text = extract_text("<p>solo texto</p>")
    assert title == ""
    assert text == "solo texto"