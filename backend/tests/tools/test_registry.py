import logging
from typing import Any, ClassVar
import pytest
from app.tools.base import Tool, ToolError
from app.tools.registry import ToolRegistry, ToolResult

class FakeTool(Tool):
    name = "falsa"
    description = "Herramienta de prueba."
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"mode": {"type": "string"}},
        "required": ["mode"],
    }

    def execute(self, mode: str) -> str:
        if mode == "ok":
            return "resultado correcto"
        if mode == "esperado":
            raise ToolError("fallo esperado y claro")
        raise RuntimeError("secreto-interno: /home/usuario/.env")

@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(FakeTool())
    return reg

def test_register_y_get(registry):
    assert registry.get("falsa") is not None
    assert registry.get("inexistente") is None
    assert registry.names() == ["falsa"]

def test_no_se_puede_registrar_dos_veces_el_mismo_nombre(registry):
    with pytest.raises(ValueError, match="Ya existe"):
        registry.register(FakeTool())

def test_schemas_lista_la_descripcion_de_cada_herramienta(registry):
    schemas = registry.schemas()
    assert [s["name"] for s in schemas] == ["falsa"]
    assert "input_schema" in schemas[0]

def test_execute_devuelve_el_resultado_sin_marcar_error(registry):
    result = registry.execute("falsa", {"mode": "ok"})
    assert result == ToolResult("resultado correcto", is_error=False)

def test_execute_herramienta_inexistente_lista_las_disponibles(registry):
    result = registry.execute("otra", {})
    assert result.is_error
    assert "no existe" in result.content
    assert "falsa" in result.content

def test_execute_convierte_toolerror_en_texto_de_error(registry):
    result = registry.execute("falsa", {"mode": "esperado"})
    assert result.is_error
    assert result.content == "Error: fallo esperado y claro"

def test_execute_argumentos_invalidos_no_llegan_a_la_herramienta(registry):
    result = registry.execute("falsa", {})
    assert result.is_error
    assert "obligatorio" in result.content


def test_execute_argumentos_que_no_son_un_objeto(registry):
    result = registry.execute("falsa", "no soy un dict")  # type: ignore[arg-type]
    assert result.is_error

def test_un_bug_inesperado_no_filtra_detalles_internos_al_modelo(registry, caplog):
    with caplog.at_level(logging.ERROR):
        result = registry.execute("falsa", {"mode": "bug"})
    assert result.is_error
    assert "secreto-interno" not in result.content  # el modelo no ve el detalle
    assert "secreto-interno" in caplog.text  # pero queda en el log para depurar