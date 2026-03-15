# =============================================================================
# test_pptx_engine.py — Tests for the Millennium BCP branded PPTX engine
# =============================================================================

import io
import pytest
from pptx_engine import (
    generate_presentation,
    generate_presentation_from_outline,
    BRAND_ACCENT_HEX,
    SLIDE_WIDTH_EMU,
    SLIDE_HEIGHT_EMU,
)


class TestGeneratePresentation:
    """Tests for the main generate_presentation function."""

    def test_minimal_presentation(self):
        """Single content slide produces valid PPTX."""
        slides = [{"type": "content", "title": "Test", "bullets": ["A", "B"]}]
        buf = generate_presentation("Test Title", slides)
        assert isinstance(buf, io.BytesIO)
        content = buf.getvalue()
        assert len(content) > 1000  # not trivially empty
        # PPTX is a ZIP — check magic bytes
        assert content[:2] == b"PK"

    def test_slide_dimensions_widescreen(self):
        """Presentation uses 13.333x7.5 inch widescreen layout."""
        from pptx import Presentation as PptxRead
        slides = [{"type": "content", "title": "X", "bullets": ["Y"]}]
        buf = generate_presentation("T", slides)
        prs = PptxRead(buf)
        assert prs.slide_width == SLIDE_WIDTH_EMU
        assert prs.slide_height == SLIDE_HEIGHT_EMU

    def test_auto_title_and_closing(self):
        """Auto-adds title and closing slides."""
        from pptx import Presentation as PptxRead
        slides = [{"type": "content", "title": "Body", "bullets": ["X"]}]
        buf = generate_presentation("Title", slides)
        prs = PptxRead(buf)
        # 1 title (auto) + 1 content + 1 closing (auto) = 3
        assert len(prs.slides) == 3

    def test_no_duplicate_title_slide(self):
        """If slides already start with title, don't add another."""
        from pptx import Presentation as PptxRead
        slides = [
            {"type": "title", "title": "My Title", "subtitle": "Sub"},
            {"type": "content", "title": "Body", "bullets": ["X"]},
        ]
        buf = generate_presentation("My Title", slides)
        prs = PptxRead(buf)
        # 1 title (from specs) + 1 content + 1 closing (auto) = 3
        assert len(prs.slides) == 3

    def test_no_duplicate_closing(self):
        """If slides already end with closing, don't add another."""
        from pptx import Presentation as PptxRead
        slides = [
            {"type": "content", "title": "Body", "bullets": ["X"]},
            {"type": "closing", "text": "Obrigado"},
        ]
        buf = generate_presentation("T", slides)
        prs = PptxRead(buf)
        # 1 title (auto) + 1 content + 1 closing (from specs) = 3
        assert len(prs.slides) == 3

    def test_all_slide_types(self):
        """All slide types generate without error."""
        slides = [
            {"type": "title", "title": "Capa", "subtitle": "Subtítulo"},
            {"type": "section", "title": "Secção 1"},
            {"type": "content", "title": "Conteúdo", "bullets": ["A", "B", "- Sub-bullet"]},
            {"type": "two_column", "title": "Duas Colunas", "left": ["L1", "L2"], "right": ["R1", "R2"]},
            {"type": "kpi", "title": "KPIs", "kpis": [
                {"value": "125", "label": "Total"},
                {"value": "98%", "label": "Cobertura"},
            ]},
            {"type": "table", "title": "Tabela", "headers": ["Col1", "Col2"], "rows": [["A", "B"], ["C", "D"]]},
            {"type": "agenda", "items": ["Item 1", "Item 2", "Item 3"]},
            {"type": "closing", "text": "Obrigado"},
        ]
        buf = generate_presentation("Full Test", slides, include_title_slide=False, include_closing_slide=False)
        from pptx import Presentation as PptxRead
        prs = PptxRead(buf)
        assert len(prs.slides) == 8

    def test_section_auto_numbering(self):
        """Section dividers auto-number correctly."""
        slides = [
            {"type": "section", "title": "Intro"},
            {"type": "content", "title": "Content", "bullets": ["X"]},
            {"type": "section", "title": "Results"},
            {"type": "content", "title": "More Content", "bullets": ["Y"]},
        ]
        buf = generate_presentation("T", slides)
        content = buf.getvalue()
        assert len(content) > 1000

    def test_empty_slides_returns_title_and_closing_only(self):
        """Empty slides list still creates title + closing."""
        from pptx import Presentation as PptxRead
        buf = generate_presentation("Empty", [])
        prs = PptxRead(buf)
        assert len(prs.slides) == 2  # title + closing

    def test_kpi_max_four(self):
        """KPI slide handles more than 4 kpis (only shows first 4)."""
        slides = [{"type": "kpi", "title": "Many KPIs", "kpis": [
            {"value": str(i), "label": f"KPI {i}"} for i in range(8)
        ]}]
        buf = generate_presentation("T", slides)
        assert len(buf.getvalue()) > 1000

    def test_table_row_cap(self):
        """Table slide caps at 15 rows."""
        slides = [{"type": "table", "title": "Big Table", "headers": ["A", "B"],
                   "rows": [[str(i), str(i*2)] for i in range(30)]}]
        buf = generate_presentation("T", slides)
        assert len(buf.getvalue()) > 1000

    def test_badge_text_custom(self):
        """Custom badge text is accepted."""
        slides = [{"type": "content", "title": "Test", "bullets": ["X"]}]
        buf = generate_presentation("T", slides, badge_text="CUSTOM TEAM")
        assert len(buf.getvalue()) > 1000

    def test_invalid_slide_type_fallback(self):
        """Unknown slide type falls back to content slide."""
        slides = [{"type": "unknown_type", "title": "Fallback", "bullets": ["X"]}]
        buf = generate_presentation("T", slides)
        assert len(buf.getvalue()) > 1000


