"""PaddleOCR Backend."""

import structlog

from app.config.settings import get_settings
from app.integrations.ocr.backends.base import OCRBackend, OCRResult

log = structlog.get_logger()


class PaddleOCRBackend(OCRBackend):
    name = "paddle"

    def __init__(self):
        self.settings = get_settings()
        self.ocr_engine = None
        self.structure_engine = None
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        log.info("loading_paddle_ocr")

        try:
            from paddleocr import PaddleOCR, PPStructureV3
        except ImportError:
            raise RuntimeError("paddleocr not installed. Run: pip install paddleocr")

        # Standard OCR
        self.ocr_engine = PaddleOCR(
            use_angle_cls=True,
            lang=self.settings.ocr.paddle_lang,
            use_gpu=self.settings.ocr.paddle_use_gpu,
            show_log=False,
        )

        # Structure recognition (tables, layouts) - optional
        try:
            self.structure_engine = PPStructureV3(
                use_gpu=self.settings.ocr.paddle_use_gpu,
                show_log=False,
            )
        except Exception as e:
            log.warning("paddle_structure_unavailable", error=str(e))

        self._loaded = True
        log.info("paddle_ocr_loaded", gpu=self.settings.ocr.paddle_use_gpu)

    def unload(self) -> None:
        self.ocr_engine = None
        self.structure_engine = None
        self._loaded = False
        log.info("paddle_ocr_unloaded")

    def is_loaded(self) -> bool:
        return self._loaded

    def get_info(self) -> dict:
        return {
            "backend": self.name,
            "lang": self.settings.ocr.paddle_lang,
            "gpu": self.settings.ocr.paddle_use_gpu,
            "loaded": self._loaded,
            "structure_available": self.structure_engine is not None,
        }

    def process(self, image_paths: list[str], paddle_mode: str = "ocr", **kwargs) -> OCRResult:
        """Blocking inference - run in thread pool."""
        if not self._loaded:
            raise RuntimeError("PaddleOCR not loaded")

        all_markdown = []
        all_json = []

        for img_path in image_paths:
            if paddle_mode == "structure" and self.structure_engine:
                result = self.structure_engine(img_path)
                markdown, json_data = self._structure_to_markdown(result)
            else:
                result = self.ocr_engine.ocr(img_path, cls=True)
                markdown, json_data = self._ocr_to_markdown(result)

            all_markdown.append(markdown)
            if json_data:
                all_json.append(json_data)

        combined_markdown = "\n\n---\n\n".join(all_markdown)

        return OCRResult(
            markdown=combined_markdown,
            json_data=all_json if all_json else None,
            pages_processed=len(image_paths),
            backend=self.name,
            model_info=f"PaddleOCR ({paddle_mode})",
        )

    def _ocr_to_markdown(self, result) -> tuple[str, dict]:
        """Convert PaddleOCR result to markdown."""
        if not result or not result[0]:
            return "", {}

        lines = []
        json_data = {"pages": []}

        for page_idx, page in enumerate(result):
            if not page:
                continue

            page_data = {"page": page_idx + 1, "blocks": []}

            # Sort by vertical position (top to bottom)
            sorted_boxes = sorted(page, key=lambda x: x[0][0][1])

            for box in sorted_boxes:
                coords, (text, conf) = box
                if conf < 0.5:
                    continue

                lines.append(text)
                page_data["blocks"].append(
                    {
                        "bbox": coords,
                        "text": text,
                        "confidence": float(conf),
                    }
                )

            json_data["pages"].append(page_data)

        return "\n".join(lines), json_data

    def _structure_to_markdown(self, result) -> tuple[str, dict]:
        """Convert PPStructureV3 result to markdown with tables."""
        markdown_parts = []
        json_data = {"pages": []}

        for page_idx, page_result in enumerate(result):
            page_md = []
            page_data = {"page": page_idx + 1, "elements": []}

            for region in page_result:
                region_type = region.get("type", "")

                if region_type == "table":
                    table_md = self._table_to_markdown(region)
                    page_md.append(table_md)
                    page_data["elements"].append(
                        {
                            "type": "table",
                            "bbox": region.get("bbox"),
                            "markdown": table_md,
                        }
                    )
                elif region_type == "text":
                    text = region.get("text", "")
                    page_md.append(text)
                    page_data["elements"].append(
                        {
                            "type": "text",
                            "bbox": region.get("bbox"),
                            "text": text,
                        }
                    )

            markdown_parts.append("\n\n".join(page_md))
            json_data["pages"].append(page_data)

        return "\n\n---\n\n".join(markdown_parts), json_data

    def _table_to_markdown(self, table_region) -> str:
        """Convert table region to markdown table."""
        cells = table_region.get("cells", [])
        if not cells:
            return ""

        # Group by row
        rows = {}
        for cell in cells:
            row_idx = cell.get("row", 0)
            col_idx = cell.get("col", 0)
            text = cell.get("text", "").replace("|", "\\|")
            rows.setdefault(row_idx, {})[col_idx] = text

        if not rows:
            return ""

        max_cols = max(max(row.keys()) for row in rows.values()) + 1
        md_rows = []

        for row_idx in sorted(rows.keys()):
            row = rows[row_idx]
            cells = [row.get(c, "") for c in range(max_cols)]
            md_rows.append("| " + " | ".join(cells) + " |")

        # Add header separator
        if len(md_rows) > 1:
            md_rows.insert(1, "| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(md_rows)
