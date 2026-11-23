from types import SimpleNamespace
from typing import Any
import anthropic
import pytest
from app.agent.errors import LLMError
from app.agent.llm import AnthropicClient, ToolCall

# El SDK construye sus excepciones con la librería HTTP que use internamente (httpx o httpx2,
# según la versión). Los tests usan la misma para no depender de una en particular.
try:
    import httpx2 as http
except ImportError:  # pragma: no cover
    import httpx as http

API_KEY = "sk-ant-clave-secreta-de-prueba"
REQUEST = http.Request("POST", "https://api.anthropic.com/v1/messages")

def sdk_response(content: list[Any], stop_reason: str | None = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
    )

def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)

def tool_block(block_id: str, name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=args)

class FakeSDK:
    """Imita lo único que usamos del SDK: client.messages.create(...)."""

    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.messages = self
        self.calls: list[dict[str, Any]] = []
        self._response = response
        self._error = error

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response

def client_with(sdk: FakeSDK, **kwargs: Any) -> AnthropicClient:
    return AnthropicClient(api_key=API_KEY, model="modelo-x", sdk_client=sdk, **kwargs)

def status_error(cls: type[anthropic.APIStatusError], status: int, message: str = "x"):
    response = http.Response(status, request=REQUEST, json={"error": {"message": message}})
    return cls(message, response=response, body=None)

CALL = {"system": "sos un analista", "messages": [{"role": "user", "content": "hola"}], "tools": []}

# ------------------------------------------------------------------ la respuesta
def test_convierte_la_respuesta_del_sdk_al_formato_propio():
    blocks = [
        text_block("Voy a "),
        tool_block("toolu_1", "eco", {"text": "x"}),
        text_block("buscar"),
    ]
    response = client_with(FakeSDK(sdk_response(blocks, "tool_use"))).create_message(**CALL)

    assert response.text == "Voy a buscar"
    assert response.tool_calls == [ToolCall("toolu_1", "eco", {"text": "x"})]
    assert response.stop_reason == "tool_use"
    assert (response.input_tokens, response.output_tokens) == (11, 7)
    assert response.raw_content == blocks  # los bloques originales, listos para reenviar

def test_una_respuesta_sin_stop_reason_queda_como_texto_vacio():
    response = client_with(FakeSDK(sdk_response([text_block("x")], stop_reason=None)))
    assert response.create_message(**CALL).stop_reason == ""

# ------------------------------------------------------------------ el pedido
def test_envia_al_sdk_modelo_limite_prompt_y_mensajes():
    sdk = FakeSDK(sdk_response([text_block("ok")]))
    client_with(sdk, max_tokens=999).create_message(**CALL)
    sent = sdk.calls[0]
    assert sent["model"] == "modelo-x"
    assert sent["max_tokens"] == 999
    assert sent["system"] == "sos un analista"
    assert sent["messages"] == CALL["messages"]

def test_envia_las_herramientas_solo_si_hay():
    schema = {"name": "eco", "description": "d", "input_schema": {"type": "object"}}
    with_tools, without_tools = FakeSDK(sdk_response([])), FakeSDK(sdk_response([]))
    client_with(with_tools).create_message(**{**CALL, "tools": [schema]})
    client_with(without_tools).create_message(**CALL)
    assert with_tools.calls[0]["tools"] == [schema]
    assert "tools" not in without_tools.calls[0]  # la API rechaza una lista vacía

# ------------------------------------------------------------------ errores
@pytest.mark.parametrize(
    ("error", "message"),
    [
        (status_error(anthropic.AuthenticationError, 401), "clave de la API de Anthropic"),
        (status_error(anthropic.PermissionDeniedError, 403), "clave de la API de Anthropic"),
        (status_error(anthropic.RateLimitError, 429), "límite de uso"),
        (status_error(anthropic.InternalServerError, 500), "HTTP 500"),
        (anthropic.APITimeoutError(request=REQUEST), "tardó demasiado"),
        (anthropic.APIConnectionError(request=REQUEST), "No se pudo conectar"),
    ],
)
def test_cada_error_del_sdk_se_traduce_a_un_mensaje_claro(error, message):
    with pytest.raises(LLMError, match=message):
        client_with(FakeSDK(error=error)).create_message(**CALL)

def test_un_pedido_rechazado_incluye_el_motivo_de_la_api():
    error = status_error(anthropic.BadRequestError, 400, "Your credit balance is too low")
    with pytest.raises(LLMError, match="credit balance is too low"):
        client_with(FakeSDK(error=error)).create_message(**CALL)

def test_el_mensaje_de_un_pedido_rechazado_se_recorta():
    error = status_error(anthropic.BadRequestError, 400, "x" * 5000)
    with pytest.raises(LLMError) as raised:
        client_with(FakeSDK(error=error)).create_message(**CALL)
    assert len(str(raised.value)) < 500

@pytest.mark.parametrize(
    "error",
    [
        status_error(anthropic.AuthenticationError, 401, f"invalid x-api-key {API_KEY}"),
        status_error(anthropic.RateLimitError, 429),
        anthropic.APIConnectionError(request=REQUEST),
    ],
)
def test_los_errores_nunca_incluyen_la_clave(error):
    with pytest.raises(LLMError) as raised:
        client_with(FakeSDK(error=error)).create_message(**CALL)
    assert API_KEY not in str(raised.value)

def test_se_conserva_la_causa_original_del_error():
    original = status_error(anthropic.RateLimitError, 429)
    with pytest.raises(LLMError) as raised:
        client_with(FakeSDK(error=original)).create_message(**CALL)
    assert raised.value.__cause__ is original