from pathlib import Path
from typing import Any, ClassVar
from app.tools.base import Tool, ToolError, truncate

ALLOWED_SUFFIXES = {".md", ".txt"}
MAX_FILE_BYTES = 200_000
MAX_LISTED = 50

class ReadFileTool(Tool):
    name = "leer_archivo"
    description = (
        "Lee una nota interna de la carpeta de notas de la empresa (archivos .md y .txt). "
        "Usala primero para consultar información propia sobre un cliente o prospecto, antes de "
        "buscar en internet. Con path='.' devuelve la lista de notas disponibles."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Ruta relativa a la carpeta de notas, por ejemplo 'acme.md'. "
                "Usá '.' para listar las notas disponibles.",
            }
        },
        "required": ["path"],
    }

    def __init__(self, base_dir: Path, max_chars: int = 8000) -> None:
        # resolve() una sola vez: convierte la ruta en absoluta y sin "..", ni enlaces simbólicos.
        self.base_dir = base_dir.resolve()
        self.max_chars = max_chars

    def execute(self, path: str) -> str:
        if not self.base_dir.is_dir():
            raise ToolError("La carpeta de notas no está configurada o no existe.")
        target = self._resolve_inside_base(path)
        if target.is_dir():
            return self._list(target)
        return self._read(target, path)

    def _resolve_inside_base(self, path: str) -> Path:
        try:
            target = (self.base_dir / path.strip()).resolve()
        except (ValueError, OSError) as exc:
            raise ToolError("La ruta no es válida.") from exc
        # La defensa contra path traversal: se resuelve la ruta REAL y se comprueba que siga
        # dentro de la carpeta de notas. Cubre "../", rutas absolutas y enlaces simbólicos.
        if not target.is_relative_to(self.base_dir):
            raise ToolError("La ruta queda fuera de la carpeta de notas: acceso denegado.")
        return target

    def _list(self, directory: Path) -> str:
        notes = sorted(
            p.relative_to(self.base_dir).as_posix()
            for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES
        )
        if not notes:
            return "La carpeta de notas no tiene archivos .md ni .txt."
        shown = notes[:MAX_LISTED]
        extra = f"\n(y {len(notes) - MAX_LISTED} más)" if len(notes) > MAX_LISTED else ""
        return "Notas disponibles:\n" + "\n".join(f"- {name}" for name in shown) + extra

    def _read(self, target: Path, requested: str) -> str:
        if target.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ToolError("Solo se pueden leer archivos .md y .txt.")
        if not target.is_file():
            raise ToolError(
                f"No existe la nota '{requested}'. Usá path='.' para ver las disponibles."
            )
        with target.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES)
        # errors="replace": un archivo con bytes raros no debe romper la herramienta.
        return truncate(raw.decode("utf-8", errors="replace"), self.max_chars)
    