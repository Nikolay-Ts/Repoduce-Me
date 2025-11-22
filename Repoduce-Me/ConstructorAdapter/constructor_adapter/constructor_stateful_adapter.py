from .constructor_adapter_base import ConstructorAdapter, AI_MESSAGE_TYPE, DONE_STATUS, PROCESSING_STATUS, KNOWLEDGE_MODEL_ONLY, LLM_ENGINE_ONLY
import requests
import logging
import time

class StatefulConstructorAdapter(ConstructorAdapter):
    """
    Stateful Adapter for Constructor API
    """

    def __init__(self, default_model_mode = LLM_ENGINE_ONLY, **kwargs):
        super().__init__(**kwargs)
        self.mode = default_model_mode # used for selecting the mode of the model, LLM_ENGINE_ONLY (default) or KNOWLEDGE_MODEL_ONLY
        self.session_id = None
        self._start_session()

    def _start_session(self):
        if not self.session_id:
            data = {"llm_id": self.llm_id, "mode": self.mode}
            url = f"{self.api_url}/knowledge-models/{self.km_id}/chat-sessions"
            response = requests.post(url, headers=self._get_headers(), json=data)

            if response.status_code == 200:
                self.session_id = response.json().get("id")
                logging.info(f"Session started. Session ID: {self.session_id}")
            else:
                print(f"Failed to start session: {response.status_code}, {response.text}")
                raise Exception(f"Failed to start session: {response.status_code}, {response.text}")

    def restart_session(self):
        self._start_session()

    def query(self, question: str, timeout=120, request_timeout=15, retry_delay=3, mode = True) -> str:
        """
        Send a query to model and waits for answers.
        :parameter question: the actual content of the question to send to the model
        :parameter mode: used for selecting the mode of the model, True for LLM_ENGINE_ONLY (default) or False for KNOWLEDGE_MODEL_ONLY
        :parameter retry_delay: number of seconds after which retrying
        :parameter request_timeout: timeout for the get request
        :parameter timeout: time after which the model response timed out
        """
        self._send_message(question, mode)
        start_time = time.time()

        while True:
            response = requests.get(
                f"{self.api_url}/knowledge-models/{self.km_id}/chat-sessions/{self.session_id}/messages",
                headers=self._get_headers(),
                timeout=request_timeout,
            )
            message = response.json()["results"][0]
            if message["type"] != AI_MESSAGE_TYPE:
                break

            status_name = message["status"]["name"]
            if status_name == PROCESSING_STATUS:
                logging.info("Waiting for reply...")
                time.sleep(retry_delay)
            elif status_name == DONE_STATUS:
                messages = response.json().get("results", [])
                for message in messages:
                    if message["type"] == AI_MESSAGE_TYPE and message["status"]["name"] == DONE_STATUS:
                        # Access the nested 'content' dictionary and then the 'text' field
                        content = message.get("content", {})
                        return content.get("text", "No response text available")
                return "Unclear answer"+message
            if time.time() - start_time > timeout:
                raise TimeoutError("Model response timed out.")

    def _send_message(self, message: str, mode: bool):
        """Send a message to the model.
        :parameter message (str): the actual content
        :parameter mode (bool): used for selecting the mode of the model, True for LLM_ENGINE_ONLY (default) or False for KNOWLEDGE_MODEL_ONLY
        """
        actual_mode = LLM_ENGINE_ONLY if mode else KNOWLEDGE_MODEL_ONLY
        data = {"text": message, "mode": actual_mode}
        response = requests.post(
            f"{self.api_url}/knowledge-models/{self.km_id}/chat-sessions/{self.session_id}/messages",
            headers=self._get_headers(),
            json=data,
        )
        response.raise_for_status()


if __name__ == "__main__":
    print("Stateful Query on default LLM:")
    model_stateful = StatefulConstructorAdapter()
    print(model_stateful.query("What is the Constructor Model?"))
    model_stateful.reset_model()

    print("Stateful Query on ChatGPT 4.o:")
    model_stateful_4o = StatefulConstructorAdapter(llm_name="GPT-4o")
    print(model_stateful_4o.query("What is the Constructor Model?"))

    print("Stateful Query on ChatGPT 4.o with extra document:")
    model_stateful_4o.add_document("sampleFileToUpload.pdf")
    print("Checking the presence of the new document in the model stateful:")

    document_names = model_stateful_4o.get_all_documents_names()

    # Print each document name
    print("Document Names:")
    for name in document_names:
        print(name)

    print(model_stateful_4o.query("What is the Constructor Model?"))