class TestGenerateFromOutline:
    """Tests for the outline parser."""

    def test_simple_outline(self):
        outline = """# Secção 1
## Slide A
- Bullet 1
- Bullet 2
# Secção 2
## Slide B
- Bullet 3
"""
        buf = generate_presentation_from_outline("Outline Test", outline)
        from pptx import Presentation as PptxRead
        prs = PptxRead(buf)
        # title(auto) + section1 + slideA + section2 + slideB + closing(auto) = 6
        assert len(prs.slides) == 6

    def test_table_in_outline(self):
        outline = """## Dados
| Nome | Valor |
| --- | --- |
| Alpha | 100 |
| Beta | 200 |
"""
        buf = generate_presentation_from_outline("Table Test", outline)
        assert len(buf.getvalue()) > 1000

    def test_empty_outline(self):
        buf = generate_presentation_from_outline("Empty", "")
        from pptx import Presentation as PptxRead
        prs = PptxRead(buf)
        assert len(prs.slides) == 2  # title + closing only


class TestToolIntegration:
    """Test tool_generate_presentation integration."""

    @pytest.mark.asyncio
    async def test_tool_generates_pptx(self):
        from tools_export import tool_generate_presentation
        result = await tool_generate_presentation(
            title="Integration Test",
            slides=[
                {"type": "content", "title": "Test", "bullets": ["A", "B"]},
            ],
        )
        assert result.get("presentation_generated") is True
        assert result.get("format") == "pptx"
        assert "_file_download" in result
        assert result["_file_download"]["format"] == "pptx"
        assert result["_file_download"]["size_bytes"] > 1000

    @pytest.mark.asyncio
    async def test_tool_rejects_empty_slides(self):
        from tools_export import tool_generate_presentation
        result = await tool_generate_presentation(title="Bad", slides=[])
        assert "error" in result

    @pytest.mark.asyncio
    async def test_tool_rejects_no_slides(self):
        from tools_export import tool_generate_presentation
        result = await tool_generate_presentation(title="Bad", slides=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_tool_rejects_too_many_slides(self):
        from tools_export import tool_generate_presentation
        result = await tool_generate_presentation(
            title="Too Many",
            slides=[{"type": "content", "title": f"S{i}", "bullets": ["X"]} for i in range(51)],
        )
        assert "error" in result
