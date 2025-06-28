from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from surgiform.api.models.transform import ConsentTransformIn
from surgiform.external.openai_client import get_chat_llm
from surgiform.core.transform.prompts import SYSTEM_PROMPT
from surgiform.core.transform.prompts import PROMPTS


def run_transform(payload: ConsentTransformIn) -> str:
    if payload.mode.value not in PROMPTS:
        raise ValueError(f"Unsupported mode: {payload.mode}")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", PROMPTS[payload.mode.value]),
        ]
    )
    chain = prompt_template | get_chat_llm() | StrOutputParser()

    # LangChain v0.2: invoke(dict)
    return chain.invoke({"consent_text": payload.consent_text})