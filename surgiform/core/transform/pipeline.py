from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from surgiform.external.openai_client import get_chat_llm
from surgiform.core.transform.prompts import SYSTEM_PROMPT
from surgiform.core.transform.prompts import PROMPTS
from surgiform.api.models.base import ConsentBase
from surgiform.api.models.base import SurgeryDetails
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

    transformed_dict = {}
    for key, value in consents.model_dump().items():
        if key == "surgery_method_content":
            transformed_dict[key] = SurgeryDetails(**{
                inner_key: chain.invoke({"consent_text": inner_value})
                for inner_key, inner_value in value.items()
            })
        else:
            transformed_dict[key] = chain.invoke({"consent_text": value})

    return ConsentBase(**transformed_dict)
