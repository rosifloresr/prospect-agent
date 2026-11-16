class ReportNotFoundError(Exception):
    """El informe pedido no existe. La capa HTTP la traduce a un 404."""