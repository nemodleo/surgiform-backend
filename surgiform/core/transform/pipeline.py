from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from surgiform.external.openai_client import get_chat_llm
from surgiform.core.transform.prompts import SYSTEM_PROMPT
from surgiform.core.transform.prompts import PROMPTS
from surgiform.api.models.base import ConsentBase
from surgiform.api.models.transform import TransformMode


def run_transform(consents: ConsentBase, mode: TransformMode) -> ConsentBase:
    if mode.value not in PROMPTS:
        raise ValueError(f"Unsupported mode: {mode}")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", PROMPTS[mode.value]),
        ]
    )
    chain = prompt_template | get_chat_llm() | StrOutputParser()

    # LangChain v0.2: invoke(dict)
    return ConsentBase(chain.invoke({k: text for k, text in consents}))
    # return chain.invoke({"consent_text": payload.consent_text})