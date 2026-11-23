import pytest
from app.tools.base import ToolError
from app.tools.read_file import MAX_FILE_BYTES, ReadFileTool

@pytest.fixture
def notes(tmp_path):
    """Carpeta de notas con un archivo, y un secreto FUERA de ella."""
    base = tmp_path / "notes"
    base.mkdir()
    (base / "acme.md").write_text("# Acme\nContacto: Laura", encoding="utf-8")
    (base / "clientes").mkdir()
    (base / "clientes" / "globex.txt").write_text("Globex: cliente desde 2024", encoding="utf-8")
    (tmp_path / "secreto.txt").write_text("CLAVE-SUPER-SECRETA", encoding="utf-8")
    return base

def test_lee_una_nota(notes):
    assert "Contacto: Laura" in ReadFileTool(notes).execute("acme.md")

def test_lee_una_nota_dentro_de_una_subcarpeta(notes):
    assert "Globex" in ReadFileTool(notes).execute("clientes/globex.txt")

def test_lista_las_notas_con_punto(notes):
    result = ReadFileTool(notes).execute(".")
    assert "- acme.md" in result
    assert "- clientes/globex.txt" in result

def test_lista_vacia_cuando_no_hay_notas(tmp_path):
    empty = tmp_path / "vacia"
    empty.mkdir()
    assert "no tiene archivos" in ReadFileTool(empty).execute(".")

def test_trunca_notas_largas(notes):
    (notes / "larga.md").write_text("x" * 5000, encoding="utf-8")
    result = ReadFileTool(notes, max_chars=100).execute("larga.md")
    assert "truncado" in result
    assert len(result) < 200

def test_no_lee_mas_de_los_bytes_maximos(notes):
    (notes / "enorme.txt").write_text("y" * (MAX_FILE_BYTES * 2), encoding="utf-8")
    result = ReadFileTool(notes, max_chars=10**9).execute("enorme.txt")
    assert len(result) <= MAX_FILE_BYTES

def test_un_archivo_con_bytes_invalidos_no_rompe_la_herramienta(notes):
    (notes / "raro.txt").write_bytes(b"hola \xff\xfe mundo")
    assert "hola" in ReadFileTool(notes).execute("raro.txt")

# ------------------------------------------------------------------ ataques
@pytest.mark.parametrize(
    "attack",
    [
        "../secreto.txt",
        "clientes/../../secreto.txt",
        "../../../../../../etc/passwd",
        "clientes/../../../secreto.txt",
    ],
)
def test_bloquea_path_traversal_con_puntos_puntos(notes, attack):
    with pytest.raises(ToolError, match="fuera de la carpeta"):
        ReadFileTool(notes).execute(attack)

def test_bloquea_rutas_absolutas(notes, tmp_path):
    with pytest.raises(ToolError, match="fuera de la carpeta"):
        ReadFileTool(notes).execute(str(tmp_path / "secreto.txt"))
    with pytest.raises(ToolError, match="fuera de la carpeta"):
        ReadFileTool(notes).execute("/etc/passwd")

def test_bloquea_enlaces_simbolicos_que_escapan_de_la_carpeta(notes, tmp_path):
    (notes / "atajo.txt").symlink_to(tmp_path / "secreto.txt")
    with pytest.raises(ToolError, match="fuera de la carpeta"):
        ReadFileTool(notes).execute("atajo.txt")

def test_un_enlace_simbolico_hacia_adentro_es_valido(notes):
    (notes / "alias.md").symlink_to(notes / "acme.md")
    assert "Acme" in ReadFileTool(notes).execute("alias.md")

def test_bloquea_el_byte_nulo(notes):
    with pytest.raises(ToolError, match="no es válida"):
        ReadFileTool(notes).execute("acme.md\x00.txt")

@pytest.mark.parametrize("name", [".env", "script.py", "clave.pem", "sin_extension"])
def test_solo_se_leen_md_y_txt(notes, name):
    (notes / name).write_text("contenido", encoding="utf-8")
    with pytest.raises(ToolError, match="Solo se pueden leer"):
        ReadFileTool(notes).execute(name)

def test_nota_inexistente_sugiere_listar(notes):
    with pytest.raises(ToolError, match="No existe la nota 'nada.md'"):
        ReadFileTool(notes).execute("nada.md")

def test_carpeta_de_notas_inexistente(tmp_path):
    with pytest.raises(ToolError, match="no está configurada o no existe"):
        ReadFileTool(tmp_path / "no-existe").execute(".")