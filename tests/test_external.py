from surgiform.external.openai_client import get_chat_llm


def test_llm_stub():
    llm = get_chat_llm()
    assert llm.model_name.startswith("gpt")
