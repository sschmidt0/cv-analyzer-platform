from pydantic import BaseModel, Field


class CVModel(BaseModel):
    """Complete model representing the structured information extracted from a candidate's CV."""

    name: str = Field(..., description="The full name of the candidate extracted from the CV")
    email: str | None = Field(None, description="The email address of the candidate extracted from the CV, or null if the CV has none")
    phone: str | None = Field(None, description="The phone number of the candidate extracted from the CV, or null if the CV has none")
    years_of_experience: int = Field(..., description="The number of relevant years of work experience of the candidate extracted from the CV", ge=0)
    key_skills: list[str] = Field(..., description="A list of 5-7 most relevant skills for the job offer possessed by the candidate extracted from the CV")
    education: str = Field(..., description="Highest educational qualification of the candidate extracted from the CV and principal specialization")
    relevant_experience: str = Field(..., description="A concise summary of the candidate's relevant work experience for the job offer extracted from the CV")
    strengths: list[str] = Field(..., description="5-7 key strengths and attributes of the candidate relevant to the job offer extracted from the CV")
    improvement_areas: list[str] = Field(..., description="3-4 key areas for improvement of the candidate relevant to the job offer extracted from the CV")
    adjustment_percentage: int = Field(..., description="The percentage (0-100) indicating how well the candidate's profile aligns with the job offer extracted from the CV based on the evaluation of their skills, experience, qualifications and education", ge=0, le=100)


class RankedCandidate(BaseModel):
    """One entry of a company's shortlist: the source file and its evaluation."""

    filename: str
    evaluation: CVModel | None = None
    error: str | None = None


class RankingResponse(BaseModel):
    """Candidates sorted by fit, best first. Files that failed are listed last."""

    candidates: list[RankedCandidate]
