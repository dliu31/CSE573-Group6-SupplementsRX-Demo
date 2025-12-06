from langchain_google_vertexai import (
    ChatVertexAI,
    HarmBlockThreshold,
    HarmCategory
)
from deepeval.models.base_model import DeepEvalBaseLLM

class GoogleVertexAI(DeepEvalBaseLLM):
    safety_settings = {
        HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    custom_model_gemini = ChatVertexAI(
        model_name="gemini-2.0-flash",
        safety_settings=safety_settings,
        project= "GOOGLE GEN LANG PROJECT",
        location= "LOCATION",
    )
    
    """Class to implement Vertex AI for DeepEval"""
    def __init__(self):
        self.model = self.custom_model_gemini

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        return chat_model.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        res = await chat_model.ainvoke(prompt)
        return res.content

    def get_model_name(self):
        return "Vertex AI Model"