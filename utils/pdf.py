from pathlib import Path
import tempfile
import json


def generate_estimate_pdf(estimate: dict) -> Path:
    """
    Генерирует PDF-файл по данным сметы.
    Сейчас возвращает NotImplementedError — заглушка для следующей итерации.
    TODO: имплементировать через reportlab или weasyprint.
    """
    raise NotImplementedError("PDF export is not yet implemented.")


def export_project_pdf(project: dict) -> Path:
    """Legacy stub."""
    raise NotImplementedError("PDF export is a placeholder for the next iteration.")
