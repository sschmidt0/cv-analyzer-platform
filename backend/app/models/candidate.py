from typing import Optional

from pydantic import BaseModel, Field


class Keyword(BaseModel):
    word: str
    found: bool


class SectionScore(BaseModel):
    section: str = Field(description="Name of the CV section (e.g. 'Experiencia', 'Formación', 'Habilidades técnicas', 'Idiomas', 'Diseño y formato')")
    score: int = Field(ge=0, le=10, description="Score from 0 to 10")
    comment: str = Field(description="Brief one-sentence justification of the score")


class ToneIssue(BaseModel):
    original: str = Field(description="Verbatim excerpt from the CV with the tone/language issue")
    issue: str = Field(description="Short description of the issue (e.g. 'Verbo débil', 'Voz pasiva', 'Frase genérica')")
    suggestion: str = Field(description="Corrected version of the excerpt")


class ATSCheckItem(BaseModel):
    label: str = Field(description="Evaluated aspect (e.g. 'Formato compatible', 'Sin tablas complejas')")
    passed: bool = Field(description="True if the CV meets this criterion, False otherwise")
    detail: str = Field(description="Brief explanation of the result")


class ImprovedBullet(BaseModel):
    section: str
    original: str
    improved: str


class MatchScoreBreakdown(BaseModel):
    category: str = Field(description="Name of the evaluated category")
    score: int = Field(ge=0, le=100, description="RAW score from 0 to 100 for this category (not multiplied by its weight). Example: if Experience is worth 85 points, score=85, NOT score=25.")
    comment: str = Field(description="Brief one-sentence justification of the score")


class GapItem(BaseModel):
    requirement: str = Field(description="Specific requirement from the job offer (technology, experience, certification, soft skill, etc.)")
    status: str = Field(description="Status: 'cumple' (met), 'parcial' (partial) or 'no cumple' (not met)")
    detail: str = Field(description="Evidence from the CV that justifies the status, or an explanation of why it is not met")
    advice: str = Field(description="Specific, actionable advice to close the gap (rephrase a bullet, take a course, build a personal project, etc.). If met, advice to highlight it even more.")


class CompetitivenessLevel(BaseModel):
    level: str = Field(description="Competitiveness level: 'alto' (high), 'medio' (medium) or 'bajo' (low)")
    summary: str = Field(description="2-3 sentence justification addressed to the user in the informal second person singular (tú), explaining the level with the main factors for and against relative to the job offer")


class AnalysisResult(BaseModel):
    summary: str = Field(description="Executive summary of the candidate's professional profile")
    strengths: list[str] = Field(description="4-6 concrete strengths of the CV. Each must cite evidence from the CV (section, sentence or data point) and the best-practice criterion it meets.")
    weaknesses: list[str] = Field(description="4-6 areas for improvement in the CV. Each must state what is missing or could be improved, citing the affected section and the best-practice criterion it fails to meet.")
    matchScore: int = Field(ge=0, le=100, description="Compatibility score with the job offer (0-100). If there is no offer, assess the overall strength of the CV. Must be the weighted average of matchScoreBreakdown.")
    matchScoreBreakdown: list[MatchScoreBreakdown] = Field(description="Breakdown of matchScore into exactly 4 categories: 'Experiencia relevante' (weight 30%), 'Habilidades y tecnologías' (weight 30%), 'Formación y certificaciones' (weight 20%), 'Presentación y formato' (weight 20%). Each category has a score from 0-100 and a justifying comment. The total matchScore must be the weighted average of these 4 categories.")
    keywords: list[Keyword] = Field(description="5-7 relevant keywords from the job offer (or from the CV if there is no offer) indicating whether they appear in the CV")
    suggestions: list[str] = Field(description="List of 4-6 general recommendations to improve the CV regardless of the job offer: format, wording, missing sections, clarity, etc.")
    offerSuggestions: list[str] = Field(description="List of 3-5 specific recommendations to tailor the CV to the provided job offer: keywords to add, experience to highlight or rephrase, sections to adjust. If there is no job offer, return an empty list [].")
    improvedBullets: list[ImprovedBullet] = Field(description="CV bullets rewritten with more impact, grouped by section (e.g. 'Experiencia', 'Formación', 'Idiomas'). Each bullet includes the section it belongs to, the original CV text and the improved version. Rely on the best practices from the knowledge base. Do not invent experience that is not in the original CV.")
    interviewQuestions: list[str] = Field(description="4-5 likely interview questions based on the profile and the job offer")
    sectionScores: list[SectionScore] = Field(description="Score from 0 to 10 for each main CV section: Experiencia, Formación, Habilidades técnicas, Idiomas, Diseño y formato, and any other section present. Include a justifying comment.")
    toneIssues: list[ToneIssue] = Field(description="3-6 detected tone or language issues: weak verbs ('responsable de', 'participé en'), passive voice, generic phrases, filler words. Include the original excerpt, issue type and suggested improvement.")
    atsChecklist: list[ATSCheckItem] = Field(description="5-7 ATS compatibility checks: file format, use of tables/columns/images, length, standard sections, use of headings, readable typography, etc. Indicate whether the CV passes each criterion.")
    gapAnalysis: list[GapItem] = Field(description="5-8 key requirements from the job offer classified as 'cumple', 'parcial' or 'no cumple', with evidence from the CV and advice to close each gap. If there is no offer, return an empty list [].")
    competitiveness: Optional[CompetitivenessLevel] = Field(default=None, description="Candidate's competitiveness level for this job offer ('alto', 'medio' or 'bajo') with justification. Only if there is a job offer; if there is no offer, return null.")


class AnalyzeResponse(BaseModel):
    cv_text: str
    result: AnalysisResult


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    cv_text: str
    job_text: str = ""
    analysis: Optional[AnalysisResult] = None
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    content: str
