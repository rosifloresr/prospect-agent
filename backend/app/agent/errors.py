class AgentError(Exception):
    """Falla del agente. El mensaje es seguro de mostrar: queda guardado en el informe.

    input_tokens y output_tokens indican cuánto se consumió antes de fallar: el dinero ya se
    gastó aunque el informe no haya salido, y conviene registrarlo.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.input_tokens = 0
        self.output_tokens = 0

class AgentConfigError(AgentError):
    """Falta algo de la configuración para poder ejecutar el agente (por ejemplo, la clave)."""

class LLMError(AgentError):
    """Falló el proveedor del modelo (clave inválida, límite de uso, red caída)."""

class MaxIterationsExceeded(AgentError):
    """El agente usó todas sus vueltas sin llegar a redactar el informe."""