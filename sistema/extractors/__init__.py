from . import base
from .projeto_pdf import PROJECT_PDF_EXTRACTOR

base.register(PROJECT_PDF_EXTRACTOR)

__all__ = ["base"]
