# errors.py

class ExceedContextSizeError(RuntimeError):
    """
    Raised when llama.cpp reports exceed_context_size_error /
    'exceeds the available context size' or similar.
    """
    pass
