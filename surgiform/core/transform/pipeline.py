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

    consent_dict = consents.model_dump()
    transformed_dict = {k: chain.invoke({"consent_text": text}) for k, text in consent_dict.items()}
    return ConsentBase(**transformed_dict)
