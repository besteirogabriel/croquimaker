"""Disabled legacy AI interpreter.

The original Anthropic/Claude implementation was moved to
ai_interpreter_original_disabled.py.txt for audit only. This module is kept so
legacy imports fail closed without importing external AI SDKs.
"""


def interpretar_pdf(*args, **kwargs):
    raise RuntimeError(
        "External AI interpretation is disabled. Use croqui_engine.core.pipeline.process_pdf."
    )


def interpretar_texto(*args, **kwargs):
    raise RuntimeError(
        "External AI interpretation is disabled. Use croqui_engine.core.pipeline.process_pdf."
    )
