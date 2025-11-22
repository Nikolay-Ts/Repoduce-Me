import argparse
import sys
import runpy
import json
import traceback

def run_external_file(path, output):
    """
    It runs the file at the path given, parse the result of runpy and writes in the
    file passed a list of dict in the form [{"name": name, "module": module}, ...]
    """
    try:
        module_globals = runpy.run_path(path)
    except Exception as e:
        payload = {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}
        with open(output, "w") as f:
            json.dump(payload, f)
        sys.exit(1)

    # Only serialize object name and __module__ (if any)
    filtered = []
    for name, obj in module_globals.items():
        mod = getattr(obj, "__module__", "")
        if isinstance(mod, str) and mod:
            filtered.append({"name": name, "module": mod})

    with open(output, "w") as f:
        json.dump({"result": filtered}, f)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path", help="path of the python file to inspect")
    p.add_argument("--output", required=True, help="path of the temporary file used to write JSON results")
    args = p.parse_args()
    run_external_file(args.path, args.output)