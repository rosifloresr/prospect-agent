import ipaddress
import socket
from collections.abc import Callable
from typing import Any, ClassVar
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from app.tools.base import Tool, ToolError, truncate

ALLOWED_PORTS = {80, 443}
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml", "text/plain"}
MAX_REDIRECTS = 3
MAX_BYTES = 1_000_000
NOISE_TAGS = (
    "head",
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "aside",
    "form",
    "svg",
    "iframe",
)

# Un resolver convierte un nombre de dominio en direcciones IP. Es un parámetro para poder
# reemplazarlo en los tests sin tocar la red.
Resolver = Callable[[str], list[str]]

def default_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ToolError(f"No se pudo resolver el dominio '{host}'.") from exc
    return sorted({info[4][0] for info in infos})

def is_public_ip(address: str) -> bool:
    """True solo si la dirección es de internet público."""
    ip = ipaddress.ip_address(address.split("%")[0])  # quita el "scope id" de IPv6 (fe80::1%eth0)
    if ip.version == 6 and ip.ipv4_mapped is not None:
        # ::ffff:127.0.0.1 es la forma IPv6 de 127.0.0.1: se evalúa la IPv4 que lleva dentro.
        ip = ip.ipv4_mapped
    # is_global es False para privadas, loopback, link-local y CGNAT, pero True para multicast,
    # por eso se excluye aparte.
    return ip.is_global and not ip.is_multicast

def extract_text(html: str) -> tuple[str, str]:
    """Devuelve (título, texto legible) de una página HTML."""
    soup = BeautifulSoup(html, "html.parser")
    # El título se toma ANTES de borrar <head>; después se descarta para no duplicarlo en el texto.
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    lines = (" ".join(line.split()) for line in soup.get_text(separator="\n").splitlines())
    return title, "\n".join(line for line in lines if line)


class ReadPageTool(Tool):
    name = "leer_pagina"
    description = (
        "Descarga una página web pública y devuelve su texto principal (sin menús ni scripts). "
        "Usala para leer en detalle una URL que apareció en una búsqueda. Solo funciona con "
        "páginas públicas http o https."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL completa, empezando con http:// o https://.",
            }
        },
        "required": ["url"],
    }

    def __init__(
        self,
        client: httpx.Client | None = None,
        resolver: Resolver = default_resolver,
        max_chars: int = 8000,
    ) -> None:
        # Los encabezados HTTP solo admiten ASCII: un acento en el User-Agent rompe el cliente.
        # follow_redirects=False: las redirecciones las seguimos nosotros, validando cada salto.
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=False,
            headers={"User-Agent": "ProspectAgent/0.3 (public page reader)"},
        )
        self._resolver = resolver
        self.max_chars = max_chars

    def execute(self, url: str) -> str:
        current = url.strip()
        for _hop in range(MAX_REDIRECTS + 1):
            self._check_url(current)
            try:
                with self._client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ToolError("La página redirige a un destino vacío.")
                        current = urljoin(current, location)
                        continue
                    return self._read(response, current)
            except httpx.TimeoutException as exc:
                raise ToolError("La página tardó demasiado en responder.") from exc
            except httpx.HTTPError as exc:
                raise ToolError("No se pudo descargar la página.") from exc
        raise ToolError("La página redirige demasiadas veces.")

    # ------------------------------------------------------------------ seguridad
    def _check_url(self, url: str) -> None:
        """Se ejecuta ANTES de cada petición, incluidas las redirecciones."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ToolError("Solo se permiten URLs http o https.")
        host = parsed.hostname
        if not host:
            raise ToolError("La URL no tiene un dominio válido.")
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc:
            raise ToolError("La URL tiene un puerto inválido.") from exc
        if port not in ALLOWED_PORTS:
            raise ToolError("Solo se permiten los puertos 80 y 443.")
        for address in self._addresses(host):
            if not is_public_ip(address):
                raise ToolError(
                    "La URL apunta a una dirección interna o no pública: bloqueada por seguridad."
                )

    def _addresses(self, host: str) -> list[str]:
        try:
            ipaddress.ip_address(host)
            return [host]  # ya es una IP escrita de forma estándar
        except ValueError:
            # Un nombre, o una IP disfrazada (0x7f000001, 2130706433, 127.1). El sistema
            # operativo las entiende y el resolver las convierte en la IP real.
            return self._resolver(host)

    # ------------------------------------------------------------------ lectura
    def _read(self, response: httpx.Response, url: str) -> str:
        if response.status_code >= 400:
            raise ToolError(f"La página respondió con error HTTP {response.status_code}.")
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ToolError(f"Tipo de contenido no soportado: {content_type or 'desconocido'}.")

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_BYTES:  # dejamos de descargar: no leemos páginas gigantes enteras
                break
        raw = b"".join(chunks)[:MAX_BYTES]
        # response.encoding sale de la cabecera Content-Type; httpx ya descarta las inválidas.
        text = raw.decode(response.encoding or "utf-8", errors="replace")

        if content_type == "text/plain":
            title, body = "", text.strip()
        else:
            title, body = extract_text(text)
        if not body:
            raise ToolError("La página no tiene texto legible (quizás se genera con JavaScript).")
        header = f"URL: {url}\n" + (f"Título: {title}\n" if title else "")
        return truncate(f"{header}\n{body}", self.max_chars)