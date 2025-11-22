import requests
import os
import tempfile
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Logging Configuration
import logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Constants
AI_MESSAGE_TYPE = "ai_message"
PROCESSING_STATUS = "processing"
DONE_STATUS = "done"
KNOWLEDGE_MODEL_ONLY = "model"
LLM_ENGINE_ONLY = "direct"

class ConstructorAdapter(ABC):
    """
    Abstract Base Class for Constructor Adapter
    """

    def __init__(self, api_url=None, api_key=None, km_id=None, llm_name=None, llm_alias="gpt-4o-mini"):
        load_dotenv()
        self.api_url = api_url or os.getenv("CONSTRUCTOR_API_URL", "https://training.constructor.app/api/platform-kmapi")
        self.api_key = api_key or os.getenv("CONSTRUCTOR_API_KEY")
        self.km_id = km_id or os.getenv("CONSTRUCTOR_KM_ID")
        self.llm_name = llm_name
        self.llm_alias = llm_alias
        self.llms = self._gather_llms()
        self.llm_id = self.get_llm_id(llm_alias)
        if llm_name is None :
            llm_name = self.get_llm_name(llm_alias)

    @abstractmethod
    def query(self, question: str, **kwargs) -> str:
        """
        Abstract method to query the Constructor Model.
        Must be implemented by subclasses.
        """
        pass

    def _get_headers(self):
        """
        Returns the headers required for API requests.
        """
        return {
            "X-KM-AccessKey": f"Bearer {self.api_key}",
        }

    def get_llms(self):
        response = requests.get(f"{self.api_url}/language_models", headers=self._get_headers())

        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to fetch LLMs: {response.status_code}, {response.text}")
            return {}

    def _gather_llms(self):
        llms_response = self.get_llms()
        llms_map = {}
        try:
            results = llms_response.get("results", [])
            for llm in results:
                alias = llm.get("alias")
                name = llm.get("name") # for stateless
                llm_id = llm.get("id")
                if name and llm_id:
                    # print(f"Found LLM: alias = {alias}, name = {name}, id = {llm_id}")
                    llms_map[alias] = llm
        except Exception as e:
            logging.error(f"Failed to process LLMs: {e}")
        return llms_map

    def get_llm_id(self, llm_alias):
        return self.llms.get(llm_alias)["id"]

    def get_llm_name(self, llm_alias):
        return self.llms.get(llm_alias)["name"]

    def add_document(self, file_path):
        # Check if the file exists and is accessible
        if not os.path.isfile(file_path):
            print(f"File '{file_path}' does not exist or is not accessible.")
            return f"Error: File '{file_path}' does not exist or is not accessible."

        endpoint = f"{self.api_url}/knowledge-models/{self.km_id}/files"
        print(endpoint)
        headers = self._get_headers()
        print("Headers: ",headers)

        try:
            files = {'file': open(file_path, 'rb')}
            response = requests.post(endpoint, headers=headers, files=files)

            if response.status_code == 200:
                print(f"File '{file_path}' uploaded successfully.")
                return response.json()
            else:
                print(f"Failed to upload file '{file_path}': {response.status_code}, {response.text}")
                return f"Failed to upload file: {response.status_code}"

        except Exception as e:
            print(f"Error uploading file '{file_path}': {e}")
            raise Exception(f"Error uploading file '{file_path}': {e}")

    def get_all_documents(self):
        """
        Queries for all documents stored in the Knowledge Model.
        """
        endpoint = f"{self.api_url}knowledge-models/{self.km_id}/files"
        try:
            response = requests.get(endpoint, headers=self._get_headers())
            response.raise_for_status()

            # Return the list of documents
            return response.json().get("results", [])
        except requests.exceptions.RequestException as e:
            print(f"Error querying documents: {e}")
            raise Exception(f"Error querying documents: {e}")

    def get_all_documents_names(self):
        """
        Queries for all documents stored in the Knowledge Model and returns their names.

        :return: List of document names.
        """
        endpoint = f"{self.api_url}/knowledge-models/{self.km_id}/files"
        try:
            response = requests.get(endpoint, headers=self._get_headers())
            response.raise_for_status()

            # Extract document names
            documents = response.json().get("results", [])
            document_names = [doc.get("filename") for doc in documents if "filename" in doc]

            logging.info(f"Retrieved {len(document_names)} document names successfully.")
            return document_names
        except requests.exceptions.RequestException as e:
            logging.error(f"Error querying document names: {e}")
            raise Exception(f"Error querying document names: {e}")

    def delete_document_by_id(self, document_id):
        """
        Deletes a specific document by its ID.
        """
        endpoint = f"{self.api_url}knowledge-models/{self.km_id}/files/{document_id}"
        try:
            response = requests.delete(endpoint, headers=self._get_headers())
            response.raise_for_status()

            if response.status_code in [200, 204]:
                logging.info(f"Document {document_id} deleted successfully.")
                return True
            else:
                logging.error(f"Failed to delete document {document_id}: {response.status_code}, {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Error deleting document {document_id}: {e}")
            raise Exception(f"Error deleting document {document_id}: {e}")

    def delete_all_documents(self):
        """
        Queries for all documents and deletes them one by one.
        """
        documents = self.get_all_documents()
        if not documents:
            logging.info("No documents found to delete.")
            return "No documents found to delete."

        for document in documents:
            document_id = document.get("id")
            print(f"Deleting document {document_id}...")
            if document_id:
                self.delete_document_by_id(document_id)

        return "All documents deleted successfully."

    def reset_model(self):
        self.delete_all_documents()

    def delete_model(self):
        """
        Deletes the Knowledge Model.
        """
        endpoint = f"{self.api_url}/knowledge-models/{self.km_id}"

        try:
            response = requests.delete(endpoint, headers=self._get_headers())
            response.raise_for_status()
            if response.status_code == 200 or response.status_code == 204:
                logging.info(f"Knowledge Model {self.km_id} reset successfully.")
                return "Knowledge Model reset successfully."
            else:
                logging.error(f"Failed to reset Knowledge Model: {response.status_code}, {response.text}")
                return f"Failed to reset Knowledge Model: {response.status_code}"
        except requests.exceptions.RequestException as e:
            logging.error(f"Error during Knowledge Model reset: {e}")
            raise Exception(f"Error during Knowledge Model reset: {e}")

    # New method to retrieve available LLMs
    def get_available_llms(self):
        response = requests.get(f"{self.api_url}/language_models", headers=self._get_headers())
        response.raise_for_status()

        llms = response.json().get("results", [])
        return [
            {
                "alias": llm.get("alias"),  # Important to add alias
                "name": llm.get("name"),
                "id": llm.get("id")
            }
            for llm in llms
        ]

    def add_facts(self, content):
        """Add facts to the Knowledge Model.

        Args:
            content (dict): Facts as key-values.
        """      
        markdown_content = "\n".join([f"{key}: {value}" for key, value in content.items()])          

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md') as temp_file:
            temp_file.write(markdown_content)
            temp_filepath = temp_file.name
    
            return self.add_document(temp_filepath)
