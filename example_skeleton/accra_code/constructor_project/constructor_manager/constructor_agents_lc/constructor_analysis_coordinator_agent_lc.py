class ConstructorAnalysisCoordinatorAgentLC:
    """
    Agent to coordinate multiple analyses and aggregate results into
    final dimension predictions
    """

    @staticmethod
    def aggregate_dimensions(
            size: dict = None,
            memory: dict = None,
            network: dict = None,
            load: dict = None,
            parallelism: dict = None
    ) -> dict:
        """
        Aggregate all analysis results into final dimension predictions

        Returns:
            dict with keys: CPUs, GPUs, RAM, Storage, NetworkBandwidth
        """
        dimensions = {
            "CPUs": 0.0,
            "GPUs": 0.0,
            "RAM": 0.0,
            "Storage": 0.0,
            "NetworkBandwidth": 0.0
        }

        # Aggregate memory
        if memory:
            total_ram = 0.0
            for _, result in memory.items():
                if isinstance(result, dict) and result.get("status") == "success":
                    mem_str = result.get("total_memory_forecasted", "0 MB").split()[0]
                    try:
                        total_ram += float(mem_str)
                    except ValueError:
                        continue
            dimensions["RAM"] = round(total_ram, 2)

        # Aggregate load (CPU/GPU)
        if load:
            total_cpu = 0.0
            total_gpu = 0.0
            for _, result in load.items():
                if isinstance(result, dict) and result.get("status") == "success":
                    total_cpu += result.get("percent_cpu", 0.0)
                    total_gpu += result.get("percent_gpu", 0.0)
            dimensions["CPUs"] = round(total_cpu, 2)
            dimensions["GPUs"] = round(total_gpu, 2)

        # Aggregate network
        if network:
            total_network_deps = len(network.get("dependencies", []))
            total_api_calls = sum(count for _, count in network.get("api_calls", []))
            dimensions["NetworkBandwidth"] = total_network_deps + total_api_calls

        # Aggregate storage from size
        if size:
            dimensions["Storage"] = size.get("total_size_mb", 0.0)

        return dimensions
