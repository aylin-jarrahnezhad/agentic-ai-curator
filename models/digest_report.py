from pydantic import BaseModel


class DigestReport(BaseModel):
    title: str
    run_date: str
    time_window: str
    executive_summary: str
    top_developments: str
    research_highlights: str
    company_platform_moves: str
    ecosystem_themes: str
    methodology_note: str
