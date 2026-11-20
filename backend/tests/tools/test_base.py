from typing import Any, ClassVar
import pytest
from app.tools.base import Tool, ToolError, truncate

class EchoTool(Tool):
    name = "eco"
    description = "Devuelve el texto recibido."
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}, "times": {"type": "integer"}},
        "required": ["text"],
    }

    def execute(self, text: str, times: int = 1) -> str:
        return text * times

def test_no_se_puede_instanciar_la_clase_abstracta():
    with pytest.raises(TypeError):
        Tool()  # type: ignore[abstract]

def test_to_api_schema_tiene_la_forma_que_espera_claude():
    schema = EchoTool().to_api_schema()
    assert set(schema) == {"name", "description", "input_schema"}
    assert schema["name"] == "eco"
    assert schema["input_schema"]["required"] == ["text"]

def test_validate_input_acepta_argumentos_correctos():
    EchoTool().validate_input({"text": "hola", "times": 2})

def test_validate_input_rechaza_argumento_obligatorio_faltante():
    with pytest.raises(ToolError, match="Falta el argumento obligatorio 'text'"):
        EchoTool().validate_input({})

def test_validate_input_rechaza_argumento_desconocido():
    with pytest.raises(ToolError, match="Argumento desconocido 'otro'"):
        EchoTool().validate_input({"text": "hola", "otro": 1})

def test_validate_input_rechaza_tipo_incorrecto():
    with pytest.raises(ToolError, match="debe ser un texto"):
        EchoTool().validate_input({"text": 123})
    with pytest.raises(ToolError, match="debe ser un número entero"):
        EchoTool().validate_input({"text": "hola", "times": "dos"})

def test_un_booleano_no_cuenta_como_entero():
    with pytest.raises(ToolError, match="debe ser un número entero"):
        EchoTool().validate_input({"text": "hola", "times": True})

def test_truncate_no_toca_textos_cortos():
    assert truncate("hola", 10) == "hola"

def test_truncate_recorta_y_avisa():
    result = truncate("a" * 100, 10)
    assert result.startswith("a" * 10)
    assert "truncado" in result
    assert len(result) < 100