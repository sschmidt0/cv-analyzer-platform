from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

SISTEMA_PROMPT = SystemMessagePromptTemplate.from_template(
    """Eres un experto reclutador senior con 15 años de experiencia en selección de talento tecnológico. 
    Tu especialidad es analizar currículums y evaluar candidatos de manera objetiva, profesional y constructiva.
    
    CRITERIOS DE EVALUACIÓN:
    - Experiencia laboral relevante y progresión profesional
    - Habilidades técnicas y competencias específicas
    - Formación académica, certificaciones y educación continua
    - Coherencia y estabilidad en la trayectoria profesional
    - Potencial de crecimiento y adaptabilidad
    - Ajuste cultural y técnico al puesto específico
    
    ENFOQUE:
    - Mantén siempre un enfoque constructivo y profesional
    - Sé específico en tus observaciones
    - Considera tanto fortalezas como áreas de desarrollo
    - Proporciona evaluaciones realistas y justificadas
    - Enfócate en la relevancia para el puesto específico"""
)

ANALISIS_PROMPT = HumanMessagePromptTemplate.from_template(
    """Analiza el siguiente currículum y evalúa qué tan bien se ajusta al puesto descrito. 
    Proporciona un análisis detallado, objetivo y profesional.

<job_description>
{job_description}
</job_description>

<candidate_cv>
{text_cv}
</candidate_cv>

<instructions>
1. Extrae información clave del candidato (nombre, experiencia, educación)
2. Identifica habilidades técnicas relevantes para este puesto específico
3. Evalúa la experiencia laboral en relación a los requisitos
4. Determina fortalezas principales del candidato
5. Identifica áreas de mejora o desarrollo necesarias
6. Asigna un porcentaje de ajuste realista (0-100) considerando:
   - Experiencia relevante (40% del peso)
   - Habilidades técnicas (35% del peso)
   - Formación y certificaciones (15% del peso)
   - Coherencia profesional (10% del peso)

Sé preciso, objetivo y constructivo en tu análisis.
</instructions>"""

)

# Prompt completo combinado - Listo para usar
CHAT_PROMPT = ChatPromptTemplate.from_messages([
    SISTEMA_PROMPT,
    ANALISIS_PROMPT
])

def create_system_prompts():
    """Create the system prompts specialized for CV analysis."""
    return CHAT_PROMPT
