from __future__ import annotations
import pandas as pd
from typing import List, Dict, Any
from pathlib import Path
from datetime import date

def load_inventory_csv_or_xlsx(path: str) -> List[Dict[str, Any]]:
    """
    Carga un CSV/XLSX con inventario de productos.
    Cada fila se convierte en un bloque textual.
    """
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    results: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        # Concatenamos campos típicos de catálogo
        texto = (
            f"SKU: {row.get('sku','N/A')}\n"
            f"Nombre: {row.get('nombre','')}\n"
            f"Descripción: {row.get('descripcion','')}\n"
            f"Categoría: {row.get('categoria','')}\n"
            f"Stock: {row.get('stock','')}\n"
            f"Precio: {row.get('precio','')}\n"
            f"Certificaciones: {row.get('certificaciones','')}"
        ).strip()

        results.append({
            "text": texto,
            "meta": {
                "doc_type": "inventory",
                "source": file_path.name,
                "category": "productos",
                "last_updated": date.today().isoformat(),
                "language": "es",
            }
        })
    return results