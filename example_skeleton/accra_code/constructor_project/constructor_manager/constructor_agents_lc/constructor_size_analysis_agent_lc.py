import os

class ConstructorSizeAnalysisAgentLC:
    """
    Agent to analyze the size of a project
    """

    def run(self, project_data: dict) -> dict:
        """
        Analyze project size

        Returns:
            dict with size metrics
        """
        if not project_data or "path" not in project_data:
            return {"total_size_mb": 0.0, "file_count": 0}

        project_path = project_data["path"]
        total_size = 0
        file_count = 0

        for root, _, files in os.walk(project_path):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except Exception:
                    continue

        total_size_mb = total_size / (1024 * 1024)

        return {
            "total_size_mb": round(total_size_mb, 2),
            "file_count": file_count,
            "avg_file_size_kb": round((total_size / file_count / 1024), 2) if file_count > 0 else 0
        }
