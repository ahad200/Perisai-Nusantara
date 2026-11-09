"""Korelasi alert -> insiden + case management (PRD M7).

Mesin korelasi mengelompokkan alert aktif berdasarkan **entitas utama** (host/aset)
menjadi satu **Insiden** yang dikelola lewat siklus respons. Idempotent lewat
`correlation_key` (dijalankan ulang tak menduplikasi insiden). Lihat
`app/correlation/engine.py`.
"""
from app.correlation.engine import correlate

__all__ = ["correlate"]
