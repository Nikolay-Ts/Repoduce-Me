from constructor_adapter.constructor_adapter_base import ConstructorAdapter
import requests


class StatelessConstructorAdapter(ConstructorAdapter):
    """
    Stateless Adapter for Constructor API
    """

    def query(self, question: str, **kwargs) -> str:
        endpoint = f"{self.api_url}/knowledge-models/{self.km_id}/chat/completions"

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": question
                }
            ],
            "mode": "model",
            "model": self.llm_alias
        }

        response = requests.post(endpoint, headers=self._get_headers(), json=payload)
        response.raise_for_status()
        response_json = response.json()
        choices = response_json.get("choices", [])
        if choices and "message" in choices[0] and "content" in choices[0]["message"]:
            return choices[0]["message"]["content"]
        else:
            return "No response received from the model."



if __name__ == "__main__":
    print("Stateless Query:")
    model_stateless = StatelessConstructorAdapter()
    print(model_stateless.query("What is the Constructor Model?"))

    print("Stateless Query on gpt-4o-2024-08-06:")
    model_stateless = StatelessConstructorAdapter()
    print(model_stateless.query("What is the Constructor Model?"))
    document_names = model_stateless.get_all_documents_names()
    model_stateless.add_document("sampleFileToUpload.pdf")

    # Print each document name
    print("Document Names:")
    for name in document_names:
        print(name)

#
#     print("Stateless Query on gpt-4o:")
#     model_stateless = StatelessConstructorAdapter(llm_name="gpt-4o")
#     print(model_stateless.query("What is the Constructor Model?"))
#
#     print("Stateless Query on gpt-4o-2024-08-06 with extra document:")
#     model_stateless = StatelessConstructorAdapter(llm_name="gpt-4o-2024-08-06")
#     model_stateless.add_document("sampleFileToUpload.pdf")
#     print(model_stateless.query("What is the Constructor Model?"))
# #    model_stateless.delete_all_documents()
