"""
===============================================================================
[LLM Factory Module] Central LLM Provider Factory (Vertex AI / Gemini / OpenAI / Anthropic)
-------------------------------------------------------------------------------
Reference Sources & Grounding Traceability:
- AAWS LLM Utility Source: c:/Users/hyoun/Desktop/github/AAWS/app/utils/llm.py
- Environment Config: c:/Users/hyoun/Desktop/github/AAWS/.env (VERTEX_PROJECT & VERTEX_LOCATION)
===============================================================================
"""

import os
from typing import Optional
from langchain.chat_models import init_chat_model


def get_llm(
    model_name: str = "gemini-2.5-pro",
    model_provider: Optional[str] = None,
    temperature: float = 0.0,
    **kwargs
):
    """
    Central LLM factory supporting OpenAI, Anthropic, Google GenAI, Vertex AI (Gemini).
    
    Priority Resolution:
    1. 'provider:model_name' prefix (e.g. 'google_vertexai:gemini-2.5-pro')
    2. Explicit model_provider argument
    3. MODEL_PROVIDER or LLM_PROVIDER in .env
    4. VERTEX_PROJECT present in .env -> 'google_vertexai'
    5. Fallback -> 'google_genai' or 'openai'
    """
    parsed_provider = None
    clean_model_name = model_name

    if ":" in model_name:
        parts = model_name.split(":", 1)
        parsed_provider = parts[0]
        clean_model_name = parts[1]

    final_provider = None

    # 1. 모델명 키워드 기반 지능형 공급자 자동 식별 (최우선 순위)
    if not model_provider and not parsed_provider:
        if "gpt" in clean_model_name.lower():
            final_provider = "openai"
        elif "claude" in clean_model_name.lower():
            final_provider = "anthropic"

    # 2. 명시적 인자 및 환경변수 디폴트 로드
    if not final_provider:
        final_provider = (
            model_provider 
            or parsed_provider 
            or os.getenv("MODEL_PROVIDER") 
            or os.getenv("LLM_PROVIDER")
        )
    
    # 3. 로컬 GCP 환경 감지 폴백
    if not final_provider:
        project = os.getenv("VERTEX_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
        final_provider = "google_vertexai" if project else "google_genai"




    # Vertex AI GCP Options
    if final_provider == "google_vertexai":
        project = os.getenv("VERTEX_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
        location = os.getenv("VERTEX_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION") or "global"
        
        if project and "project" not in kwargs:
            kwargs["project"] = project
        if location and "location" not in kwargs:
            kwargs["location"] = location

    return init_chat_model(
        model=clean_model_name,
        model_provider=final_provider,
        temperature=temperature,
        **kwargs
    )
