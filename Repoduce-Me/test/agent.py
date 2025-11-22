import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from constructor_model import ConstructorModel

model = ConstructorModel()
print(model.invoke("print hello world in c"))

